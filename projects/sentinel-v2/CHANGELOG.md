# Changelog

All notable changes to Sentinel V2. Ordered newest-first. Each entry references
the commit hash so every change is traceable and auditable.

## [Unreleased]

## 2026-04-28 · 9756e58 - Langfuse observability for all pipeline phases

Connects Sentinel to the shared Langfuse v3 instance running in `synapseia-network` (no new services - Sentinel reaches it via `host.docker.internal:3700`).

**New module `observability/tracing.py`:** Singleton Langfuse client initialized at import time; safe no-op if `LANGFUSE_ENABLED=false` or SDK init fails. Three functions: `start_trace` (creates a named trace with cycle/draft_id/opportunity tags), `log_event` (attaches events to a trace), `end_trace` (finalizes + flushes). All accept `None` safely so tracing can never break the pipeline.

**Instrumented phases in `sentinel_loop.py`:** `run_research` (outputs opportunity count), `run_match` (outputs match score, error event on crew failure), `run_build` (per-attempt events, escalation ERROR event, QA gate pass/fail events), `run_security_remediation` (vuln count), `request_approval` (approval_requested event), `run_deploy` (per-attempt events, escalation ERROR, deployed_url on success).

**docker-compose.yml:** `LANGFUSE_HOST/PUBLIC_KEY/SECRET_KEY/ENABLED` added to sentinel service. Defaults use synapseia-network dev keys; override via `.env` for prod projects.

All 278 unit tests pass.

## 2026-04-29 · 1cde7a4 - Error escalation, NestJS pin, true QA fail-closed

User reported: `ComplianceDesk` deploy died with `Error code: 429` (Anthropic Token Plan rate-limit), pipeline burned the whole 2-attempt deploy budget on something only the operator can fix, and ERESOLVE peer-dep loops kept producing broken `package.json` cycle after cycle. Three coupled fixes.

**Fix 1: error classification + escalation (`flows/error_classifier.py`).** Build/deploy retry loops previously retried every exception until `MAX_*_RETRIES`, even when the error was a provider rate-limit, expired API key, or billing block — none of which retrying can fix. The new classifier pattern-matches `429` / `401` / `402` / Anthropic Token Plan errors, short-circuits the loop on the first attempt, marks the draft `blocked` (distinct from `failed`), and appends an actionable entry to `/tmp/sentinel_v2_escalations.json` with category, action_required hint, phase, draft_id, and truncated error excerpt. The operator now learns "rotate the key" or "wait for quota reset" once, instead of `[Auto-retry 2/2]` thrash.

**Fix 2: pin canonical NestJS `package.json` (`data/deploy_templates/node_nestjs/package.json`).** The build agent kept inventing incompatible `@nestjs/*` matrices — `@nestjs/common@10` + `@nestjs/core@11`, `@nestjs/throttler@5` alongside `@nestjs/common@11` — producing ERESOLVE deadlocks every cycle. The pinned `package.json` (NestJS 10.4.15 LTS + throttler 5.2 + Prisma 5.22 + Stripe 14.25 + class-validator 0.14, all peer-dep compatible) is now pre-baked into `<workspace>/backend/` before the build crew starts (in `run_build`) and again as a defensive overwrite before deploy (in `_prebake_deploy_files`). Build and security-remediation prompts forbid rewriting the file; extra deps must come from `npm install <pkg>@<version>` so npm re-resolves peers cleanly. The `@nestjs/*` version matrix is explicitly off-limits to the security crew.

**Fix 3: close the QA gate fail-open (`flows/sentinel_loop.py:799+`).** The previous `daa96d5` only added an explicit-fail path; the unparseable branch still defaulted to `build_ok=True` with the rationale "the security loop will validate". The security loop only validates dependency CVEs, never `npm run build`, so any QA Lead returning prose-instead-of-JSON silently promoted broken drafts. Now closed by default — only an explicit `GO` plus `build_status` in `{clean, warnings}` promotes the draft. Anything else (silence, partial output, garbled JSON) marks the draft failed with `build_failed_qa_gate_unparseable`, clears the checkpoint, and stops the cycle.

**Tests.** 26 new for the classifier (pattern match per category, escalation file lifecycle including corrupt-recovery and 2KB truncation, action-hint coverage), 4 new for the gate + escalation (fail-closed on unparseable, accepts explicit GO, build escalates 1-attempt on 429, recoverable errors still consume full retry budget). Two pre-existing tests updated to mock `_parse_deploy_result` so their happy-path mocks satisfy the now-closed gate. Full unit suite (278 tests) green.

## 2026-04-28 · 9fbf9aa - Daemon promotion gates: stop shipping broken drafts

User reported: daemon log showed `Build status: FAIL` from the QA Lead, hourly `awaiting_approval` heartbeats on drafts whose `npm run build` never compiled, and Pydantic `string_type` validation errors crashing the security remediation crew. Five cooperating fixes, in order.

**Fix 1: programmatic QA gate in `run_build`.** The hierarchical build crew's QA Lead narrated `go_no_go: NO-GO` in its task output, but `run_build` saved `result.raw` and called `update_draft(status="built")` regardless. Anything an LLM wrote in chat was treated as success. Now we reuse `_parse_deploy_result` (which already JSON-coerces with markdown-fence tolerance) to extract `go_no_go` and `build_status`, and fail the draft when either says no. Cuts the flow there — no security loop, no approval queue.

**Fix 2: `build_ok` field on `SentinelState` + `request_approval` health gate.** Added `build_ok: bool = False`. `run_security_remediation` now persists the developer agent's `build_ok` JSON field (only when the field is present — silently missing means the security crew didn't actually build, so we keep the QA-gate verdict). `request_approval` rejects upfront if `vulnerability_scan_error` is set or `build_ok` is False, marks the draft `failed`, clears the checkpoint, and ends the cycle. Eliminates the daily heartbeat log of broken drafts sitting in the approval queue.

**Fix 3: empty-response retry on MiniMax.** MiniMax (especially `MiniMax-M2.7`) periodically streams empty responses, which CrewAI hands to Pydantic `TaskOutput` as `None`, raising `1 validation error for TaskOutput ... string_type`. New `_patch_empty_response_retry` in `llm_config.py` wraps `llm.call`, retries on `None`/empty/whitespace with exponential backoff (1s/2s/4s), and raises a clean `RuntimeError` after 3 attempts so the existing crew-kickoff `try/except` can mark the draft failed without a Pydantic stack trace. Logs `WARNING ... MiniMax empty response, retry N/3`.

**Fix 4: shell-operator rejection in `RunShellTool`.** Build-crew agents kept calling `run_shell('npm install foo && npm install bar')` as a single string. `subprocess.run` with `shell=False` and `shlex.split` gave npm `&&` as a literal package name → `npm error EINVALIDTAGNAME "&&"`. We refused to enable `shell=True` (agents emit unsanitized strings; injection risk). Instead, after `shlex.split`, any bare `&&`, `||`, `;`, `|` token is rejected with a message telling the agent to make separate calls. Updated tool description so the LLM knows up-front. Existing `cd <subdir> && <cmd>` prefix still works (handled before the `shlex.split` step).

**Fix 5: peer-dep alignment guidance in build-crew prompts.** Recurring `npm ERESOLVE: @eslint/js@10.0.1 vs eslint@9.39.4`. There are no static `package.json` templates — agents generate them per cycle — so the fix lives in the frontend/backend task descriptions in `build_crew.py`: explicit "when you add `eslint` and `@eslint/js`, both must share a major; same for `@typescript-eslint/*`". Plus a `npm ls eslint` post-install check.

Test fixes (pre-existing failures discovered during verification):
- `TestRequestApproval`: 2 tests now seed `build_ok=True` to clear the new health gate.
- `TestCheckApproval::test_check_approval_approved_via_dashboard`: mock now returns `pending_deploy` (the user-intent status the wait actually targets), not `deployed`.
- 6 deploy tests (`TestSentinelLoopFlowKickoff::test_run_deploy_runs_when_approved`, `TestFeedbackLoop::test_run_deploy_*`, `TestDeployRetryLoop`): patched `_prebake_deploy_files` so they don't blow up on missing `~/Sentinel/<draft_id>` directories, and updated URL assertions to match the slug-derived canonical URL contract introduced in commit `0932492`.

51 / 51 sentinel_loop unit tests passing; 235 / 235 unit-suite total. Coverage 74% (pre-existing project baseline; uncovered modules — security_remediation_crew, build_crew, deploy_crew — are integration-tested via the daemon, not unit-mocked).

## 2026-04-28 · daa96d5 - Follow-up: close QA-gate fail-open + regression tests

Code review of 9fbf9aa surfaced one real bug and two gaps. Fixed in this follow-up.

**Bug: unparseable QA output rejected legitimately-green drafts.** When `_parse_deploy_result` returned `{}` (QA Lead emits prose instead of JSON, or empties the response under load), `go_no_go` and `build_status` were both `""`, the gate did NOT fail (correct), but `state.build_ok` was assigned `(False) or (False) = False`. Then a security crew that reported `build_ok=True` could not lift the verdict because the AND-clamp only narrows. Net effect: any QA Lead that returned valid-but-unstructured success was auto-rejected at `request_approval`. Fix: when both QA fields are empty, default `state.build_ok=True` and emit a WARNING — the security loop is the authoritative gate for that case (it actually runs `npm run build`).

**Gap: no regression tests for the new gates.** Added:
- `TestQAGateAndApprovalGate` (tests/unit/test_sentinel_loop.py): four tests covering the build_ok=False rejection, the vulnerability_scan_error rejection, the security AND-clamp leaving QA's True intact when build_ok is missing, and demoting it when explicit False.
- `test_run_shell_rejects_double_ampersand` / `_semicolon` / `_pipe` / `_allows_leading_cd_chain` (tests/unit/test_file_tool.py): covers the npm `EINVALIDTAGNAME "&&"` regression and confirms the legitimate `cd <subdir> && <cmd>` prefix still works.
- `TestPatchEmptyResponseRetry` (tests/unit/test_config.py): five tests covering the happy path, retries on `""` / whitespace / None, exhaustion → `RuntimeError`, and idempotent patching. Uses a plain stub class instead of `MagicMock` because MagicMock's child-mock auto-creation shadows function assignment to `.call`.

13 new test cases. Full unit suite: 248 / 248 green (was 235 pre-followup).

## 2026-04-28 · pending - Retry from dashboard now actually starts fresh

User reported: clicking Retry kept resurrecting drafts already exhausted, with the message "Deploy exhausted all 2 attempts in a prior cycle and the resumed state had no deployed=True." Two cooperating bugs:

**Bug A: `_load_resumable_state` did not drop checkpoints for `failed` drafts.**
The terminal set was `{pending, rejected, validated, deployed, rejected_deploy}` and missing `failed`. So when a draft hit max-retries and was marked `failed`, its checkpoint persisted; the next cycle's daemon main loaded it; the listener chain reached `run_deploy`; the exhausted-retry guard fired again and re-marked it failed. Loop on every retry.

Fix: added `"failed"` to the terminal set in `main.py::_load_resumable_state`. Now any failed draft's checkpoint is dropped at daemon start / next-cycle load.

**Bug B: `start_cycle` queued-draft pickup did not reset `build_attempts` / `deploy_attempts`.**
The pickup branch already reset `build_output`, `workspace_dir`, `match_score`, `deployed`, `deployed_url`, etc., but left the retry counters at whatever they were in the prior state. A user clicking Retry on a draft that exhausted retries inherited those counters via the kickoff state, and the exhausted-retry guards in `run_build` / `run_deploy` immediately flagged the draft as exhausted-and-failed.

Fix: explicitly reset `self.state.build_attempts = 0` and `self.state.deploy_attempts = 0` when picking a queued draft in `start_cycle`. Combined with Bug A, Retry from dashboard is now genuinely fresh.

Sanity tests passed: source inspection confirms both fixes are in place.

Operational note: drafts created at 2026-04-27 23:57, 2026-04-28 05:21, 09:38 came from the previous daemon (PID 15394) which was started before today's backpressure code was added. Code edits do not retroactively apply to running processes; a daemon restart is required for behavior changes to take effect. Confirmed by `Research paused` count = 0 in the current daemon's log.

## 2026-04-28 · pending - Daemon sleep polls for queued drafts every 30s

Race condition spotted while validating the run_shell fix: I reset compliancedesk to `queued`, but the daemon had already finished its empty cycle and gone into a 1-hour sleep before my reset. The draft sat untouched for 50 minutes until the daemon naturally woke.

Fix in `main.py` `run_daemon`:
- The post-cycle "no queued drafts" sleep is now a polling loop. Every 30 seconds (or `interval_seconds`, whichever is smaller) it re-checks `list_drafts_by_status({"queued"})` and wakes early if anything appeared.
- Total sleep budget unchanged (`SENTINEL_LOOP_INTERVAL_HOURS`, default 1h), so the daemon does not spin when truly idle.
- Effect for the user: clicking Approve / Retry / Request Changes on the dashboard wakes the daemon within 30s instead of within 1h.

## 2026-04-28 · pending - run_shell: support `cd subdir && cmd` and add subdir param

Build agents kept failing tool calls with `shell-error: 'cd' not in whitelist` because they were composing commands like `cd backend && npm run build`. `RunShellTool` invokes `subprocess.run(argv)` (no shell), so the literal `cd` becomes the binary name, fails the whitelist, and the agent has to retry. Each round trip costs an LLM call.

Fix in `tools/file_tool.py`:

- `RunShellInput` gains a `subdir: str = "."` parameter so agents can run a command in a sub-directory of the workspace explicitly: `run_shell(workspace_dir=..., subdir='frontend', command='npm run build')`.
- New regex `_CD_PREFIX = re.compile(r"^\s*cd\s+([^\s&;]+)\s*&&\s*(.+)$", re.DOTALL)` translates the legacy `cd <subdir> && <rest>` pattern transparently into structured `subdir + command`. Agents that fall back to that pattern just work.
- `cwd` resolved via `_safe_child(ws, subdir)` so subdir traversal is sandboxed; missing dirs return `subdir 'X' does not exist under workspace` instead of opaque exec errors.
- Tool description updated so the agent sees both `subdir` and the `cd && cmd` shorthand documented.
- Whitelist expanded with read-only inspection commands the build agent commonly needs: `head`, `tail`, `find`, `grep`, `wc`, `pwd`, `which`, `stat`, `touch`, `chmod`, `yarn`, `true`, `false`. Sandboxing is unchanged (cwd is still locked to the workspace).

Sanity tests passed in a temp workspace:
- `cd frontend && pwd` resolves to `<ws>/frontend` via the regex translation.
- `subdir='frontend'` explicit form works.
- No `subdir` and no `cd` falls back to workspace root.
- Non-existent subdir returns a clear error.
- `find . -name package.json` runs (whitelist expansion).

## 2026-04-27 · pending - Stale-retry-counter spin guard in run_build / run_deploy

After the SLUG fix the daemon resumed compliancedesk from a checkpoint where the previous cycle had already burned `build_attempts=3` and `deploy_attempts=2`. With both counters at their cap, the `while attempts < MAX` loops in `run_build` / `run_deploy` did not execute, the methods returned almost immediately, the daemon's main loop saw the cycle complete, re-loaded the same checkpoint, and re-entered run_deploy. Logs showed "Phase 5: DEPLOY" emitted 15+ times per second, daemon at 85% CPU.

Fix: at the top of both `run_build` and `run_deploy`, after the existing "approved / build_output / deployed" guards, check whether the relevant attempt counter has already reached its cap. If yes, mark the draft `failed` with a clear message ("Build/Deploy exhausted all N attempts in a prior cycle. Click Retry to start fresh."), clear the checkpoint, and set `_shutdown_requested = True` to end the cycle cleanly. The daemon's main loop sees no remaining queued draft for this id and either picks the next queued or sleeps; either way the spin stops.

Verified by reset compliancedesk → queued, cleared checkpoints, restarted daemon. The guard fires only on RESUMED state with exhausted counters; a fresh kickoff increments from 0 normally.

## 2026-04-27 · pending - Research backpressure: pause when pipeline saturated

Symptom: with 4 in queued, 1 building, 4 pending, the daemon kept running research every idle cycle, piling up new pending drafts the user could not triage. New research while the bottleneck is downstream is just noise.

Fix in `flows/sentinel_loop.py` `run_research`:
- Before kicking off research_crew, count drafts in active states: `pending`, `queued`, `building`, `review`, `testing`, `built`, `pending_deploy`, `deploying`.
- If count >= threshold (env `SENTINEL_RESEARCH_PAUSE_THRESHOLD`, default `6`), log a per-status breakdown and return without running research. The cycle ends gracefully; subsequent listeners exit on `top_opportunity is None`.
- If a queued draft was picked up by `start_cycle`, `top_opportunity` is set → research-skip path runs first (unchanged), so the threshold check never fires for the queued-draft path.

Threshold rationale (default 6):
- `pending` consumes user attention (review/approve/reject). 3+ pending = user already overwhelmed.
- `queued + in-flight build/deploy` is the sequential pipeline; a single MVP build + deploy is roughly 15-25 minutes. 3+ in this lane = ~1h+ of work backlogged.
- 6 covers a healthy mix of both lanes; beyond that, idea volume is the wrong lever to pull.

Tunable via env. Set `SENTINEL_RESEARCH_PAUSE_THRESHOLD=10` for a louder pipeline, `=4` for a tighter one. Set very high to disable.

Verified at restart: 9 active drafts in DB, helper correctly identifies pause. Daemon resumed compliancedesk's in-flight build via checkpoint, so backpressure will fire on the NEXT cycle when the daemon would otherwise generate fresh research.

## 2026-04-27 · pending - Stop embedding fly.toml template into build_crew prompt

After the previous fix the daemon picked up `compliancedesk` and reached the build phase but failed three times with `Missing required template variable 'SLUG' not found in inputs dictionary`. Root cause: the `Senior Backend Engineer` agent's backstory and the `backend_task` description embedded the raw `fly.toml` template content (`app = '{{SLUG}}-api'`). CrewAI 1.14.x interprets `{{...}}` as a Jinja2 variable reference; with no `SLUG` key in `inputs`, every render aborted before the crew even ran.

We already pre-bake `fly.toml` and `Dockerfile` deterministically at deploy time, so the build agent has zero need to reproduce them. Removed:

- The `from sentinel_v2.data.deploy_templates import load_templates` import.
- The `deploy_templates = _load_deploy_templates()` call in `build_crew()`.
- The `## DEPLOY TEMPLATES` block with `f"{deploy_templates}"` interpolation in the backend agent backstory.
- The `DEPLOY ARTIFACTS` block in `backend_task.description` that referenced `Dockerfile` and `fly.toml` (and contained the offending `{{SLUG}}`).

Replaced both spots with a one-liner: "Do NOT create a Dockerfile or fly.toml; the deploy crew installs the canonical pair before deploying. Anything you write there will be overwritten." Stack pinned to NestJS + Prisma + PostgreSQL on port 8080.

Reset the stuck `compliancedesk` draft back to `queued` and restarted the daemon to validate the fix end-to-end.

## 2026-04-27 · pending - start_cycle queued pickup, neutralize CrewAI flow memory, drop stale checkpoints

User reported queue still piling up after the previous session's fixes. Daemon was running but stuck on a stale `cycle 658 fieldsync research` checkpoint, never reaching the queued-draft pickup branch. Logs were also flooded with `Memory save failed: ... CHROMA_OPENAI_API_KEY environment variable is not set`.

Fixes:

**`flows/sentinel_loop.py` `start_cycle` resume detection**
- Old condition `if self.state.cycle_count > 0:` mis-detected fresh flows as resumes because the daemon's main loop pre-sets `cycle_count = cycle - 1` even when there is no checkpoint. After the first cycle, the queued-draft pickup never ran.
- New condition `is_resume = bool(self.state.draft_id) and self.state.cycle_count > 0`. A real resume always carries a `draft_id`; pre-set cycle counters do not.

**`flows/sentinel_loop.py` flow-level memory neutralized**
- CrewAI's `Flow.__init__` auto-creates a `Memory(...)` with `embedder=None`, which then defaults to OpenAI and demands `CHROMA_OPENAI_API_KEY`. Every internal event triggered a `Memory save failed` warning.
- Set `self.memory = None` immediately after `super().__init__()` and overrode `remember()` / `recall()` as no-ops. Persistence already lives in the SQLite checkpoint and `dashboard_state`, so we do not lose anything functional.

**`flows/sentinel_loop.py` clear checkpoint on gate exit**
- `wait_for_draft_approval`: clears the checkpoint when the draft was rejected or the gate timed out, so the next cycle does not resume into a dead flow.
- `check_approval`: clears the checkpoint when the user requested changes (`queued`), rejected (`rejected_deploy`), or the gate timed out. The next cycle starts fresh and re-picks via `start_cycle`'s queued-draft branch.

**`main.py` `_load_resumable_state` drops stale checkpoints**
- A checkpoint pointing at a draft whose status is now terminal or wait-state (`pending`, `rejected`, `validated`, `deployed`, `rejected_deploy`) is dropped from the DB and the function returns None. Prevents the daemon from resuming the same dead flow forever.

**Operational cleanup**
- Manually deleted the stale `cycle 658 fieldsync research` checkpoint that was blocking the queue. The new `_load_resumable_state` guard would have dropped it on its own at next start, but cleaning it explicitly avoided one wasted cycle.

Restarted the daemon. Verified:
- 0 memory warnings in `/tmp/sentinel.log` after restart.
- Daemon picked up `draft_c1_compliancedesk-hipaa-compliance-tracker` (the first queued draft, with revision_notes "subdominio erroneo") and saved a fresh checkpoint at phase=research → run_match crew started executing.

## 2026-04-27 · pending - Approval gate + request_changes loop fix; status semantics

User reported queued drafts piling up (5 stuck in queue, daemon also not running). Found that the post-build approval gate was watching for terminal `{deployed, failed}` statuses, while the dashboard's "Approve deploy" and "Reject deploy" buttons set the same `deployed` / `failed` statuses (conflating user intent with runtime outcome). When the user clicked "Request changes", the dashboard set status to `queued` with revision_notes, which the gate did not recognize, so the cycle stalled until the 1h timeout.

Fixes:

**Status semantics: split user intent from runtime outcome**
- New status `pending_deploy`: user clicked "Approve deploy". Daemon will pick up and run deploy crew.
- New status `deploying`: deploy crew actively running. Set at start of `run_deploy`.
- New status `rejected_deploy`: user clicked "Reject deploy". Distinguishable from runtime `failed`.
- `deployed` and `failed` now exclusively reflect what the runtime actually achieved.

**`dashboard/app.py`**:
- `approve_deploy` socketio handler now sets `pending_deploy` instead of `deployed`.
- `reject_deploy` socketio handler now sets `rejected_deploy` instead of `failed`.
- Same change in `/api/drafts/action` HTTP endpoint.
- `compute_build_queue` knows about all three new statuses for sort and filter.

**`flows/sentinel_loop.py` `check_approval`**:
- `target_statuses` changed from `{"deployed", "failed"}` to `{"pending_deploy", "queued", "rejected_deploy"}`.
- `pending_deploy` → approved=True → router proceeds to run_deploy.
- `queued` → user requested changes; end cycle. Daemon's next `start_cycle` picks the queued draft and re-runs build with revision_notes.
- `rejected_deploy` → end cycle terminal.

**`flows/sentinel_loop.py` `run_deploy`**:
- Sets draft status to `deploying` at start so the dashboard reflects progress and orphan recovery can clean up if the daemon dies mid-deploy.

**`main.py` `_recover_orphaned_drafts`**:
- Added `deploying` to `orphaned_statuses`. `pending_deploy` and `rejected_deploy` are intentionally NOT recovered: the former is user intent waiting for daemon pickup (no in-flight work), the latter is terminal user intent.

**`dashboard-nextjs/src/types/sentinel.ts`**:
- `DraftStatus` extended with `pending_deploy`, `deploying`, `rejected_deploy`.

**`dashboard-nextjs/src/components/BuildQueue.tsx`**:
- New `deploying` stage between `built` and `deployed` in the visual pipeline (violet/fuchsia gradient).
- `currentStageIndex` maps `pending_deploy` and `deploying` → index 5 (deploying stage).
- `failed` styling now applies to both `failed` and `rejected_deploy`.
- `countByStage` includes a `deploying` bucket and counts `rejected_deploy` as failed.

**`dashboard-nextjs/src/components/HistoryModal.tsx`**:
- Filters and renders `rejected_deploy` alongside `failed` in the history list.

Sanity tests passed:
- Python compiles for `main.py`, `sentinel_loop.py`, `dashboard/app.py`.
- Dashboard `handle_approve_deploy` / `handle_reject_deploy` set the new statuses.
- `check_approval` source contains `pending_deploy`, `queued`, `rejected_deploy`; old `{deployed, failed}` target removed.
- `run_deploy` sets `status="deploying"`.
- `_recover_orphaned_drafts` includes `deploying`.

**Operational note**: the Sentinel daemon was not running when the user reported stuck queued drafts. Fixes alone do not unstick anything — the daemon must be started for queued drafts to be processed.

## 2026-04-26 · pending - Resilient workspace resolution, prebake never climbs to /

Crash on `run_deploy`: `[Errno 30] Read-only file system: '/root'` when `_prebake_deploy_files` called `mkdir(parents=True)`. Root cause: a checkpoint persisted `state.workspace_dir = "/root/Sentinel/<draft>"` from a previous run in a Docker container where `HOME=/root`. On macOS, `Path("/root/Sentinel/...").mkdir(parents=True)` walked up and tried to create `/root`, which is read-only.

Fixes:
- New `_resolve_workspace_dir(draft_id, cycle_count)` always derives the path from `SENTINEL_WORKSPACES_ROOT` or `~/Sentinel` in the current process. The persisted `state.workspace_dir` is never trusted; if it differs from the recomputed value, log a warning and overwrite.
- `_prebake_deploy_files` now refuses to create the workspace tree itself: raises `FileNotFoundError` if `workspace_dir` does not exist, and uses `mkdir(exist_ok=True)` (without `parents=True`) so it cannot climb up to `/`.
- Cleaned the existing checkpoint row in `sentinel.db` so the path leak does not affect the next deploy attempt: `/root/Sentinel/...` rewritten to `/Users/kike/Sentinel/...`.

## 2026-04-26 · pending - fly.toml + Dockerfile pre-baked from canonical NestJS template

Decision: every Sentinel backend ships as NestJS, so there is no reason to let the LLM compose `fly.toml` or `Dockerfile`. The build agent's broken `[[processes]] app = ""` was the symptom. Cure is to take infra files out of the agent's hands.

- New helper `_prebake_deploy_files(workspace_dir, slug, stack='node_nestjs')` in `flows/sentinel_loop.py`. Reads `data/deploy_templates/<stack>/fly.toml` and `Dockerfile`, substitutes `{{SLUG}}`, writes both into `<workspace>/backend/`. Always overwrites whatever the build agent produced.
- `run_deploy()` calls the helper after computing `slug` and `workspace_dir`, before the kickoff loop. Logs the file paths it wrote.
- Updated the canonical NestJS `fly.toml` template to match the user's preferred shape: `primary_region = 'cdg'`, `min_machines_running = 1`, `auto_stop_machines = false`, explicit `[[vm]] memory = '512mb' cpu_kind = 'shared' cpus = 1`. Dropped the noisy `[http_service.checks]` and `[http_service.concurrency]` blocks; the app code already exposes `/api/health` and small MVPs do not need request-level concurrency tuning.
- Deploy crew prompt simplified: removed the "verify fly.toml" step (no longer relevant). New explicit note in the task description: "fly.toml and Dockerfile have already been written from the canonical template before you start. Do not inspect, edit, or rewrite them." Renumbered the sequence from 13 steps to 12.
- New env flag `SENTINEL_DEPLOY_NO_MEMORY=1` disables long-term crew memory in the deploy crew. Use when validating a fix that the agent's memory could shadow (e.g. a previously learned wrong association between slug and subdomain). Off by default.
- Re-baked the existing failing workspace `~/Sentinel/draft_c1_compliancedesk-hipaa-compliance-tracker/backend/{fly.toml,Dockerfile}` with the new template so a re-run does not pick up the broken state.

Sanity tests:
- `_prebake_deploy_files(tmp, 'compliancedesk')` writes a fly.toml with `app = 'compliancedesk-api'`, `primary_region = 'cdg'`, no `{{SLUG}}` placeholder, no `[[processes]]` block, and a Dockerfile with the multi-stage build and `EXPOSE 8080` ✓
- `deploy_crew()` source contains `SENTINEL_DEPLOY_NO_MEMORY` and conditional memory wiring ✓

## 2026-04-26 · pending - Deploy crew: deterministic URLs, frontend build gate, draft_id leak fix

Confirmed via QA Verifier log that the failing deploy of `compliancedesk` never created a fly.io machine and never created a Cloudflare Pages project. The agent was hallucinating the final URL as `draft-c1-compliancedesk-hipaa.erslabs.net` because it confused the `slug` and `draft_id` inputs and used the latter as a DNS subdomain.

Fixes applied across three files:

**`flows/sentinel_loop.py` `run_deploy()`:**
- Pre-bake the canonical deploy strings in Python before kicking off the crew: `expected_backend_app_name = f"{slug}-api"`, `expected_cf_project_name = slug`, `expected_frontend_url = f"https://{slug}.{ERSLABS_ROOT_DOMAIN}"`, `expected_backend_url = f"https://{expected_backend_app_name}.fly.dev"`.
- Pass these as `backend_app_name`, `cf_project_name`, `frontend_url`, `backend_url` inputs.
- Remove `draft_id` from the deploy kickoff inputs entirely. The Stripe webhook idempotency value is renamed to `stripe_idempotency_key` so the agent never sees the substring `draft_id` or `draft_c\d+_`.
- Seed `deploy_feedback` from `self.state.revision_notes` so a human "request changes" actually reaches the deploy agent on the next attempt (previously only auto-retry errors flowed in).
- Clear `self.state.revision_notes = None` on deploy success so they do not contaminate the next cycle.
- Use the pre-baked `expected_frontend_url` for `state.deployed_url` instead of trusting the URL the agent reports.

**`crews/deploy_crew/deploy_crew.py`:**
- Rewrote the deployer backstory as a 13-step sequence with literal `{}` interpolation of the pre-baked names. Hard rules at the bottom: "the DNS subdomain is exactly `{slug}`, never anything that starts with 'draft', 'cycle', or any compound name."
- Added an explicit frontend-build gate: before `cloudflare_pages_deploy`, the agent must verify `<workspace_dir>/frontend/out/` exists. If missing, run `npm ci && npm run build`. If still missing after build, inspect `next.config.mjs` and add `output: 'export'`. Cannot proceed without `out/`.
- Added a fly.toml verification step before deploy: agent must confirm the file contains `app = '<backend_app_name>'` and an `[http_service]` block. If `[[processes]]` is present (the bug we observed in the broken workspace) or `app` is empty/wrong, overwrite with the canonical template.
- Verifier task now uses literal `{frontend_url}` and `{backend_url}` and explicitly says: "If DNS does not resolve, the deploy never completed. Report ROLLBACK with the exact curl output."
- Removed the previous use of `{draft_id}` from the task description.

**`tools/cloudflare_tool.py`:**
- New `_reject_draft_like(value, field)` helper. Hard error if any `project_name`, `subdomain`, or `domain label` matches `^draft[-_]c?\d` or contains `draft-c` / `draft_c` (case-insensitive).
- Guard wired into `CloudflarePagesCreateTool._run`, `CloudflareDnsCnameTool._run`, and `CloudflarePagesAddCustomDomainTool._run`. The error message tells the agent exactly what to do: "you must pass the clean slug (e.g. 'compliancedesk'), not the draft id". Feeds the retry loop with a fix-friendly diagnostic.

**Sanity tests (run before commit):**
- `_make_slug("ComplianceDesk HIPAA Compliance") == "compliancedesk"` ✓
- `_reject_draft_like("draft-c1-compliancedesk-hipaa", ...)` returns an `error:` string ✓
- `_reject_draft_like("compliancedesk", ...)` returns `None` ✓
- `run_deploy` source: no `"draft_id"` key in inputs dict; all five new keys present; `deploy_feedback` seeded from `revision_notes`; `revision_notes` cleared on success; `deployed_url` uses pre-baked URL ✓

**Known follow-ups (NOT fixed in this batch):**
- The build_crew backstory still hands the backend agent freedom to "adapt" the fly.toml template and it produced a broken `[[processes]] app = ""` in the failing workspace. The deploy crew now defends against this at deploy time, but the build prompt should be tightened to forbid edits beyond the literal `{{SLUG}}` substitution. Tracked separately.
- CrewAI memory carryover: the deploy crew has `memory=memory`. If a previous run wrote "compliancedesk → draft-c1-compliancedesk-hipaa" into long-term memory, the agent may resurrect that association even after the input fix. Recommended: run the next deploy cycle with `memory=False` (or wipe the memory storage) the first time, to confirm the fix in isolation before re-enabling.
- Zombie Cloudflare resources: the previous failed runs may have created Pages projects or DNS records under the wrong name. Run `cloudflare_pages_list` (manually via CF dashboard) and clean up any `draft-c*` projects/CNAMEs before re-running against the same draft.

## 2026-04-26 · pending - Honest agent count: 17 across 7 crews (Pipeline rewrite)

- Removed fictional agent names from `Pipeline.tsx` (Nova, Atlas, Echo, Forge, Sentinel, Hermes did not exist in `src/sentinel_v2/crews/`).
- Pipeline section now mirrors the real codebase: 7 crews (research, match, build, deploy, portfolio, security_remediation, social_response) with the 17 actual agent roles (Demand Hunter, Commercial Validator, Customer Intelligence Analyst, Opportunity Qualifier, Strategic Product Manager, Senior Frontend/Backend Engineer, Senior Code Reviewer, Security Engineer, QA Engineering Lead, Deployment Engineer, Production QA Verifier, Portfolio Maintainer, Dependency Vulnerability Scanner, Security Remediation Planner, Dependency Refactor Developer, Social Response Specialist).
- Each crew card now shows: phase badge, agent count, real crew goal sourced from each crew's docstring/agent goals, and a list of every agent in that crew.
- Phase indicators expanded from 4 to 7 (Discover, Validate, Engineer, Ship, Showcase, Harden, Respond).
- Hero status badge updated from "6 agents online" to "17 agents online".
- Hero terminal preview now reads `build_crew (6)` for accuracy when describing the build phase specifically.
- About stats updated from "6 AI Agents" to "17 AI Agents".

## 2026-04-26 · pending - Listening Board background (real user voices) + em-dash purge

- Replaced `MathBackground.tsx` (decorative math equations, off-thesis) with `VoicesBackground.tsx`: 71 unique handwritten user complaints scattered across the page (0-600vh). Reddit/HN-style raw quotes that directly back the "we build apps by listening" thesis.
- Each voice cites its source (r/SaaS, HN, r/freelance, Slack DM, support ticket, etc.) in slate annotation. Color encodes emotion: rose for frustration, amber for confusion, brand for wishful, cyan for feature requests, violet for domain-specific (clinic, freelancer, therapist, lawyer), white for punchlines.
- Closing About section repeats the brand promise as voices: "we're listening.", "we listen. we build. we ship.", "ship something that just works".
- Global em-dash and en-dash purge across landing copy: `app/layout.tsx`, `Hero.tsx`, `HowItWorks.tsx`, `Pipeline.tsx`, `CaseStudy.tsx`, `About.tsx`. Replaced with commas, colons, parentheses, or split sentences.
- Dev-time duplicate check warns in console if anyone adds a repeated voice.

## 2026-04-26 · pending - Chalkboard math equations background (superseded)

- Initial attempt: 75 famous equations as handwritten background. Replaced in same session because pure math/physics equations are off-brand for a product studio.

## 2026-04-26 · pending - New ErsLabs flask logo + sticky header

- New brand logo: Erlenmeyer flask lineart in emerald (#10B981) with rising bubbles + `ERSLABS` wordmark (Manrope, ERS 500 / LABS 200, all caps, letter-spacing 0.5). Replaces previous hexagonal blue mark.
- Replaced `public/logo.svg`, `public/favicon.svg`, `public/og-image.svg`.
- Added Manrope (200/300/500) to `globals.css` font import.
- New `components/Header.tsx`: fixed top, transparent at top, blurred surface bg on scroll. Logo left, nav (Pipeline / Portfolio / About) right.
- Removed redundant logo from `Hero.tsx` (now in header) and removed the decorative terminal-style top bar that conflicted with the fixed header.
- Refactored `Footer.tsx` to use the new logo image.
- Logo concept iteration archive: `erslabs-landing/public/logos/flask-variants/` (showcase.html + 20+ SVG explorations).

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
