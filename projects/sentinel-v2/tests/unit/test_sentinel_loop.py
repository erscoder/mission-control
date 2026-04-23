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

    def test_get_kike_profile_returns_dict(self, flow):
        profile = flow._get_kike_profile()
        assert isinstance(profile, dict)
        assert profile["name"] == "Kike (Enrique Rubio)"
        assert "@kikerub" in profile["twitter"]

    def test_parse_opportunities_with_list(self, flow):
        mock_result = Mock()
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
        mock_result = Mock()
        mock_result.raw = {"error": "no results"}
        parsed = flow._parse_opportunities(mock_result)
        assert parsed == []

    def test_parse_match_result(self, flow):
        mock_result = Mock()
        mock_result.raw = {"profile": {"name": "Kike"}, "score": 0.9}
        parsed = flow._parse_match_result(mock_result)
        assert parsed["score"] == 0.9

    def test_parse_deploy_result(self, flow):
        mock_result = Mock()
        mock_result.raw = {"url": "https://example.com", "deployment_id": "abc123"}
        parsed = flow._parse_deploy_result(mock_result)
        assert parsed["url"] == "https://example.com"
        assert parsed["deployment_id"] == "abc123"

    def test_build_approval_summary(self, flow):
        flow.state.cycle_count = 5
        flow.state.top_opportunity = {
            "title": "AI Code Review Tool",
            "problem_statement": "Teams need faster code reviews",
        }
        flow.state.build_output = "A complete SaaS for automated code reviews."
        flow.state.pending_since = "2026-04-23T10:00:00Z"

        summary = flow._build_approval_summary()
        assert "Cycle #5" in summary
        assert "AI Code Review Tool" in summary
        assert "Teams need faster code reviews" in summary


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
        mock_result = Mock()
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

        mock_result = Mock()
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

        mock_result = Mock()
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

        mock_result = Mock()
        mock_result.raw = {"url": "https://example.com", "deployment_id": "xyz"}

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
        flow.state.top_opportunity = {"title": "Test Opportunity",
                                     "problem_statement": "Test problem"}
        flow.state.build_output = "Test build output"

        with patch.object(flow, "remember"):
            with patch("sentinel_v2.tools.telegram_tool.TelegramTool") as mock_tg_cls:
                mock_tool = MagicMock()
                mock_tool.send_approval_poll = MagicMock()
                mock_tg_cls.return_value = mock_tool

                result = flow.request_approval()

        assert result == "pending"
        assert flow.state.current_phase == "approve"
        assert flow.state.pending_since != ""
        mock_tool.send_approval_poll.assert_called_once()

    def test_request_approval_calls_remember(self, flow):
        """request_approval() stores approval pending in memory."""
        flow.state.cycle_count = 7
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.build_output = "output"
        flow.state.pending_since = "2026-04-23T10:00:00Z"

        with patch.object(flow, "remember") as mock_remember:
            with patch("sentinel_v2.tools.telegram_tool.TelegramTool"):
                flow.request_approval()

        mock_remember.assert_called()
        call_args = str(mock_remember.call_args)
        assert "pending approval" in call_args


class TestCheckApproval:
    """Tests for check_approval() polling logic."""

    def test_check_approval_sets_pending(self, flow):
        """check_approval() writes pending state to ApprovalState."""
        flow.state.cycle_count = 4
        flow.state.top_opportunity = {"title": "Op"}
        flow.state.build_output = "draft"

        mock_approval = MagicMock()
        mock_approval.is_stop_requested.return_value = False
        mock_approval.is_revison_requested.return_value = False
        mock_approval.is_approved.side_effect = [False, False, True]
        mock_approval.get_action.return_value = "approved"
        mock_approval.set_pending = MagicMock()
        mock_approval.clear_pending = MagicMock()

        with patch(
            "sentinel_v2.tools.approval_state.ApprovalState",
            return_value=mock_approval,
        ):
            with patch("sentinel_v2.dashboard_state.write_state"):
                with patch("time.sleep"):
                    result = flow.check_approval()

        assert result == "approved"
        assert flow.state.approved is True
        mock_approval.set_pending.assert_called_once()
        mock_approval.clear_pending.assert_called_once_with(4)

    def test_check_approval_returns_stop_when_stop_requested(self, flow):
        """check_approval() returns 'stop' when stop is requested."""
        flow.state.cycle_count = 5

        mock_approval = MagicMock()
        mock_approval.is_stop_requested.return_value = True
        mock_approval.set_pending = MagicMock()

        with patch(
            "sentinel_v2.tools.approval_state.ApprovalState",
            return_value=mock_approval,
        ):
            with patch("sentinel_v2.dashboard_state.write_state"):
                result = flow.check_approval()

        assert result == "stop"
        # _shutdown_requested is on the Flow object, not the State
        assert flow._shutdown_requested is True

    def test_check_approval_returns_revision_when_revision_requested(self, flow):
        """check_approval() returns 'revision' when revision is requested."""
        flow.state.cycle_count = 6
        flow.state.top_opportunity = {"title": "Op"}

        mock_approval = MagicMock()
        mock_approval.is_stop_requested.return_value = False
        # First check returns False, second returns True (revision requested)
        # But we need to mock is_approved to return False always
        mock_approval.is_revison_requested.side_effect = [True]
        mock_approval.is_approved.return_value = False
        mock_approval.set_pending = MagicMock()

        with patch(
            "sentinel_v2.tools.approval_state.ApprovalState",
            return_value=mock_approval,
        ):
            with patch("sentinel_v2.dashboard_state.write_state"):
                with patch("time.sleep"):
                    result = flow.check_approval()

        assert result == "revision"
        assert flow.state.approved is False
        assert flow.state.revision_notes == "revision requested"
        assert flow.state.current_phase == "build"

    def test_check_approval_shutdown_while_waiting_returns_stop(self, flow):
        """check_approval() returns 'stop' when shutdown during polling."""
        flow.state.cycle_count = 7
        flow._shutdown_requested = True

        with patch("sentinel_v2.dashboard_state.write_state"):
            with patch("time.sleep"):
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
        mock_result = Mock()
        mock_result.raw = {"url": "https://example.com", "deployment_id": "abc"}

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
        mock_result = Mock()
        mock_result.raw = {"url": "https://example.com", "deployment_id": "abc"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_cls:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            mock_crew_cls.return_value = mock_crew

            with patch.object(flow, "remember") as mock_remember:
                flow.run_deploy()

        mock_remember.assert_called()


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
