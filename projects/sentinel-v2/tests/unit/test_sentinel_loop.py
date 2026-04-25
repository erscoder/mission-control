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
        ) as mock_crew_cls:
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
        """run_deploy() runs crew when approved."""
        flow.state.approved = True
        flow.state.build_output = "Built: SaaS app"
        flow.state.top_opportunity = {"title": "Opportunity"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"url": "https://example.com", "deployment_id": "xyz", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_deploy()

            mock_crew.kickoff.assert_called_once()
        assert flow.state.deployed is True
        assert flow.state.deployed_url == "https://example.com"


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
        """check_approval() returns 'approved' when draft reaches 'deployed' status."""
        flow.state.draft_id = "draft_c1_test"
        with patch("sentinel_v2.dashboard_state.write_state"), \
             patch("sentinel_v2.dashboard_state.write_flow_breakdown"), \
             patch("sentinel_v2.dashboard_state.wait_for_draft_status", return_value="deployed"):
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
        """run_build() calls write_state (build and build_completed)."""
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.user_profile = {}
        mock_result = Mock()
        mock_result.raw = "Built: SaaS app"

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls:
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
        """run_build() stores build result in CrewAI memory."""
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.user_profile = {}
        mock_result = Mock()
        mock_result.raw = "Built: SaaS"

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember") as mock_remember:
                flow.run_build()

        mock_remember.assert_called()

    def test_run_deploy_calls_remember(self, flow):
        """run_deploy() stores deployment result in CrewAI memory."""
        flow.state.approved = True
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

    def test_run_build_passes_revision_notes_in_inputs(self, flow):
        """run_build() passes revision_notes to crew.kickoff inputs."""
        flow.state.top_opportunity = {"title": "SaaS Tool"}
        flow.state.revision_notes = "Fix the auth flow"

        mock_result = Mock(spec=["raw"])
        mock_result.raw = "Built: SaaS app"

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_cls:
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
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_build()

            inputs = mock_crew.kickoff.call_args.kwargs.get("inputs") or mock_crew.kickoff.call_args[1].get("inputs", {})
            assert inputs["revision_notes"] == ""

    def test_run_deploy_fails_without_frontend_url(self, flow):
        """run_deploy() marks draft as failed when no frontend_url is returned."""
        flow.state.approved = True
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.draft_id = "draft_c1_test"

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"deployment_id": "abc", "go_no_go": "GO"}  # No url or frontend_url

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"), \
                 patch("sentinel_v2.dashboard_state.update_draft") as mock_update:
                flow.run_deploy()

            assert flow.state.deployed is False
            assert "did not return a real frontend URL" in (flow.state.error or "")
            mock_update.assert_called()
            # Last call should mark draft as failed
            last_call = mock_update.call_args_list[-1]
            assert last_call.kwargs.get("status") == "failed"

    def test_run_deploy_succeeds_with_frontend_url(self, flow):
        """run_deploy() succeeds when frontend_url is returned."""
        flow.state.approved = True
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"frontend_url": "https://myapp.erslabs.net", "deployment_id": "abc", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_deploy()

        assert flow.state.deployed is True
        assert flow.state.deployed_url == "https://myapp.erslabs.net"

    def test_run_deploy_succeeds_with_url_key(self, flow):
        """run_deploy() also accepts 'url' key as fallback for frontend_url."""
        flow.state.approved = True
        flow.state.build_output = "Built: app"
        flow.state.top_opportunity = {"title": "Op"}

        mock_result = Mock(spec=["raw"])
        mock_result.raw = {"url": "https://myapp.example.com", "deployment_id": "xyz", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_deploy()

        assert flow.state.deployed is True
        assert flow.state.deployed_url == "https://myapp.example.com"


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
