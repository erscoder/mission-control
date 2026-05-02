"""
SentinelLoopFlow — The Sentinel Loop in CrewAI Flow form.

Uses CrewAI built-ins:
- Flow state (Pydantic BaseModel)
- CrewAI Memory (self.remember / self.recall via Flow)
- @start, @listen, @router, @human_feedback decorators
"""
from datetime import datetime, timezone
import hashlib
import logging
import os
import re
import signal
import threading
from typing import Optional

from crewai.flow.flow import Flow, listen, start, router
from pydantic import BaseModel, Field

from sentinel_v2.flows.error_classifier import classify_error, is_transient, write_escalation
from sentinel_v2.observability.tracing import end_trace, log_event, start_trace

log = logging.getLogger("sentinel_v2.flow")

ERSLABS_ROOT_DOMAIN = "erslabs.net"


def _resolve_workspace_dir(draft_id: Optional[str], cycle_count: int) -> str:
    """Compute the workspace path from current env + draft id.

    Always derived locally; never trust a persisted ``state.workspace_dir`` value
    because checkpoints can carry paths from a different environment (e.g. a
    Docker container where ``HOME=/root``).
    """
    from pathlib import Path
    root = Path(os.environ.get("SENTINEL_WORKSPACES_ROOT", os.path.expanduser("~/Sentinel")))
    return str(root / (draft_id or f"cycle_{cycle_count}"))


def _prebake_deploy_files(workspace_dir: str, slug: str, stack: str = "node_nestjs") -> dict:
    """Write the canonical ``fly.toml`` and ``Dockerfile`` for the deploy.

    The build agent's only job for infra files is to know the stack. Templates
    live in ``data/deploy_templates/<stack>/`` and are slug-substituted here in
    Python so the LLM cannot break the format. Always overwrites.

    Refuses to create the workspace tree itself: if ``workspace_dir`` does not
    exist, the build phase never ran here (or wrote elsewhere). Caller must
    have validated the path first.

    Returns the substituted file paths so callers can log/verify them.
    """
    from pathlib import Path
    ws = Path(workspace_dir)
    if not ws.exists():
        raise FileNotFoundError(
            f"workspace_dir {workspace_dir!r} does not exist. The build phase "
            "may have written to a different path (e.g. inside a container). "
            "Re-run the build for this draft, or copy the workspace into place."
        )
    backend = ws / "backend"
    backend.mkdir(exist_ok=True)  # parents=False on purpose: do not climb to /
    template_dir = Path(__file__).resolve().parent.parent / "data" / "deploy_templates" / stack

    if not template_dir.exists():
        raise FileNotFoundError(
            f"Missing canonical template tree: {template_dir}. The deploy_templates "
            f"directory for stack {stack!r} is missing; refusing to silently skip."
        )

    # Walk the template tree and mirror every file into <workspace>/backend/,
    # preserving relative paths. This covers infra files (Dockerfile, fly.toml,
    # package.json) and protected source files (src/config/stripe.config.ts,
    # src/modules/stripe/stripe.controller.ts) that must not be rewritten by
    # the build agent. {{SLUG}} substitution applied uniformly.
    written: dict[str, str] = {}
    for src_path in template_dir.rglob("*"):
        if not src_path.is_file():
            continue
        rel = src_path.relative_to(template_dir)
        dst_path = backend / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        content = src_path.read_text().replace("{{SLUG}}", slug)
        dst_path.write_text(content)
        written[str(rel)] = str(dst_path)
    return written


def _prebake_frontend_files(workspace_dir: str, slug: str, stack: str = "nextjs_frontend") -> dict:
    """Mirror canonical Next.js 14 frontend files into ``<workspace>/frontend/``.

    Pinned counterpart to ``_prebake_deploy_files``. The frontend agent
    routinely drifts the eslint major past what eslint-config-next can peer
    with (observed live: agent wrote eslint@^9.13.0 but eslint-config-next@14
    requires eslint@^7 || ^8, ERESOLVE). Pinning the package.json deterministically
    eliminates that whole class of failures while still letting the agent author
    everything else (pages, components, styles).

    Same walk-recursive pattern as the backend bake; ``{{SLUG}}`` substitution
    applied uniformly. Idempotent; called both before and after the build crew.
    """
    from pathlib import Path
    ws = Path(workspace_dir)
    if not ws.exists():
        raise FileNotFoundError(
            f"workspace_dir {workspace_dir!r} does not exist. The build phase "
            "may have written to a different path (e.g. inside a container)."
        )
    frontend = ws / "frontend"
    frontend.mkdir(exist_ok=True)
    template_dir = Path(__file__).resolve().parent.parent / "data" / "deploy_templates" / stack

    if not template_dir.exists():
        raise FileNotFoundError(
            f"Missing canonical frontend template tree: {template_dir}. The "
            f"deploy_templates directory for stack {stack!r} is missing; refusing "
            "to silently skip."
        )

    written: dict[str, str] = {}
    for src_path in template_dir.rglob("*"):
        if not src_path.is_file():
            continue
        rel = src_path.relative_to(template_dir)
        dst_path = frontend / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        content = src_path.read_text().replace("{{SLUG}}", slug)
        dst_path.write_text(content)
        written[str(rel)] = str(dst_path)
    return written


def _verify_package_json_unchanged(workspace_dir: str, stack: str = "node_nestjs") -> bool:
    """Return True if backend/package.json matches the canonical template, False if it diverged.

    On divergence (or missing file), log a WARNING with both sha256 hashes and
    re-bake the canonical via ``_prebake_deploy_files``. This is a defensive
    check against prompt-only enforcement of the package.json immutability
    rule: the build agent still has ``write_file`` and could clobber the
    pinned NestJS matrix despite the prompt forbidding it.

    The template contains a ``{{SLUG}}`` token that ``_prebake_deploy_files``
    substitutes at bake time. To compare apples to apples, this helper
    recovers the slug used at bake time from the workspace pkg's ``name``
    field (``"<slug>-backend"``), falls back to the workspace dir name if
    the file is unreadable, then hashes the slug-substituted template.
    The deploy phase re-bakes again, so this helper never fails the build;
    divergence is logged and silently corrected here.
    """
    from pathlib import Path
    import json
    backend_pkg = Path(workspace_dir) / "backend" / "package.json"
    template_pkg = (
        Path(__file__).resolve().parent.parent
        / "data" / "deploy_templates" / stack / "package.json"
    )

    if not template_pkg.exists():
        # No canonical template for this stack, nothing to verify.
        return True

    # Recover slug used at bake time. Workspace pkg "name" is "<slug>-backend";
    # if unreadable or missing, fall back to the workspace dir basename so a
    # re-bake still produces a stable name.
    slug = Path(workspace_dir).name or "app"
    if backend_pkg.exists():
        try:
            data = json.loads(backend_pkg.read_text())
            name = str(data.get("name") or "")
            if name.endswith("-backend"):
                slug = name[: -len("-backend")] or slug
        except (json.JSONDecodeError, OSError):
            pass

    canonical_bytes = template_pkg.read_text().replace("{{SLUG}}", slug).encode("utf-8")
    template_hash = hashlib.sha256(canonical_bytes).hexdigest()

    if not backend_pkg.exists():
        log.warning(
            "package.json missing in workspace: %s (template sha256=%s). Re-baking canonical.",
            backend_pkg, template_hash,
        )
    else:
        workspace_hash = hashlib.sha256(backend_pkg.read_bytes()).hexdigest()
        if workspace_hash == template_hash:
            return True
        log.warning(
            "package.json diverged from canonical template: %s (workspace sha256=%s, template sha256=%s). Re-baking canonical.",
            backend_pkg, workspace_hash, template_hash,
        )

    try:
        _prebake_deploy_files(workspace_dir, slug, stack=stack)
    except FileNotFoundError as e:
        log.warning("Could not re-bake package.json: %s", e)
    return False


_STRIPE_CONTROLLER_IMPORT = (
    "import { StripeWebhookController } from "
    "'./modules/stripe/stripe.controller';"
)
_STRIPE_CONTROLLER_NAME = "StripeWebhookController"


def _ensure_stripe_controller_registered(workspace_dir: str) -> dict:
    """Defense-in-depth for the per-app Stripe wiring.

    The build agent is told (in build_crew.py backstory) to import
    ``StripeWebhookController`` in ``AppModule`` and add it to the
    ``controllers`` array. Prompt-only enforcement is brittle. This helper
    parses ``backend/src/app.module.ts`` and patches it idempotently when
    the controller is missing from either the import list or the
    ``controllers`` array. Webhook URLs would otherwise return 404 silently
    while Stripe quietly retries.

    Returns ``{registered: bool, patched: bool, reason: str}``. Never raises;
    on file missing or unparseable shape, returns ``registered=False`` and
    logs a WARNING. The deploy phase will surface the resulting 404 via the
    QA verifier, which is loud enough that the operator can see it.
    """
    from pathlib import Path

    app_module = Path(workspace_dir) / "backend" / "src" / "app.module.ts"
    if not app_module.exists():
        log.warning(
            "app.module.ts missing: %s. Stripe webhook controller cannot be auto-registered.",
            app_module,
        )
        return {"registered": False, "patched": False, "reason": "app_module_missing"}

    try:
        text = app_module.read_text()
    except OSError as exc:
        log.warning("Could not read %s: %s", app_module, exc)
        return {"registered": False, "patched": False, "reason": f"read_error:{exc}"}

    has_import = _STRIPE_CONTROLLER_NAME in text and "stripe.controller" in text
    has_controllers_entry = bool(
        re.search(
            r"controllers\s*:\s*\[[^\]]*\b" + _STRIPE_CONTROLLER_NAME + r"\b[^\]]*\]",
            text,
            flags=re.DOTALL,
        )
    )
    if has_import and has_controllers_entry:
        return {"registered": True, "patched": False, "reason": "already_registered"}

    patched_text = text
    if not has_import:
        last_import = list(re.finditer(r"^\s*import\s+.+?;\s*$", patched_text, flags=re.MULTILINE))
        if last_import:
            insert_at = last_import[-1].end()
            patched_text = (
                patched_text[:insert_at]
                + "\n"
                + _STRIPE_CONTROLLER_IMPORT
                + patched_text[insert_at:]
            )
        else:
            patched_text = _STRIPE_CONTROLLER_IMPORT + "\n" + patched_text

    if not has_controllers_entry:
        controllers_match = re.search(
            r"(controllers\s*:\s*\[)([^\]]*)(\])",
            patched_text,
            flags=re.DOTALL,
        )
        if controllers_match:
            head, body, tail = controllers_match.groups()
            stripped = body.strip()
            if stripped:
                if stripped.endswith(","):
                    new_body = body + " " + _STRIPE_CONTROLLER_NAME
                else:
                    new_body = body + ", " + _STRIPE_CONTROLLER_NAME
            else:
                new_body = _STRIPE_CONTROLLER_NAME
            patched_text = (
                patched_text[: controllers_match.start()]
                + head
                + new_body
                + tail
                + patched_text[controllers_match.end():]
            )
        else:
            log.warning(
                "app.module.ts has no controllers: [...] array; cannot auto-register %s. "
                "Build agent must add it manually. File: %s",
                _STRIPE_CONTROLLER_NAME,
                app_module,
            )
            return {
                "registered": False,
                "patched": False,
                "reason": "no_controllers_array",
            }

    try:
        app_module.write_text(patched_text)
    except OSError as exc:
        log.warning("Could not write patched %s: %s", app_module, exc)
        return {"registered": False, "patched": False, "reason": f"write_error:{exc}"}

    log.warning(
        "AppModule was missing StripeWebhookController. Auto-patched: %s "
        "(import added=%s, controllers entry added=%s).",
        app_module,
        not has_import,
        not has_controllers_entry,
    )
    return {"registered": True, "patched": True, "reason": "auto_patched"}


def _ensure_main_ts_raw_body(workspace_dir: str) -> dict:
    """Defense-in-depth for the NestJS bootstrap rawBody requirement.

    The Stripe webhook controller reads ``req.rawBody`` to verify the
    Stripe-Signature header. NestJS only populates ``rawBody`` when the
    bootstrap call passes ``{ rawBody: true }`` to ``NestFactory.create``.
    The build_crew prompt requires this; this helper auto-patches when
    forgotten.

    Three insertion shapes the helper recognises (all common NestJS templates):

      NestFactory.create(AppModule)                     -> add second arg
      NestFactory.create(AppModule, {})                 -> set rawBody key
      NestFactory.create(AppModule, { foo: 1 })         -> add rawBody key
      NestFactory.create(AppModule, { rawBody: true })  -> no-op

    Returns ``{patched: bool, reason: str}``. Never raises.
    """
    from pathlib import Path

    main_ts = Path(workspace_dir) / "backend" / "src" / "main.ts"
    if not main_ts.exists():
        log.warning(
            "main.ts missing: %s. Cannot ensure rawBody bootstrap; webhook signature "
            "verification will fail at runtime.",
            main_ts,
        )
        return {"patched": False, "reason": "main_ts_missing"}

    try:
        text = main_ts.read_text()
    except OSError as exc:
        log.warning("Could not read %s: %s", main_ts, exc)
        return {"patched": False, "reason": f"read_error:{exc}"}

    # `NestFactory.create<X>(AppModule, ...)` is also valid TypeScript (e.g.
    # fastify adapter). Optional generic accepted by all shapes below.
    nf_create = r"NestFactory\.create(?:<[^>]+>)?\("

    # Already correct: rawBody: true present anywhere in the NestFactory.create call.
    if re.search(nf_create + r"[^)]*rawBody\s*:\s*true", text, flags=re.DOTALL):
        return {"patched": False, "reason": "already_set"}

    # Shape 3: existing options object, add rawBody key inside it.
    options_match = re.search(
        r"(" + nf_create + r"\s*\w+\s*,\s*\{)([^}]*)(\}\s*\))",
        text,
        flags=re.DOTALL,
    )
    if options_match:
        head, body, tail = options_match.groups()
        body_stripped = body.strip()
        if body_stripped:
            new_body = body.rstrip() + ", rawBody: true "
        else:
            new_body = " rawBody: true "
        patched = (
            text[: options_match.start()]
            + head
            + new_body
            + tail
            + text[options_match.end():]
        )
    else:
        # Shape 1: only AppModule arg, add full options object.
        single_arg = re.search(
            r"(" + nf_create + r"\s*\w+)(\s*\))",
            text,
            flags=re.DOTALL,
        )
        if not single_arg:
            log.warning(
                "main.ts has no recognisable NestFactory.create(...) call; cannot "
                "auto-patch rawBody. File: %s",
                main_ts,
            )
            return {"patched": False, "reason": "no_nestfactory_call"}
        head, tail = single_arg.groups()
        patched = (
            text[: single_arg.start()]
            + head
            + ", { rawBody: true }"
            + tail
            + text[single_arg.end():]
        )

    try:
        main_ts.write_text(patched)
    except OSError as exc:
        log.warning("Could not write patched %s: %s", main_ts, exc)
        return {"patched": False, "reason": f"write_error:{exc}"}

    log.warning(
        "main.ts was missing { rawBody: true } in NestFactory.create. Auto-patched: %s",
        main_ts,
    )
    return {"patched": True, "reason": "auto_patched"}


def _verify_npm_build(workspace_dir: str, *, timeout: int = 600) -> dict:
    """Run `npm install` + build deterministically in backend and frontend subdirs.

    Trust-but-verify gate that runs AFTER the build crew finishes. The QA Lead
    self-reports `build_status` but a hallucinating LLM can claim 'clean' on a
    workspace that does not even `npm install`. Running the real commands here
    is the only way to be sure.

    For each subdir (backend, frontend):
      1. Skip if the dir does not exist or has no package.json.
      2. `npm install --no-audit --no-fund --prefer-offline`. Non-zero -> fail.
      3. If package.json has a "build" script: `npm run build`. Else fall
         back to `npx tsc --noEmit` if a tsconfig.json exists; otherwise the
         install alone counts as a pass (no-build TypeScript-less project).

    Returns:
        {
            "ok": bool,
            "first_failure": str | None,        # e.g. "backend.install", "frontend.build"
            "details": {
                "backend": {"install": int|None, "build": int|None,
                            "tail": str, "skipped": str|None},
                "frontend": {...},
            },
        }
    """
    import json as _json
    import shutil
    import subprocess
    from pathlib import Path

    out: dict = {
        "ok": True,
        "first_failure": None,
        "details": {"backend": None, "frontend": None},
    }

    npm = shutil.which("npm")
    if not npm:
        out["ok"] = False
        out["first_failure"] = "npm_not_found"
        return out

    npx = shutil.which("npx")

    for sub in ("backend", "frontend"):
        sub_path = Path(workspace_dir) / sub
        pkg_path = sub_path / "package.json"
        info: dict = {"install": None, "build": None, "tail": "", "skipped": None}

        if not sub_path.is_dir():
            info["skipped"] = "no_directory"
            out["details"][sub] = info
            continue
        if not pkg_path.is_file():
            info["skipped"] = "no_package_json"
            out["details"][sub] = info
            continue

        try:
            pkg = _json.loads(pkg_path.read_text())
        except Exception as e:
            info["skipped"] = f"package_json_parse_error:{e}"
            info["tail"] = str(e)
            out["ok"] = False
            if out["first_failure"] is None:
                out["first_failure"] = f"{sub}.parse"
            out["details"][sub] = info
            continue

        scripts = pkg.get("scripts") or {}

        try:
            install_proc = subprocess.run(
                [npm, "install", "--no-audit", "--no-fund", "--prefer-offline"],
                cwd=str(sub_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            info["install"] = -1
            info["tail"] = f"timeout after {timeout}s: {e}"
            out["ok"] = False
            if out["first_failure"] is None:
                out["first_failure"] = f"{sub}.install"
            out["details"][sub] = info
            continue

        info["install"] = install_proc.returncode
        if install_proc.returncode != 0:
            tail_src = install_proc.stderr or install_proc.stdout or ""
            info["tail"] = tail_src[-800:]
            out["ok"] = False
            if out["first_failure"] is None:
                out["first_failure"] = f"{sub}.install"
            out["details"][sub] = info
            continue

        if "build" in scripts:
            cmd = [npm, "run", "build"]
        elif npx and (sub_path / "tsconfig.json").is_file():
            cmd = [npx, "--no-install", "tsc", "--noEmit"]
        else:
            info["build"] = 0
            info["skipped"] = "no_build_script_no_tsconfig"
            out["details"][sub] = info
            continue

        try:
            build_proc = subprocess.run(
                cmd,
                cwd=str(sub_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            info["build"] = -1
            info["tail"] = f"timeout after {timeout}s: {e}"
            out["ok"] = False
            if out["first_failure"] is None:
                out["first_failure"] = f"{sub}.build"
            out["details"][sub] = info
            continue

        info["build"] = build_proc.returncode
        if build_proc.returncode != 0:
            tail_src = build_proc.stderr or build_proc.stdout or ""
            info["tail"] = tail_src[-800:]
            out["ok"] = False
            if out["first_failure"] is None:
                out["first_failure"] = f"{sub}.build"

        out["details"][sub] = info

    return out


def _make_slug(title: str) -> str:
    """Extract the product name from an opportunity title and return a DNS-safe slug.

    Examples:
        "ComplianceDesk HIPAA Compliance" → "compliancedesk"
        "QuickInvoice - Fast invoicing"   → "quickinvoice"
        "AI Resume Builder"               → "airesumebuilder"

    Strategy: take the first token that looks like a product name (CamelCase word
    or the first word before a separator like ' - ', ':', '|').
    """
    # Strip draft_cN_ prefix if accidentally passed
    s = re.sub(r"^draft_c\d+_", "", title).strip()
    # Split on common title separators
    s = re.split(r"\s*[-:|/]\s*", s)[0].strip()
    # Concatenate tokens until the slug is at least 4 chars
    tokens = s.split()
    product = ""
    for token in tokens:
        product += token
        if len(re.sub(r"[^a-z0-9]", "", product.lower())) >= 4:
            break
    # DNS-safe: lowercase, alphanumeric only, no hyphens
    slug = re.sub(r"[^a-z0-9]", "", product.lower()) or "app"
    return slug[:30] or "app"


# ── Stripe provisioning (per-app Product + Webhook + Fly secret injection) ──

DEFAULT_STRIPE_EVENTS = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
]


def _provision_stripe_resources(
    *,
    draft_id: str,
    slug: str,
    backend_url: str,
    opportunity: dict,
) -> dict:
    """Provision per-app Stripe Product + Webhook BEFORE the deploy crew runs.

    No Fly interaction. Returns the live signing secret + IDs so the deploy
    crew can stage them as Fly secrets in the same release as DATABASE_URL,
    so the first boot of the app already has STRIPE_SECRET_KEY +
    STRIPE_WEBHOOK_SECRET present (otherwise the protected
    ``stripe.config.ts`` throws at module load and Fly rolls back the
    release).

    Idempotent on ``draft_id`` (Stripe metadata search). On retry the
    existing webhook is deleted and recreated so the live signing secret
    is always returned (Stripe never returns an existing endpoint's
    secret).

    Returns: ``{product_id, price_id, price_ids, webhook_endpoint_id,
    webhook_secret, secret_was_rotated}``.

    Raises on Stripe API failure, missing daemon ``STRIPE_SECRET_KEY``, or
    empty webhook secret (defense against the F-01 empty-string fallback).
    Caller is expected to abort the deploy on any raise.
    """
    from sentinel_v2.tools.stripe_tool import (
        provision_product_for_draft,
        provision_webhook_for_draft,
    )

    daemon_secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not daemon_secret_key:
        raise RuntimeError(
            "STRIPE_SECRET_KEY not set on Sentinel daemon; cannot provision "
            f"Stripe Product/Webhook for {draft_id!r}."
        )

    title = (opportunity or {}).get("title") or slug
    description = (
        (opportunity or {}).get("tagline")
        or (opportunity or {}).get("description")
        or title
    )[:500]
    pricing = (opportunity or {}).get("pricing") or {}
    amount_cents = int(pricing.get("amount_cents") or 1900)
    interval = pricing.get("interval") or "month"

    product = provision_product_for_draft(
        draft_id=draft_id,
        name=title,
        description=description,
        prices=[{
            "amount_cents": amount_cents,
            "currency": pricing.get("currency", "usd"),
            "interval": interval,
            "nickname": f"{slug}-{interval}",
        }],
    )
    price_id = product["price_ids"][0] if product["price_ids"] else None

    webhook_url = f"{backend_url.rstrip('/')}/api/stripe/webhook"
    webhook = provision_webhook_for_draft(
        url=webhook_url,
        events=DEFAULT_STRIPE_EVENTS,
        draft_id=draft_id,
    )

    if not webhook.get("secret"):
        raise RuntimeError(
            f"Stripe webhook {webhook['endpoint_id']} returned no signing secret; "
            "refusing to proceed with empty STRIPE_WEBHOOK_SECRET (would "
            "re-introduce F-01 empty-string fallback)."
        )

    return {
        "product_id": product["product_id"],
        "price_id": price_id,
        "price_ids": product["price_ids"],
        "webhook_endpoint_id": webhook["endpoint_id"],
        "webhook_secret": webhook["secret"],
        "secret_was_rotated": webhook.get("secret_was_rotated", False),
    }


# ── State ────────────────────────────────────────────────────────────────────

MAX_BUILD_RETRIES = int(os.getenv("SENTINEL_MAX_BUILD_RETRIES", "3"))
MAX_DEPLOY_RETRIES = int(os.getenv("SENTINEL_MAX_DEPLOY_RETRIES", "2"))


class SentinelState(BaseModel):
    """Flow state — lives inside the Flow, serialized on kickoff/resume."""

    cycle_count: int = 0
    current_phase: str = "research"
    last_update: str = ""
    error: Optional[str] = None

    # Retry counters (for automatic feedback loops)
    build_attempts: int = 0
    deploy_attempts: int = 0

    # Research
    opportunities: list[dict] = []
    top_opportunity: Optional[dict] = None

    # Match
    user_profile: dict = {}
    match_score: float = 0.0

    # Build
    draft: Optional[dict] = None
    draft_file: Optional[str] = None
    build_output: Optional[str] = None
    workspace_dir: Optional[str] = None          # ~/Sentinel/<draft_id>
    stripe_product_ids: list[str] = []
    build_ok: bool = False                        # gate: QA GO + security build green

    # Security remediation (between build and approval)
    security_remediated: bool = False
    vulnerability_count: int = 0
    vulnerability_scan_error: Optional[str] = None
    vulnerability_findings: list[dict] = []

    # Approve
    approved: bool = False
    revision_notes: Optional[str] = None
    pending_since: Optional[str] = None

    # Draft tracking (dashboard pipeline id)
    draft_id: Optional[str] = None

    # Deploy
    deployed: bool = False
    deployed_url: Optional[str] = None            # https://<slug>.erslabs.net (frontend)
    deployment_id: Optional[str] = None
    backend_url: Optional[str] = None             # https://<slug>-api.fly.dev
    fly_app_name: Optional[str] = None
    cf_pages_project: Optional[str] = None
    stripe_webhook_endpoint_id: Optional[str] = None
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None


# ── Main Flow ────────────────────────────────────────────────────────────────

class SentinelLoopFlow(Flow[SentinelState]):
    """
    The Sentinel Loop — fully powered by CrewAI.

    RESEARCH → MATCH → BUILD → APPROVE (human feedback) → DEPLOY
    """

    # ─── Lifecycle ───────────────────────────────────────────────────────

    _shutdown_requested: bool = False

    def __init__(self):
        super().__init__()
        # Drop the auto-created CrewAI Memory: it spins up with embedder=None
        # which then tries the OpenAI default (CHROMA_OPENAI_API_KEY) on every
        # event and floods logs. Our `remember()` is a no-op override and our
        # persistence is handled by the SQLite checkpoint + dashboard_state.
        try:
            self.memory = None
        except Exception:
            object.__setattr__(self, "memory", None)
        # Set _state directly to avoid the read-only `state` property setter error.
        # Accessing self.state for the first time triggers lazy init from
        # Flow[SentinelState].initial_state_class via _create_initial_state().
        object.__setattr__(self, "_state", SentinelState())
        self._shutdown_requested = False

    def remember(self, *args, **kwargs):  # type: ignore[override]
        """No-op override. Persistence happens via SQLite checkpoint + dashboard
        state. CrewAI's flow-level memory needs an embedder we do not configure
        for the flow; calling base remember() raises and floods logs."""
        return None

    def recall(self, *args, **kwargs):  # type: ignore[override]
        return []

        # Register signals only on main thread
        try:
            if threading.current_thread() is threading.main_thread():
                signal.signal(signal.SIGTERM, self._on_signal)
                signal.signal(signal.SIGINT, self._on_signal)
        except Exception:
            pass

    def _on_signal(self, signum, frame):
        log.info("Received signal %s — will stop after current cycle", signum)
        self._shutdown_requested = True

    def _touch(self):
        self.state.last_update = datetime.now(timezone.utc).isoformat()

    def _save_checkpoint(self) -> None:
        if not self.state.draft_id:
            return
        try:
            from sentinel_v2 import db
            db.save_flow_checkpoint(
                self.state.draft_id,
                self.state.current_phase,
                self.state.model_dump_json(),
            )
        except Exception as e:
            log.warning("Checkpoint save failed: %s", e)

    def _clear_checkpoint(self) -> None:
        if not self.state.draft_id:
            return
        try:
            from sentinel_v2 import db
            db.clear_flow_checkpoint(self.state.draft_id)
        except Exception as e:
            log.warning("Checkpoint clear failed: %s", e)

    # ─── Phase 1: RESEARCH ───────────────────────────────────────────────

    @start()
    def start_cycle(self):
        """Begin a new cycle."""
        if self._shutdown_requested:
            log.info("Shutdown requested — skipping start_cycle")
            return

        # A real resume always carries a draft_id from the persisted checkpoint.
        # The daemon's main loop pre-sets cycle_count > 0 even on FRESH flows
        # (so make_draft_id produces unique ids across cycles), so we cannot use
        # cycle_count alone to detect resume. draft_id is the unambiguous signal.
        is_resume = bool(self.state.draft_id) and self.state.cycle_count > 0
        if is_resume:
            log.info("Resuming cycle #%d from phase %s", self.state.cycle_count, self.state.current_phase)
            print(f"\n{'='*50}\nResuming Cycle #{self.state.cycle_count} (phase: {self.state.current_phase})\n{'='*50}")
            return

        # Remember the prior cycle's draft id so we can detect when a new draft
        # enters the loop and avoid bleeding revision_notes from a rejected
        # previous draft into the fresh one. Resume path returned above, so
        # reaching here means a new cycle is starting.
        prev_draft_id = self.state.draft_id

        self.state.cycle_count += 1
        self.state.current_phase = "research"
        self._touch()
        log.info("=== Sentinel Loop Cycle #%d ===", self.state.cycle_count)
        print(f"\n{'='*50}\nCycle #{self.state.cycle_count}\n{'='*50}")

        # Clear agent messages from previous cycle
        try:
            from sentinel_v2.dashboard_state import clear_agent_messages
            clear_agent_messages()
        except Exception:
            pass

        # Before spawning new research, pick up any draft that was already approved
        # for build (status="queued") in a previous cycle — typically from the retry
        # button or from a rejected approval gate leaving an orphan behind.
        picked_queued_draft = False
        try:
            from sentinel_v2.dashboard_state import list_drafts_by_status
            queued = list_drafts_by_status({"queued"})
            if queued:
                draft = queued[0]
                picked_queued_draft = True
                log.info(
                    "Found queued draft %s from previous cycle — skipping research",
                    draft["id"],
                )
                print(f"Found queued draft {draft['id']} — skipping research")
                self.state.draft_id = draft["id"]
                self.state.top_opportunity = {
                    "title": draft.get("title", "retry"),
                    "tagline": draft.get("tagline") or "",
                    "description": draft.get("description") or "",
                    "problem": draft.get("problem") or "",
                    "solution": draft.get("solution") or "",
                    "tags": draft.get("tags") or [],
                    "tech_fit": draft.get("tech_fit", 0.0),
                    "complexity": draft.get("complexity", 0),
                }
                self.state.opportunities = [self.state.top_opportunity]
                self.state.approved = True  # user already approved via retry
                # Carry revision_notes from the draft so build crew can use them.
                # When the queued draft id differs from the previous cycle's,
                # any stale notes carried in state must NOT bleed into the new
                # draft's first build. When it matches (same draft re-queued),
                # the draft record's notes are still authoritative.
                if prev_draft_id is None or draft["id"] != prev_draft_id:
                    self.state.revision_notes = draft.get("revision_notes") or None
                else:
                    self.state.revision_notes = (
                        draft.get("revision_notes") or self.state.revision_notes
                    )
                # Reset phase outputs so phases actually run
                self.state.build_output = None
                self.state.workspace_dir = None
                self.state.match_score = 0.0
                self.state.user_profile = {}
                self.state.security_remediated = False
                self.state.vulnerability_count = 0
                self.state.vulnerability_scan_error = None
                self.state.vulnerability_findings = []
                self.state.deployed = False
                self.state.deployed_url = None
                self.state.deployment_id = None
                self.state.backend_url = None
                self.state.fly_app_name = None
                self.state.cf_pages_project = None
                self.state.stripe_webhook_endpoint_id = None
                self.state.stripe_product_ids = []
                self.state.error = None
                self.state.draft = None
                # CRITICAL: reset retry counters. Without this, a queued draft
                # that previously hit MAX retries would inherit those counters
                # via the persisted state, and the exhausted-retry guards in
                # run_build / run_deploy would mark it failed before the
                # crews even start.
                self.state.build_attempts = 0
                self.state.deploy_attempts = 0
                self.state.draft_file = None
                self.state.pending_since = None
                self._save_checkpoint()
        except Exception as e:
            log.warning("Could not check for queued drafts at cycle start: %s", e)

        # Research-path fall-through: when no queued draft was picked, the
        # state still carries the previous cycle's draft_id (run_research will
        # overwrite it with a new id later). Stale revision_notes from that
        # prior draft must be cleared so the upcoming build crew does not
        # chase ghost feedback against a brand new opportunity.
        if not picked_queued_draft and prev_draft_id is not None and self.state.revision_notes:
            log.info(
                "Clearing stale revision_notes from prior draft %s before new cycle",
                prev_draft_id,
            )
            self.state.revision_notes = None

    @listen(start_cycle)
    def run_research(self):
        """Phase 1: Run research crew to scout opportunities."""
        if self._shutdown_requested:
            return
        if self.state.top_opportunity is not None:
            log.info("Resume: research already done, skipping")
            return

        # Backpressure: suppress new research when the pipeline is already
        # saturated with pending review or in-flight builds/deploys. Adding
        # more opportunities here just piles work the user cannot triage.
        try:
            from sentinel_v2.dashboard_state import list_drafts_by_status
            active = list_drafts_by_status({
                "pending", "queued", "building", "review", "testing",
                "built", "pending_deploy", "deploying",
            })
            threshold = int(os.environ.get("SENTINEL_RESEARCH_PAUSE_THRESHOLD", "6"))
            if len(active) >= threshold:
                by_status: dict[str, int] = {}
                for d in active:
                    s = d.get("status") or "?"
                    by_status[s] = by_status.get(s, 0) + 1
                summary = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
                log.info(
                    "Research paused: %d active drafts (>= threshold %d) [%s]. "
                    "Skipping new research this cycle.",
                    len(active), threshold, summary,
                )
                self.state.opportunities = []
                return
        except Exception as e:
            log.warning("Could not evaluate research backpressure: %s", e)

        self.state.current_phase = "research"
        self._touch()
        log.info("Phase 1: RESEARCH")
        print("Phase 1: RESEARCH — scouting web...")
        _trace = start_trace("run_research", cycle=self.state.cycle_count)

        from sentinel_v2.crews.research_crew.research_crew import research_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        # Emit state update
        write_state(
            cycle=self.state.cycle_count,
            phase="research",
            opportunity=self.state.top_opportunity if self.state.top_opportunity else None,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="research",
            sub_phase="scouting-opportunities",
            status="running",
            progress=0.3,
            current_task="Scouting web for opportunities",
            pending_tasks=["Analyze opportunities", "Select top opportunity"],
            activity={
                "type": "phase_start",
                "agent": "web-scout",
                "message": "Starting web research for opportunities",
            },
        )

        crew = research_crew(cycle=self.state.cycle_count)
        result = crew.kickoff(
            inputs={
                "trend_signals": self._get_trend_signals(),
                "operator_capacity": self._get_operator_capacity(),
                "cycle": self.state.cycle_count,
            }
        )

        self.state.opportunities = self._parse_opportunities(result)

        # ── Cross-cycle dedup ─────────────────────────────────────────────
        from sentinel_v2.dedup import filter_duplicates
        unique, dupes = filter_duplicates(self.state.opportunities)
        if dupes:
            log.info("Filtered %d duplicate(s): %s", len(dupes), [d.get("title", "?") for d in dupes])
        self.state.opportunities = unique

        self.state.top_opportunity = (
            self.state.opportunities[0] if self.state.opportunities else None
        )

        # Publish ALL surfaced opportunities as pending drafts so the user can
        # see and approve any of them. The flow proceeds with top_opportunity
        # for the current cycle; if the user approves a different one, future
        # cycles' start_cycle will pick it up via the queued-draft lookup.
        if self.state.opportunities:
            from sentinel_v2.dashboard_state import write_draft, make_draft_id
            for idx, opp in enumerate(self.state.opportunities):
                draft_id = make_draft_id(self.state.cycle_count, opp)
                if idx == 0:
                    self.state.draft_id = draft_id
                write_draft(
                    draft_id=draft_id,
                    cycle=self.state.cycle_count,
                    title=opp.get("title", "Untitled opportunity"),
                    tagline=opp.get("tagline") or opp.get("summary") or "",
                    description=opp.get("description") or opp.get("solution") or "",
                    problem=opp.get("problem") or opp.get("problem_statement") or "",
                    solution=opp.get("solution") or "",
                    tech_fit=float(opp.get("tech_fit", 0.0) or 0.0),
                    complexity=int(opp.get("complexity", 0) or 0),
                    estimated_hours=opp.get("estimated_hours"),
                    tags=opp.get("tags") or [],
                    status="pending",
                )
                # Persist source URLs for social response after validation
                if opp.get("source_urls"):
                    from sentinel_v2 import db as _db
                    _db.patch_phase(draft_id, "opportunity", {"source_urls": opp["source_urls"]})

        # Update state after research
        opp_title = self.state.top_opportunity.get("title", "?") if self.state.top_opportunity else None
        write_state(
            cycle=self.state.cycle_count,
            phase="research_completed",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="research",
            sub_phase="scouting-opportunities",
            status="completed",
            progress=1.0,
            completed_tasks=["Scout web for opportunities", "Fetch top opportunity"],
            pending_tasks=[],
            opportunity_title=opp_title,
            activity={
                "type": "phase_complete",
                "agent": "sentinel",
                "message": f"Research complete — {len(self.state.opportunities)} opportunities found",
            },
        )

        # Store in CrewAI memory
        if self.state.opportunities:
            try:
                self.remember(
                    f"Cycle #{self.state.cycle_count} research: top opportunity = {self.state.top_opportunity.get('title', '?')}",
                    scope="/sentinel/research",
                )
            except Exception as e:
                log.warning("Memory save failed: %s", e)

        self._touch()
        self._save_checkpoint()
        log_event(_trace, "research_complete", metadata={"opportunity_count": len(self.state.opportunities), "top": (self.state.top_opportunity or {}).get("title")})
        end_trace(_trace, output={"opportunities": len(self.state.opportunities)})

    # ─── Gate 1: DRAFT APPROVAL (dashboard) ──────────────────────────────

    @listen(run_research)
    def wait_for_draft_approval(self) -> str:
        """Block until Kike approves the draft from the dashboard (or rejects it)."""
        if self._shutdown_requested or not self.state.draft_id:
            return "stop"
        if self.state.current_phase not in ("research",):
            log.info("Resume: draft approval gate already resolved, skipping")
            return "approved"

        from sentinel_v2.dashboard_state import wait_for_draft_status, get_draft, update_draft

        auto = os.getenv("SENTINEL_AUTO_APPROVE", "").lower() in {"1", "true", "yes"}
        if auto:
            update_draft(self.state.draft_id, status="queued")
            log.info("AUTO_APPROVE=1 — draft %s queued without human input", self.state.draft_id)
            return "approved"

        log.info("Waiting for dashboard approval on draft %s", self.state.draft_id)
        status = wait_for_draft_status(
            self.state.draft_id,
            target_statuses={"queued", "approved", "rejected"},
            timeout_seconds=int(os.getenv("SENTINEL_APPROVAL_TIMEOUT_SECONDS", "3600")),
        )
        if status in (None, "rejected"):
            log.info("Draft %s not approved (status=%s) — ending cycle", self.state.draft_id, status)
            # Clear the checkpoint so the next cycle does not resume on this
            # dead draft and skip queued-draft pickup.
            self._clear_checkpoint()
            self._shutdown_requested = status is None  # timeout stops the loop
            return "rejected"
        return "approved"

    # ─── Phase 2: MATCH ──────────────────────────────────────────────────

    @listen(wait_for_draft_approval)
    def run_match(self):
        """Phase 2: Match top opportunity to Kike's profile."""
        if self._shutdown_requested or not self.state.top_opportunity:
            return
        if self.state.match_score > 0 and self.state.user_profile:
            log.info("Resume: match already done, skipping")
            return

        self.state.current_phase = "match"
        self._touch()
        log.info("Phase 2: MATCH")
        print("Phase 2: MATCH — profiling Kike and matching...")
        _trace = start_trace("run_match", cycle=self.state.cycle_count, draft_id=self.state.draft_id, opportunity=(self.state.top_opportunity or {}).get("title"))

        from sentinel_v2.crews.match_crew.match_crew import match_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        # Emit state update
        write_state(
            cycle=self.state.cycle_count,
            phase="match",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="match",
            sub_phase="profile-matching",
            status="running",
            progress=0.3,
            current_task="Fetching Kike profile and matching",
            pending_tasks=["Calculate match score"],
            activity={
                "type": "phase_start",
                "agent": "matcher",
                "message": "Starting profile matching",
            },
        )

        try:
            crew = match_crew(cycle=self.state.cycle_count)
            result = crew.kickoff(
                inputs={
                    "opportunity": self.state.top_opportunity,
                    "operator_capacity": self._get_operator_capacity(),
                }
            )
        except Exception as e:
            log.error("Match crew failed: %s", e)
            if self.state.draft_id:
                try:
                    from sentinel_v2.dashboard_state import update_draft
                    update_draft(self.state.draft_id, status="failed",
                                 revision_notes=f"Match failed: {e}")
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self.state.error = str(e)
            self._save_checkpoint()
            log_event(_trace, "match_error", level="ERROR", metadata={"error": str(e)})
            end_trace(_trace, output={"error": str(e)}, level="ERROR")
            return

        parsed = self._parse_match_result(result)
        self.state.user_profile = parsed.get("profile", self.state.user_profile)
        self.state.match_score = parsed.get("score", 0.0)

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            update_draft(
                self.state.draft_id,
                tech_fit=float(self.state.match_score or 0.0),
            )

        # Store in CrewAI memory
        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} match: score={self.state.match_score}",
                scope="/sentinel/match",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        # Update state after match
        write_state(
            cycle=self.state.cycle_count,
            phase="match_completed",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="match",
            sub_phase="profile-matching",
            status="completed",
            progress=1.0,
            completed_tasks=["Fetch Kike profile", "Match opportunity to profile"],
            pending_tasks=[],
            match_score=self.state.match_score,
            activity={
                "type": "phase_complete",
                "agent": "matcher",
                "message": f"Match complete — score: {self.state.match_score}",
            },
        )

        self._touch()
        self._save_checkpoint()
        log_event(_trace, "match_complete", metadata={"score": self.state.match_score})
        end_trace(_trace, output={"match_score": self.state.match_score})

    # ─── Phase 3: BUILD ───────────────────────────────────────────────────

    @listen(run_match)
    def run_build(self):
        """Phase 3: Build micro-business draft with hierarchical crew."""
        if self._shutdown_requested or not self.state.top_opportunity:
            return
        if self.state.build_output is not None:
            log.info("Resume: build already done, skipping")
            return

        # Stale-checkpoint guard: a resumed state with build_attempts already
        # at the cap means a previous run blew through every retry without
        # producing build_output. Re-entering run_build would just spin (the
        # while loop below will not execute). Mark failed, clear checkpoint,
        # let the user retry or request changes.
        if self.state.build_attempts >= MAX_BUILD_RETRIES:
            log.error(
                "Build exhausted (attempts=%d/%d) on resumed state with no build_output. "
                "Marking draft failed and clearing checkpoint.",
                self.state.build_attempts, MAX_BUILD_RETRIES,
            )
            if self.state.draft_id:
                try:
                    from sentinel_v2.dashboard_state import update_draft
                    update_draft(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=(
                            f"Build exhausted all {MAX_BUILD_RETRIES} attempts in a prior cycle "
                            "and the resumed state had no build_output. Click Retry to start fresh."
                        ),
                    )
                except Exception as e:
                    log.warning("Could not mark draft failed: %s", e)
            self._clear_checkpoint()
            self._shutdown_requested = True  # end this cycle cleanly
            return

        self.state.current_phase = "build"
        self._touch()
        log.info("Phase 3: BUILD")
        print("Phase 3: BUILD — building micro-business draft...")
        _trace = start_trace("run_build", cycle=self.state.cycle_count, draft_id=self.state.draft_id, opportunity=(self.state.top_opportunity or {}).get("title"))

        from sentinel_v2.crews.build_crew.build_crew import build_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown

        # Emit state update
        write_state(
            cycle=self.state.cycle_count,
            phase="build",
            opportunity=self.state.top_opportunity,
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="build",
            sub_phase="draft-generation",
            status="running",
            progress=0.3,
            current_task="Generating micro-business draft",
            pending_tasks=["Validate draft", "Write output files"],
            activity={
                "type": "phase_start",
                "agent": "manager",
                "message": "Starting build phase",
            },
        )

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            update_draft(self.state.draft_id, status="building", build_progress=0.1)

        # Materialize a per-draft workspace so the build agents can write files to disk
        from pathlib import Path as _Path
        workspaces_root = _Path(os.environ.get("SENTINEL_WORKSPACES_ROOT", os.path.expanduser("~/Sentinel")))
        workspace_dir = workspaces_root / (self.state.draft_id or f"cycle_{self.state.cycle_count}")
        workspace_dir.mkdir(parents=True, exist_ok=True)
        self.state.workspace_dir = str(workspace_dir)
        slug = _make_slug(
            (self.state.top_opportunity or {}).get("title")
            or self.state.draft_id
            or f"cycle-{self.state.cycle_count}"
        )

        # Pre-bake fly.toml, Dockerfile, and the pinned NestJS package.json
        # BEFORE the build crew runs, so the builder treats them as inputs
        # and cannot regenerate an ERESOLVE-prone dependency matrix. The
        # deploy phase re-bakes the same files defensively.
        try:
            written = _prebake_deploy_files(self.state.workspace_dir, slug)
            if written:
                log.info("Pre-baked canonical templates: %s", list(written))
        except FileNotFoundError as e:
            log.warning("Skipping pre-bake: %s", e)

        # Frontend canonical pinning. Mirror of _prebake_deploy_files for the
        # Next.js side. Pinned to eliminate ERESOLVE drift between eslint and
        # eslint-config-next that the frontend agent triggers on roughly every
        # other build.
        try:
            written_fe = _prebake_frontend_files(self.state.workspace_dir, slug)
            if written_fe:
                log.info("Pre-baked canonical frontend templates: %s", list(written_fe))
        except FileNotFoundError as e:
            log.warning("Skipping frontend pre-bake: %s", e)

        # ── Build with automatic retry loop ──────────────────────────────
        feedback = self.state.revision_notes or ""
        result = None

        while self.state.build_attempts < MAX_BUILD_RETRIES:
            self.state.build_attempts += 1
            attempt = self.state.build_attempts
            log.info("Build attempt %d/%d", attempt, MAX_BUILD_RETRIES)
            log_event(_trace, "build_attempt_start", metadata={"attempt": attempt, "max": MAX_BUILD_RETRIES})

            if self.state.draft_id and attempt > 1:
                from sentinel_v2.dashboard_state import update_draft
                update_draft(
                    self.state.draft_id,
                    status="building",
                    build_progress=0.1,
                    revision_notes=f"[Auto-retry {attempt}/{MAX_BUILD_RETRIES}] {feedback}",
                )

            try:
                crew = build_crew(cycle=self.state.cycle_count)
                result = crew.kickoff(
                    inputs={
                        "opportunity": self.state.top_opportunity,
                        "operator_capacity": self._get_operator_capacity(),
                        "workspace_dir": self.state.workspace_dir,
                        "slug": slug,
                        "draft_id": self.state.draft_id or "unknown",
                        "revision_notes": feedback,
                    }
                )
                # Success — break out of retry loop
                break
            except Exception as e:
                error_msg = str(e)
                log.error("Build attempt %d/%d failed: %s", attempt, MAX_BUILD_RETRIES, error_msg)

                # Tag transient network blips so the operator can tell at a
                # glance that a retry was caused by infrastructure, not by
                # a bug in the generated code. The retry feedback string is
                # left intact so the LLM still sees the original error.
                if is_transient(error_msg):
                    log.info(
                        "Transient network error on attempt %d/%d: %s. Retrying.",
                        attempt,
                        MAX_BUILD_RETRIES,
                        error_msg[:200],
                    )

                # Unrecoverable errors (rate-limit, expired key, payment) get
                # escalated immediately. Retrying just wastes the budget and
                # masks the real action item from the operator.
                category = classify_error(error_msg)
                if category:
                    write_escalation(
                        category,
                        error_msg,
                        phase="build",
                        draft_id=self.state.draft_id,
                        cycle=self.state.cycle_count,
                        extra={"attempt": attempt, "slug": slug},
                    )
                    if self.state.draft_id:
                        try:
                            from sentinel_v2.dashboard_state import update_draft
                            update_draft(
                                self.state.draft_id,
                                status="blocked",
                                revision_notes=(
                                    f"[ESCALATED:{category}] Build halted on attempt {attempt}/"
                                    f"{MAX_BUILD_RETRIES}. Operator action required. "
                                    f"Last error: {error_msg[:500]}"
                                ),
                            )
                        except Exception as db_err:
                            log.warning("Could not mark draft blocked: %s", db_err)
                    self.state.error = f"escalated:{category}"
                    # Stop the cycle here. Without this flag the @listen chain
                    # carries on into run_security_remediation -> request_approval
                    # -> run_deploy, all of which run a full crew on a workspace
                    # that never produced a clean build. Observed live: an
                    # escalation marked the draft 'blocked' but the cycle still
                    # spent 5 security iterations grinding on build_ok=False
                    # output before the deploy gate finally rejected it.
                    self._shutdown_requested = True
                    self._save_checkpoint()
                    log_event(_trace, "build_escalated", level="ERROR", metadata={"category": category, "attempt": attempt, "error": error_msg[:500]})
                    end_trace(_trace, output={"escalated": category}, level="ERROR")
                    return

                feedback = f"Build attempt {attempt} failed with error:\n{error_msg}\n\nFix the issues and try again."

                if attempt >= MAX_BUILD_RETRIES:
                    log.error("Build exhausted all %d retries", MAX_BUILD_RETRIES)
                    if self.state.draft_id:
                        try:
                            from sentinel_v2.dashboard_state import update_draft
                            update_draft(
                                self.state.draft_id,
                                status="failed",
                                revision_notes=f"Build failed after {MAX_BUILD_RETRIES} attempts. Last error: {error_msg}",
                            )
                        except Exception as db_err:
                            log.warning("Could not mark draft failed: %s", db_err)
                    self.state.error = error_msg
                    self._save_checkpoint()
                    return

                self._save_checkpoint()

        self.state.build_output = str(result.raw) if hasattr(result, "raw") else str(result)

        # ── Defensive re-bake: revert ALL protected template files in one pass.
        # The build_crew prompt forbids overwriting Dockerfile, fly.toml,
        # backend/package.json, the Stripe + Prisma protected sources, and
        # the tsconfig / nest-cli configs, but the backend Lead still has the
        # write_file tool and routinely clobbers them (observed live: a
        # rewritten src/modules/stripe/stripe.controller.ts pinned
        # apiVersion='2024-06-20' but the canonical stripe@14.25.0 type only
        # accepts '2023-10-16', and the TS2322 mismatch killed `nest build`).
        # Re-running the walk-recursive bake overwrites every template file
        # back to its canonical, slug-substituted contents. Idempotent and
        # cheap; touches only files that exist in the template tree.
        try:
            rebaked = _prebake_deploy_files(self.state.workspace_dir, slug)
            log.info("Re-baked protected template files post-build: %s", list(rebaked))
            log_event(
                _trace,
                "post_build_rebake",
                metadata={"files": list(rebaked)},
            )
        except FileNotFoundError as e:
            log.warning("Post-build re-bake skipped: %s", e)

        # Mirror for the frontend canonical pin (package.json). The agent has
        # write_file and routinely clobbers the pinned matrix with newer
        # majors that break peer-deps.
        try:
            rebaked_fe = _prebake_frontend_files(self.state.workspace_dir, slug)
            log.info("Re-baked canonical frontend templates post-build: %s", list(rebaked_fe))
            log_event(
                _trace,
                "post_build_frontend_rebake",
                metadata={"files": list(rebaked_fe)},
            )
        except FileNotFoundError as e:
            log.warning("Post-build frontend re-bake skipped: %s", e)

        # Defensive: revert any agent-side rewrites of the pinned package.json.
        # Kept for the per-file hash log: tells the operator at a glance
        # whether the agent tried to drift the dependency matrix this run.
        try:
            _verify_package_json_unchanged(self.state.workspace_dir)
        except Exception as e:
            log.warning("package.json verification skipped: %s", e)

        # Defense-in-depth: build agent may have skipped the prompt rule about
        # importing the protected StripeWebhookController in AppModule. Without
        # registration the webhook URL returns 404 and Stripe quietly retries.
        # Auto-patch idempotently; never fail the build here (the deploy QA
        # verifier will catch a totally broken AppModule downstream).
        try:
            stripe_reg = _ensure_stripe_controller_registered(self.state.workspace_dir)
            log_event(
                _trace,
                "stripe_controller_check",
                metadata=stripe_reg,
            )
        except Exception as e:  # noqa: BLE001 - defensive only
            log.warning("StripeWebhookController auto-registration skipped: %s", e)

        # Sibling defense: webhook controller reads req.rawBody, which NestJS
        # only populates when bootstrap passes { rawBody: true }. Auto-patch
        # main.ts when the agent forgot. Same defensive contract: never raises,
        # never fails the build.
        try:
            raw_body_check = _ensure_main_ts_raw_body(self.state.workspace_dir)
            log_event(
                _trace,
                "main_ts_raw_body_check",
                metadata=raw_body_check,
            )
        except Exception as e:  # noqa: BLE001 - defensive only
            log.warning("main.ts rawBody auto-patch skipped: %s", e)

        # ── Deterministic build verification ─────────────────────────────
        # Trust-but-verify gate. The QA Lead self-reports build_status, but a
        # hallucinating LLM can claim 'clean' on a workspace that won't even
        # `npm install`. Run the real commands ourselves; if they fail,
        # short-circuit before security/approval/deploy. This is the only
        # way to guarantee a broken build never reaches the deploy queue.
        verify_timeout = int(os.environ.get("SENTINEL_BUILD_VERIFY_TIMEOUT", "600"))
        try:
            verify = _verify_npm_build(self.state.workspace_dir, timeout=verify_timeout)
        except Exception as e:  # noqa: BLE001 - defensive only
            log.error("Build verification raised; treating as failure: %s", e)
            verify = {
                "ok": False,
                "first_failure": f"exception:{type(e).__name__}",
                "details": {},
            }

        if not verify.get("ok"):
            self.state.build_ok = False
            self.state.error = "build_verification_failed"
            details = verify.get("details") or {}
            tail = ""
            for sub in ("backend", "frontend"):
                d = details.get(sub) or {}
                if d.get("tail"):
                    tail = d["tail"]
                    break
            reason = (
                f"npm verify failed at {verify.get('first_failure') or 'unknown'}. "
                f"Last output: {tail[:400]!r}"
            )
            log.error("Build verification failed - %s", reason)
            if self.state.draft_id:
                from sentinel_v2.dashboard_state import update_draft
                try:
                    update_draft(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=f"Auto-rejected by build verification. {reason}",
                    )
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self._clear_checkpoint()
            self._shutdown_requested = True
            log_event(
                _trace,
                "build_verification_fail",
                level="ERROR",
                metadata={"first_failure": verify.get("first_failure"), "details": details},
            )
            end_trace(_trace, output={"build_verification": "fail"}, level="ERROR")
            return

        log_event(
            _trace,
            "build_verification_pass",
            metadata=verify.get("details") or {},
        )

        # ── QA gate: refuse to promote a draft the QA Lead failed ────────
        # Reads the QA Lead's structured output (go_no_go, build_status,
        # blocking_issues). If the gate is NO-GO or build_status=='fail',
        # mark the draft failed and stop the cycle here. Without this gate
        # the loop sends broken builds through security/approval anyway.
        qa_parsed = self._parse_deploy_result(result) or {}
        go_no_go = str(qa_parsed.get("go_no_go") or "").strip().upper()
        build_status = str(qa_parsed.get("build_status") or "").strip().lower()
        blocking_issues = qa_parsed.get("blocking_issues") or []
        qa_failed = (
            (go_no_go and go_no_go != "GO")
            or build_status == "fail"
        )
        if qa_failed:
            self.state.build_ok = False
            self.state.error = "build_failed_qa_gate"
            reason = (
                f"QA gate: go_no_go={go_no_go or 'unknown'}, "
                f"build_status={build_status or 'unknown'}, "
                f"blockers={blocking_issues!r}"
            )
            log.error("Build QA gate failed — %s", reason)
            if self.state.draft_id:
                from sentinel_v2.dashboard_state import update_draft
                try:
                    update_draft(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=f"Auto-rejected by QA gate. {reason}",
                    )
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self._clear_checkpoint()
            self._shutdown_requested = True
            log_event(_trace, "qa_gate_fail", level="ERROR", metadata={"go_no_go": go_no_go, "build_status": build_status, "blockers": blocking_issues})
            end_trace(_trace, output={"qa_gate": "fail", "reason": reason}, level="ERROR")
            return

        # QA gate decision. Closed-by-default: only an explicit positive
        # signal from the QA Lead promotes the draft. Anything else (silence,
        # prose-instead-of-JSON, partial output) is a fail. The previous
        # "default to True if unparseable, security loop will validate"
        # branch was a fail-open: when the QA Lead returns natural language
        # instead of structured output, we have NO evidence the build is
        # green, and the security loop only validates dependency CVEs, not
        # the actual `npm run build`. Treating "no signal" as "green" let
        # broken builds reach the approval queue cycle after cycle.
        if go_no_go == "GO" or build_status in {"clean", "warnings"}:
            self.state.build_ok = True
        else:
            self.state.build_ok = False
            self.state.error = "build_failed_qa_gate_unparseable"
            reason = (
                f"QA gate produced no positive signal: "
                f"go_no_go={go_no_go or 'unknown'!r}, "
                f"build_status={build_status or 'unknown'!r}. "
                "QA Lead must return GO + build_status in {clean, warnings} "
                "for the draft to be promoted."
            )
            log.error("Build QA gate fail-closed — %s", reason)
            if self.state.draft_id:
                from sentinel_v2.dashboard_state import update_draft
                try:
                    update_draft(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=f"Auto-rejected by QA gate (no positive signal). {reason}",
                    )
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self._clear_checkpoint()
            self._shutdown_requested = True
            log_event(_trace, "qa_gate_fail_closed", level="ERROR", metadata={"go_no_go": go_no_go, "build_status": build_status})
            end_trace(_trace, output={"qa_gate": "fail_closed"}, level="ERROR")
            return

        log_event(_trace, "qa_gate_pass", metadata={"go_no_go": go_no_go, "build_status": build_status})

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            # Move to review first (code-review + security-audit), then built with metrics.
            update_draft(self.state.draft_id, status="review", build_progress=0.7)
            update_draft(
                self.state.draft_id,
                status="built",
                build_progress=1.0,
                coverage_percent=self._extract_metric(result, "coverage_percent"),
                tests_passed=self._extract_metric(result, "tests_passed"),
                tests_total=self._extract_metric(result, "tests_total"),
                issues_count=self._extract_metric(result, "issues_count"),
            )

        # Update state after build
        write_state(
            cycle=self.state.cycle_count,
            phase="build_completed",
            opportunity=self.state.top_opportunity,
            build_output=self.state.build_output[:1000] if self.state.build_output else "",  # Truncate
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="build",
            sub_phase="draft-generation",
            status="completed",
            progress=1.0,
            completed_tasks=["Generate draft", "Write output files"],
            pending_tasks=[],
            activity={
                "type": "phase_complete",
                "agent": "builder",
                "message": "Build draft complete",
            },
        )

        # Store in CrewAI memory
        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} build: draft complete",
                scope="/sentinel/build",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        self._touch()
        self._save_checkpoint()
        end_trace(_trace, output={"build_ok": self.state.build_ok, "attempts": self.state.build_attempts})

    # ─── Phase 3b: SECURITY REMEDIATION ──────────────────────────────────

    @listen(run_build)
    def run_security_remediation(self):
        """Phase 3b: scan deps with osv-scanner and apply fixes in a loop until 0 vulns."""
        if self._shutdown_requested or not self.state.workspace_dir:
            return
        if self.state.security_remediated:
            log.info("Resume: security remediation already completed")
            return

        self.state.current_phase = "security"
        self._touch()
        log.info("Phase 3b: SECURITY REMEDIATION")
        print("Phase 3b: SECURITY — scanning + remediating dependency vulnerabilities...")
        _trace = start_trace("run_security", cycle=self.state.cycle_count, draft_id=self.state.draft_id)

        from sentinel_v2.crews.security_remediation_crew.security_remediation_crew import (
            security_remediation_crew,
        )
        from sentinel_v2.dashboard_state import update_draft, write_flow_breakdown

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="security",
            sub_phase="vulnerability-scan",
            status="running",
            progress=0.0,
            current_task="osv-scanner + remediation loop",
            activity={
                "type": "phase_start",
                "agent": "security-scanner",
                "message": "Starting dependency vulnerability remediation",
            },
        )

        max_iter = int(os.environ.get("SENTINEL_MAX_REMEDIATION_ITERATIONS", "5"))
        remaining = 0
        build_ok = False
        for i in range(1, max_iter + 1):
            log.info("Security remediation iteration %d/%d", i, max_iter)
            crew = security_remediation_crew(cycle=self.state.cycle_count)
            try:
                result = crew.kickoff(inputs={
                    "workspace_dir": self.state.workspace_dir,
                    "iteration": i,
                    "max_iterations": max_iter,
                    "draft_id": self.state.draft_id or "",
                })
            except Exception as e:
                log.warning("Security iteration %d failed: %s", i, e)
                self.state.vulnerability_scan_error = f"iter {i}: {e}"
                break

            parsed = self._parse_deploy_result(result) or {}
            try:
                remaining = int(parsed.get("total_vulns_after", 0) or 0)
            except (TypeError, ValueError):
                remaining = 0
            build_ok = bool(parsed.get("build_ok", False))
            tests_ok = bool(parsed.get("tests_ok", False))
            self.state.vulnerability_count = remaining
            # Persist the security loop's build verdict so request_approval
            # can gate on it. Only override if the apply_task explicitly
            # reported build_ok — if the field is missing the crew never
            # ran a real build and we keep the QA-gate verdict from
            # run_build. An explicit False from security overrides True
            # from QA (a passing QA agent + broken security build = NO-GO).
            if "build_ok" in parsed:
                self.state.build_ok = self.state.build_ok and build_ok
            if isinstance(parsed.get("findings"), list):
                self.state.vulnerability_findings = parsed["findings"][:50]

            if self.state.draft_id:
                update_draft(
                    self.state.draft_id,
                    revision_notes=(
                        f"Security iter {i}/{max_iter}: {remaining} vulns remaining, "
                        f"build={'ok' if build_ok else 'fail'}, "
                        f"tests={'ok' if tests_ok else 'fail'}"
                    ),
                )

            if remaining == 0 and build_ok:
                log.info("Security: 0 vulns and build green after %d iterations", i)
                break
            log.info(
                "Security iter %d/%d: remaining=%d build=%s tests=%s",
                i, max_iter, remaining, build_ok, tests_ok,
            )
        else:
            self.state.vulnerability_scan_error = (
                f"Could not reach 0 vulns / green build after {max_iter} iterations "
                f"(remaining={remaining}, build_ok={build_ok})"
            )
            log.warning(self.state.vulnerability_scan_error)
            if self.state.draft_id:
                update_draft(
                    self.state.draft_id,
                    revision_notes=self.state.vulnerability_scan_error,
                )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="security",
            sub_phase="vulnerability-scan",
            status="completed" if self.state.vulnerability_scan_error is None else "blocked",
            progress=1.0,
            completed_tasks=["Remediation loop"],
            pending_tasks=[],
            activity={
                "type": "phase_complete",
                "agent": "security-scanner",
                "message": (
                    f"Remediation finished: {self.state.vulnerability_count} vulns remaining"
                ),
            },
        )

        self.state.security_remediated = True
        self._touch()
        self._save_checkpoint()
        log_event(_trace, "security_complete", metadata={"vuln_count": self.state.vulnerability_count, "scan_error": self.state.vulnerability_scan_error})
        end_trace(_trace, output={"vuln_count": self.state.vulnerability_count})

    # ─── Phase 4: APPROVE (human feedback) ───────────────────────────────

    @listen(run_security_remediation)
    def request_approval(self) -> str:
        """Phase 4: Present draft to Kike for approval via the dashboard."""
        if self.state.approved:
            log.info("Resume: already approved, skipping request_approval gate")
            return "pending"

        # ── Health gate: never park a broken draft in the approval queue ──
        # Without this, drafts whose security loop exhausted retries (or
        # whose build never went green) sat as "Built — awaiting deploy
        # approval" indefinitely, polluting the dashboard.
        if self.state.vulnerability_scan_error or not self.state.build_ok:
            reason = (
                self.state.vulnerability_scan_error
                or f"build_ok={self.state.build_ok}"
            )
            log.error("Skipping approval gate — broken build/security: %s", reason)
            if self.state.draft_id:
                from sentinel_v2.dashboard_state import update_draft
                try:
                    update_draft(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=f"Auto-rejected before approval. {reason}",
                    )
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self._clear_checkpoint()
            self._shutdown_requested = True
            return "stop"

        self.state.current_phase = "approve"
        self.state.pending_since = datetime.now(timezone.utc).isoformat()
        self._touch()
        log.info("Phase 4: APPROVE — waiting for Kike")
        print("Phase 4: APPROVE — sending to Kike for review...")
        _trace = start_trace("request_approval", cycle=self.state.cycle_count, draft_id=self.state.draft_id)
        log_event(_trace, "approval_requested")
        end_trace(_trace, output={"pending_since": self.state.pending_since})

        # Store in CrewAI memory
        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} pending approval since {self.state.pending_since}",
                scope="/sentinel/approvals",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        return "pending"

    @listen(request_approval)
    def check_approval(self) -> str:
        """Block until the Deploy/Reject gate is resolved via the dashboard."""
        if self.state.approved:
            log.info("Resume: deploy gate already approved")
            return "approved"

        from sentinel_v2.dashboard_state import (
            wait_for_draft_status,
            write_state,
            write_flow_breakdown,
        )

        # Emit state update for approval waiting
        write_state(
            cycle=self.state.cycle_count,
            phase="approve",
            opportunity=self.state.top_opportunity,
            build_output=self.state.build_output[:1000] if self.state.build_output else "",
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="approve",
            sub_phase="human-review",
            status="running",
            progress=0.5,
            current_task="Waiting for deploy approval",
            pending_tasks=["Dashboard approval", "Deploy to production"],
            activity={
                "type": "awaiting_approval",
                "agent": "sentinel",
                "message": "Built — awaiting deploy approval from dashboard",
            },
        )

        if not self.state.draft_id:
            return "stop"

        auto = os.getenv("SENTINEL_AUTO_APPROVE", "").lower() in {"1", "true", "yes"}
        if auto:
            self.state.approved = True
            log.info("AUTO_APPROVE=1 — deploying draft %s without human input", self.state.draft_id)
            return "approved"

        log.info("Waiting for deploy gate on draft %s", self.state.draft_id)
        # Wait for the user's INTENT statuses, not the runtime's terminal states.
        #   pending_deploy   → user clicked "Approve deploy" → we run run_deploy
        #   queued           → user clicked "Request changes" with notes → end
        #                       cycle so the daemon's next start_cycle picks the
        #                       queued draft up and re-runs build with the notes
        #   rejected_deploy  → user clicked "Reject deploy" → end cycle final
        status = wait_for_draft_status(
            self.state.draft_id,
            target_statuses={"pending_deploy", "queued", "rejected_deploy"},
            timeout_seconds=int(os.getenv("SENTINEL_APPROVAL_TIMEOUT_SECONDS", "3600")),
        )
        if status == "pending_deploy":
            self.state.approved = True
            return "approved"
        if status == "queued":
            log.info(
                "Deploy gate on %s: user requested changes (status=queued). "
                "Ending cycle; next cycle will pick up the queued draft and rebuild.",
                self.state.draft_id,
            )
            # Drop the checkpoint so the next cycle does NOT resume into the
            # post-build approval gate; it should restart from start_cycle and
            # re-pick the queued draft via the queued-list path.
            self._clear_checkpoint()
            return "stop"
        log.info("Deploy gate on %s resolved as %s — stopping cycle", self.state.draft_id, status)
        self._clear_checkpoint()
        return "stop"

    # ─── Phase 5: DEPLOY ──────────────────────────────────────────────────

    @listen(check_approval)
    def run_deploy(self):
        """Phase 5: Deploy approved build."""
        if not self.state.approved or self._shutdown_requested:
            log.info("Not approved or shutdown — skipping deploy")
            return
        if self.state.deployed:
            log.info("Resume: already deployed, skipping")
            self._clear_checkpoint()
            return

        # Stale-checkpoint guard: a resumed state with deploy_attempts already
        # at the cap means a previous run exhausted every retry without
        # marking the draft deployed. Re-entering would just spin (the while
        # loop below cannot increment past MAX). Mark failed, clear, exit.
        if self.state.deploy_attempts >= MAX_DEPLOY_RETRIES:
            log.error(
                "Deploy exhausted (attempts=%d/%d) on resumed state without success. "
                "Marking draft failed and clearing checkpoint.",
                self.state.deploy_attempts, MAX_DEPLOY_RETRIES,
            )
            if self.state.draft_id:
                try:
                    from sentinel_v2.dashboard_state import update_draft
                    update_draft(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=(
                            f"Deploy exhausted all {MAX_DEPLOY_RETRIES} attempts in a prior cycle "
                            "and the resumed state had no deployed=True. Click Retry to start fresh."
                        ),
                    )
                except Exception as e:
                    log.warning("Could not mark draft failed: %s", e)
            self._clear_checkpoint()
            self._shutdown_requested = True  # end this cycle cleanly
            return

        # Health gate: mirrors request_approval(). A force-approval or
        # resumed state could otherwise carry build_ok=False or a scan
        # error into Fly/CF deploys and burn tokens on a never-green draft.
        if self.state.vulnerability_scan_error or not self.state.build_ok:
            reason = (
                self.state.vulnerability_scan_error
                or f"build_ok={self.state.build_ok}"
            )
            log.error("Skipping deploy gate - broken build/security: %s", reason)
            _gate_trace = start_trace(
                "run_deploy_health_gate",
                cycle=self.state.cycle_count,
                draft_id=self.state.draft_id,
            )
            log_event(
                _gate_trace,
                "deploy_health_gate_fail",
                level="ERROR",
                metadata={"reason": reason, "build_ok": self.state.build_ok},
            )
            end_trace(_gate_trace, output={"gate": "fail", "reason": reason}, level="ERROR")
            if self.state.draft_id:
                try:
                    from sentinel_v2.dashboard_state import update_draft
                    update_draft(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=f"Auto-rejected before deploy. {reason}",
                    )
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self._clear_checkpoint()
            self._shutdown_requested = True
            return

        self.state.current_phase = "deploy"
        self._touch()
        log.info("Phase 5: DEPLOY")
        print("Phase 5: DEPLOY — deploying to production...")
        _trace = start_trace("run_deploy", cycle=self.state.cycle_count, draft_id=self.state.draft_id, opportunity=(self.state.top_opportunity or {}).get("title"))

        from sentinel_v2.crews.deploy_crew.deploy_crew import deploy_crew
        from sentinel_v2.dashboard_state import write_state, write_flow_breakdown, update_draft

        # Mark the draft as actively deploying so the dashboard shows progress
        # and orphan recovery on daemon restart can clean up partial deploys.
        if self.state.draft_id:
            try:
                update_draft(self.state.draft_id, status="deploying", build_progress=0.85)
            except Exception as e:
                log.warning("Could not set deploying status: %s", e)

        # Emit state update for deploy phase
        write_state(
            cycle=self.state.cycle_count,
            phase="deploy",
            opportunity=self.state.top_opportunity,
            build_output=self.state.build_output[:1000] if self.state.build_output else "",
        )

        write_flow_breakdown(
            cycle=self.state.cycle_count,
            phase="deploy",
            sub_phase="deployment",
            status="running",
            progress=0.5,
            current_task="Deploying to production",
            pending_tasks=["Deploy", "Verify deployment"],
            activity={
                "type": "phase_start",
                "agent": "deployer",
                "message": "Starting deployment to production",
            },
        )

        slug = _make_slug(
            (self.state.top_opportunity or {}).get("title")
            or self.state.draft_id
            or f"cycle-{self.state.cycle_count}"
        )
        # Always recompute from current env. A persisted state.workspace_dir
        # may carry a stale path from a different environment (e.g. a previous
        # Docker run where HOME=/root). Files actually live under the local
        # workspaces root; trust the env, not the snapshot.
        workspace_dir = _resolve_workspace_dir(self.state.draft_id, self.state.cycle_count)
        if self.state.workspace_dir and self.state.workspace_dir != workspace_dir:
            log.warning(
                "Ignoring stale state.workspace_dir=%r; using current env path %r",
                self.state.workspace_dir, workspace_dir,
            )
        self.state.workspace_dir = workspace_dir

        # Pre-bake the EXACT names the deploy agent must use.
        # The agent receives these as plain strings: it has no access to draft_id,
        # so it cannot accidentally use the draft_cN_ form as a Cloudflare project
        # name or DNS subdomain.
        expected_backend_app_name = f"{slug}-api"
        expected_cf_project_name = slug
        expected_frontend_url = f"https://{slug}.{ERSLABS_ROOT_DOMAIN}"
        expected_backend_url = f"https://{expected_backend_app_name}.fly.dev"

        # Pre-bake fly.toml and Dockerfile from the canonical template. The build
        # agent has no business writing infra files: every backend ships with the
        # same NestJS stack, so we overwrite whatever it produced with the known-
        # good template, slug-substituted. Same defense for the Dockerfile.
        try:
            prebaked = _prebake_deploy_files(workspace_dir, slug)
            log.info("Prebaked deploy files: %s", prebaked)
        except FileNotFoundError as e:
            log.warning("Skipping pre-bake before deploy: %s", e)

        # ── Shared Fly Postgres cluster: lazy-create + attach this app's DB ─
        # Cluster spin-up is gated by run_deploy entry: build verification
        # already passed and the user already approved the deploy gate, so
        # this is the first irreversible piece of infra spend. Subsequent
        # deploys reuse the cluster (idempotent infra_state lookup) and just
        # attach a new database per app.
        database_url: Optional[str] = None
        try:
            from sentinel_v2.flows import shared_postgres as _spg
            cluster_info = _spg.ensure_shared_pg_cluster()
            log.info(
                "Shared PG cluster ready: name=%s region=%s source=%s created=%s",
                cluster_info["cluster_name"],
                cluster_info["region"],
                cluster_info["source"],
                cluster_info["created"],
            )
            log_event(_trace, "shared_pg_ready", metadata=cluster_info)

            attach_info = _spg.attach_db_for_app(
                cluster_name=cluster_info["cluster_name"],
                backend_app_name=expected_backend_app_name,
            )
            database_url = attach_info["database_url"]
            log.info(
                "Per-app DB attached: app=%s db=%s user=%s already_attached=%s url=%s",
                expected_backend_app_name,
                attach_info["database_name"],
                attach_info["database_user"],
                attach_info["already_attached"],
                "<set>" if database_url else "<absent>",
            )
            log_event(
                _trace,
                "shared_pg_attached",
                metadata={
                    "database_name": attach_info["database_name"],
                    "database_user": attach_info["database_user"],
                    "already_attached": attach_info["already_attached"],
                    "has_url": bool(database_url),
                },
            )
        except Exception as pg_err:  # noqa: BLE001
            log.error("Shared Postgres provisioning failed: %s", pg_err)
            self.state.error = f"shared_pg_provisioning_failed: {pg_err}"
            if self.state.draft_id:
                from sentinel_v2.dashboard_state import update_draft as _upd
                try:
                    _upd(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=(
                            "Shared Fly Postgres provisioning failed before deploy: "
                            f"{pg_err}. App not deployed."
                        ),
                    )
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self._save_checkpoint()
            log_event(
                _trace,
                "shared_pg_failed",
                level="ERROR",
                metadata={"error": str(pg_err)[:500]},
            )
            end_trace(
                _trace,
                output={"shared_pg_failed": str(pg_err)[:500]},
                level="ERROR",
            )
            return

        # Provision Stripe Product + Webhook BEFORE the deploy crew runs so the
        # secrets land in the SAME release as DATABASE_URL (staged in step 3 of
        # the crew, applied at fly_deploy in step 4). Otherwise the protected
        # `stripe.config.ts` throws at module load on the first boot, Fly rolls
        # back the release, and the QA verifier returns ROLLBACK in a loop.
        try:
            stripe_resources = _provision_stripe_resources(
                draft_id=self.state.draft_id or "unknown",
                slug=slug,
                backend_url=expected_backend_url,
                opportunity=self.state.top_opportunity or {},
            )
            log.info(
                "Stripe resources provisioned for %s: product=%s webhook=%s rotated=%s",
                self.state.draft_id,
                stripe_resources["product_id"],
                stripe_resources["webhook_endpoint_id"],
                stripe_resources["secret_was_rotated"],
            )
            log_event(
                _trace,
                "stripe_provisioned",
                metadata={
                    k: v
                    for k, v in stripe_resources.items()
                    if k != "webhook_secret"
                },
            )
            self.state.stripe_product_id = stripe_resources["product_id"]
            self.state.stripe_price_id = stripe_resources["price_id"]
            self.state.stripe_webhook_endpoint_id = stripe_resources["webhook_endpoint_id"]
        except Exception as stripe_err:  # noqa: BLE001
            log.error("Stripe provisioning failed: %s", stripe_err)
            self.state.error = f"stripe_provisioning_failed: {stripe_err}"
            if self.state.draft_id:
                from sentinel_v2.dashboard_state import update_draft as _upd
                try:
                    _upd(
                        self.state.draft_id,
                        status="failed",
                        revision_notes=(
                            "Stripe provisioning failed before deploy: "
                            f"{stripe_err}. App not deployed."
                        ),
                    )
                except Exception as db_err:
                    log.warning("Could not mark draft failed: %s", db_err)
            self._save_checkpoint()
            log_event(_trace, "stripe_failed", level="ERROR", metadata={"error": str(stripe_err)[:500]})
            end_trace(_trace, output={"stripe_failed": str(stripe_err)[:500]}, level="ERROR")
            return

        # ── Deploy with automatic retry loop ─────────────────────────────
        # Seed feedback with any human revision_notes so a "request changes"
        # actually reaches the deploy agent on the next attempt.
        deploy_feedback = self.state.revision_notes or ""
        result = None
        parsed = None
        deploy_success = False

        while self.state.deploy_attempts < MAX_DEPLOY_RETRIES:
            self.state.deploy_attempts += 1
            attempt = self.state.deploy_attempts
            log.info("Deploy attempt %d/%d", attempt, MAX_DEPLOY_RETRIES)
            log_event(_trace, "deploy_attempt_start", metadata={"attempt": attempt, "max": MAX_DEPLOY_RETRIES})

            if self.state.draft_id and attempt > 1:
                from sentinel_v2.dashboard_state import update_draft
                update_draft(
                    self.state.draft_id,
                    status="deploying",
                    revision_notes=f"[Auto-retry {attempt}/{MAX_DEPLOY_RETRIES}] {deploy_feedback}",
                )

            try:
                crew = deploy_crew(cycle=self.state.cycle_count)
                result = crew.kickoff(
                    inputs={
                        "draft": self.state.build_output,
                        "opportunity": self.state.top_opportunity,
                        "workspace_dir": workspace_dir,
                        "slug": slug,
                        # Pre-baked names the agent MUST use literally.
                        # We do NOT pass draft_id: it confuses the agent, which
                        # then uses the draft_cN_ form as a Pages project name.
                        "backend_app_name": expected_backend_app_name,
                        "cf_project_name": expected_cf_project_name,
                        "frontend_url": expected_frontend_url,
                        "backend_url": expected_backend_url,
                        "erslabs_root": ERSLABS_ROOT_DOMAIN,
                        "stripe_publishable": os.environ.get("STRIPE_API_KEY", ""),
                        # Sentinel pre-provisioned the Stripe Product +
                        # Webhook above. The deploy agent stages these as
                        # Fly secrets in step 3 (alongside DATABASE_URL) so
                        # the FIRST release boots with stripe.config.ts
                        # validation passing. No Stripe API call from the
                        # agent.
                        "stripe_secret_key": os.environ.get("STRIPE_SECRET_KEY", ""),
                        "stripe_webhook_secret": stripe_resources["webhook_secret"],
                        "stripe_product_id": stripe_resources["product_id"],
                        "stripe_price_id": stripe_resources["price_id"] or "",
                        # Shared Postgres cluster: empty string when the app
                        # was already attached on a previous cycle (Fly secret
                        # already set; the deploy crew skips re-staging).
                        "database_url": database_url or "",
                        "deploy_feedback": deploy_feedback,
                    }
                )
            except Exception as e:
                error_msg = str(e)
                log.error("Deploy attempt %d/%d failed: %s", attempt, MAX_DEPLOY_RETRIES, error_msg)

                # Mirror the build loop: transient network blips get an
                # INFO line so the operator does not chase a phantom code
                # bug, while the retry feedback string keeps the original
                # error verbatim for the deploy crew.
                if is_transient(error_msg):
                    log.info(
                        "Transient network error on attempt %d/%d: %s. Retrying.",
                        attempt,
                        MAX_DEPLOY_RETRIES,
                        error_msg[:200],
                    )

                # Same escalation policy as the build retry loop: an
                # unrecoverable failure (provider rate-limit, expired key,
                # billing block) skips the remaining retries and surfaces
                # an explicit action for the operator.
                category = classify_error(error_msg)
                if category:
                    write_escalation(
                        category,
                        error_msg,
                        phase="deploy",
                        draft_id=self.state.draft_id,
                        cycle=self.state.cycle_count,
                        extra={"attempt": attempt, "slug": slug},
                    )
                    if self.state.draft_id:
                        try:
                            from sentinel_v2.dashboard_state import update_draft
                            update_draft(
                                self.state.draft_id,
                                status="blocked",
                                revision_notes=(
                                    f"[ESCALATED:{category}] Deploy halted on attempt {attempt}/"
                                    f"{MAX_DEPLOY_RETRIES}. Operator action required. "
                                    f"Last error: {error_msg[:500]}"
                                ),
                            )
                        except Exception as db_err:
                            log.warning("Could not mark draft blocked: %s", db_err)
                    self.state.error = f"escalated:{category}"
                    self._save_checkpoint()
                    log_event(_trace, "deploy_escalated", level="ERROR", metadata={"category": category, "attempt": attempt, "error": error_msg[:500]})
                    end_trace(_trace, output={"escalated": category}, level="ERROR")
                    return

                deploy_feedback = f"Deploy attempt {attempt} failed with error:\n{error_msg}\n\nFix the issues and retry."

                if attempt >= MAX_DEPLOY_RETRIES:
                    log.error("Deploy exhausted all %d retries", MAX_DEPLOY_RETRIES)
                    if self.state.draft_id:
                        try:
                            from sentinel_v2.dashboard_state import update_draft
                            update_draft(
                                self.state.draft_id,
                                status="failed",
                                revision_notes=f"Deploy failed after {MAX_DEPLOY_RETRIES} attempts. Last error: {error_msg}",
                            )
                        except Exception as db_err:
                            log.warning("Could not mark draft failed: %s", db_err)
                    self.state.error = error_msg
                    self._save_checkpoint()
                    return

                self._save_checkpoint()
                continue

            parsed = self._parse_deploy_result(result)

            # Check whether the QA verifier said GO or ROLLBACK
            raw_text = str(getattr(result, "raw", result)).upper()
            go_no_go = parsed.get("go_no_go", "").upper() if isinstance(parsed, dict) else ""
            is_go = go_no_go == "GO" or ("GO" in raw_text and "ROLLBACK" not in raw_text)

            if is_go:
                deploy_success = True
                break
            else:
                failing_step = parsed.get("failing_step", "unknown") if isinstance(parsed, dict) else "unknown"
                log.error("Deploy verification ROLLBACK (attempt %d): %s", attempt, failing_step)
                deploy_feedback = (
                    f"Deploy attempt {attempt} verification ROLLBACK. Failing step: {failing_step}.\n"
                    "Fix the deployment issues and retry."
                )

                if attempt >= MAX_DEPLOY_RETRIES:
                    log.error("Deploy exhausted all %d retries after ROLLBACK", MAX_DEPLOY_RETRIES)
                    self.state.error = f"Deploy verification failed: {failing_step}"
                    if self.state.draft_id:
                        from sentinel_v2.dashboard_state import update_draft
                        update_draft(
                            self.state.draft_id,
                            status="failed",
                            revision_notes=f"Deploy failed after {MAX_DEPLOY_RETRIES} attempts. Last: ROLLBACK on {failing_step}",
                        )
                    self._save_checkpoint()
                    return

                self._save_checkpoint()

        if not deploy_success:
            return

        reported_frontend_url = parsed.get("frontend_url") or parsed.get("url") if isinstance(parsed, dict) else None
        if not reported_frontend_url:
            log.error("Deploy crew returned no frontend_url -- marking as failed")
            self.state.error = "Deploy crew did not return a real frontend URL"
            if self.state.draft_id:
                from sentinel_v2.dashboard_state import update_draft
                update_draft(self.state.draft_id, status="failed",
                             revision_notes="Deploy failed: no frontend URL returned by deploy crew")
            self._save_checkpoint()
            return

        # Use the deterministic URL we pre-baked (not whatever the agent reported).
        # The QA verifier step inside the crew already curl'd it, so if we got
        # here without an early failure the URL resolves.
        backend_url_resolved = parsed.get("backend_url") or expected_backend_url

        # Stripe resources were provisioned BEFORE the crew kicked off and the
        # IDs/secret were passed to the crew as inputs to be staged with the
        # other Fly secrets in step 3, so the first Fly release boots with
        # stripe.config.ts validation passing. State fields already set above.
        self.state.deployed = True
        self.state.deployed_url = expected_frontend_url
        self.state.deployment_id = parsed.get("deployment_id")
        self.state.backend_url = backend_url_resolved
        self.state.fly_app_name = expected_backend_app_name
        self.state.cf_pages_project = expected_cf_project_name
        # Clear revision_notes so they don't bleed into the next cycle.
        self.state.revision_notes = None

        if self.state.draft_id:
            from sentinel_v2.dashboard_state import update_draft
            update_draft(
                self.state.draft_id,
                status="deployed",
                deployment_url=self.state.deployed_url,
                build_progress=1.0,
                stripe_product_id=self.state.stripe_product_id,
                stripe_price_id=self.state.stripe_price_id,
                stripe_webhook_endpoint_id=self.state.stripe_webhook_endpoint_id,
            )

        try:
            self.remember(
                f"Cycle #{self.state.cycle_count} deployed at {self.state.deployed_url}",
                scope="/sentinel/deployments",
            )
        except Exception as e:
            log.warning("Memory save failed: %s", e)

        self._touch()
        self._clear_checkpoint()
        log_event(_trace, "deploy_success", metadata={"url": self.state.deployed_url, "attempts": self.state.deploy_attempts})
        end_trace(_trace, output={"deployed_url": self.state.deployed_url, "attempts": self.state.deploy_attempts})

    # ─── Loop Router ─────────────────────────────────────────────────────

    @router(check_approval)
    def route_after_approval(self) -> str:
        """
        Router: after approval check, decide next step.
        - approved → deploy
        - revision → run_build (rebuild with feedback)
        - stop → stop
        """
        if self._shutdown_requested or not self.state.approved:
            return "stop"
        return "deploy"

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _get_operator_capacity(self) -> dict:
        """Execution constraints for the build crew. NOT a personal profile — what the
        agent swarm can ship, not who the operator is. Research/match must stay demand-driven.
        """
        return {
            "build_window_hours": 60,       # 1–2 week solo MVP ceiling
            "max_mvp_features": 8,
            "delivery_stack": {
                "frontend": "Next.js 14 App Router + TypeScript + Tailwind + Radix UI",
                "backend": "Next.js Route Handlers or NestJS; Prisma + PostgreSQL",
                "payments": "Stripe Checkout + webhooks (live from day 1)",
                "auth": "Supabase auth or NextAuth magic link",
                "hosting": "Vercel + Neon/Supabase Postgres",
                "telemetry": "PostHog or Plausible, Sentry for errors",
            },
            "pricing_range": {
                "saas_monthly_usd": [9, 299],
                "one_off_usd": [200, 2000],
            },
            "distribution_budget_usd_per_month": 200,
            "team_size": 1,
            "timezone": "Europe/Madrid",
            "locale_support": ["en", "es"],
        }

    def _get_trend_signals(self) -> list[dict]:
        """Optional seed of demand signals. Fetched from memory if present; empty list is
        valid — the research crew is expected to source signals itself."""
        try:
            matches = self.recall("demand signal", limit=8)
            if matches:
                return [{"source": "memory", "snippet": str(m)[:400]} for m in matches]
        except Exception as e:
            log.debug("Memory recall skipped: %s", e)
        return []

    def _parse_opportunities(self, result) -> list[dict]:
        """Accept list, JSON string (plain/fenced), or CrewOutput with .raw/.pydantic."""
        raw = self._extract_raw(result)
        parsed = self._coerce_json(raw)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            for key in ("opportunities", "top_opportunities", "items", "results"):
                if isinstance(parsed.get(key), list):
                    return [x for x in parsed[key] if isinstance(x, dict)]
            if "title" in parsed:
                return [parsed]
        return []

    def _parse_match_result(self, result) -> dict:
        raw = self._extract_raw(result)
        parsed = self._coerce_json(raw)
        return parsed if isinstance(parsed, dict) else {}

    def _parse_deploy_result(self, result) -> dict:
        """Best-effort dict view of a deploy or QA crew result.

        Preference order:
        1. ``result.pydantic`` is a ``QAGateReport`` (or any BaseModel): emit
           its ``model_dump()`` so the QA gate sees ``go_no_go`` and
           ``build_status`` even when the agent emitted prose alongside the
           structured object.
        2. Existing string-parse path: pull ``raw`` and coerce via JSON / fenced
           block / loose substring match. Empty dict on garbage so the QA gate
           fails closed (build_failed_qa_gate_unparseable).
        """
        from pydantic import BaseModel

        pydantic_obj = getattr(result, "pydantic", None)
        if isinstance(pydantic_obj, BaseModel):
            try:
                dumped = pydantic_obj.model_dump()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                pass
        if isinstance(result, BaseModel):
            try:
                dumped = result.model_dump()
                if isinstance(dumped, dict):
                    return dumped
            except Exception:
                pass

        raw = self._extract_raw(result)
        if isinstance(raw, dict):
            return raw
        parsed = self._coerce_json(raw)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _extract_metric(result, key: str):
        raw = SentinelLoopFlow._extract_raw(result)
        if isinstance(raw, dict) and key in raw:
            return raw[key]
        parsed = SentinelLoopFlow._coerce_json(raw)
        if isinstance(parsed, dict) and key in parsed:
            return parsed[key]
        pydantic = getattr(result, "pydantic", None)
        if pydantic is not None:
            value = getattr(pydantic, key, None)
            if value is not None:
                return value
        return None

    @staticmethod
    def _extract_raw(result):
        if result is None:
            return None
        if hasattr(result, "pydantic") and result.pydantic is not None:
            try:
                return result.pydantic.model_dump()
            except Exception:
                pass
        if hasattr(result, "json_dict") and result.json_dict is not None:
            return result.json_dict
        if hasattr(result, "raw"):
            return result.raw
        return result

    @staticmethod
    def _coerce_json(value):
        """Accept dict/list/str. For strings, try plain JSON, fenced ```json blocks,
        then a loose [...] / {...} substring match. Return best-effort parsed value or None."""
        import json
        import re

        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                return None

        s = value.strip()
        if not s:
            return None

        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

        fence = re.search(r"```(?:json)?\s*([\[{].*?[\]}])\s*```", s, re.DOTALL)
        if fence:
            try:
                return json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass

        for pattern in (r"\[[\s\S]*\]", r"\{[\s\S]*\}"):
            m = re.search(pattern, s)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    continue

        return None



# ── Entry Points ─────────────────────────────────────────────────────────────

def kickoff():
    """Run the Sentinel Loop once."""
    SentinelLoopFlow().kickoff()


def plot():
    """Visualize the Flow graph."""
    SentinelLoopFlow().plot()


if __name__ == "__main__":
    kickoff()
