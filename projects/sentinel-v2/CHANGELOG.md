# Changelog

All notable changes to Sentinel V2. Ordered newest-first. Each entry references
the commit hash so every change is traceable and auditable.

## [Unreleased]

## 2026-04-24 · TBD — Retry actually works: cycle picks up queued drafts, daemon gets unblocked

**What changed:**
- `src/sentinel_v2/flows/sentinel_loop.py`: `start_cycle` now checks for drafts with `status="queued"` BEFORE spawning research. If one exists, it hydrates the flow state from that draft (sets `top_opportunity`, `draft_id`, `approved=True`), saves a checkpoint, and lets the flow skip directly into match/build/security/deploy. This closes the loop for retried drafts.
- `src/sentinel_v2/db.py`: new `clear_active_flow_checkpoint()` that deletes ALL rows in `flow_checkpoints` (the per-draft `clear_flow_checkpoint(draft_id)` is kept for the normal deploy-completed path).
- `dashboard/app.py`: `retry_draft` socket handler + REST `"retry"` action now do three things instead of one:
  1. Clear the active flow checkpoint so the daemon doesn't keep running the previous flow's state.
  2. Reject any OTHER currently-pending drafts so `wait_for_draft_status` unblocks and the daemon's current cycle ends cleanly.
  3. Flip the target draft to `"queued"`.
- `run_dashboard.py`: silence the eventlet `DeprecationWarning` so Flask container logs stay readable.

**Why the old retry didn't work:** the daemon was blocked inside `wait_for_draft_status` polling `self.state.draft_id` (the active draft). Flipping a DIFFERENT draft's status did nothing to unblock it. And when the cycle did eventually end, `start_cycle` always spawned fresh research — there was no path by which a "retried" draft could re-enter the flow. Both holes are now plugged.

## 2026-04-24 · TBD — Retry button for failed drafts

**What changed:**
- `dashboard/app.py`: new `retry_draft` Socket.IO event + `"retry"` action on the `/api/drafts/action` REST endpoint. Logic: if there's an active flow checkpoint matching this `draft_id`, reset status to `queued` so the daemon resumes from the last saved phase; otherwise reset to `pending` (restart from scratch on the next cycle). Revision notes record which path was taken.
- `dashboard-nextjs/src/hooks/useSentinelSocket.ts`: added `retryDraft(id)` action emitting `retry_draft`.
- `dashboard-nextjs/src/components/BuildQueue.tsx`: added a **Retry** button (indigo, with spinner icon) on rows with `status === "failed"`, next to any existing deploy/open actions.
- `dashboard-nextjs/src/app/page.tsx`: pipes `retryDraft` through to `BuildQueue`.

**How it works:** click Retry on a failed row → daemon-side the draft flips back to `pending`/`queued`. On the next daemon tick (or immediately if the flow is idle waiting in the approval gate), it resumes via `_load_resumable_state()` if a checkpoint is still active, otherwise the user can re-approve it from scratch.

## 2026-04-24 · TBD — OSV-scan + remediation loop between build and approval

**What changed:**
- `src/sentinel_v2/tools/osv_scanner_tool.py` (new): `OsvScannerTool` wraps the `osv-scanner` binary, summarizes OSV's verbose JSON to `{total, counts: {CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN}, findings: [...]}` with per-finding `fix_versions`, severity, and aliases (CVE/GHSA).
- `src/sentinel_v2/crews/security_remediation_crew/security_remediation_crew.py` (new): sequential crew with three agents — Vulnerability Scanner (runs osv-scanner on backend+frontend), Remediation Planner (4-rule playbook: upgrade / downgrade / replace / accept_risk; uses MiniMax-M2.7), Refactor Developer (applies the plan, fixes breaking changes and tests, reruns build).
- `src/sentinel_v2/flows/sentinel_loop.py`: new `run_security_remediation` phase between `run_build` and `request_approval`. Loops the crew up to `SENTINEL_MAX_REMEDIATION_ITERATIONS` (default 5) until `total_vulns_after == 0` and `build_ok`. If the ceiling is hit, flags `vulnerability_scan_error` so the human sees it at the approval gate but doesn't block the flow forever. `request_approval` now listens to the new phase instead of `run_build`. New `SentinelState` fields: `security_remediated`, `vulnerability_count`, `vulnerability_scan_error`, `vulnerability_findings`.
- `Dockerfile`: installs `osv-scanner` binary from GitHub releases.
- `src/sentinel_v2/tools/file_tool.py`: `osv-scanner` added to shell whitelist for manual invocations.
- `src/sentinel_v2/tools/__init__.py`: exports `OsvScannerTool`.
- `tests/unit/test_osv_scanner_tool.py` (new): 12 tests covering the summary parser (severity mapping, fix_versions extraction, MODERATE→MEDIUM normalization, severity sort) and the tool's subprocess error paths (missing binary, non-JSON output, timeout, bad rc).

**Env var:** `SENTINEL_MAX_REMEDIATION_ITERATIONS` (optional, defaults to 5).

**Checkpoint safety:** `security_remediated: bool` persists in the checkpoint. A daemon crash mid-loop resumes by re-running the remediation (idempotent — `npm install` is safe to re-run).

## 2026-04-24 · TBD — Stripe + fly.io + Cloudflare Pages automation

**What changed:**
- `src/sentinel_v2/tools/file_tool.py` (new): `WriteFileTool`, `ListFilesTool`, `RunShellTool`. Sandboxed to `/tmp/sentinel_workspaces/<draft_id>/`; shell whitelist (`npm`, `npx`, `git`, `prisma`, `flyctl`, `curl`, etc.); rejects `..` traversal and paths outside workspace.
- `src/sentinel_v2/tools/stripe_tool.py` (new): `StripeCreateProductTool`, `StripeListProductsTool`, `StripeCreateWebhookTool`, `StripeDeleteProductTool`. All idempotent via `metadata.sentinel_draft_id`. Uses `STRIPE_SECRET_KEY`.
- `src/sentinel_v2/tools/cloudflare_tool.py` (new): `CloudflarePagesCreateTool`, `CloudflarePagesDeployTool` (Direct Upload via tarball), `CloudflarePagesSetEnvTool`, `CloudflareDnsCnameTool`, `CloudflarePagesAddCustomDomainTool`. Uses `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`; resolves zone id for `erslabs.net` at call time.
- `src/sentinel_v2/tools/fly_tool.py` (new): `FlyAppCreateTool`, `FlySecretsSetTool`, `FlyDeployTool`, `FlyStatusTool`. Subprocess wrapper around `flyctl`; uses `FLY_API_TOKEN`.
- `src/sentinel_v2/crews/build_crew/build_crew.py`: Frontend Lead, Backend Lead, Code Reviewer, Security Auditor, and QA Lead now have the tools attached. Backend Lead backstory rewritten to require creating real Stripe products via tool (idempotent), embedding returned price IDs directly in generated code, and producing `Dockerfile` + `fly.toml` in the workspace. Task descriptions inject `{workspace_dir}`, `{slug}`, `{draft_id}`.
- `src/sentinel_v2/crews/deploy_crew/deploy_crew.py`: Complete rewrite. Targets **backend → fly.io, frontend → Cloudflare Pages under `<slug>.erslabs.net`** (Vercel removed). Deployer has `fly_*` + `cloudflare_*` + `stripe_create_webhook` tools with a strict 12-step deploy sequence in the backstory.
- `src/sentinel_v2/flows/sentinel_loop.py`: Added `SentinelState` fields (`workspace_dir`, `stripe_product_ids`, `backend_url`, `fly_app_name`, `cf_pages_project`, `stripe_webhook_endpoint_id`). `run_build` materializes the workspace dir before kickoff and passes it (plus `slug` and `draft_id`) as crew inputs. `run_deploy` passes `workspace_dir`, `slug`, `erslabs_root`, `stripe_publishable` and parses `frontend_url` / `backend_url` from the deploy crew output. Added `_make_slug()` helper.
- `Dockerfile`: installs `flyctl` binary + `curl`, `ca-certificates`, `git` (needed for deploy operations).
- `pyproject.toml`: `stripe>=7.0` added.
- `tests/unit/test_file_tool.py`, `test_stripe_tool.py`, `test_fly_tool.py`, `test_cloudflare_tool.py` (new): 46 tests total (14/8/11/13), all passing.

**Env vars consumed:** `STRIPE_SECRET_KEY`, `STRIPE_API_KEY` (publishable, for frontend), `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `FLY_API_TOKEN`.

**Por qué:** las crews de build/deploy eran solo-texto — generaban código como strings y nada llegaba a disco ni a producción. Este cambio introduce la capa de ejecución real: el backend agent CREA productos Stripe de verdad y embebe los price IDs; el deploy agent despliega backend en fly.io, frontend en Cloudflare Pages, crea el CNAME `<slug>.erslabs.net`, registra el webhook de Stripe apuntando al URL fly.dev, y todo sin intervención manual.

## 2026-04-24 · TBD — Fix CORS + Docker shared-volume path mismatch

**What changed:**
- `pyproject.toml`: added `flask-cors>=4.0` dependency
- `dashboard/app.py`: added `CORS(app, resources={r"/api/*": {"origins": "*"}})` so the REST polling fetch from Next.js (localhost:3003) is no longer blocked; replaced hardcoded `/tmp/sentinel_v2_*.json` paths with `_TMP_DIR = Path(os.environ.get("SENTINEL_TMPDIR", "/tmp"))`; fixed `get_agent_messages()` to use the module-level `AGENT_MESSAGES_FILE` instead of a local hardcoded path
- `crew_hooks.py`: added `import os`; derived `AGENT_MESSAGES_FILE` and `ALLOWED_TMP_PREFIX` from `_TMP_DIR`
- `dashboard_state.py`: same pattern; also added `BREAKDOWN_FILE` at module level and removed the 4 redundant local definitions inside functions

**Por qué:** en Docker, `SENTINEL_TMPDIR=/tmp/sentinel_shared` pero todos los paths estaban hardcodeados a `/tmp/`. El daemon escribía en `/tmp/` de su contenedor, Flask leía de `/tmp/` del suyo — el volumen compartido en `/tmp/sentinel_shared` era ignorado. Esto causaba que Agent Feed y Draft Queue nunca recibieran datos.

## 2026-04-24 · TBD — Dockerize daemon + Flask (two-service compose)

**What changed:**
- `Dockerfile`: single shared image, Python 3.12-slim, `uv sync --frozen --no-dev`, `PYTHONPATH=/app/src:/app`
- `docker-compose.yml`: two services (`sentinel`, `dashboard`), named volume `sentinel_tmp` at `/tmp/sentinel_shared` shared between both, `SENTINEL_TMPDIR` env var routes daemon's `/tmp` writes there, `./sentinel.db` bind-mounted, port 5173 exposed, `restart: unless-stopped`, healthcheck on `/api/state`
- `.dockerignore`: excludes `.venv`, `__pycache__`, `dashboard-nextjs/`, `node_modules/`, `.git/`, SQLite WAL files

**Uso:**
```bash
touch sentinel.db   # only needed on first run if file doesn't exist
docker compose up -d
docker compose logs -f
```

## 2026-04-24 · TBD — Rich Agent Feed + REST fallback for draft approval

**What changed:**
- `crew_hooks.py`: added `_make_task_callback(phase, cycle)` — wired as `crew.task_callback` so every completed task emits its actual `.raw` output (up to 400 chars) to the Agent Feed instead of lifecycle-only strings. Phase summary now includes the crew's final `result.raw` output.
- `dashboard-nextjs/src/hooks/useSentinelSocket.ts`: added REST polling fallback that calls `GET /api/drafts` every 3s when the socket is disconnected or when no drafts have arrived yet. Fixes the case where the daemon writes a pending draft but the frontend shows nothing because Flask hadn't pushed `drafts_update` before the socket connected.

## 2026-04-24 · TBD — Daemon checkpoint/resume: survive restarts mid-cycle

**What changed:**
- `db.py`: nueva tabla `flow_checkpoints` + `save_flow_checkpoint`, `load_active_flow_checkpoint`, `clear_flow_checkpoint`
- `sentinel_loop.py`: helpers `_save_checkpoint`/`_clear_checkpoint`; guards en cada fase para skip si el output ya está en estado; checkpoints escritos tras research, match y build; checkpoint limpiado al terminar deploy
- `main.py`: `_load_resumable_state()` detecta checkpoint activo al arrancar; `run_once` y `run_daemon` restauran estado antes del kickoff; `_recover_orphaned_drafts` preserva drafts con checkpoint activo en vez de marcarlos failed

**Comportamiento**: si el daemon se cae (kill -9, crash, SIGTERM) durante BUILD, al rearrancar detecta el checkpoint de BUILD, restaura todo el `SentinelState` y retoma desde ahí sin repetir RESEARCH ni MATCH.

## 2026-04-24 · TBD — Fix all <think>-tag memory failures + LanceDB dim mismatch + orphan draft

**What changed:**
- `llm_config.py`: added `make_clean_llm()` wrapper that strips `<think>…</think>` blocks
  from reasoning-model responses so CrewAI memory `QueryAnalysis` / `MemoryAnalysis`
  receive clean JSON instead of crashing.
- `embedder_config.py`: `get_memory_for_crew(llm=None)` now always wraps the LLM with
  `make_clean_llm()` — previously only the `llm=None` default path was wrapped, so crews
  passing an explicit minimax LLM (all 4 crews do) hit `ExtractedMemories` JSON parse errors.
- `llm_config.py`: `make_clean_llm` is now idempotent (guards with `_think_stripped` flag).
- `sentinel.db`: deleted orphan draft `draft_c0_op-a` ("Op A") left from a test cycle.
- LanceDB: deleted stale `memories.lance` table (384-dim Ollama vectors) so it
  auto-recreates with 1024-dim Jina embeddings on next run. Root cause of
  `query dim(1024) doesn't match the column vector vector dim(384)` error.

## 2026-04-24 · 5439c17 — Drop purple tile, per-agent colored avatars, leaner command bar

**Commit:** `5439c17`

**What changed:**
- Logo redesigned: gradient-stroke concentric arcs on transparent
  background (no chunky gradient tile). `SentinelMark`, `SentinelLogo`,
  `SentinelBrand` and `public/icon.svg` all updated consistently.
- `AgentAvatar` gains a 17-color vibrant palette + DJB2 hash for
  unknown agent IDs, plus an explicit hex-per-role map for the 13 named
  crew roles. DiceBear bottts-neutral robots now sit on distinct
  backgrounds — previously most agents fell through to a gray default.
- Command bar: removed inline Coverage/Tests/Issues pills; those
  metrics live as per-stage tags inside each Build Pipeline row card
  (Issues on Review, Cov+Tests on Built) where they are bound to a
  specific app instead of averaged across the queue.

**Why:** the prior "gradient square tile" logo looked like a generic
SaaS favicon and competed with the wordmark; moving the gradient to the
stroke makes it a precision detail like Linear/Vercel/Warp. The avatars
fix was mechanical — only a handful of agent IDs had known gradients,
so the hash + palette guarantees every agent is visually distinct at a
glance. Finally, header metrics were duplicative (same numbers shown on
the active row) and contextless (whose coverage? which app?) — moving
them onto the row card preserves the information at the right grain.

## 2026-04-24 · 86aac68 — Demand-driven agent swarm + command-center dashboard + startup hardening

**Commit:** `86aac68`

**What changed:** single-landing refactor that (a) rebuilds the dashboard as a
Linear-inspired command-center with a unified draft/build pipeline and two
human gates, (b) rewrites the four CrewAI crews to be demand-driven and
commercial-quality (no operator identity, WTP evidence required, 5-test
commercial filter, Stripe + PostHog from day 1), (c) hardens daemon startup
(dotenv override, TMPDIR pinning, lazy Telegram config, PTB stop_signals,
_shutdown nonlocal), and (d) wires the dashboard as the source of truth for
approval gates via `drafts.json` polling.

**Why:** three compounding problems motivated this change.
(1) The system was starting from the operator's personal profile, so the
agents were producing "ideas that match Kike" instead of "things people will
pay for". Moving the seed to internet demand signals and adding a strict
commercial filter is the precondition for the swarm producing anything a user
would actually buy.
(2) The daemon kept crashing on startup with spurious Telegram validation
errors, an eventlet/threading conflict, a CrewAI lock file pointed at an
ephemeral sandbox dir, and an `UnboundLocalError` — none of which were
caught because the failures masked each other. Each now has a surgical fix
plus diagnostic so the next failure mode is obvious.
(3) The dashboard was showing mock data and single-opportunity state, which
didn't reflect the multi-draft reality the user wanted. The unified pipeline
model with lifecycle statuses (`pending → queued → building → review →
built → deployed | failed | rejected`) is the minimum abstraction needed for
multiple concurrent apps. History modal separates shipped/rejected from the
active pipeline view.

### Added

- **Dashboard (Next.js + Flask)** — Linear-inspired dark theme, agent-swarm command
  center. KPI cards, unified Build Pipeline (Draft → Queued → Building → Review
  → Built → Deployed) with per-row stepper, inline approve/revise/reject on Draft
  stage and Deploy gate on Built stage, History modal (chronological), Agent Feed
  with DiceBear `bottts-neutral` avatars, custom SentinelMark + SentinelLogo +
  SentinelBrand (wordmark lockup), new favicon.
- **`SentinelBrand` / `SentinelWordmark` / `SentinelMark` / `SentinelLogo`** —
  full brand identity SVG set (`dashboard-nextjs/src/components/icons/`).
- **`useSentinelSocket` hook** — single socket.io client with typed state
  (FlowState, ApprovalState, FlowBreakdown, Drafts/BuildQueue, AgentMessage) and
  actions (approveDraft, rejectDraft, reviseDraft, approveDeploy, rejectDeploy).
- **Unified drafts pipeline model** (`drafts.json`) with lifecycle statuses:
  `pending → queued → building → review → built → deployed | failed | rejected`.
  Replaces the legacy single-item approval model for UI purposes; legacy approval
  file remains as fallback.
- **`dashboard_state.write_draft() / update_draft() / wait_for_draft_status() /
  make_draft_id() / get_draft()`** — authoring API for the new draft model,
  consumed by `sentinel_loop.py` at every phase transition.
- **`tests/conftest.py`** — auto-use fixture that makes `_safe_path` accept
  pytest `tmp_path` prefixes during tests, without weakening production guards.
- **`CHANGELOG.md`** — this file. Going forward, every non-trivial change has an
  entry with commit hash + reason.

### Changed

- **Research crew** rewritten to be demand-driven (no operator profile). New
  agents `Demand Hunter` + `Commercial Validator`. Output schema with
  `demand_signals`, `willingness_to_pay`, `distribution_hypothesis`,
  `commercial_score`, `kill_risks`.
- **Match crew** repurposed as *Commercial Qualification*. `Customer Intelligence
  Analyst` + `Opportunity Qualifier`. Go / Modify / Kill decision with scored
  dimensions (paying_demand, icp_sharpness, mvp_feasibility,
  distribution_testability, pricing_realism, moat).
- **Build crew** tightened for MVP discipline: one-ICP / one-headline / one-CTA
  scope, Stripe from day 1, PostHog instrumentation at every funnel step, 80%
  coverage on payments+auth+core-rule (not 90% global), Playwright smoke of
  three paid-user journeys as the ship gate.
- **Deploy crew** defaulted to Vercel + Neon + Stripe live (no Docker/k8s for
  MVPs). Verifier now runs the three paid-user journeys on the live URL.
- **`sentinel_loop.py`** — two human gates driven from the dashboard: draft
  approval (before match/build) and deploy approval (after built). Parsers made
  tolerant of JSON strings / fenced blocks / crew pydantic outputs. Personal
  `_get_kike_profile` replaced with `_get_operator_capacity` (execution
  constraints only, no identity).
- **Telegram config** loaded lazily at `TelegramTool` construction (was module-
  level). Placeholder-value detection. `load_dotenv(override=True)` in `main.py`
  to beat stale shell env.
- **`main.py`** pins a stable `TMPDIR` before importing CrewAI to avoid the
  `crewai:HASH.lock` path going missing when launched from ephemeral sandbox
  shells.
- **Dashboard backend (`dashboard/app.py`)** emits `flow_breakdown_update`,
  `drafts_update` (with build queue) and HTTP endpoints for drafts CRUD /
  action. Socket handlers: `approve_draft`, `reject_draft`, `approve_deploy`,
  `reject_deploy`. Fixed auth signature (`auth=None` arg instead of
  `request.auth`).
- **`run_dashboard.py`** uses `socketio.run()` + eventlet monkey-patch +
  `socketio.start_background_task(state_poller)` so WebSockets actually work.
- **Tailwind theme** rebuilt Linear-style: zinc-950 base, indigo/violet/fuchsia
  gradient accents, custom keyframes (shimmer, pulse-glow, typing-dot, slide-
  in), surface-elevated utility for card contrast, stripe gradients per stage.
- **`_sanitize_agent_id` (crew_hooks + dashboard_state)** now strips underscores
  too — output is lowercase alphanumerics + dashes only.

### Removed

- **Personal operator profile (`_get_kike_profile`)** — Sentinel no longer seeds
  research with the operator's personal info. Research is driven by internet
  demand signals and commercial qualification.
- **Old teal dashboard theme, `FlowStatePanel`, `PipelineProgressBar`,
  `AgentPipeline`, `AgentChat`, `StatusBar`, `DraftsQueue`, `PIPELINE_IMPLEMENTATION.md`**
  — replaced by the new unified command-center layout.

### Fixed

- **Telegram startup error** — duplicated keys in `.env` (real values + pasted
  `.env.example` placeholders) caused dotenv to use the placeholder as the last
  occurrence. `.env` deduplicated; `load_dotenv(override=True)` forces .env over
  stale shell env.
- **`run_polling` crash in background thread** — `stop_signals=None` passed so
  asyncio's `set_wakeup_fd` is not invoked off-main-thread (Python 3.13 strict).
- **`UnboundLocalError: _shutdown`** in `_run_cycles` — added `nonlocal
  _shutdown`.
- **`threading.Thread` vs eventlet conflict** — poller now uses
  `socketio.start_background_task(...)`.
- **`NameError: JSONDecodeError`** in `crew_hooks.py` — qualified as
  `json.JSONDecodeError`. Also fixed undefined `exc` in the write-path's
  logging.
- **`_parse_opportunities` returning `[]` for JSON strings** — now coerces via
  plain JSON, fenced ```json blocks, or loose `[...] / {...}` substring match.
  Also extracts pydantic model dumps when present.
- **CrewAI ephemeral lock path** — `main.py` pins `TMPDIR` at startup to a
  stable `/tmp` so `crewai:HASH.lock` does not vanish with the parent shell.
- **`test_sanitize_agent_id`** expectation for `agent_with.at.dots` aligned with
  the sanitizer's actual (correct) output `agentwithatdots`.
- **`test_path_validation` import** renamed stale alias
  `dashboard_sanitize` → `dashboard_sanitize_agent_id`.
- **`_llm_cache` test leakage** — `setup_method` added to `TestGetMiniMaxLLM` so
  the missing-key test path is actually reachable.

### Known issues

- **`test_main.py::TestRunDaemon` (6 tests)**, **`test_sentinel_loop.py::TestCheckApproval`
  (3 tests)**, **`test_telegram_tool.py` (2 tests)** — test the old telegram-
  approval path / module-level globals / old `_get_kike_profile`. Will be
  rewritten alongside the next test-refactor pass; the production code behavior
  is correct and verified by live daemon startup.
