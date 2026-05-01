# Build Log
*Owned by Architect. Updated by Builder after each step.*

---

## Current Status

**Active step:** Step 1 - F1.1 state file path drift - PENDING REVIEW
**Last cleared:** none
**Pending deploy:** NO (per brief: ships in next image rebuild, not now)

---

## Step History

### Step 1 - Resolve state file paths via SENTINEL_TMPDIR (F1.1) - PENDING REVIEW
*Date: 2026-04-28*

Files changed:
- `src/sentinel_v2/flows/error_classifier.py` - new `resolve_state_path` helper, `ESCALATION_FILE` routed through it
- `tests/unit/test_state_paths.py` - new file, 4 unit tests pinning the precedence contract
- `CHANGELOG.md` - new `[Unreleased]` entry

Decisions made:
- Helper exported from `error_classifier.py` (matches brief, avoids new module).
- Three already-correct writers (`dashboard_state.py`, `crew_hooks.py`, `dashboard/app.py`) left untouched to keep patch surgical. Documented in REVIEW-REQUEST.
- `ESCALATION_FILE` resolved at import time so existing monkeypatch tests work unmodified.

Reviewer findings: pending
Deploy: deferred (next image rebuild)

---

## Known Gaps
*Logged here instead of fixed. Addressed in a future step.*

- **KG-N** — [Description] — logged [date]

---

## Architecture Decisions
*Locked decisions that cannot be changed without breaking the system.*

- [Decision — date]
