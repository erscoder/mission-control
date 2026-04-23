"""Match Crew — Profile Researcher + Matcher (with hooks)."""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full


def match_crew() -> Crew:
    """Create the match crew with dashboard streaming hooks."""
    
    minimax = get_minimax_llm()
    memory = get_memory_for_crew_full(minimax)

    profile_researcher = Agent(
        role="Profile Researcher",
        goal="Research and expand Kike's profile: skills, stack, preferences, constraints, timezone, recent wins/blockers",
        backstory="You're a profilist who's worked with 50+ top engineers. You dive deep: not just the tech stack, but coding style preferences, productivity tools, coordination habits, domain expertise, business constraints, personal preferences (time flexibility, risk tolerance), recent achievements and blockers.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    matcher = Agent(
        role="Opportunity Matcher",
        goal="Match top opportunity to Kike's profile. Calculate fit score (0-1) across 6 dimensions: tech stack, market interest, complexity preference, revenue potential, time availability, business model fit",
        backstory="You're a match-making algorithm for opportunities and engineers. You're not impressed by buzzwords — you match based on real capability, market need, and business viability. You weigh: tech stack alignment (40%), market interest (20%), doable in 3 months (15%), revenue >$2k/mo (15%), flexibility (10%).",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    profile_task = Task(
        description="Research and expand Kike's profile based on available context. Include: mission statement, full tech stack (languages, frameworks, DBs, cloud, tools), coding style preferences (strict vs loose, functional vs OOP), productivity environment (IDE, tools), timezone and working hours preferences, recent wins and blockers, what they've learned recently, business constraints (budget, time availability), risk tolerance. Structure as JSON.",
        expected_output="Updated profile as structured JSON with sections: mission, tech_stack (expanded), coding_preferences, productivity_environment, timezone_schedule, recent_context (wins+blockers), business_constraints, risk_profile",
        agent=profile_researcher,
    )

    match_task = Task(
        description="Given the opportunity and Kike's profile, calculate a match score (0-1) across 6 dimensions. Dimensions: tech_stack_fit (0-1), market_interest (0-1), complexity_feasibility (0-1), revenue_potential ($/mo), time_availability_fit (0-1), business_model_fit (0-1). Weighted average: tech 40%, market 20%, complexity 15%, revenue 15%, time 10%. Final score 0-1. Explain why this is or isn't a good fit. If score <0.6, suggest a different opportunity.",
        expected_output="Match report with: match_score (0-1), dimension_breakdown (each 0-1 with weight), rationale paragraph explaining the score, recommendation (MATCH/NO_MATCH), if NO_MATCH: suggested alternative opportunity with brief justification.",
        agent=matcher,
    )

    crew = Crew(
        agents=[profile_researcher, matcher],
        tasks=[profile_task, match_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )
    
    crew = hook_crew_full(crew, phase="match", cycle=1)
    
    return crew
