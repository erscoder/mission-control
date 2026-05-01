# Review Request - Step 7 (F2.3)

Ready for Review: YES
Builder: Bob
Date: 2026-04-30

## Step

Step 7 - Hook-based revert of `backend/package.json` drift after the build crew runs.

## Commits

- `84fd4bb` fix(sentinel-v2): hook-based revert of package.json drift (F2.3)
- (changelog commit follows immediately)

## Files changed

- `src/sentinel_v2/flows/sentinel_loop.py`
  - Line 10: `import hashlib` added.
  - Lines 82-141: new helper `_verify_package_json_unchanged(workspace_dir, stack="node_nestjs") -> bool` placed immediately after `_prebake_deploy_files` per brief.
  - Call site inside `run_build` (right after the retry-loop success `break`, before `qa_parsed = self._parse_deploy_result(result)`), wrapped in `try/except Exception` so the helper can never blow up the build.
- `tests/unit/test_sentinel_loop.py` lines 1224-1303: new `TestVerifyPackageJsonUnchanged` class with 3 tests.
- `CHANGELOG.md`: new entry pinned at `84fd4bb`, above the F2.2 entry.
- `handoff/BUILD-LOG.md`: Step 7 history entry.

Net diff: 160 lines (78 production + 82 tests). Under the 200 ceiling.

## Summary of change

The `build_crew` prompt forbids the backend Lead from rewriting `backend/package.json`, but the agent still has the `write_file` tool. Prompt-only enforcement is brittle: a clobbered NestJS matrix means ERESOLVE deadlocks at deploy time. The deploy phase already re-bakes defensively, but the QA gate sees the post-build artifact in between and a NO-GO there hides the root cause.

`_verify_package_json_unchanged` computes sha256 of the workspace `backend/package.json` vs the slug-substituted canonical template at `data/deploy_templates/<stack>/package.json`. On match: returns True, file untouched. On divergence or missing: WARNING log with both hashes plus the offending path, then re-bake via `_prebake_deploy_files`, return False. Never raises.

Slug recovery: the helper signature in the brief omits `slug`, so the helper recovers it from the workspace pkg's `name` field (`<slug>-backend`, written by `_prebake_deploy_files` from the template's `"name": "{{SLUG}}-backend"`). If the JSON is missing or unreadable, falls back to `Path(workspace_dir).name` so the re-bake still produces a stable name. Both paths are covered by tests.

## Test evidence

`LANGFUSE_ENABLED=false uv run pytest -x -q tests/unit/` -> `314 passed` (311 prior + 3 new). Local run on 2026-04-30, ~87s.

`TestVerifyPackageJsonUnchanged` alone -> 3 passed in ~5s.

## Open questions

1. Slug recovery via `name` field: I followed the brief signature verbatim (no slug param). At the call site `slug` is in scope and could have been threaded; if Richard prefers that, it is a 1-line change to add `slug=slug` and drop the JSON-parse fallback.
2. The helper's return value is informational; nobody consumes it. Could be wired into a counter or `state` flag in a follow-up if drift telemetry is wanted.

## Known gaps

None introduced. Unrelated dirty files in the worktree predate this step.

## Scope lock

No touches outside `_prebake_deploy_files` neighborhood (helper + call site + import), `TestVerifyPackageJsonUnchanged`, CHANGELOG, BUILD-LOG. Did not modify agent tools (revoking `write_file` was explicitly out of scope per brief).
