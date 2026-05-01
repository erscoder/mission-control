# Review Request - Step 1 (F1.1 state file path drift)

Ready for Review: YES

**Commit (code):** `3ede94f` - `fix(sentinel-v2): resolve state file paths via SENTINEL_TMPDIR`
**Commit (changelog):** appended below this file's commit; hash captured in CHANGELOG.md and at the end of this doc.
**Diff size:** 95 lines net, 2 files (1 source, 1 new test). Well under the 150-line cap.

---

## What Was Built

`flows/error_classifier.py` defaulted `ESCALATION_FILE` to `/tmp/sentinel_v2_escalations.json`, ignoring the `SENTINEL_TMPDIR=/tmp/sentinel_shared` mount in `docker-compose.yml`. Inside the container that path lives on the ephemeral overlayfs, so every restart wiped the escalation history. Added an exported `resolve_state_path(filename, *, env_override=None)` helper with precedence `env_override > SENTINEL_TMPDIR > /tmp` and routed `ESCALATION_FILE` through it. Helper stays exported (no underscore) so Step 5+ can reuse it without circular imports.

## Files Changed

| File | Lines | Change |
|---|---|---|
| `src/sentinel_v2/flows/error_classifier.py` | 11-13 | Module docstring updated to describe the new resolution behavior. |
| `src/sentinel_v2/flows/error_classifier.py` | 32-66 | New `resolve_state_path` helper; `ESCALATION_FILE` rebuilt through it (still resolved at import time so existing monkeypatches in `test_error_classifier.py:107` and `test_sentinel_loop.py:509,544` keep working unmodified). |
| `tests/unit/test_state_paths.py` | 1-60 | New unit test file. 4 cases per the brief: SENTINEL_TMPDIR honored, /tmp fallback, env_override precedence, returns Path not str. |

## Audit Results (rg `/tmp/sentinel_v2`)

Pre-edit grep returned 5 production matches:

| File | Line | Status |
|------|------|--------|
| `src/sentinel_v2/flows/error_classifier.py` | 11 | Docstring; updated. |
| `src/sentinel_v2/flows/error_classifier.py` | 34 | The actual hardcoded default; FIXED. |
| `src/sentinel_v2/crew_hooks.py` | 4 | Docstring only. |
| `src/sentinel_v2/crew_hooks.py` | 50 | `_safe_path` docstring comment. |
| `src/sentinel_v2/dashboard_state.py` | 31 | `_safe_path` docstring comment. |

`crew_hooks.py`, `dashboard_state.py`, and `dashboard/app.py` already resolve `_TMP_DIR = Path(os.environ.get("SENTINEL_TMPDIR", "/tmp"))` at module load and derive every state file from it. They are NOT broken today and were intentionally left untouched to keep the patch surgical (per brief: "DO NOT broaden scope"). Migrating them to call `resolve_state_path` would be a consistency follow-up, not a bug fix.

## Verification

- `uv run pytest -x -q tests/unit/test_state_paths.py tests/unit/test_error_classifier.py tests/unit/test_sentinel_loop.py` -> 89 passed (4 new + 85 pre-existing).
- `uv run pytest -q tests/unit/ tests/integration/` -> 314 passed. Baseline was 278 unit + 32 integration; after +4 new in unit this is 282 + 32 = 314 as expected.
- Full `uv run pytest -x -q` shows the **pre-existing** e2e failure `tests/e2e/test_sentinel_loop_e2e.py::TestFlowEventChain::test_flow_runs_deploy_phase_when_approved`. Re-ran on `HEAD~` via `git stash` and reproduced the identical `Failed to resolve 'host.docker.internal'` Langfuse OTel error. Unrelated to this change; tracked under F3.5 / F4.1 in the master plan.

## Open Questions

- None blocking. Helper signature matches the brief verbatim.
- The advisor flagged precedence order as the load-bearing test case; covered by `test_env_override_wins_over_sentinel_tmpdir`.

## Known Gaps Logged

- None new. Boundary held: did NOT touch F1.2 (Jinja `%{http_code}`), F1.3 (orphan drafts), F1.4 (QA JSON), F2.x - F4.x. All queued in the master plan in order.
- The three already-correct writers (`dashboard_state.py`, `crew_hooks.py`, `dashboard/app.py`) are NOT a gap; they work today because they read `SENTINEL_TMPDIR` directly. Migrating them to the helper is a tidiness follow-up if Arch wants it, not a deferred bug.

---

## Changelog Pointer

`CHANGELOG.md` updated under `[Unreleased]` with a new entry dated `2026-04-28 . 3ede94f`, ordered above the Langfuse v4 entry (`f623a51`) per the brief's DoD.
