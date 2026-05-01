# Build Log
*Owned by Architect. Updated by Builder after each step.*

---

## Current Status

**Active step:** Final - rebuild + e2e verify (in flight).
**Last cleared:** Steps 1-11 (all 11 plan steps shipped, all reviewer-approved).
**Pending deploy:** rebuild in progress, restart pending.

---

## Step History

### Step 1 - Resolve state file paths via SENTINEL_TMPDIR (F1.1) - SHIPPED
*Date: 2026-05-01*. Commits: `3ede94f`, `729244d`, `fdb336f`, `8bd0af0` (em-dash purge per Richard).
Reviewer: NEEDS WORK (em-dash) -> resolved -> APPROVED.

### Step 2 - Bulk-fail orphan drafts (F1.3) - DONE (operator one-shot)
*Date: 2026-05-01*. SQL UPDATE on sentinel.db cleared 13 stale `pending` drafts blocking research.

### Step 3 - Escape http_code Jinja interpolation (F1.2) - SHIPPED
*Date: 2026-05-01*. Commits: `f072a30` (code), changelog pin.

### Step 4 - QA Lead Pydantic output schema (F1.4) - SHIPPED
*Date: 2026-05-01*. Commits: `84ff29b` (code) + `4234fbd` (changelog). Reviewer: APPROVED.

### Step 5 - Transient network patterns in error_classifier (F2.1) - SHIPPED
*Date: 2026-05-01*. Commits: `10a2180` (code) + `6822686` (changelog). Reviewer: APPROVED.

### Step 6 - Reset revision_notes on new draft cycle (F2.2) - SHIPPED
*Date: 2026-05-01*. Commits: `7fd43de` (code) + `37525d5` (changelog). Reviewer: APPROVED.

### Step 7 - Hook-based revert of package.json drift (F2.3) - SHIPPED
*Date: 2026-05-01*. Commits: `84fd4bb` (code) + `6ced9b4` (changelog) + `3a501f0` (em-dash purge per Richard).
Reviewer: NEEDS WORK (em-dash) -> resolved -> APPROVED.

### Step 8 - Pin Langfuse to >=4.5,<5.0 (F2.4) - SHIPPED
*Date: 2026-05-01*. Commits: `95d9dc4` (deps) + `ad0cbbb` (changelog) + `69d9269` (date correction per Richard).
Reviewer: NEEDS WORK (date drift) -> resolved -> APPROVED.

### Step 9 - Health gate before run_deploy (F3.1) - SHIPPED
*Date: 2026-05-01*. Commits: `c608f07` (code) + `3d28681` (changelog). Reviewer: APPROVED.

### Step 10 - Sentinel healthcheck + SQLite WAL/busy_timeout=30s (F3.2/F3.3) - SHIPPED
*Date: 2026-05-01*. Commits: `f883c81` (code) + `63e91db` (changelog). Reviewer: APPROVED.

### Step 11 - Strict prebake + OTel flush timeout (F3.4/F3.5) - SHIPPED
*Date: 2026-05-01*. Commits: `5953139` (code) + `484c3aa` (changelog). Reviewer: APPROVED.

### Final - Rebuild + e2e verify (in flight)
Rebuild in progress. Will restart sentinel + flask, run a cycle, verify state files + traces + no errors.

---

## Test Suite Health

After every step the unit suite was green under `LANGFUSE_ENABLED=false uv run pytest -x -q tests/unit/`. Final count: 326 (was 278 at session start, +48 net).

---

## Known Gaps

- **KG-1**: synapseia langfuse-web OTel ingestion intermittently returns 500. Pipeline traces lost. Not blocking; mitigated by Step 11's 2s flush timeout. Tracked as plan F4.1, owned by synapseia-network maintainer. Logged 2026-05-01.
- **KG-2**: Pre-existing e2e test `test_flow_runs_deploy_phase_when_approved` fails on hosts where `host.docker.internal` does not resolve. Reproduced on `HEAD~`. Mitigated by Step 11's 2s OTel timeout cap. Logged 2026-05-01.

---

## Architecture Decisions

- 2026-05-01: Path resolution for state files goes through `resolve_state_path(filename, *, env_override=None)` exported from `flows/error_classifier.py`, with precedence `env_override > $SENTINEL_TMPDIR > /tmp`. Future state writers should call this helper rather than rebuilding the env-resolution logic.
- 2026-05-01: Curl format specs in CrewAI Task descriptions must double their braces (`%{{http_code}}`). Same rule applies to any literal `{}` content destined for the agent prompt that should not be interpolated.
- 2026-05-01: QA Lead task uses `output_pydantic=QAGateReport`. CrewAI rejects non-JSON output and retries. The flow gate consumes structured `{go_no_go, build_status, blocking_issues}` and only promotes a draft on explicit `GO` + `clean`/`warnings`.
- 2026-05-01: Transient network errors (`ECONNREFUSED`, `ECONNRESET`, etc.) are classified as `transient_network` and retried with feedback, not escalated. Operator never sees them in the escalation file.
- 2026-05-01: `revision_notes` is reset to None at `start_cycle` only when the queued draft id differs from the previous cycle's. Resume preserves human revision feedback.
- 2026-05-01: `_verify_package_json_unchanged` runs after every successful build, sha256-comparing against the canonical template. On divergence: WARN log + re-bake. Build is never failed by this check; the deploy phase re-bakes again.
- 2026-05-01: `langfuse>=4.5,<5.0` pinned. Rebuilds will not silently jump major versions and break tracing.
- 2026-05-01: `run_deploy` has a health gate mirroring `request_approval`. A draft with `vulnerability_scan_error` or `not build_ok` cannot reach Fly/CF.
- 2026-05-01: `sentinel` Docker service has a healthcheck probing `/tmp/sentinel_shared/sentinel_v2_state.json` mtime. SQLite uses `timeout=30` + WAL + `busy_timeout=30000` + `synchronous=NORMAL` on every connection.
- 2026-05-01: `_prebake_deploy_files` raises `FileNotFoundError` instead of silently skipping. OTel exporter timeout capped at 2000 ms via env vars set BEFORE the langfuse import.
