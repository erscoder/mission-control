"""Research Crew — Scout the web for opportunities (with dashboard hooks)."""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full


def research_crew() -> Crew:
    """Create the research crew with dashboard streaming hooks."""
    
    minimax = get_minimax_llm()
    memory = get_memory_for_crew_full(minimax)

    scout = Agent(
        role="Web Scout",
        goal="Scout the web continuously for market gaps, unmet needs, and high-potential micro-business opportunities",
        backstory="You have a sixth sense for spotting opportunities where others see problems. You're constantly scanning: Twitter trends, Product Hunt launches, Hacker News discussions, Reddit threads. You filter out noise and surface only high-quality opportunities.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    analyst = Agent(
        role="Market Analyst",
        goal="Analyze opportunities for market validity, technical feasibility, and business potential",
        backstory="You're a market researcher who's evaluated 200+ SaaS ideas. You can spot fake trends from mile away. You assess: market size, competition gaps, technical complexity, monetization potential, and time-to-market.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    scout_task = Task(
        description="Scout the web for 5 high-potential micro-business opportunities suitable for a solo AI agent entrepreneur. Focus on: SaaS micro-tools (under $10k/mo revenue), AI agents that can run autonomous, developer tooling, crypto trading tools. Consider recent trends in: Hacker News, Product Hunt, Twitter dev community, Reddit r/SaaS and r/IndieHackers. Return concise opportunity entries.",
        expected_output="5 opportunity entries, each with: title, problem statement (1-2 sentences), solution outline (1-2 sentences), tech stack needed, market fit score (0-1), complexity (1-5), estimated revenue potential (seed).",
        agent=scout,
    )

    analyze_task = Task(
        description="Analyze the 5 opportunities found by Web Scout. For each, assess: market size (TAM/SAM), competitive landscape (number of competitors, differentiation potential), technical feasibility (can 1-2 developers build in 3 months?), monetization strategy (SaaS pricing, transaction fee, freemium?), time-to-market (MVP timeline). Keep the top 3 opportunities.",
        expected_output="3 top opportunities ranked by overall score. For each: refined problem statement, target customer segment, market size estimate, competitive analysis (top 3 competitors), revenue model, MVP milestone list (first 3 months), final recommendation score (1-10).",
        agent=analyst,
    )

    crew = Crew(
        agents=[scout, analyst],
        tasks=[scout_task, analyze_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )
    
    # Apply dashboard streaming hooks
    crew = hook_crew_full(crew, phase="research", cycle=1)
    
    return crew
