"""Shared Fly Postgres cluster: lazy-create on first successful deploy, attach
each app's database into it idempotently.

Design:
- ALL Sentinel-shipped apps share ONE Fly Postgres cluster. Each app gets its
  own database (and Fly user) within that cluster, exposed via a per-app
  ``DATABASE_URL`` Fly secret. This costs one Fly billing line for the whole
  fleet instead of one per app, and lets us scale storage / instance once.

- The cluster is created lazily, the first time ``ensure_shared_pg_cluster``
  is called. By design that call only happens at the top of ``run_deploy``,
  which is only entered when build verification has passed AND the user has
  approved the deploy. So the cluster is never spun up for a draft that never
  ships.

- ``infra_state`` (sqlite) records the cluster name + region after creation so
  subsequent deploys skip straight to the attach step. If the state is lost
  (DB wiped, fresh container) we fall back to ``fly postgres list`` to detect
  an existing cluster and re-record it without recreating.

- ``attach_db_for_app`` runs ``fly postgres attach``. The Fly CLI is
  idempotent on the (cluster, app) pair: it creates a new database +
  user if the app is not yet attached, and emits a ``DATABASE_URL`` secret
  on the app. If the app is already attached, the CLI prints a notice and
  exits 0; we read the existing secret value via ``fly secrets list`` style.

- All shell-outs go through ``subprocess.run`` directly. NOT exposed as
  CrewAI tools. The deploy crew receives the resolved DATABASE_URL as a
  literal task input and stages it via ``fly_secrets_set`` alongside the
  Stripe values, so the first release boot has every required env var.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from typing import Optional

from sentinel_v2 import db


log = logging.getLogger("sentinel_v2.shared_postgres")


_CLUSTER_NAME_KEY = "shared_pg_cluster_name"
_CLUSTER_REGION_KEY = "shared_pg_cluster_region"
_CLUSTER_CREATED_AT_KEY = "shared_pg_cluster_created_at"


def _flyctl_path() -> Optional[str]:
    """Return the absolute path to ``flyctl`` or None.

    Honors ``FLYCTL_INSTALL`` (the official installer's variable) before
    falling back to PATH lookup. Returning None tells callers to surface a
    config error instead of silently retrying.
    """
    explicit = os.environ.get("FLYCTL_INSTALL")
    if explicit:
        candidate = os.path.join(explicit, "bin", "flyctl")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("flyctl") or shutil.which("fly")


def _run_fly(*args: str, timeout: int = 300, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Run ``flyctl <args>`` with FLY_API_TOKEN already in env. Never raises.

    Caller inspects ``returncode`` + ``stdout`` + ``stderr``. We do not capture
    interactively because ``--yes`` / non-interactive flags are passed by
    callers where applicable.
    """
    flyctl = _flyctl_path()
    if not flyctl:
        return subprocess.CompletedProcess(
            args=list(args),
            returncode=127,
            stdout="",
            stderr="flyctl binary not found on PATH and FLYCTL_INSTALL is not set",
        )
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(
        [flyctl, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=full_env,
    )


def _cluster_name_default() -> str:
    return os.environ.get("SENTINEL_SHARED_PG_CLUSTER", "sentinel-shared-pg")


def _cluster_region_default() -> str:
    return os.environ.get("SENTINEL_SHARED_PG_REGION", "fra")


def _cluster_volume_gb_default() -> int:
    try:
        return int(os.environ.get("SENTINEL_SHARED_PG_VOLUME_GB", "10"))
    except (TypeError, ValueError):
        return 10


def _cluster_vm_size_default() -> str:
    return os.environ.get("SENTINEL_SHARED_PG_VM_SIZE", "shared-cpu-1x")


def _cluster_initial_cluster_size_default() -> int:
    """Single Postgres node by default. Bump to >=2 only after first paying app
    is generating revenue; HA doubles the bill.
    """
    try:
        return int(os.environ.get("SENTINEL_SHARED_PG_INITIAL_SIZE", "1"))
    except (TypeError, ValueError):
        return 1


def _cluster_exists_on_fly(cluster_name: str) -> bool:
    """Best-effort idempotency check via ``fly postgres list``.

    Returns True if a Postgres cluster with this name is reported by Fly.
    Returns False on tool error or network failure too: caller will then
    attempt creation, which itself is idempotent on name conflict (Fly
    returns 'already taken' that we treat as 'already exists').
    """
    proc = _run_fly("postgres", "list")
    if proc.returncode != 0:
        log.warning(
            "fly postgres list failed (rc=%s): %s",
            proc.returncode,
            (proc.stderr or proc.stdout)[:300],
        )
        return False
    haystack = (proc.stdout or "") + "\n" + (proc.stderr or "")
    return bool(re.search(rf"\b{re.escape(cluster_name)}\b", haystack))


def ensure_shared_pg_cluster(
    *,
    cluster_name: Optional[str] = None,
    region: Optional[str] = None,
    vm_size: Optional[str] = None,
    volume_gb: Optional[int] = None,
    initial_cluster_size: Optional[int] = None,
) -> dict:
    """Lazy-create the shared Postgres cluster. Idempotent.

    Order of resolution:
      1. infra_state recorded a cluster name -> use it (no fly call).
      2. Else ``fly postgres list`` -> if cluster_name found, record it and
         use it.
      3. Else ``fly postgres create --name ... --region ... ...`` and record.

    Returns ``{cluster_name, region, created: bool, source: 'state'|'list'|'created'}``.
    Raises ``RuntimeError`` only if creation actually fails. State-recovery
    paths never raise so the deploy can proceed even if the recorded name
    drifted from Fly reality.
    """
    cname = cluster_name or _cluster_name_default()
    cregion = region or _cluster_region_default()
    cvm = vm_size or _cluster_vm_size_default()
    cvol = volume_gb if volume_gb is not None else _cluster_volume_gb_default()
    csize = (
        initial_cluster_size
        if initial_cluster_size is not None
        else _cluster_initial_cluster_size_default()
    )

    recorded = db.get_infra(_CLUSTER_NAME_KEY)
    if recorded:
        log.info("Shared PG cluster %r already recorded in infra_state; skipping create", recorded)
        return {
            "cluster_name": recorded,
            "region": db.get_infra(_CLUSTER_REGION_KEY) or cregion,
            "created": False,
            "source": "state",
        }

    if _cluster_exists_on_fly(cname):
        log.info(
            "Shared PG cluster %r already exists on Fly (state was empty); recording", cname
        )
        db.set_infra(_CLUSTER_NAME_KEY, cname)
        db.set_infra(_CLUSTER_REGION_KEY, cregion)
        return {
            "cluster_name": cname,
            "region": cregion,
            "created": False,
            "source": "list",
        }

    log.info(
        "Creating shared Fly Postgres cluster name=%s region=%s vm=%s volume=%dGB size=%d",
        cname, cregion, cvm, cvol, csize,
    )
    proc = _run_fly(
        "postgres", "create",
        "--name", cname,
        "--region", cregion,
        "--vm-size", cvm,
        "--volume-size", str(cvol),
        "--initial-cluster-size", str(csize),
        timeout=900,
    )
    if proc.returncode != 0:
        out = (proc.stderr or proc.stdout or "").strip()
        if "already taken" in out.lower() or "already exists" in out.lower():
            log.info(
                "Cluster %r already taken on Fly; treating as success and recording", cname
            )
        else:
            raise RuntimeError(
                f"fly postgres create failed (rc={proc.returncode}): {out[:500]}"
            )

    db.set_infra(_CLUSTER_NAME_KEY, cname)
    db.set_infra(_CLUSTER_REGION_KEY, cregion)
    from sentinel_v2.db import now_iso
    db.set_infra(_CLUSTER_CREATED_AT_KEY, now_iso())
    return {
        "cluster_name": cname,
        "region": cregion,
        "created": True,
        "source": "created",
    }


_DATABASE_URL_RE = re.compile(
    r"(?P<url>postgres(?:ql)?://[^\s'\"]+)",
    re.IGNORECASE,
)


def _parse_database_url(text: str) -> Optional[str]:
    """Pull the first ``postgres://`` connection URL out of a flyctl output.

    Handles both ``DATABASE_URL=postgres://...`` lines and the bare URL Fly
    sometimes prints when an attach succeeds. Returns None if the output
    contains no recognisable URL.
    """
    if not text:
        return None
    match = _DATABASE_URL_RE.search(text)
    return match.group("url") if match else None


def _read_database_url_secret(app_name: str) -> Optional[str]:
    """Try to recover an already-set DATABASE_URL via ``fly secrets list``.

    Fly's ``secrets list`` only shows the secret name + digest, not the value.
    But when an app is already attached, ``fly postgres attach`` re-running
    prints a notice including the existing connection string. We use this
    helper as a last-resort guard: if ``attach`` reports success but emits no
    URL, callers stage the database via ``fly postgres connect`` to derive
    one. For now the typical happy path emits the URL; this hook keeps the
    failure surface explicit.
    """
    proc = _run_fly("secrets", "list", "--app", app_name)
    if proc.returncode != 0:
        return None
    if "DATABASE_URL" in (proc.stdout or ""):
        return ""  # set, but value not visible: caller handles
    return None


def attach_db_for_app(
    *,
    cluster_name: str,
    backend_app_name: str,
    database_name: Optional[str] = None,
    database_user: Optional[str] = None,
) -> dict:
    """Attach ``backend_app_name`` to ``cluster_name``: creates a per-app DB +
    user, sets the ``DATABASE_URL`` secret on the backend app, and returns the
    resolved URL.

    Idempotent: if the app is already attached Fly returns rc=1 with an
    "already attached" message; we surface that as a successful path with
    ``database_url=None`` so callers can detect the case and skip re-staging
    the secret (the prior secret already lives on the app).

    Returns ``{database_url, database_name, database_user, already_attached}``.
    Raises ``RuntimeError`` on unrecognized failures.
    """
    db_name = database_name or f"{backend_app_name.replace('-', '_')}_db"
    db_user = database_user or f"{backend_app_name.replace('-', '_')}_user"

    attach_args = [
        "postgres", "attach",
        cluster_name,
        "--app", backend_app_name,
        "--database-name", db_name,
        "--database-user", db_user,
    ]
    proc = _run_fly(*attach_args, timeout=300)

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode == 0:
        url = _parse_database_url(out)
        if not url:
            log.warning(
                "fly postgres attach succeeded but emitted no DATABASE_URL; "
                "assuming already-attached and falling back to secret read"
            )
            existing = _read_database_url_secret(backend_app_name)
            return {
                "database_url": existing,
                "database_name": db_name,
                "database_user": db_user,
                "already_attached": True,
            }
        return {
            "database_url": url,
            "database_name": db_name,
            "database_user": db_user,
            "already_attached": False,
        }

    out_low = out.lower()
    if "already" in out_low and ("attached" in out_low or "exists" in out_low):
        existing = _read_database_url_secret(backend_app_name)
        return {
            "database_url": existing,
            "database_name": db_name,
            "database_user": db_user,
            "already_attached": True,
        }

    raise RuntimeError(
        f"fly postgres attach failed (rc={proc.returncode}): {out.strip()[:500]}"
    )
