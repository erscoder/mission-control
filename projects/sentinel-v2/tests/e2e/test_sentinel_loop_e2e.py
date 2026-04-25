"""
E2E smoke tests for sentinel-v2 flow.

Tests the full flow orchestration with real CrewAI instances.
Uses Ollama (localhost:11434) to avoid OpenAI quota dependency.
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import patch, Mock

OLLAMA_AVAILABLE = os.environ.get("TEST_OLLAMA") == "1"


class TestResearchPhaseE2E:
    """E2E tests for research phase — require TEST_OLLAMA=1."""

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Set TEST_OLLAMA=1 to run Ollama e2e tests")
    def test_research_crew_with_ollama_instantiates(self):
        """Research crew can be created with Ollama LLM."""
        os.environ["OLLAMA_API_BASE"] = "http://localhost:11434/v1"
        os.environ["OLLAMA_MODEL"] = "qwen2.5:1.5b"

        from crewai import LLM
        from sentinel_v2.crews.research_crew.research_crew import research_crew

        crew = research_crew()
        for agent in crew.agents:
            agent.llm = LLM(
                model=os.environ["OLLAMA_MODEL"],
                api_base=os.environ["OLLAMA_API_BASE"],
            )

        assert crew is not None
        assert len(crew.agents) == 2

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Set TEST_OLLAMA=1 to run Ollama e2e tests")
    def test_research_crew_kickoff_with_ollama(self):
        """Research crew kickoff returns output with Ollama."""
        os.environ["OLLAMA_API_BASE"] = "http://localhost:11434/v1"
        os.environ["OLLAMA_MODEL"] = "qwen2.5:1.5b"

        from crewai import LLM
        from sentinel_v2.crews.research_crew.research_crew import research_crew

        crew = research_crew()
        for agent in crew.agents:
            agent.llm = LLM(
                model=os.environ["OLLAMA_MODEL"],
                api_base=os.environ["OLLAMA_API_BASE"],
            )

        result = crew.kickoff(
            inputs={
                "kike_profile": {
                    "name": "Kike",
                    "skills": ["Python", "TypeScript"],
                    "twitter": "@kikerub",
                },
                "cycle": 1,
            }
        )

        assert hasattr(result, "raw")
        assert result.raw is not None


class TestMatchPhaseE2E:
    """E2E tests for match phase — require TEST_OLLAMA=1."""

    @pytest.mark.skipif(not OLLAMA_AVAILABLE, reason="Set TEST_OLLAMA=1 to run Ollama e2e tests")
    def test_match_crew_with_ollama_instantiates(self):
        """Match crew can be created with Ollama LLM."""
        os.environ["OLLAMA_API_BASE"] = "http://localhost:11434/v1"
        os.environ["OLLAMA_MODEL"] = "qwen2.5:1.5b"

        from crewai import LLM
        from sentinel_v2.crews.match_crew.match_crew import match_crew

        crew = match_crew()
        for agent in crew.agents:
            agent.llm = LLM(
                model=os.environ["OLLAMA_MODEL"],
                api_base=os.environ["OLLAMA_API_BASE"],
            )

        assert crew is not None
        assert len(crew.agents) == 2


class TestFlowEventChain:
    """Test the flow's event chain with mocked crews."""

    def test_start_cycle_increments_count(self):
        """start_cycle increments cycle_count."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow

        flow = SentinelLoopFlow()
        assert flow.state.cycle_count == 0

        # Directly call start_cycle (bypasses @start decorator)
        flow.start_cycle()

        assert flow.state.cycle_count == 1
        assert flow.state.current_phase == "research"

    def test_flow_runs_research_phase_with_mocked_crew(self):
        """Flow runs research phase and stores opportunities."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
        from crewai import Crew

        flow = SentinelLoopFlow()
        flow.start_cycle()

        mock_result = Mock()
        # Force _extract_raw to fall through to .raw — without these, the auto-Mock
        # for .pydantic / .json_dict shadows the real payload and parsers see Mock objects.
        mock_result.pydantic = None
        mock_result.json_dict = None
        mock_result.raw = [
            {
                "title": "AI Code Review Tool",
                "problem_statement": "Dev teams need faster code reviews",
                "target_market": "Software teams",
                "estimated_complexity": 3,
                "potential_revenue_model": "SaaS subscription",
            },
            {
                "title": "Crypto Portfolio Tracker",
                "problem_statement": "Retail traders need simple portfolio tracking",
                "target_market": "Crypto retail",
                "estimated_complexity": 2,
                "potential_revenue_model": "Freemium",
            },
        ]

        with patch(
            "sentinel_v2.crews.research_crew.research_crew.research_crew"
        ) as mock_crew_factory:
            mock_crew = Mock(spec=Crew)
            mock_crew.kickoff.return_value = mock_result
            mock_crew_factory.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_research()

        assert len(flow.state.opportunities) == 2
        assert flow.state.top_opportunity["title"] == "AI Code Review Tool"
        assert flow.state.current_phase == "research"

    def test_flow_runs_match_phase_with_mocked_crew(self):
        """Flow runs match phase and stores profile + score."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
        from crewai import Crew

        flow = SentinelLoopFlow()
        flow.state.top_opportunity = {"title": "DeFi Tracker"}
        flow.state.cycle_count = 1

        mock_result = Mock()
        mock_result.pydantic = None
        mock_result.json_dict = None
        mock_result.raw = {
            "profile": {"name": "Kike", "skills": ["Python", "TypeScript"]},
            "score": 0.82,
        }

        with patch(
            "sentinel_v2.crews.match_crew.match_crew.match_crew"
        ) as mock_crew_factory:
            mock_crew = Mock(spec=Crew)
            mock_crew.kickoff.return_value = mock_result
            mock_crew_factory.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_match()

        assert flow.state.match_score == 0.82
        assert flow.state.user_profile["name"] == "Kike"

    def test_flow_runs_build_phase_with_mocked_crew(self):
        """Flow runs build phase and stores output."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
        from crewai import Crew

        flow = SentinelLoopFlow()
        flow.state.top_opportunity = {"title": "SaaS Tool"}
        flow.state.user_profile = {"name": "Kike"}
        flow.state.cycle_count = 1

        mock_result = Mock()
        mock_result.raw = "Built: Next.js SaaS with Stripe integration"

        with patch(
            "sentinel_v2.crews.build_crew.build_crew.build_crew"
        ) as mock_crew_factory:
            mock_crew = Mock(spec=Crew)
            mock_crew.kickoff.return_value = mock_result
            mock_crew_factory.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_build()

        assert "Next.js" in flow.state.build_output

    def test_flow_runs_deploy_phase_when_approved(self):
        """Flow deploys only when approved."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
        from crewai import Crew

        flow = SentinelLoopFlow()
        flow.state.approved = True
        flow.state.build_output = "Built: SaaS app"
        flow.state.top_opportunity = {"title": "Opportunity"}
        flow.state.cycle_count = 1

        mock_result = Mock()
        mock_result.pydantic = None
        mock_result.json_dict = None
        mock_result.raw = {"url": "https://myapp.onrender.com", "deployment_id": "xyz", "go_no_go": "GO"}

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_factory:
            mock_crew = Mock(spec=Crew)
            mock_crew.kickoff.return_value = mock_result
            mock_crew_factory.return_value = mock_crew

            with patch.object(flow, "remember"):
                flow.run_deploy()

        assert flow.state.deployed is True
        assert flow.state.deployed_url == "https://myapp.onrender.com"

    def test_flow_skips_deploy_when_not_approved(self):
        """Flow skips deploy when approved is False."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
        from crewai import Crew

        flow = SentinelLoopFlow()
        flow.state.approved = False
        flow.state.build_output = "Built: SaaS app"

        with patch(
            "sentinel_v2.crews.deploy_crew.deploy_crew.deploy_crew"
        ) as mock_crew_factory:
            flow.run_deploy()
            mock_crew_factory.assert_not_called()

        assert flow.state.deployed is False
