"""Match Crew — Match opportunities to Kike's profile."""
from crewai import Agent, Crew, Process, Task

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full


def match_crew() -> Crew:
    """Create the match crew for opportunity-user matching."""

    minimax = get_minimax_llm()
    memory = get_memory_for_crew_full(minimax)

    profile_researcher = Agent(
        role="Profile Researcher",
        goal="Research and maintain Kike's profile: skills, interests, constraints, goals, timezone, preferences",
        backstory="You're an expert at user research. You build deep psychological profiles by analyzing interactions, stated preferences, and behavior patterns. You know Kike's mission: autonomous agents that generate income 24/7.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    matcher = Agent(
        role="Opportunity Matcher",
        goal="Match opportunities to Kike's profile with high precision. Ensure alignment with skills, interests, and business goals.",
        backstory="You're a matchmaker for entrepreneurs. You've paired thousands of opportunities with the right founders. You understand alignment goes beyond skills—includes interests, timing, and long-term vision.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    profile_task = Task(
        description="Research and update Kike's profile based on available context. Include: mission, tech stack, skills, timezone, preferences, constraints, recent wins, blockers.",
        expected_output="Updated profile as structured JSON with: name, mission, skills (list), stack (list), timezone, preferences, constraints, recent_context.",
        agent=profile_researcher,
    )

    match_task = Task(
        description="Given the opportunity and Kike's profile, calculate a match score (0-1). Explain why this is or isn't a good fit. Suggest adjustments if score is below 0.7.",
        expected_output="Match analysis with: match_score (0-1), fit_reasoning (string), strengths (list), gaps (list), suggested_modifications (string or null), recommendation (proceed / modify / skip).",
        agent=matcher,
    )

    return Crew(
        agents=[profile_researcher, matcher],
        tasks=[profile_task, match_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )