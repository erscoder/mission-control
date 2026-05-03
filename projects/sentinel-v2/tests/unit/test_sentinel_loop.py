"""
Unit tests for sentinel_v2/flows/sentinel_loop.py

Validates state transitions, crew input construction, and helpers.
No real LLM calls — mocked crews.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, Mock, MagicMock
from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow, SentinelState


@pytest.fixture
def flow():
    """Fresh flow instance with empty state."""
    return SentinelLoopFlow()


class TestSentinelState:
    """Tests for SentinelState."""

    def test_default_state(self):
        s = SentinelState()
        assert s.cycle_count == 0
        assert s.current_phase == "research"
        assert s.approved is False
        assert s.deployed is False
        assert s.opportunities == []
        assert s.top_opportunity is None

    def test_state_is_pydantic_model(self):
        s = SentinelState(cycle_count=3, match_score=0.85)
        assert s.cycle_count == 3
        assert s.match_score == 0.85


class TestSentinelLoopFlowHelpers:
    """Tests for Flow helper methods."""

    def test_get_operator_capacity_returns_dict(self, flow):
        capacity = flow._get_operator_capacity()
        assert isinstance(capacity, dict)
        assert "build_window_hours" in capacity
        assert "delivery_stack" in capacity

    def test_parse_opportunities_with_list(self, flow):
        mock_result = Mock(spec=["raw"])
        mock_result.raw = [
            {"title": "Opportunity 1"},
            {"title": "Opportunity 2"},
        ]
        parsed = flow._parse_opportunities(mock_result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["title"] == "Opportunity 1"

    def test_parse_opportunities_with_no_raw(self, flow):
        mock_result = Mock(spec=[])
        parsed = flow._parse_opportunities(mock_result)
        assert parsed == []

    def test_parse_opportunities_with_dict(self, flow):
        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"error": "no results"}
        parsed = flow._parse_opportunities(mock_result)
        assert parsed == []

    def test_parse_match_result(self, flow):
        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"profile": {"name": "Kike"}, "score": 0.9}
        parsed = flow._parse_match_result(mock_result)
        assert parsed["score"] == 0.9

    def test_parse_deploy_result(self, flow):
        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"url": "https://example.com", "deployment_id": "abc123"}
        parsed = flow._parse_deploy_result(mock_result)
        assert parsed["url"] == "https://example.com"
        assert parsed["deployment_id"] == "abc123"


class TestWorkspaceFileManifest:
    """Tests for ``_workspace_file_manifest``: file inventory the build crew
    consumes on retries to patch instead of regenerate.
    """

    def test_returns_empty_for_missing_workspace(self, tmp_path):
        from sentinel_v2.flows.sentinel_loop import _workspace_file_manifest
        assert _workspace_file_manifest(str(tmp_path / "does_not_exist")) == {}

    def test_lists_authored_files_with_short_sha1(self, tmp_path):
        from sentinel_v2.flows.sentinel_loop import _workspace_file_manifest

        (tmp_path / "backend" / "src").mkdir(parents=True)
        (tmp_path / "backend" / "src" / "main.ts").write_text("hello")
        (tmp_path / "frontend" / "src").mkdir(parents=True)
        (tmp_path / "frontend" / "src" / "page.tsx").write_text("page")

        manifest = _workspace_file_manifest(str(tmp_path))
        assert "backend/src/main.ts" in manifest
        assert "frontend/src/page.tsx" in manifest
        # sha1 truncated to 12 chars
        assert len(manifest["backend/src/main.ts"]) == 12
        assert all(c in "0123456789abcdef" for c in manifest["backend/src/main.ts"])

    def test_skips_node_modules_dist_next_out_cache_git_coverage(self, tmp_path):
        from sentinel_v2.flows.sentinel_loop import _workspace_file_manifest

        (tmp_path / "backend" / "node_modules").mkdir(parents=True)
        (tmp_path / "backend" / "node_modules" / "pkg.js").write_text("noise")
        (tmp_path / "backend" / "dist").mkdir()
        (tmp_path / "backend" / "dist" / "main.js").write_text("compiled")
        (tmp_path / "frontend" / ".next").mkdir(parents=True)
        (tmp_path / "frontend" / ".next" / "build.json").write_text("{}")
        (tmp_path / "frontend" / "out").mkdir()
        (tmp_path / "frontend" / "out" / "index.html").write_text("static")
        (tmp_path / "frontend" / "node_modules" / ".cache").mkdir(parents=True)
        (tmp_path / "frontend" / "node_modules" / ".cache" / "babel.json").write_text("{}")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main")
        (tmp_path / "coverage").mkdir()
        (tmp_path / "coverage" / "lcov.info").write_text("data")
        (tmp_path / "backend" / "src").mkdir(parents=True, exist_ok=True)
        (tmp_path / "backend" / "src" / "keep.ts").write_text("kept")

        manifest = _workspace_file_manifest(str(tmp_path))
        assert "backend/src/keep.ts" in manifest
        for excluded in (
            "backend/node_modules/pkg.js",
            "backend/dist/main.js",
            "frontend/.next/build.json",
            "frontend/out/index.html",
            "frontend/node_modules/.cache/babel.json",
            ".git/HEAD",
            "coverage/lcov.info",
        ):
            assert excluded not in manifest, f"manifest should skip {excluded}"

    def test_skips_tsbuildinfo_files(self, tmp_path):
        from sentinel_v2.flows.sentinel_loop import _workspace_file_manifest
        (tmp_path / "backend").mkdir()
        (tmp_path / "backend" / "tsconfig.tsbuildinfo").write_text("stale")
        (tmp_path / "backend" / "tsconfig.build.tsbuildinfo").write_text("stale")
        (tmp_path / "backend" / "tsconfig.json").write_text("{}")

        manifest = _workspace_file_manifest(str(tmp_path))
        assert "backend/tsconfig.json" in manifest
        assert "backend/tsconfig.tsbuildinfo" not in manifest
        assert "backend/tsconfig.build.tsbuildinfo" not in manifest

    def test_truncates_with_sentinel_marker(self, tmp_path):
        from sentinel_v2.flows.sentinel_loop import _workspace_file_manifest
        d = tmp_path / "src"
        d.mkdir()
        for i in range(10):
            (d / f"f{i:02d}.ts").write_text(f"// {i}")

        manifest = _workspace_file_manifest(str(tmp_path), max_files=3)
        # 3 capped real files + 1 truncation sentinel
        assert "__truncated__" in manifest
        assert len([k for k in manifest if k != "__truncated__"]) == 3
        assert "+7 more files" in manifest["__truncated__"]


class TestSentinelLoopFlowKickoff:
    """Tests for full kickoff flow (with mocked crews)."""

    def test_kickoff_increments_cycle_count(self, flow):
        """kickoff() increments cycle_count."""
        assert flow.state.cycle_count == 0

        # CrewAI Flow stores method references in self._methods at init time.
        # Patch those directly so asyncio threads use the mocks.
        mock_research = Mock(return_value=None)
        mock_match = Mock(return_value=None)
        mock_build = Mock(return_value=None)
        mock_approval = Mock(return_value=None)
        mock_check = Mock(return_value=None)
        mock_deploy = Mock(return_value=None)

        orig_methods = dict(flow._methods)
        flow._methods.update({
            "run_research": mock_research,
            "run_match": mock_match,
            "run_build": mock_build,
            "request_approval": mock_approval,
            "check_approval": mock_check,
            "run_deploy": mock_deploy,
        })
        try:
            flow.kickoff()
        finally:
            flow._methods.clear()
            flow._methods.update(orig_methods)

        assert flow.state.cycle_count == 1

    def test_shutdown_stops_start_cycle(self, flow):
        """_shutdown_requested stops before running research."""
        flow._shutdown_requested = True
        with patch("signal.signal"):
            flow.start_cycle()
        assert flow._shutdown_requested is True

    def test_run_research_stores_opportunities(self, flow):
        """run_research() parses and stores top opportunity."""
        mock_result = Mock(spec=["raw"])
        mock_result.raw = [
            {"title": "Op A", "problem_statement": "A"},
            {"title": "Op B", "problem_statement": "B"},
        ]

        with patch(
            "sentinel_v2.crews.research_crew.research_crew.research_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_research()

        assert len(flow.state.opportunities) == 2
        assert flow.state.top_opportunity["title"] == "Op A"

    def test_source_urls_stored_in_opportunity_blob(self, flow):
        """run_research() persists source_urls via db.patch_phase."""
        mock_result = Mock(spec=["raw"])
        mock_result.raw = [
            {"title": "Op A", "problem_statement": "A", "source_urls": ["https://reddit.com/r/test"]},
        ]

        with patch(
            "sentinel_v2.crews.research_crew.research_crew.research_crew"
        ) as mock_crew_cls, \
             patch("sentinel_v2.dedup.filter_duplicates", side_effect=lambda c, **kw: (c, [])), \
             patch("sentinel_v2.db.patch_phase") as mock_patch:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_research()

            mock_patch.assert_called_once_with(
                flow.state.draft_id,
                "opportunity",
                {"source_urls": ["https://reddit.com/r/test"]},
            )

    def test_run_match_stores_score(self, flow):
        """run_match() updates user_profile and match_score."""
        flow.state.top_opportunity = {"title": "DeFi Tracker"}
        flow.state.user_profile = {}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"profile": {"name": "Kike", "skills": ["Python"]}, "score": 0.87}

        with patch(
            "sentinel_v2.crews.match_crew.match_crew.match_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_match()

        assert flow.state.match_score == 0.87
        assert flow.state.user_profile["name"] == "Kike"

    def test_run_build_stores_output(self, flow):
        """run_build() stores build_output."""
        flow.state.top_opportunity = {"title": "SaaS Tool"}
        flow.state.user_profile = {"name": "Kike"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = "Built: Next.js app with API"

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_build()

        assert "Next.js" in flow.state.build_output

    def test_run_deploy_skips_when_not_approved(self, flow):
        """run_deploy() skips if state.approved is False."""
        flow.state.approved = False
        flow.state.build_output = "some output"

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls:
            flow.run_deploy()
            mock_crew_cls.assert_not_called()

    def test_run_deploy_runs_when_approved(self, flow):
        """run_deploy() runs crew when approved.

        URL is now derived deterministically from slug (`<slug>.erslabs.net`),
        not from whatever the deploy crew reports — keeps the contract stable
        even if the agent invents a URL.
        """
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: SaaS app"
        flow.state.top_opportunity = {"title": "Opportunity"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"frontend_url": "https://opportunity.erslabs.net",
                           "deployment_id": "xyz", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_test",
                "price_id": "price_test",
                "price_ids": ["price_test"],
                "webhook_endpoint_id": "we_test",
                "webhook_secret": "whsec_test",
                "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://test_user:pw@h:5432/test_db",
                "database_name": "test_db",
                "database_user": "test_user",
                "already_attached": False,
            },
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_deploy()

            mock_crew.kickoff.assert_called_once()
        assert flow.state.deployed is True
        assert flow.state.deployed_url == "https://opportunity.erslabs.net"


class TestFlowLifecycle:
    """Tests for signal handling and lifecycle."""

    def test_signal_sets_shutdown(self, flow):
        """SIGTERM/SIGINT sets _shutdown_requested."""
        import signal

        flow._shutdown_requested = False
        with patch("signal.signal"):
            flow._on_signal(signal.SIGTERM, None)
        assert flow._shutdown_requested is True

    def test_kickoff_touches_state(self, flow):
        """kickoff() updates last_update."""
        mock_research = Mock(return_value=None)
        mock_match = Mock(return_value=None)
        mock_build = Mock(return_value=None)
        mock_approval = Mock(return_value=None)
        mock_check = Mock(return_value=None)
        mock_deploy = Mock(return_value=None)

        orig_methods = dict(flow._methods)
        flow._methods.update({
            "run_research": mock_research,
            "run_match": mock_match,
            "run_build": mock_build,
            "request_approval": mock_approval,
            "check_approval": mock_check,
            "run_deploy": mock_deploy,
        })
        try:
            flow.kickoff()
        finally:
            flow._methods.clear()
            flow._methods.update(orig_methods)

        assert flow.state.last_update != ""


class TestRequestApproval:
    """Tests for request_approval() phase."""

    def test_request_approval_sets_phase_and_pending_since(self, flow):
        """request_approval() sets current_phase and pending_since."""
        flow.state.cycle_count = 3
        flow.state.top_opportunity = {"title": "Test Opportunity"}
        flow.state.build_output = "Test build output"
        flow.state.build_ok = True  # required to pass health gate

        with patch.object(flow, "remember"):
            result = flow.request_approval()

        assert result == "pending"
        assert flow.state.current_phase == "approve"
        assert flow.state.pending_since != ""

    def test_request_approval_calls_remember(self, flow):
        """request_approval() stores approval pending in memory."""
        flow.state.cycle_count = 7
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.build_output = "output"
        flow.state.pending_since = "2026-04-23T10:00:00Z"
        flow.state.build_ok = True  # required to pass health gate

        with patch.object(flow, "remember") as mock_remember:
            flow.request_approval()

        mock_remember.assert_called()
        call_args = str(mock_remember.call_args)
        assert "pending approval" in call_args


class TestCheckApproval:
    """Tests for check_approval() — polls dashboard draft status."""

    def test_check_approval_returns_stop_when_no_draft_id(self, flow):
        """check_approval() returns 'stop' when no draft_id is set."""
        flow.state.draft_id = None
        with patch("sentinel_v2.dashboard_state.write_state"), \
             patch("sentinel_v2.dashboard_state.write_flow_breakdown"):
            result = flow.check_approval()
        assert result == "stop"

    def test_check_approval_auto_approve(self, flow):
        """check_approval() auto-approves when SENTINEL_AUTO_APPROVE=1."""
        flow.state.draft_id = "draft_c1_test"
        with patch("sentinel_v2.dashboard_state.write_state"), \
             patch("sentinel_v2.dashboard_state.write_flow_breakdown"), \
             patch.dict("os.environ", {"SENTINEL_AUTO_APPROVE": "1"}):
            result = flow.check_approval()
        assert result == "approved"
        assert flow.state.approved is True

    def test_check_approval_approved_via_dashboard(self, flow):
        """check_approval() returns 'approved' when user clicks Approve deploy.

        The wait now blocks on the user's intent statuses (pending_deploy /
        queued / rejected_deploy), not the runtime's terminal state.
        """
        flow.state.draft_id = "draft_c1_test"
        with patch("sentinel_v2.dashboard_state.write_state"), \
             patch("sentinel_v2.dashboard_state.write_flow_breakdown"), \
             patch("sentinel_v2.dashboard_state.wait_for_draft_status", return_value="pending_deploy"):
            result = flow.check_approval()
        assert result == "approved"
        assert flow.state.approved is True

    def test_check_approval_timeout_returns_stop(self, flow):
        """check_approval() returns 'stop' on timeout (wait_for_draft_status returns None)."""
        flow.state.draft_id = "draft_c1_test"
        with patch("sentinel_v2.dashboard_state.write_state"), \
             patch("sentinel_v2.dashboard_state.write_flow_breakdown"), \
             patch("sentinel_v2.dashboard_state.wait_for_draft_status", return_value=None):
            result = flow.check_approval()
        assert result == "stop"


class TestQAGateAndApprovalGate:
    """Regression tests for the daemon promotion gates added in 9fbf9aa."""

    def _patch_dashboard(self):
        return patch.multiple(
            "sentinel_v2.dashboard_state",
            write_state=Mock(),
            write_flow_breakdown=Mock(),
            update_draft=Mock(),
        )

    def test_request_approval_blocks_when_build_ok_false(self, flow):
        """Health gate marks draft failed and stops cycle when build_ok=False."""
        flow.state.draft_id = "draft_c1_test"
        flow.state.build_ok = False
        flow.state.cycle_count = 1
        with patch("sentinel_v2.dashboard_state.update_draft") as mock_update, \
             patch.object(flow, "_clear_checkpoint") as mock_clear:
            result = flow.request_approval()
        assert result == "stop"
        assert flow.state.current_phase != "approve"
        mock_update.assert_called_once()
        assert mock_update.call_args.kwargs.get("status") == "failed"
        mock_clear.assert_called_once()

    def test_request_approval_blocks_on_vulnerability_scan_error(self, flow):
        """Health gate blocks even with build_ok=True if security loop errored out."""
        flow.state.draft_id = "draft_c1_test"
        flow.state.build_ok = True
        flow.state.vulnerability_scan_error = "Could not reach 0 vulns after 5 iterations"
        with patch("sentinel_v2.dashboard_state.update_draft") as mock_update, \
             patch.object(flow, "_clear_checkpoint"):
            result = flow.request_approval()
        assert result == "stop"
        notes = mock_update.call_args.kwargs.get("revision_notes") or ""
        assert "Could not reach 0 vulns" in notes

    def test_security_loop_does_not_demote_when_field_missing(self, flow):
        """An iteration that omits build_ok must NOT clobber a True QA verdict.

        This is the fail-safe for the reviewer-flagged inversion bug: if
        the security crew never actually built (e.g. zero remediation
        actions, agent skips the verify step), parsed has no `build_ok`
        key. The flow must keep the QA gate's verdict instead of
        defaulting it to False and rejecting a legitimately-green draft.
        """
        flow.state.build_ok = True  # set by run_build's QA gate
        parsed = {"total_vulns_after": 0, "tests_ok": True}  # no build_ok
        # Mirror the persistence logic in run_security_remediation.
        if "build_ok" in parsed:
            flow.state.build_ok = flow.state.build_ok and bool(parsed.get("build_ok", False))
        assert flow.state.build_ok is True

    def test_security_loop_demotes_when_field_explicit_false(self, flow):
        """An explicit build_ok=False from the security crew vetoes QA's True."""
        flow.state.build_ok = True
        parsed = {"total_vulns_after": 0, "build_ok": False}
        if "build_ok" in parsed:
            flow.state.build_ok = flow.state.build_ok and bool(parsed.get("build_ok", False))
        assert flow.state.build_ok is False

    def test_qa_gate_fail_closed_on_unparseable_output(self, flow):
        """A QA Lead that returns prose (no go_no_go, no build_status) must
        fail the gate. Previously this defaulted to build_ok=True under the
        rationale that the security loop would catch real failures, but the
        security loop only validates dependency CVEs, not `npm run build`.
        Closed-by-default is the only way to guarantee broken drafts never
        reach the approval queue.
        """
        flow.state.draft_id = "draft_c1_qatest"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "Demo App"}
        flow.state.user_profile = {"name": "Kike"}

        # Crew returns prose, no JSON fields the gate looks at
        mock_result = Mock(spec=["raw"])
        mock_result.raw = "I have completed the build. All looks good."

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.dashboard_state.update_draft"
        ) as mock_update, patch.object(
            flow, "remember"
        ), patch.object(
            flow, "_clear_checkpoint"
        ) as mock_clear, patch.object(
            flow, "_parse_deploy_result", return_value={}
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew
            flow.run_build()

        assert flow.state.build_ok is False, "QA gate must fail-closed on unparseable output"
        assert flow.state.error == "build_failed_qa_gate_unparseable"
        # Draft marked failed, checkpoint cleared, shutdown requested for clean exit
        assert any(
            call.kwargs.get("status") == "failed" for call in mock_update.call_args_list
        ), "Draft must be marked failed when QA gate fails closed"
        mock_clear.assert_called_once()
        assert flow._shutdown_requested is True

    def test_qa_gate_accepts_explicit_go(self, flow):
        """An explicit GO + clean build_status promotes the draft."""
        flow.state.draft_id = "draft_c1_gotest"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "Demo App"}
        flow.state.user_profile = {"name": "Kike"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = '{"go_no_go": "GO", "build_status": "clean"}'

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.dashboard_state.update_draft"
        ), patch.object(flow, "remember"), patch.object(
            flow,
            "_parse_deploy_result",
            return_value={"go_no_go": "GO", "build_status": "clean"},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew
            flow.run_build()

        assert flow.state.build_ok is True


class TestExtractReviewCritical:
    """Defense-in-depth helper that re-parses Code Reviewer + Security
    Engineer task outputs so the QA gate cannot be hoodwinked by an LLM
    QA Lead that returns GO while criticals remain open.
    """

    def _task(self, agent_role: str, raw: str):
        t = Mock(spec=["agent", "raw", "pydantic", "json_dict"])
        t.agent = agent_role
        t.raw = raw
        t.pydantic = None
        t.json_dict = None
        return t

    def test_returns_zeros_when_no_tasks_output(self, flow):
        result = Mock(spec=["raw"])
        summary = flow._extract_review_critical(result)
        assert summary["code_review_critical"] == 0
        assert summary["security_critical"] == 0
        assert summary["matched_tasks"] == []

    def test_counts_code_review_critical_from_findings_array(self, flow):
        review_raw = (
            '{"go_no_go": "NO_GO", "issues_count": 3, '
            '"findings": ['
            '  {"severity": "critical", "file": "a.ts", "fix": "x"},'
            '  {"severity": "critical", "file": "b.ts", "fix": "y"},'
            '  {"severity": "high", "file": "c.ts", "fix": "z"}'
            ']}'
        )
        result = Mock(spec=["tasks_output"])
        result.tasks_output = [self._task("Senior Code Reviewer", review_raw)]
        summary = flow._extract_review_critical(result)
        assert summary["code_review_critical"] == 2
        assert summary["security_critical"] == 0

    def test_counts_security_critical_from_severity_map(self, flow):
        sec_raw = (
            '{"go_no_go": "NO_GO", '
            '"vulnerability_count_by_severity": {"critical": 4, "high": 1}, '
            '"findings": []}'
        )
        result = Mock(spec=["tasks_output"])
        result.tasks_output = [self._task("Security Engineer", sec_raw)]
        summary = flow._extract_review_critical(result)
        assert summary["security_critical"] == 4
        assert summary["code_review_critical"] == 0

    def test_treats_no_go_with_no_count_as_one_critical(self, flow):
        review_raw = '{"go_no_go": "NO_GO", "notes": "see report"}'
        result = Mock(spec=["tasks_output"])
        result.tasks_output = [self._task("Senior Code Reviewer", review_raw)]
        summary = flow._extract_review_critical(result)
        assert summary["code_review_critical"] == 1

    def test_ignores_unrelated_agents(self, flow):
        review_raw = '{"go_no_go": "NO_GO", "critical": 5}'
        result = Mock(spec=["tasks_output"])
        result.tasks_output = [self._task("Senior Frontend Engineer", review_raw)]
        summary = flow._extract_review_critical(result)
        assert summary["code_review_critical"] == 0
        assert summary["security_critical"] == 0

    def test_qa_gate_override_on_review_critical(self, flow):
        """QA Lead says GO but Code Reviewer reports critical>0: force fail."""
        flow.state.draft_id = "draft_c1_override_review"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "Demo App"}
        flow.state.user_profile = {"name": "Kike"}

        review_task = Mock(spec=["agent", "raw", "pydantic", "json_dict"])
        review_task.agent = "Senior Code Reviewer"
        review_task.raw = (
            '{"go_no_go": "NO_GO", '
            '"findings": [{"severity": "critical", "file": "x.ts", "fix": "y"}]}'
        )
        review_task.pydantic = None
        review_task.json_dict = None

        mock_result = Mock(spec=["raw", "tasks_output"])
        mock_result.raw = '{"go_no_go": "GO", "build_status": "clean"}'
        mock_result.tasks_output = [review_task]

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.dashboard_state.update_draft"
        ), patch.object(flow, "remember"), patch.object(
            flow, "_clear_checkpoint"
        ), patch.object(
            flow,
            "_parse_deploy_result",
            return_value={"go_no_go": "GO", "build_status": "clean"},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew
            flow.run_build()

        assert flow.state.build_ok is False
        assert flow.state.error == "build_failed_qa_gate_critical_override"
        assert flow._shutdown_requested is True

    def test_qa_gate_override_on_security_critical(self, flow):
        """QA Lead says GO but Security Engineer reports critical>0: force fail."""
        flow.state.draft_id = "draft_c1_override_sec"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "Demo App"}
        flow.state.user_profile = {"name": "Kike"}

        sec_task = Mock(spec=["agent", "raw", "pydantic", "json_dict"])
        sec_task.agent = "Security Engineer"
        sec_task.raw = (
            '{"go_no_go": "NO_GO", '
            '"vulnerability_count_by_severity": {"critical": 2, "high": 0}}'
        )
        sec_task.pydantic = None
        sec_task.json_dict = None

        mock_result = Mock(spec=["raw", "tasks_output"])
        mock_result.raw = '{"go_no_go": "GO", "build_status": "clean"}'
        mock_result.tasks_output = [sec_task]

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.dashboard_state.update_draft"
        ), patch.object(flow, "remember"), patch.object(
            flow, "_clear_checkpoint"
        ), patch.object(
            flow,
            "_parse_deploy_result",
            return_value={"go_no_go": "GO", "build_status": "clean"},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew
            flow.run_build()

        assert flow.state.build_ok is False
        assert flow.state.error == "build_failed_qa_gate_critical_override"
        assert flow._shutdown_requested is True


class TestEscalationOnUnrecoverableErrors:
    """Build/deploy retry loops escalate on unrecoverable errors instead of
    burning the full retry budget on something only the operator can fix.
    """

    def test_build_escalates_on_429_and_skips_retries(self, flow, tmp_path, monkeypatch):
        """A 429 rate-limit during build halts on attempt 1, no further retries."""
        monkeypatch.setattr(
            "sentinel_v2.flows.error_classifier.ESCALATION_FILE",
            tmp_path / "esc.json",
        )

        flow.state.draft_id = "draft_c1_429"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "RateLimited App"}
        flow.state.user_profile = {"name": "Kike"}

        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = Exception(
            "Error code: 429 - rate_limit_error from upstream provider"
        )
        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew",
            return_value=mock_crew,
        ), patch(
            "sentinel_v2.dashboard_state.update_draft"
        ) as mock_update, patch.object(flow, "remember"):
            flow.run_build()

        # Only ONE attempt — escalation skips remaining retries
        assert mock_crew.kickoff.call_count == 1
        assert flow.state.build_attempts == 1
        assert flow.state.error.startswith("escalated:")
        # Draft marked blocked, not failed
        statuses = [c.kwargs.get("status") for c in mock_update.call_args_list]
        assert "blocked" in statuses
        # Escalation file written
        esc_file = tmp_path / "esc.json"
        assert esc_file.exists()
        # Shutdown flag set so the @listen chain stops here. Without this the
        # cycle continued into security + approval + deploy on a workspace
        # that never produced a clean build (observed live: 5 security iters
        # grinding on build_ok=False before the deploy gate finally rejected).
        assert flow._shutdown_requested is True

    def test_build_recoverable_error_still_retries(self, flow, tmp_path, monkeypatch):
        """A normal code error must NOT trigger escalation — full retry budget used."""
        monkeypatch.setattr(
            "sentinel_v2.flows.error_classifier.ESCALATION_FILE",
            tmp_path / "esc.json",
        )

        flow.state.draft_id = "draft_c1_recoverable"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "App"}
        flow.state.user_profile = {"name": "Kike"}

        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = Exception("ERESOLVE peer dep mismatch")
        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew",
            return_value=mock_crew,
        ), patch("sentinel_v2.dashboard_state.update_draft"), patch.object(
            flow, "remember"
        ):
            flow.run_build()

        # Used the full retry budget (3 by default), not escalated on attempt 1
        from sentinel_v2.flows.sentinel_loop import MAX_BUILD_RETRIES
        assert mock_crew.kickoff.call_count == MAX_BUILD_RETRIES
        assert not flow.state.error.startswith("escalated:")


class TestRouter:
    """Tests for route_after_approval() router."""

    def test_router_returns_deploy_when_approved(self, flow):
        """Router returns 'deploy' when approved."""
        flow.state.approved = True
        flow._shutdown_requested = False
        result = flow.route_after_approval()
        assert result == "deploy"

    def test_router_returns_stop_when_not_approved(self, flow):
        """Router returns 'stop' when not approved."""
        flow.state.approved = False
        flow._shutdown_requested = False
        result = flow.route_after_approval()
        assert result == "stop"

    def test_router_returns_stop_when_shutdown_requested(self, flow):
        """Router returns 'stop' when shutdown requested."""
        flow.state.approved = True
        flow._shutdown_requested = True
        result = flow.route_after_approval()
        assert result == "stop"


class TestWriteState:
    """Tests for write_state calls in each phase."""

    def test_run_research_calls_write_state(self, flow):
        """run_research() calls write_state (research and research_completed)."""
        mock_result = Mock()
        mock_result.raw = [{"title": "Op A", "problem_statement": "A"}]

        with patch(
            "sentinel_v2.crews.research_crew.research_crew.research_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                with patch(
                    "sentinel_v2.dashboard_state.write_state"
                ) as mock_ws:
                    flow.run_research()

        # write_state is called twice: once at start of research, once after
        assert mock_ws.call_count == 2
        phases = [c.kwargs["phase"] for c in mock_ws.call_args_list]
        assert "research" in phases
        assert "research_completed" in phases

    def test_run_match_calls_write_state(self, flow):
        """run_match() calls write_state (match and match_completed)."""
        flow.state.top_opportunity = {"title": "Op"}
        mock_result = Mock()
        mock_result.raw = {"profile": {}, "score": 0.8}

        with patch(
            "sentinel_v2.crews.match_crew.match_crew.match_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                with patch(
                    "sentinel_v2.dashboard_state.write_state"
                ) as mock_ws:
                    flow.run_match()

        phases = [c.kwargs["phase"] for c in mock_ws.call_args_list]
        assert "match" in phases
        assert "match_completed" in phases

    def test_run_build_calls_write_state(self, flow):
        """run_build() calls write_state (build and build_completed).

        Mocks the QA gate parse so the closed-by-default gate sees a positive
        GO signal — otherwise the gate stops the cycle before build_completed
        is written. The intent of this test is the write_state emission, not
        the gate behavior (covered separately).
        """
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.user_profile = {}
        mock_result = Mock()
        mock_result.raw = '{"go_no_go": "GO", "build_status": "clean"}'

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch.object(
            flow,
            "_parse_deploy_result",
            return_value={"go_no_go": "GO", "build_status": "clean"},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                with patch(
                    "sentinel_v2.dashboard_state.write_state"
                ) as mock_ws:
                    flow.run_build()

        phases = [c.kwargs["phase"] for c in mock_ws.call_args_list]
        assert "build" in phases
        assert "build_completed" in phases

    def test_run_deploy_calls_write_state(self, flow):
        """run_deploy() calls write_state for deploy phase."""
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}
        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"url": "https://example.com", "deployment_id": "abc", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                with patch(
                    "sentinel_v2.dashboard_state.write_state"
                ) as mock_ws:
                    flow.run_deploy()

        phases = [c.kwargs["phase"] for c in mock_ws.call_args_list]
        assert "deploy" in phases


class TestRememberCalls:
    """Tests for self.remember() calls in each phase."""

    def test_run_match_calls_remember(self, flow):
        """run_match() stores match result in CrewAI memory."""
        flow.state.top_opportunity = {"title": "Op"}
        mock_result = Mock()
        mock_result.raw = {"profile": {}, "score": 0.8}

        with patch(
            "sentinel_v2.crews.match_crew.match_crew.match_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember") as mock_remember:
                flow.run_match()

        mock_remember.assert_called()

    def test_run_build_calls_remember(self, flow):
        """run_build() stores build result in CrewAI memory.

        QA gate is closed-by-default; mock _parse_deploy_result so the gate
        sees a positive GO and the flow reaches the remember() call.
        """
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.user_profile = {}
        mock_result = Mock()
        mock_result.raw = '{"go_no_go": "GO", "build_status": "clean"}'

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch.object(
            flow,
            "_parse_deploy_result",
            return_value={"go_no_go": "GO", "build_status": "clean"},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember") as mock_remember:
                flow.run_build()

        mock_remember.assert_called()

    def test_run_deploy_calls_remember(self, flow):
        """run_deploy() stores deployment result in CrewAI memory."""
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}
        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"url": "https://example.com", "deployment_id": "abc", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_t", "price_id": "price_t",
                "price_ids": ["price_t"], "webhook_endpoint_id": "we_t",
                "webhook_secret": "whsec_t", "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://t_user:pw@h:5432/t_db",
                "database_name": "t_db",
                "database_user": "t_user",
                "already_attached": False,
            },
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember") as mock_remember:
                flow.run_deploy()

        mock_remember.assert_called()


class TestFeedbackLoop:
    """Tests for the feedback loop: revision_notes flow and deploy URL validation."""

    def test_start_cycle_reads_revision_notes_from_draft(self, flow):
        """start_cycle() reads revision_notes from a queued draft."""
        mock_draft = {
            "id": "draft_c1_test",
            "title": "Test App",
            "revision_notes": "Fix the login page",
            "status": "queued",
            "tech_fit": 0.8,
            "complexity": 3,
        }
        with patch("sentinel_v2.dashboard_state.list_drafts_by_status", return_value=[mock_draft]), \
             patch("sentinel_v2.dashboard_state.clear_agent_messages"):
            flow.start_cycle()

        assert flow.state.revision_notes == "Fix the login page"
        assert flow.state.draft_id == "draft_c1_test"

    def test_start_cycle_clears_revision_notes_when_none(self, flow):
        """start_cycle() sets revision_notes to None when draft has none."""
        mock_draft = {
            "id": "draft_c1_test",
            "title": "Test App",
            "revision_notes": None,
            "status": "queued",
            "tech_fit": 0.8,
            "complexity": 3,
        }
        with patch("sentinel_v2.dashboard_state.list_drafts_by_status", return_value=[mock_draft]), \
             patch("sentinel_v2.dashboard_state.clear_agent_messages"):
            flow.start_cycle()

        assert flow.state.revision_notes is None

    def test_start_cycle_clears_revision_notes_for_new_draft(self, flow):
        """A queued draft with a different id than the previous cycle's draft
        must NOT inherit stale revision_notes from state."""
        # Prior draft id and stale notes survived in state but cycle_count=0
        # keeps the is_resume guard False so start_cycle proceeds into the
        # new-cycle path and triggers the diff check.
        flow.state.cycle_count = 0
        flow.state.draft_id = "draft_c1_old"
        flow.state.revision_notes = "stale notes from rejected draft A"

        new_draft = {
            "id": "draft_c2_new",
            "title": "Fresh App",
            "revision_notes": None,
            "status": "queued",
            "tech_fit": 0.7,
            "complexity": 2,
        }
        with patch("sentinel_v2.dashboard_state.list_drafts_by_status", return_value=[new_draft]), \
             patch("sentinel_v2.dashboard_state.clear_agent_messages"), \
             patch.object(flow, "_save_checkpoint"):
            flow.start_cycle()

        assert flow.state.draft_id == "draft_c2_new"
        assert flow.state.revision_notes is None

    def test_start_cycle_preserves_on_same_queued_draft(self, flow):
        """When the same draft id is re-queued (retry button on the same
        draft), the draft's revision_notes win, but if the draft has none,
        state's existing notes are preserved (same draft, same context)."""
        flow.state.cycle_count = 0
        flow.state.draft_id = "draft_c1_same"
        flow.state.revision_notes = "user feedback to address"

        same_draft = {
            "id": "draft_c1_same",
            "title": "Same App",
            "revision_notes": None,
            "status": "queued",
            "tech_fit": 0.7,
            "complexity": 2,
        }
        with patch("sentinel_v2.dashboard_state.list_drafts_by_status", return_value=[same_draft]), \
             patch("sentinel_v2.dashboard_state.clear_agent_messages"), \
             patch.object(flow, "_save_checkpoint"):
            flow.start_cycle()

        assert flow.state.revision_notes == "user feedback to address"

    def test_start_cycle_handles_no_previous_draft(self, flow):
        """First-ever cycle has prev_draft_id=None and revision_notes=None,
        and must not crash."""
        first_draft = {
            "id": "draft_c1_first",
            "title": "First App",
            "revision_notes": "initial feedback",
            "status": "queued",
            "tech_fit": 0.6,
            "complexity": 1,
        }
        with patch("sentinel_v2.dashboard_state.list_drafts_by_status", return_value=[first_draft]), \
             patch("sentinel_v2.dashboard_state.clear_agent_messages"), \
             patch.object(flow, "_save_checkpoint"):
            flow.start_cycle()

        assert flow.state.draft_id == "draft_c1_first"
        assert flow.state.revision_notes == "initial feedback"

    def test_start_cycle_clears_revision_notes_when_no_queued_draft(self, flow):
        """Research-path fall-through: no queued draft, but state still
        carries stale revision_notes from a previous draft. start_cycle must
        clear them so the upcoming research-driven build does not chase
        ghosts."""
        flow.state.cycle_count = 0
        flow.state.draft_id = "draft_c1_old"
        flow.state.revision_notes = "stale notes from rejected deploy"

        with patch("sentinel_v2.dashboard_state.list_drafts_by_status", return_value=[]), \
             patch("sentinel_v2.dashboard_state.clear_agent_messages"):
            flow.start_cycle()

        assert flow.state.revision_notes is None

    def test_run_build_passes_revision_notes_in_inputs(self, flow):
        """run_build() passes revision_notes to crew.kickoff inputs."""
        flow.state.top_opportunity = {"title": "SaaS Tool"}
        flow.state.revision_notes = "Fix the auth flow"

        mock_result = Mock(spec=["raw"])
        mock_result.raw = "Built: SaaS app"

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_build()

            inputs = mock_crew.kickoff.call_args.kwargs.get("inputs") or mock_crew.kickoff.call_args[1].get("inputs", {})
            assert inputs["revision_notes"] == "Fix the auth flow"

    def test_run_build_passes_empty_revision_notes_when_none(self, flow):
        """run_build() passes empty string when revision_notes is None."""
        flow.state.top_opportunity = {"title": "SaaS Tool"}
        flow.state.revision_notes = None

        mock_result = Mock(spec=["raw"])
        mock_result.raw = "Built: SaaS app"

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_build()

            inputs = mock_crew.kickoff.call_args.kwargs.get("inputs") or mock_crew.kickoff.call_args[1].get("inputs", {})
            assert inputs["revision_notes"] == ""

    def test_run_deploy_fails_without_frontend_url(self, flow):
        """run_deploy() marks draft as failed when crew returns no frontend_url."""
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.draft_id = "draft_c1_test"

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"deployment_id": "abc", "go_no_go": "GO"}  # No url or frontend_url

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_t", "price_id": "price_t",
                "price_ids": ["price_t"], "webhook_endpoint_id": "we_t",
                "webhook_secret": "whsec_t", "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://t_user:pw@h:5432/t_db",
                "database_name": "t_db",
                "database_user": "t_user",
                "already_attached": False,
            },
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"), \
                 patch("sentinel_v2.dashboard_state.update_draft") as mock_update:
                flow.run_deploy()

            assert flow.state.deployed is False
            assert "did not return a real frontend URL" in (flow.state.error or "")
            mock_update.assert_called()
            last_call = mock_update.call_args_list[-1]
            assert last_call.kwargs.get("status") == "failed"

    def test_run_deploy_succeeds_with_frontend_url(self, flow):
        """run_deploy() succeeds when crew confirms a frontend_url.

        deployed_url is the slug-derived canonical URL (`op.erslabs.net`),
        not whatever string the crew returned — keeps DNS predictable.
        """
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"frontend_url": "https://op.erslabs.net",
                           "deployment_id": "abc", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_t", "price_id": "price_t",
                "price_ids": ["price_t"], "webhook_endpoint_id": "we_t",
                "webhook_secret": "whsec_t", "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://t_user:pw@h:5432/t_db",
                "database_name": "t_db",
                "database_user": "t_user",
                "already_attached": False,
            },
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_deploy()

        assert flow.state.deployed is True
        assert flow.state.deployed_url == "https://op.erslabs.net"

    def test_run_deploy_succeeds_with_url_key(self, flow):
        """run_deploy() also accepts 'url' key as fallback for frontend_url."""
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"url": "https://op.erslabs.net",
                           "deployment_id": "xyz", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_t", "price_id": "price_t",
                "price_ids": ["price_t"], "webhook_endpoint_id": "we_t",
                "webhook_secret": "whsec_t", "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://t_user:pw@h:5432/t_db",
                "database_name": "t_db",
                "database_user": "t_user",
                "already_attached": False,
            },
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_deploy()

        assert flow.state.deployed is True
        assert flow.state.deployed_url == "https://op.erslabs.net"


class TestParseExceptions:
    """Tests for exception handling in parse methods."""

    def test_parse_opportunities_exception(self, flow):
        """_parse_opportunities returns [] on exception."""
        mock_result = Mock()
        del mock_result.raw  # accessing raises AttributeError
        # When raw attribute access raises an exception
        def raise_on_raw():
            raise RuntimeError("crew result error")
        type(mock_result).raw = property(raise_on_raw)

        result = flow._parse_opportunities(mock_result)
        assert result == []

    def test_parse_match_result_exception(self, flow):
        """_parse_match_result returns {} on exception."""
        mock_result = Mock()
        del mock_result.raw
        def raise_on_raw():
            raise RuntimeError("crew result error")
        type(mock_result).raw = property(raise_on_raw)

        result = flow._parse_match_result(mock_result)
        assert result == {}

    def test_parse_deploy_result_exception(self, flow):
        """_parse_deploy_result returns {} on exception."""
        mock_result = Mock()
        del mock_result.raw
        def raise_on_raw():
            raise RuntimeError("crew result error")
        type(mock_result).raw = property(raise_on_raw)

        result = flow._parse_deploy_result(mock_result)
        assert result == {}


class TestModuleLevelKickoff:
    """Tests for module-level kickoff() and plot() in sentinel_loop.py."""

    def test_module_kickoff_calls_flow_kickoff(self):
        """Module-level kickoff() creates flow and kicks it off."""
        with patch(
            "sentinel_v2.flows.sentinel_loop.SentinelLoopFlow"
        ) as mock_flow_cls:
            mock_flow = MagicMock()
            mock_flow_cls.return_value = mock_flow

            from sentinel_v2.flows.sentinel_loop import kickoff
            kickoff()

            mock_flow_cls.assert_called_once()
            mock_flow.kickoff.assert_called_once()

    def test_module_plot_calls_flow_plot(self):
        """Module-level plot() creates flow and plots it."""
        with patch(
            "sentinel_v2.flows.sentinel_loop.SentinelLoopFlow"
        ) as mock_flow_cls:
            mock_flow = MagicMock()
            mock_flow_cls.return_value = mock_flow

            from sentinel_v2.flows.sentinel_loop import plot
            plot()

            mock_flow.plot.assert_called_once()


class TestBuildRetryLoop:
    """Tests for the automatic build retry feedback loop."""

    def test_build_retries_on_failure_then_succeeds(self, flow):
        """Build fails once, then succeeds on second attempt."""
        flow.state.top_opportunity = {"title": "SaaS Tool"}
        flow.state.user_profile = {"name": "Kike"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = "Built: app"

        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [RuntimeError("npm ci failed"), mock_result]

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew",
            return_value=mock_crew,
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            with patch.object(flow, "remember"):
                flow.run_build()

        assert flow.state.build_output is not None
        assert flow.state.build_attempts == 2
        assert mock_crew.kickoff.call_count == 2
        # Second call should include error feedback in revision_notes
        second_call_inputs = mock_crew.kickoff.call_args_list[1].kwargs["inputs"]
        assert "npm ci failed" in second_call_inputs["revision_notes"]

    def test_build_exhausts_retries_marks_failed(self, flow):
        """Build fails all retries and marks draft as failed."""
        flow.state.top_opportunity = {"title": "Broken App"}
        flow.state.draft_id = "draft_test_retry"

        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = RuntimeError("persistent failure")

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew",
            return_value=mock_crew,
        ), patch("sentinel_v2.dashboard_state.update_draft") as mock_update:
            with patch.object(flow, "remember"):
                flow.run_build()

        assert flow.state.build_output is None
        assert flow.state.error is not None
        assert "persistent failure" in flow.state.error
        # Should have tried MAX_BUILD_RETRIES times
        from sentinel_v2.flows.sentinel_loop import MAX_BUILD_RETRIES
        assert flow.state.build_attempts == MAX_BUILD_RETRIES
        # Last update_draft should set status=failed
        final_call = mock_update.call_args_list[-1]
        assert final_call.kwargs.get("status") == "failed"
        assert "persistent failure" in final_call.kwargs.get("revision_notes", "")

    def test_build_first_attempt_succeeds_no_retry(self, flow):
        """Build succeeds on first try — no retry needed."""
        flow.state.top_opportunity = {"title": "Good App"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = "Built: good app"
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = mock_result

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew",
            return_value=mock_crew,
        ), patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ):
            with patch.object(flow, "remember"):
                flow.run_build()

        assert flow.state.build_attempts == 1
        assert flow.state.build_output is not None
        assert mock_crew.kickoff.call_count == 1


class TestDeployRetryLoop:
    """Tests for the automatic deploy retry feedback loop."""

    def test_deploy_retries_on_rollback_then_succeeds(self, flow):
        """Deploy gets ROLLBACK, retries, then succeeds."""
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Opportunity"}

        rollback_result = Mock(spec=["raw"])
        rollback_result.raw = {"go_no_go": "ROLLBACK", "failing_step": "health check"}

        success_result = Mock(spec=["raw"])
        success_result.raw = {"frontend_url": "https://opportunity.erslabs.net",
                              "deployment_id": "xyz", "go_no_go": "GO"}

        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = [rollback_result, success_result]

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew",
            return_value=mock_crew,
        ), patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_t", "price_id": "price_t",
                "price_ids": ["price_t"], "webhook_endpoint_id": "we_t",
                "webhook_secret": "whsec_t", "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://t_user:pw@h:5432/t_db",
                "database_name": "t_db",
                "database_user": "t_user",
                "already_attached": False,
            },
        ):
            with patch.object(flow, "remember"):
                flow.run_deploy()

        assert flow.state.deployed is True
        assert flow.state.deploy_attempts == 2

    def test_deploy_exhausts_retries_marks_failed(self, flow):
        """Deploy fails all retries."""
        flow.state.approved = True
        flow.state.build_ok = True  # required to pass deploy health gate
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Opportunity"}
        flow.state.draft_id = "draft_deploy_retry"

        mock_crew = MagicMock()
        mock_crew.kickoff.side_effect = RuntimeError("fly deploy failed")

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew",
            return_value=mock_crew,
        ), patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_t", "price_id": "price_t",
                "price_ids": ["price_t"], "webhook_endpoint_id": "we_t",
                "webhook_secret": "whsec_t", "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://t_user:pw@h:5432/t_db",
                "database_name": "t_db",
                "database_user": "t_user",
                "already_attached": False,
            },
        ), patch("sentinel_v2.dashboard_state.update_draft") as mock_update:
            with patch.object(flow, "remember"):
                flow.run_deploy()

        assert flow.state.deployed is False
        from sentinel_v2.flows.sentinel_loop import MAX_DEPLOY_RETRIES
        assert flow.state.deploy_attempts == MAX_DEPLOY_RETRIES
        final_call = mock_update.call_args_list[-1]
        assert final_call.kwargs.get("status") == "failed"


class TestPostBuildRebake:
    """Pin the post-crew re-bake of protected template files in run_build.

    The build agent has the write_file tool and routinely clobbers protected
    sources (Stripe controller, Prisma module, tsconfig, package.json, etc.)
    despite the prompt forbidding it. Observed live: a rewritten Stripe
    controller pinned ``apiVersion: '2024-06-20'`` against the canonical
    ``stripe@14.25.0`` typing that requires ``'2023-10-16'``, killing
    ``nest build`` with TS2322. The fix re-runs ``_prebake_deploy_files``
    after ``crew.kickoff()`` succeeds so every protected file is reverted to
    canonical before the verification gate runs.
    """

    def test_run_build_calls_prebake_twice(self, flow):
        flow.state.top_opportunity = {"title": "Demo App"}
        flow.state.user_profile = {}
        mock_result = Mock()
        mock_result.raw = '{"go_no_go": "GO", "build_status": "clean"}'

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ) as mock_prebake, patch(
            "sentinel_v2.flows.sentinel_loop._verify_npm_build",
            return_value={"ok": True, "first_failure": None, "details": {}},
        ), patch.object(
            flow,
            "_parse_deploy_result",
            return_value={"go_no_go": "GO", "build_status": "clean"},
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_build()

        # Once before crew (existing behavior), once after crew (new defense).
        assert mock_prebake.call_count == 2, (
            f"Expected 2 prebake calls (pre-crew + post-crew rebake), "
            f"got {mock_prebake.call_count}"
        )


class TestVerifyPackageJsonUnchanged:
    """Tests for _verify_package_json_unchanged hook-based revert helper."""

    def _canonical_for(self, slug, stack="node_nestjs"):
        """Return the slug-substituted template bytes (what _prebake writes)."""
        from pathlib import Path
        import sentinel_v2.flows.sentinel_loop as mod
        template = (
            Path(mod.__file__).resolve().parent.parent
            / "data" / "deploy_templates" / stack / "package.json"
        )
        return template.read_text().replace("{{SLUG}}", slug)

    def test_verify_package_json_unchanged_returns_true_when_match(self, tmp_path):
        """Workspace package.json matches canonical -> True, no rewrite."""
        from sentinel_v2.flows.sentinel_loop import _verify_package_json_unchanged

        # Use a workspace whose basename is a known slug; the helper recovers
        # slug from the file's "name" field which lines up with this.
        ws = tmp_path / "myslug"
        backend = ws / "backend"
        backend.mkdir(parents=True)
        canonical = self._canonical_for("myslug")
        (backend / "package.json").write_text(canonical)
        original_mtime = (backend / "package.json").stat().st_mtime_ns

        result = _verify_package_json_unchanged(str(ws))

        assert result is True
        # File untouched
        assert (backend / "package.json").stat().st_mtime_ns == original_mtime
        assert (backend / "package.json").read_text() == canonical

    def test_verify_package_json_unchanged_returns_false_when_diverged(self, tmp_path, caplog):
        """Workspace package.json diverged -> False, WARNING logged, file re-baked to canonical."""
        import logging
        from sentinel_v2.flows.sentinel_loop import _verify_package_json_unchanged

        ws = tmp_path / "myslug"
        backend = ws / "backend"
        backend.mkdir(parents=True)
        canonical = self._canonical_for("myslug")
        # Agent wrote a clobbered package.json. Keep the "name" field so the
        # helper recovers slug correctly when picking the canonical to compare.
        clobbered = '{"name": "myslug-backend", "dependencies": {"express": "^4.0.0"}}'
        (backend / "package.json").write_text(clobbered)
        assert (backend / "package.json").read_text() != canonical

        with caplog.at_level(logging.WARNING, logger="sentinel_v2.flow"):
            result = _verify_package_json_unchanged(str(ws))

        assert result is False
        # Re-baked to canonical (slug-substituted)
        assert (backend / "package.json").read_text() == canonical
        # WARNING logged with both hashes
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("diverged" in r.getMessage() for r in warnings)
        assert any("sha256" in r.getMessage() for r in warnings)

    def test_verify_package_json_unchanged_returns_false_when_missing(self, tmp_path, caplog):
        """Workspace lacks package.json (agent never created it) -> False, WARN, file re-baked."""
        import logging
        from sentinel_v2.flows.sentinel_loop import _verify_package_json_unchanged

        ws = tmp_path / "myslug"
        backend = ws / "backend"
        backend.mkdir(parents=True)
        # No package.json present
        assert not (backend / "package.json").exists()

        with caplog.at_level(logging.WARNING, logger="sentinel_v2.flow"):
            result = _verify_package_json_unchanged(str(ws))

        assert result is False
        # Re-baked from template using workspace dir basename as slug fallback
        canonical = self._canonical_for("myslug")
        assert (backend / "package.json").exists()
        assert (backend / "package.json").read_text() == canonical
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("missing" in r.getMessage() for r in warnings)


class TestRunDeployHealthGate:
    """Tests for run_deploy()'s health gate (Step 9 / F3.1).

    Sits after the early-returns and before current_phase is flipped to
    "deploy". Mirrors request_approval()'s gate.
    """

    def test_run_deploy_refuses_when_build_ok_false(self, flow):
        """build_ok=False blocks deploy even with approved=True."""
        flow.state.approved = True
        flow.state.build_ok = False
        flow.state.draft_id = "draft_c1_broken_build"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "Broken App"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.dashboard_state.update_draft"
        ) as mock_update, patch.object(
            flow, "_clear_checkpoint"
        ) as mock_clear:
            flow.run_deploy()

        # Deploy crew never instantiated
        mock_crew_cls.assert_not_called()
        # Draft marked failed with the reason in the notes
        mock_update.assert_called_once()
        kwargs = mock_update.call_args.kwargs
        assert kwargs.get("status") == "failed"
        assert "build_ok=False" in (kwargs.get("revision_notes") or "")
        # Cycle terminated cleanly
        mock_clear.assert_called_once()
        assert flow._shutdown_requested is True
        assert flow.state.deployed is False
        assert flow.state.current_phase != "deploy"

    def test_run_deploy_refuses_when_security_scan_errored(self, flow):
        """vulnerability_scan_error set blocks deploy even with build_ok=True."""
        flow.state.approved = True
        flow.state.build_ok = True
        flow.state.vulnerability_scan_error = "osv-scanner crashed"
        flow.state.draft_id = "draft_c1_scan_err"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "Scan Crash App"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.dashboard_state.update_draft"
        ) as mock_update, patch.object(
            flow, "_clear_checkpoint"
        ) as mock_clear:
            flow.run_deploy()

        mock_crew_cls.assert_not_called()
        notes = mock_update.call_args.kwargs.get("revision_notes") or ""
        assert "osv-scanner crashed" in notes
        assert mock_update.call_args.kwargs.get("status") == "failed"
        mock_clear.assert_called_once()
        assert flow._shutdown_requested is True
        assert flow.state.deployed is False

    def test_run_deploy_passes_when_healthy(self, flow):
        """Both flags clean: gate does NOT trigger and deploy logic proceeds."""
        flow.state.approved = True
        flow.state.build_ok = True
        flow.state.vulnerability_scan_error = None
        flow.state.draft_id = "draft_c1_healthy"
        flow.state.cycle_count = 1
        flow.state.top_opportunity = {"title": "Healthy App"}
        flow.state.build_output = "Built: Healthy App"

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {
            "frontend_url": "https://healthy-app.erslabs.net",
            "deployment_id": "dep-xyz",
            "go_no_go": "GO",
        }

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls, patch(
            "sentinel_v2.flows.sentinel_loop._prebake_deploy_files",
            return_value={},
        ), patch(
            "sentinel_v2.flows.sentinel_loop._provision_stripe_resources",
            return_value={
                "product_id": "prod_t", "price_id": "price_t",
                "price_ids": ["price_t"], "webhook_endpoint_id": "we_t",
                "webhook_secret": "whsec_t", "secret_was_rotated": False,
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.ensure_shared_pg_cluster",
            return_value={
                "cluster_name": "sentinel-shared-pg",
                "region": "fra",
                "created": False,
                "source": "state",
            },
        ), patch(
            "sentinel_v2.flows.shared_postgres.attach_db_for_app",
            return_value={
                "database_url": "postgres://t_user:pw@h:5432/t_db",
                "database_name": "t_db",
                "database_user": "t_user",
                "already_attached": False,
            },
        ), patch(
            "sentinel_v2.dashboard_state.update_draft"
        ) as mock_update, patch.object(
            flow, "remember"
        ):
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew
            flow.run_deploy()

            # Deploy crew was actually invoked: gate did NOT short-circuit
            mock_crew.kickoff.assert_called_once()

        # Healthy path landed in deploy state, not failed
        assert flow.state.deployed is True
        assert flow._shutdown_requested is False
        # No update_draft call carries status="failed" from the gate path
        for call in mock_update.call_args_list:
            assert call.kwargs.get("status") != "failed"
