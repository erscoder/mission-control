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

    def test_research_crew_memory_disabled_by_default(self):
        """Memory is disabled by default — see embedder_config docs."""
        from sentinel_v2.crews.research_crew.research_crew import research_crew

        crew = research_crew()
        # crew.memory is False/None when disabled, not a Memory instance
        assert not crew.memory

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

    def test_build_crew_sequential_process(self):
        """Crew uses sequential process. Hierarchical wraps the crew in an LLM
        manager that re-evaluates outputs and crashes on MiniMax-M2.7's
        tool-call-heavy final answers, so the crew runs sequentially with an
        explicit context chain instead.
        """
        from sentinel_v2.crews.build_crew.build_crew import build_crew
        from crewai import Process

        crew = build_crew()
        assert crew.process == Process.sequential

    def test_build_crew_has_eleven_tasks(self):
        """Crew has six planner tasks (architecture, domain, services, api,
        infra, files) followed by frontend, backend, code review, security
        audit, and QA. The planner chain replaces the prior monolithic
        plan_task to constrain agent output and reduce hallucinations.
        """
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        assert len(crew.tasks) == 11

    def test_build_crew_planner_chain_uses_strategic_manager(self):
        """The first six tasks are the planning stages, all driven by
        strategic_manager. Splitting one agent across six smaller tasks
        constrains output structure without forcing new agent prompts.
        """
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        for task in crew.tasks[:6]:
            assert task.agent.role == "Strategic Product Manager"

    def test_build_crew_plan_files_in_frontend_context(self):
        """The frontend lead must read the file-by-file write plan so it
        knows exactly which files to write and in what order. Without it
        the lead invents paths and breaks downstream code review.
        """
        from sentinel_v2.crews.build_crew.build_crew import build_crew

        crew = build_crew()
        plan_files = crew.tasks[5]
        frontend_task = crew.tasks[6]
        assert plan_files in (frontend_task.context or [])

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


# ─── Cycle Parameter Acceptance ──────────────────────────────────────────────

class TestCrewCycleParameter:
    """All crew factories accept a cycle parameter for dashboard hook propagation."""

    def test_research_crew_accepts_cycle(self):
        from sentinel_v2.crews.research_crew.research_crew import research_crew
        crew = research_crew(cycle=5)
        assert crew is not None

    def test_match_crew_accepts_cycle(self):
        from sentinel_v2.crews.match_crew.match_crew import match_crew
        crew = match_crew(cycle=3)
        assert crew is not None

    def test_build_crew_accepts_cycle(self):
        from sentinel_v2.crews.build_crew.build_crew import build_crew
        crew = build_crew(cycle=7)
        assert crew is not None

    def test_security_remediation_crew_accepts_cycle(self):
        from sentinel_v2.crews.security_remediation_crew.security_remediation_crew import security_remediation_crew
        crew = security_remediation_crew(cycle=2)
        assert crew is not None

    def test_deploy_crew_accepts_cycle(self):
        from sentinel_v2.crews.deploy_crew.deploy_crew import deploy_crew
        crew = deploy_crew(cycle=10)
        assert crew is not None


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
