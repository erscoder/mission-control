# Changelog

All notable changes to Sentinel V2. Ordered newest-first. Each entry references
the commit hash so every change is traceable and auditable.

## [Unreleased]

## 2026-04-26 · 7d2ec27 — Fix CSS purging in ErsLabs landing

- Dynamic Tailwind class interpolation (`bg-${accent}/10`) invisible to JIT scanner. Replaced with explicit pre-composed class strings in `HowItWorks.tsx`.

## 2026-04-26 · d8b050a — Redesign ErsLabs landing — dark theme with agent pipeline showcase

- Complete visual overhaul: void-black canvas, emerald accent (#10B981), terminal-native aesthetic.
- New **Pipeline** section showcasing 6 named agents (Nova, Atlas, Echo, Forge, Sentinel, Hermes) with gradient icons and phase badges.
- New **CaseStudy** section: ComplianceDesk end-to-end story from Reddit discovery to live deploy in 3h49m.
- Enhanced Hero with terminal preview, status badge, and radial glows.
- Custom Tailwind theme: surface palette, accent colors, animations (float, glow, scan-line, slide-up).
- CSS utilities: `.text-gradient`, `.border-glow`, `.card-shine`, `.grid-bg`, `.noise`, `.pipeline-flow`.

## 2026-04-26 · 54ed188 — Process queued drafts continuously

- Daemon loop now checks for remaining queued drafts after each cycle. If any exist, starts the next cycle immediately instead of sleeping `SENTINEL_LOOP_INTERVAL_HOURS`. Only sleeps when the queue is empty.

## 2026-04-26 · 86dcb35 — Automatic retry loop for build/deploy + error display

- **Build retry loop**: on crew failure, feeds the error back as `revision_notes` and re-runs the build crew (up to `SENTINEL_MAX_BUILD_RETRIES`, default 3). Dashboard shows `[Auto-retry N/M]` status.
- **Deploy retry loop**: on crew exception or QA ROLLBACK, feeds the failing step back to the deploy crew and retries (up to `SENTINEL_MAX_DEPLOY_RETRIES`, default 2).
- **Error visibility**: failed pipeline cards now show `revision_notes` (error reason) always visible below the title in a red mono-font banner — no need to expand the card.
- State model: added `build_attempts` and `deploy_attempts` counters to `SentinelState`.
- Deploy crew: added `deploy_feedback` input to `deploy_task` description for retry context.
- 5 new unit tests covering retry success, retry exhaustion, and first-attempt success paths.

## 2026-04-26 · 43a4959 — Deploy templates for build crew

- Added proven Dockerfile + fly.toml templates for three stacks: **Python/FastAPI**, **Node/NestJS**, **Rust/Axum**.
- Templates injected into `backend_lead` agent backstory so the LLM copies from working multi-stage builds instead of generating from scratch.
- `backend_task` description updated to reference templates explicitly.
- Template loader in `data/deploy_templates/__init__.py` auto-discovers stack directories.

## 2026-04-26 · b8b7b4a — Register new crews in package init

- `crews/__init__.py`: added `social_response_crew` and `portfolio_crew` to eager imports and `__all__`, matching existing pattern for all other crews.

## 2026-04-26 · be7e9cf — Dedup + Social Response + ErsLabs Landing

- **Cross-cycle dedup** (`dedup.py`): filters duplicate opportunities against existing drafts using `SequenceMatcher` on title+problem text. Threshold configurable via `SENTINEL_DEDUP_THRESHOLD` env var (default 0.7).
- **Source URL tracking**: research crew now outputs `source_urls` per opportunity. Persisted in opportunity blob via `db.patch_phase`.
- **Social response crew**: new crew that composes platform-adapted replies (Reddit casual, Twitter concise, HN technical) for source communities after validation. Compose-only — user posts manually.
- **Portfolio crew**: new crew that maintains `erslabs-landing/data/portfolio.json` with validated apps.
- **Post-validation trigger**: on draft validation, background thread runs social response + portfolio update + landing rebuild/deploy.
- **ErsLabs landing page** (`erslabs-landing/`): Next.js 14 App Router, static export, Tailwind CSS, Lucide icons. Sections: Hero, How It Works, Portfolio grid, About, Footer. Cloudflare Pages ready.
- **ErsLabs branding**: logo.svg, favicon.svg, og-image.svg with hexagonal neural-network icon + blue accent.
- **deploy.sh**: initial Cloudflare Pages deployment script.
- 22 new unit tests (230 total, all passing).

## 2026-04-25 · cce6ba9 — Fix history modal failed variant + REST validation

- `HistoryModal`: added `failed` variant with distinct orange stripe and label. Fixed `rejectedCount` to exclude failed items from rejected total.
- REST `/api/drafts/action`: `request_changes` now validates non-empty `notes`, matching socket handler behavior.

## 2026-04-25 · 4d06341 — Feedback loop + deploy validation

- **New `validated` status**: `deployed` stays in the pipeline for user verification. Only `validated` moves to history. Prevents marking apps as done without confirming they work.
- **Request Changes button**: available on `built`, `deployed`, and `failed` stages. Sends revision notes back to the build crew which re-queues the draft with surgical change instructions.
- **Validate button**: on `deployed` stage, user confirms the app works and marks it `validated`.
- **revision_notes flow-through**: `start_cycle` reads notes from queued draft, `run_build` passes them to crew inputs, `build_crew` plan_task instructs agents to make surgical changes (not rebuild from scratch).
- **Deploy URL validation**: `run_deploy` no longer invents fallback URLs (`f"https://{slug}.erslabs.net"`). If deploy crew returns no real `frontend_url`, the draft is marked `failed`.
- **Flask backend**: new `request_changes` and `validate_draft` socket handlers + REST actions.
- **Tests**: 8 new tests for feedback loop (revision_notes propagation, deploy URL validation). Fixed pre-existing deploy test mocks missing `go_no_go: "GO"`.

## 2026-04-25 · 67676bb — Derive subdomain from app name only

- `_make_slug()`: rewrote to extract the product name from the opportunity title. "ComplianceDesk HIPAA Compliance" now produces `compliancedesk` (not `draft-c1-compliancedesk-hipaa`). No hyphens, just clean app name. Concatenates tokens until >= 4 chars.
- Build and deploy phases now pass opportunity title to `_make_slug()` instead of draft_id.

## 2026-04-25 · 7b3c36a — Use app name as subdomain + verify deploy before success

- `_make_slug()`: strips `draft_cN_` prefix so subdomain is the app name (e.g. `compliancedesk-hipaa.erslabs.net`) not the internal draft id.
- `run_deploy()`: now checks QA verifier's GO/ROLLBACK verdict. If ROLLBACK, draft is marked `failed` with the failing step instead of blindly marking `deployed`.

## 2026-04-25 · 78b81d7 — Change default workspace root to ~/Sentinel

- `sentinel_loop.py` + `file_tool.py`: default `SENTINEL_WORKSPACES_ROOT` changed from `/tmp/sentinel_workspaces` to `~/Sentinel`. Generated app code now persists across reboots. Env var override still works.

## 2026-04-25 · b3404d4 — Fix deploy phase crash: CrewAI template variable collision

- `deploy_crew.py`: verify_task description contained `%{{http_code}}` which CrewAI's template engine resolved to `{http_code}` and then failed with "Missing required template variable 'http_code'". Rewrote the curl verification instructions to describe the check without brace-delimited tokens. Deploy was never executing; it crashed at task initialization every time.

## 2026-04-25 · 65ad362 — Fix BUILD error 400, dashboard cycle#1 stuck, agent feed cross-cycle bleed

**Bug 1 - BUILD fails with MiniMax "invalid message role: system":**
- `llm_config.py`: added `_patch_litellm_system_messages()` that monkey-patches `litellm.completion` and `litellm.acompletion` globally to rewrite `system` role to `user` before any API call. Called once from `get_minimax_llm()`. The existing per-LLM `.call()` patch remains as defense-in-depth; the global patch catches CrewAI hierarchical process code paths that bypass it.

**Bug 2 - Dashboard always shows cycle #1:**
- All 5 crew factories (`research_crew`, `match_crew`, `build_crew`, `security_remediation_crew`, `deploy_crew`) now accept `cycle: int = 1` param and pass it to `hook_crew_full()` instead of hardcoding `cycle=1`.
- `match_crew` now calls `hook_crew_full()` (was missing entirely).
- `sentinel_loop.py`: passes `cycle=self.state.cycle_count` to every crew factory call.
- `main.py`: daemon pre-sets `flow.state.cycle_count = cycle - 1` so `start_cycle()` increments to the correct number.

**Bug 3 - Agent feed repeats messages from previous cycles:**
- `dashboard_state.py`: added `clear_agent_messages()` that resets the messages file to `[]`.
- `sentinel_loop.py`: calls `clear_agent_messages()` at the start of each new cycle in `start_cycle()`.

**Tests:** 239 passed (+11 new), 0 failed. Coverage 77%.

## 2026-04-25 · e93372e — Fix builds stuck/looping: stale flow state + missing error handling

**What changed:**
- `main.py`: daemon now creates a fresh `SentinelLoopFlow()` inside the `while` loop instead of reusing the same instance. Prevents cycles 2+ from silently skipping all phases due to stale state.
- `sentinel_loop.py`: wrapped `build_crew()`, `match_crew()`, and `deploy_crew()` kickoff calls in try/except. On failure, the draft is marked `"failed"` with error details instead of staying stuck in `"building"` forever.
- `sentinel_loop.py`: when `start_cycle` picks up a queued (retried) draft, all phase outputs are now reset (`build_output`, `match_score`, `deployed`, security fields, etc.) so downstream phases actually execute instead of hitting their "already done" guards.

**Root causes:** (A) single flow instance across daemon cycles, (B) unhandled crew exceptions leaving drafts in limbo, (C) stale state on retry pickup.

**Follow-up (8c51883):** hardened `update_draft` inside except blocks with nested try/except to prevent DB errors from swallowing the original crew error. Added `revision_notes`, `pending_since`, `draft`, `draft_file` to retry reset list.

**Result:** 228 passed, 0 failed. Orphaned "building" drafts will be recovered to "failed" on next daemon start via `_recover_orphaned_drafts`.

## 2026-04-25 · TBD — Tests no longer leak into prod sentinel.db; full suite green

**What changed:**
- `tests/conftest.py`: new autouse `_isolated_sentinel_db` fixture that points `SENTINEL_DB_PATH` at a per-test temp SQLite and resets `db._initialized` (the module-level "schema already created" flag) before and after each test. Previously, fixture data like `[{"title": "Op A"}, {"title": "Op B"}]` from `test_crews_integration.py` leaked into the running daemon's `drafts` table → spurious "Op A / Op B" cards in the dashboard.
- `tests/unit/test_main.py`: updated `TestOrphanRecovery` to match the corrected behavior (`queued` is no longer marked `failed` on restart). Added `test_preserves_queued_drafts` covering the new contract.
- `tests/unit/test_config.py`, `tests/integration/test_crews_integration.py`: aligned with `get_memory_for_crew_full` returning None by default.
- `tests/e2e/test_sentinel_loop_e2e.py`: explicitly set `mock_result.pydantic = None` and `mock_result.json_dict = None` so `_extract_raw` falls through to `.raw`. Without this, `Mock()` auto-generated those attributes as further Mocks, shadowing the real payload and causing 3 "pre-existing" e2e failures going back several sessions.
- DB cleanup: removed the `Op A` (and any leftover `Op B`) stub drafts from production `sentinel.db`.

**Result:** 228 passed, 0 failed (was 211 passed + 3-10 failing depending on what got dragged in).

## 2026-04-25 · TBD — Disable broken memory, surgical retry, all candidates → drafts, markdown feed

**What changed:**
- `src/sentinel_v2/config/embedder_config.py`: `get_memory_for_crew_full` returns `None` by default. CrewAI's `UnifiedMemory.QueryAnalysis` uses LiteLLM structured outputs that bypass our `<think>`-stripping wrapper, and the embedder kept falling back to OpenAI (raising `CHROMA_OPENAI_API_KEY` errors). Memory was causing more pain than value. Set `SENTINEL_ENABLE_MEMORY=1` to opt back in.
- `src/sentinel_v2/main.py`: removed `"queued"` from the orphan-recovery status set. `queued` means "approved, awaiting daemon pickup" — not in-flight. The previous behavior wiped retry-flagged drafts on every daemon restart.
- `src/sentinel_v2/flows/sentinel_loop.py`: `run_research` now writes ALL surfaced opportunities as pending drafts (not just `opportunities[0]`). The user can approve any of them; future cycles' `start_cycle` queued-draft hook picks up whichever one they choose.
- `dashboard/app.py`: extracted `_unblock_daemon_for_retry()` helper. Retry now identifies the SPECIFIC draft the daemon is polling on (via the active checkpoint state JSON) and rejects only that one. Fresh pending drafts from later research runs are no longer collateral-damaged.
- `dashboard-nextjs/src/components/AgentConversation.tsx`: replaced `<p>{message}</p>` with `<ReactMarkdown remark-gfm>` and styled component overrides for headings, lists, code blocks, tables, and links. Agent outputs now render cleanly instead of as raw markdown.
- `package.json`: `react-markdown@^10` + `remark-gfm`.
- `tests/unit/test_config.py`, `tests/integration/test_crews_integration.py`: updated to reflect memory-disabled-by-default behavior.

## 2026-04-24 · TBD — Agent Feed: drop lifecycle noise, surface real task outputs

**What changed:**
- `src/sentinel_v2/crew_hooks.py`:
  - Removed per-agent `"Agent initialized: <role>"` messages (one per agent per phase — pure noise, the avatar already tells you the agent exists).
  - Removed per-task `"Task started: <80 char description>"` messages (`_hook_task` is no longer called from the wrapped kickoff). These were the most-complained-about noise.
  - `phase_started` is now a single concise ping: `🚀 RESEARCH phase started · 2 tasks · 2 agents`. Agent roles are included in metadata.
  - `phase_completed` is prefixed with `✅ <PHASE> complete` and shows up to 800 chars of the crew's final output (vs 500 before).
  - `phase_error` is prefixed with `❌ <PHASE> failed:`.
  - `task_callback` (`_make_task_callback`) now includes a **task description header** (first line, bold, truncated to 80 chars) above the raw output, and bumps the output preview from 400 → 800 chars. `metadata` includes `agent_role` and `description_first_line` so the UI can render it structured later.

**Why:** the previous feed was 90% lifecycle pings (`Task started: <the full 500-char task prompt>`, `Agent initialized: Demand Hunter`, `Agent initialized: Commercial Validator`…) and only revealed agent output after tasks completed. That mix felt spammy without being informative. After this change, each phase produces one start ping, one completion summary, and one rich message per completed task with its actual findings.

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
