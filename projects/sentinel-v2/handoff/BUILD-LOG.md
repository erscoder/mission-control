# Build Log
*Owned by Architect. Updated by Builder after each step.*

---

## Current Status

**Active step:** Step 1 + Step 3 (F1.2) shipped. Waiting on dashboard approval to verify build/deploy phases end-to-end.
**Last cleared:** Step 1 (F1.1) and Step 3 (F1.2). Step 2 (operator one-shot) executed.
**Pending deploy:** N/A (changes already live in running container).

---

## Step History

### Step 1 - Resolve state file paths via SENTINEL_TMPDIR (F1.1) - SHIPPED
*Date: 2026-04-28*

Files changed:
- `src/sentinel_v2/flows/error_classifier.py` - new `resolve_state_path` helper, `ESCALATION_FILE` routed through it
- `tests/unit/test_state_paths.py` - new file, 4 unit tests pinning the precedence contract
- `CHANGELOG.md` - new `[Unreleased]` entry
- `handoff/BUILD-LOG.md` - em-dash purge (Arch follow-up commit `8bd0af0`)

Commits: `3ede94f` (code), `729244d` (changelog), `fdb336f` (handoff), `8bd0af0` (em-dash purge per Richard's review).
Reviewer verdict: NEEDS WORK (em-dashes), resolved by Arch in `8bd0af0`. Re-check passed.
Deploy: live in running sentinel container (rebuild + restart at 13:24 local).

### Step 2 - Bulk-fail orphan drafts to unblock research (F1.3) - DONE (operator one-shot)
*Date: 2026-04-28*

13 drafts in `pending` from prior cycles were blocking new research (`SENTINEL_RESEARCH_PAUSE_THRESHOLD=6`). UPDATE statement on `sentinel.db` set status to `failed` with revision_notes "Auto-failed by Arch on 2026-04-28: pre-fix backlog cleared to unblock research. Click Retry to start fresh." After clear: 19 failed, 11 rejected, 0 pending. Research resumed on next cycle.

### Step 3 - Escape http_code Jinja interpolation in deploy verify task (F1.2) - SHIPPED
*Date: 2026-04-28*

Files changed:
- `src/sentinel_v2/crews/deploy_crew/deploy_crew.py:204` - escaped `%{http_code}` to `%{{http_code}}` so `str.format(**inputs)` renders the literal `%{http_code}` curl needs.
- `CHANGELOG.md` - new `[Unreleased]` entry

Commits: `f072a30` (code), changelog commit pinned hash `f072a30`.
Test impact: 282 unit tests green (up from 278: +4 from Step 1). No new tests added for this single-line escape; the next deploy attempt is the runtime verification.
Deploy: live in running sentinel container (second rebuild + restart at 13:30 local).

---

## Runtime Verification (post-Step 3)

After rebuild + restart, cycle 1 entered `Phase 1: RESEARCH` cleanly at 11:30:48. Research crew produced a structured opportunity list and persisted draft `draft_c1_reconcilepm-auto-reconciliation-for-smal` at 11:39:58. Flow then advanced to `wait_for_draft_approval`, holding for human action via the dashboard. End-to-end verification of build/deploy phases is gated on operator approval (intentional design).

Observed warning: OTel exporter retries to `host.docker.internal:3700` returning Internal Server Error from the synapseia langfuse-web instance. Tracked under F4.1 (synapseia stack instability). Not blocking sentinel pipeline; tracing degrades silently.

---

## Known Gaps

- **KG-1**: Synapseia langfuse-web OTel ingestion intermittently returns 500. Pipeline traces lost. Tracked as plan F4.1, owned by synapseia-network maintainer. Logged 2026-04-28.
- **KG-2**: Pre-existing e2e test `test_flow_runs_deploy_phase_when_approved` fails on hosts where `host.docker.internal` does not resolve. Reproduced on `HEAD~`. Not introduced by Step 1 / Step 3. Tracked as F3.5. Logged 2026-04-28.

---

## Architecture Decisions

- 2026-04-28: Path resolution for state files goes through `resolve_state_path(filename, *, env_override=None)` exported from `flows/error_classifier.py`, with precedence `env_override > $SENTINEL_TMPDIR > /tmp`. Future state writers should call this helper rather than rebuilding the env-resolution logic.
- 2026-04-28: Curl format specs in CrewAI Task descriptions must double their braces (`%{{http_code}}`). Same rule applies to any literal `{}` content destined for the agent prompt that should not be interpolated.
