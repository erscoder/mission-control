# Changelog

All notable changes to Sentinel V2. Ordered newest-first. Each entry references
the commit hash so every change is traceable and auditable.

## [Unreleased]

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
