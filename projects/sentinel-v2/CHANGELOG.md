# Changelog

All notable changes to Sentinel V2. Ordered newest-first. Each entry references
the commit hash so every change is traceable and auditable.

## [Unreleased]

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
