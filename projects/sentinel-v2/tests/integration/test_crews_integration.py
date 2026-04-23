"""
Integration tests for sentinel-v2 crews.

Tests crew orchestration (agents + tasks + process) WITHOUT real LLM calls.
Verifies crew structure, agent counts, and process types.
"""
from __future__ import annotations

import pytest


class TestResearchCrew:
    """Integration tests for research_crew structure."""

    def test_research_crew_instantiates(self):
        """Crew can be instantiated without error."""
        from sentinel_v2.crews.research_crew.research_crew import research_crew

        crew = research_crew()
        assert crew is not None

    def test_research_crew_has_two_agents(self):
        """Crew is configured with Scout and Analyst agents."""
        from sentinel_v2.crews.research_crew.research_crew import research_crew

        crew = research_crew()
        assert len(crew.agents) == 2

    def test_research_crew_sequential_process(self):
        """Crew uses sequential process."""
        from sentinel_v2.crews.research_crew.research_crew import research_crew
        from crewai import Process

        crew = research_crew()
        assert crew.process == Process.sequential

    def test_research_crew_has_memory(self):
        """Crew has memory enabled."""
        from sentinel_v2.crews.research_crew.research_crew import research_crew
        from crewai.memory.unified_memory import Memory

        crew = research_crew()
        assert crew.memory is not None
        assert isinstance(crew.memory, Memory)

    def test_research_crew_agents_have_roles(self):
        """Both agents have defined roles."""
        from sentinel_v2.crews.research_crew.research_crew import research_crew

        crew = research_crew()
        roles = {agent.role for agent in crew.agents}
        assert len(roles) == 2
        assert all(role for role in roles)

    def test_research_crew_tasks_match_agents(self):
        """Each task is assigned to an agent."""
        from sentinel_v2.crews.research_crew.research_crew import research_crew

        crew = research_crew()
        for task in crew.tasks:
            assert task.agent is not None


class TestMatchCrew:
    """Integration tests for match_crew structure."""

    def test_match_crew_instantiates(self):
        """Crew can be instantiated without error."""
        from sentinel_v2.crews.match_crew.match_crew import match_crew

        crew = match_crew()
        assert crew is not None

    def test_match_crew_has_two_agents(self):
        """Crew has Profile Researcher and Matcher agents."""
        from sentinel_v2.crews.match_crew.match_crew import match_crew

        crew = match_crew()
        assert len(crew.agents) == 2

    def test_match_crew_sequential_process(self):
        """Crew uses sequential process."""
        from sentinel_v2.crews.match_crew.match_crew import match_crew
        from crewai import Process

        crew = match_crew()
        assert crew.process == Process.sequential

    def test_match_crew_tasks_have_descriptions(self):
        """All tasks have non-empty descriptions."""
        from sentinel_v2.crews.match_crew.match_crew import match_crew

        crew = match_crew()
        for task in crew.tasks:
            assert task.description
            assert len(task.description) > 10


class TestBuildCrew:
    """Integration tests for build_crew structure."""

    def test_build_crew_instantiates(self):
        """Crew can be instantiated without error."""
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        assert crew is not None

    def test_build_crew_has_six_agents(self):
        """Crew has Manager + Frontend + Backend + Code Reviewer + Security + QA agents."""
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        assert len(crew.agents) == 6

    def test_build_crew_hierarchical_process(self):
        """Crew uses hierarchical process."""
        from sentinel_v2.crews.build_crew.build_crew import build_crew
        from crewai import Process

        crew = build_crew()
        assert crew.process == Process.hierarchical

    def test_build_crew_has_manager_llm(self):
        """Crew has a manager_llm configured for delegation."""
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        assert crew.manager_llm is not None

    def test_build_crew_tasks_have_descriptions(self):
        """All tasks have non-empty descriptions."""
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        for task in crew.tasks:
            assert task.description
            assert len(task.description) > 10

    def test_build_crew_tasks_match_agents(self):
        """Each task is assigned to an agent."""
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        for task in crew.tasks:
            assert task.agent is not None


class TestDeployCrew:
    """Integration tests for deploy_crew structure."""

    def test_deploy_crew_instantiates(self):
        """Crew can be instantiated without error."""
        from sentinel_v2.crews.deploy_crew.deploy_crew import deploy_crew

        crew = deploy_crew()
        assert crew is not None

    def test_deploy_crew_has_two_agents(self):
        """Crew has Deployment Engineer and QA Verifier agents."""
        from sentinel_v2.crews.deploy_crew.deploy_crew import deploy_crew

        crew = deploy_crew()
        assert len(crew.agents) == 2

    def test_deploy_crew_sequential_process(self):
        """Crew uses sequential process."""
        from sentinel_v2.crews.deploy_crew.deploy_crew import deploy_crew
        from crewai import Process

        crew = deploy_crew()
        assert crew.process == Process.sequential

    def test_deploy_crew_tasks_have_expected_output(self):
        """All tasks have expected_output defined."""
        from sentinel_v2.crews.deploy_crew.deploy_crew import deploy_crew

        crew = deploy_crew()
        for task in crew.tasks:
            assert task.expected_output
            assert len(task.expected_output) > 10


# ─── Telegram Tool ───────────────────────────────────────────────────────────

class TestTelegramTool:
    """Integration tests for TelegramTool interface."""

    def test_telegram_tool_instantiates(self):
        """TelegramTool can be instantiated."""
        from sentinel_v2.tools.telegram_tool import TelegramTool
        tool = TelegramTool()
        assert tool is not None

    def test_has_send_message(self):
        """TelegramTool has send_message method."""
        from sentinel_v2.tools.telegram_tool import TelegramTool
        assert hasattr(TelegramTool, "send_message")

    def test_has_send_approval_poll(self):
        """TelegramTool has send_approval_poll method."""
        from sentinel_v2.tools.telegram_tool import TelegramTool
        assert hasattr(TelegramTool, "send_approval_poll")

    def test_has_approval_callback_setter(self):
        """TelegramTool has _set_approval_callback method."""
        from sentinel_v2.tools.telegram_tool import TelegramTool
        assert hasattr(TelegramTool, "_set_approval_callback")

    def test_send_message_is_callable(self):
        """send_message is callable."""
        from sentinel_v2.tools.telegram_tool import TelegramTool
        assert callable(TelegramTool.send_message)

    def test_send_approval_poll_is_callable(self):
        """send_approval_poll is callable."""
        from sentinel_v2.tools.telegram_tool import TelegramTool
        assert callable(TelegramTool.send_approval_poll)


# ─── Flow Smoke Tests ────────────────────────────────────────────────────────

class TestFlowSmoke:
    """Smoke tests that verify the flow state machine transitions."""

    def test_state_stores_opportunities(self):
        """SentinelState can store opportunities list."""
        from sentinel_v2.flows.sentinel_loop import SentinelState

        state = SentinelState()
        state.opportunities = [
            {"title": "Op A", "problem_statement": "Problem A"},
            {"title": "Op B", "problem_statement": "Problem B"},
        ]
        assert len(state.opportunities) == 2

    def test_state_stores_user_profile(self):
        """SentinelState can store user profile dict."""
        from sentinel_v2.flows.sentinel_loop import SentinelState

        state = SentinelState()
        state.user_profile = {"name": "Kike", "skills": ["Python", "TypeScript"]}
        assert state.user_profile["name"] == "Kike"

    def test_state_stores_match_score(self):
        """SentinelState can store match_score."""
        from sentinel_v2.flows.sentinel_loop import SentinelState

        state = SentinelState()
        state.match_score = 0.87
        assert state.match_score == 0.87

    def test_state_tracks_approval(self):
        """SentinelState tracks approved/revision state."""
        from sentinel_v2.flows.sentinel_loop import SentinelState

        state = SentinelState()
        state.approved = True
        state.revision_notes = "Add dark mode"
        assert state.approved is True
        assert state.revision_notes == "Add dark mode"

    def test_state_tracks_deployment(self):
        """SentinelState tracks deployed URL and ID."""
        from sentinel_v2.flows.sentinel_loop import SentinelState

        state = SentinelState()
        state.deployed = True
        state.deployed_url = "https://my-saas.onrender.com"
        state.deployment_id = "abc123"
        assert state.deployed is True
        assert state.deployed_url == "https://my-saas.onrender.com"
        assert state.deployment_id == "abc123"

    def test_flow_instantiates(self):
        """SentinelLoopFlow can be instantiated."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
        flow = SentinelLoopFlow()
        assert flow is not None
        assert flow.state is not None

    def test_flow_state_initial_values(self):
        """Flow starts with correct initial state."""
        from sentinel_v2.flows.sentinel_loop import SentinelLoopFlow
        flow = SentinelLoopFlow()
        assert flow.state.cycle_count == 0
        assert flow.state.approved is False
        assert flow.state.deployed is False
        assert flow.state.opportunities == []
