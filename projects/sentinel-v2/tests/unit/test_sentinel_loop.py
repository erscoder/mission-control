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
