"""Security Remediation Crew — osv-scanner → plan → apply → verify.

Sequential process:
  1. Vulnerability Scanner runs osv-scanner on backend + frontend, produces a
     merged JSON report.
  2. Remediation Planner reads the report and produces a per-package action
     plan: upgrade, downgrade, replace, or accept_risk.
  3. Refactor Developer applies the plan (edits package.json, runs npm
     install, refactors code for breaking changes, fixes tests, re-runs build).

The crew is driven in a loop by ``SentinelLoopFlow.run_security_remediation``
until vulnerability_count == 0 and build is green (or max iterations reached).
"""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full
from sentinel_v2.tools import (
    ListFilesTool,
    OsvScannerTool,
    RunShellTool,
    WriteFileTool,
)


def security_remediation_crew() -> Crew:
    """Create the remediation crew — one iteration of scan → plan → apply."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)

    osv_scan = OsvScannerTool()
    write_file = WriteFileTool()
    list_files = ListFilesTool()
    run_shell = RunShellTool()

    scanner = Agent(
        role="Dependency Vulnerability Scanner",
        goal=(
            "Produce a single, merged vulnerability report for the backend and frontend "
            "subdirectories of the workspace. Report MUST be the exact JSON returned by "
            "osv_scan (concatenated)."
        ),
        backstory=(
            "You are the gatekeeper between a freshly-built MVP and its first paying customer. "
            "You run osv_scan(scan_dir='<workspace>/backend') and osv_scan(scan_dir='<workspace>/frontend'), "
            "then merge the outputs into one report with total counts across both.\n\n"
            "You never interpret severities yourself — you pass OSV's labels through unchanged so "
            "the planner can reason about them."
        ),
        tools=[osv_scan, list_files],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    planner = Agent(
        role="Security Remediation Planner",
        goal=(
            "Turn a vulnerability report into a concrete per-package action plan that, if applied, "
            "results in zero known vulnerabilities."
        ),
        backstory=(
            "You are a senior security engineer who has triaged thousands of Dependabot-style alerts. "
            "Your rules for each finding:\n\n"
            "1. If `fix_versions` is non-empty → `strategy: 'upgrade'` to the MINIMUM version that "
            "   patches it (prefer the smallest SemVer bump). Note expected breaking changes.\n"
            "2. If `fix_versions` is empty → `strategy: 'downgrade'` to a version PRIOR to when the "
            "   vuln was introduced. You infer that from the affected ranges embedded in OSV IDs. "
            "   Specify the exact target version.\n"
            "3. If the package is unmaintained (no fix in 12+ months and no viable downgrade) → "
            "   `strategy: 'replace'` with a concrete, maintained alternative. Only suggest libs "
            "   with >1k weekly downloads and recent activity.\n"
            "4. If none of the above are safe (kernel-level vuln, etc.) → `strategy: 'accept_risk'` "
            "   with a one-paragraph justification the approver can read.\n\n"
            "Output a strict JSON object: {\"actions\": [{\"package\", \"ecosystem\", \"current\", "
            "\"target\", \"strategy\", \"breaking_changes\": [], \"risk\": \"low|medium|high\"}, ...]}. "
            "No prose outside the JSON."
        ),
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    developer = Agent(
        role="Dependency Refactor Developer",
        goal=(
            "Apply the remediation plan. After you finish, the project MUST build and tests MUST "
            "pass. If they do not, you iterate on the same plan until they do or you hit the "
            "budget."
        ),
        backstory=(
            "You are a senior full-stack engineer who has migrated dozens of projects across major "
            "framework versions. Your workflow per action:\n\n"
            "1. Update the manifest with `write_file` — `package.json` for npm/pnpm, "
            "   `requirements.txt` / `pyproject.toml` for Python, `Cargo.toml` for Rust.\n"
            "2. Run `run_shell('npm install', cwd=<scan_dir>)` (or the ecosystem's equivalent). "
            "   Capture the output; if it fails, adjust and retry.\n"
            "3. Run `run_shell('npm run build', cwd=<scan_dir>)`. If build fails due to breaking "
            "   changes (deprecated APIs, renamed exports), read the erroring files with "
            "   list_files + write the fixes with write_file. Use the planner's breaking_changes "
            "   hints.\n"
            "4. Run `run_shell('npm test', cwd=<scan_dir>)`. If tests fail, fix the tests (update "
            "   fixtures, mocks, snapshots — whatever is stale).\n"
            "5. After all actions are applied, produce a final JSON status: "
            "   {\"actions_applied\": <int>, \"build_ok\": <bool>, \"tests_ok\": <bool>, "
            "   \"total_vulns_after\": <int>, \"touched_files\": [...], \"notes\": \"...\"}.\n\n"
            "You never skip the build step. A green scan with a broken build is a regression, "
            "not a fix."
        ),
        tools=[write_file, list_files, run_shell],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    scan_task = Task(
        description=(
            "Scan the workspace for dependency vulnerabilities.\n\n"
            "INPUT: workspace_dir={workspace_dir}; iteration={iteration}/{max_iterations}; "
            "draft_id={draft_id}.\n\n"
            "STEPS:\n"
            "1. Run `osv_scan(scan_dir='{workspace_dir}/backend')` if that directory exists.\n"
            "2. Run `osv_scan(scan_dir='{workspace_dir}/frontend')` if that directory exists.\n"
            "3. Merge the two JSON outputs into a single report: sum totals, concatenate findings, "
            "   keep per-finding `scan_dir` so the developer knows which subdir to fix.\n"
            "4. Return the merged JSON VERBATIM. Do not add commentary."
        ),
        expected_output=(
            "A single JSON object with shape {\"total\": int, \"counts\": {...}, \"findings\": [...]}. "
            "Each finding must include `scan_dir` so the developer can act on it."
        ),
        agent=scanner,
    )

    plan_task = Task(
        description=(
            "Read the scanner's report (available to you through the task context) and output a "
            "remediation plan using the 4-rule playbook in your backstory.\n\n"
            "If the report shows `total == 0`, output `{\"actions\": []}` — no work needed.\n\n"
            "Otherwise, produce one action per distinct (package, ecosystem). If multiple CVEs "
            "affect the same package, consolidate into a single action targeting the version that "
            "fixes ALL of them.\n\n"
            "Output JSON ONLY — no markdown fences, no prose."
        ),
        expected_output=(
            "JSON object {\"actions\": [{\"package\", \"ecosystem\", \"current\", \"target\", "
            "\"strategy\" ∈ {upgrade|downgrade|replace|accept_risk}, \"breaking_changes\": [strings], "
            "\"risk\": \"low|medium|high\", \"reason\": \"...\"}]}"
        ),
        agent=planner,
        context=[scan_task],
    )

    apply_task = Task(
        description=(
            "Apply the plan from the context to `{workspace_dir}`. Work inside the backend and "
            "frontend subdirectories as appropriate per finding.\n\n"
            "For EACH action with strategy `upgrade`, `downgrade`, or `replace`:\n"
            "  1. Edit the manifest(s) (`package.json` etc.) via `write_file`.\n"
            "  2. Run `npm install` in the right subdir via `run_shell`.\n"
            "  3. If the action has `breaking_changes`, read the relevant source files and write "
            "     fixed versions via `write_file`.\n\n"
            "For each action with strategy `accept_risk`: skip the code changes but record the "
            "package + reason in `notes`.\n\n"
            "After ALL actions are applied:\n"
            "  - Run `npm run build` in backend and frontend. Capture success/failure.\n"
            "  - Run `npm test` where tests exist. Fix failing tests — they are usually stale "
            "    mocks or snapshots after a dep bump.\n"
            "  - Re-run `osv_scan` on both subdirs. Sum the new `total`.\n\n"
            "Return a final JSON with:\n"
            "{\"actions_applied\": int, \"total_vulns_after\": int, \"build_ok\": bool, "
            "\"tests_ok\": bool, \"touched_files\": [str], \"notes\": str}"
        ),
        expected_output=(
            "JSON with actions_applied (int), total_vulns_after (int), build_ok (bool), "
            "tests_ok (bool), touched_files (list of relative paths), notes (string summary)."
        ),
        agent=developer,
        context=[scan_task, plan_task],
    )

    crew = Crew(
        agents=[scanner, planner, developer],
        tasks=[scan_task, plan_task, apply_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )

    crew = hook_crew_full(crew, phase="security", cycle=1)
    return crew
