"""Research Crew — Scout the web for opportunities."""
from crewai import Agent, Crew, Process, Task

from sentinel_v2.config.llm_config import get_minimax_llm


def research_crew() -> Crew:
    """Create the research crew for finding opportunities."""

    minimax = get_minimax_llm()

    scout = Agent(
        role="Web Scout",
        goal="Scout the web continuously for market gaps, unmet needs, and high-potential micro-business opportunities",
        backstory="You have a sixth sense for spotting opportunities where others see problems. You're constantly scanning: Twitter trends, Product Hunt launches, Hacker News discussions, Reddit threads, and emerging communities.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    analyst = Agent(
        role="Opportunity Analyst",
        goal="Analyze and prioritize opportunities based on market fit, feasibility, and potential value for Kike",
        backstory="You're an expert at evaluating micro-business ideas. You assess market demand, technical feasibility, required resources, and potential ROI. You know Kike's strengths.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    scout_task = Task(
        description="Scout the web for 5 high-potential micro-business opportunities suitable for a solo AI agent entrepreneur. Focus on: SaaS micro-tools, AI agents, developer tools, crypto trading tools. Consider recent trends in: Hacker News, Product Hunt, and developer communities.",
        expected_output="A list of 5 opportunities with: title, problem statement, target market, estimated complexity (1-5), potential revenue model.",
        agent=scout,
    )

    analyze_task = Task(
        description="Analyze the 5 opportunities identified by the scout. Filter for Kike's strengths (Next.js, TypeScript, NestJS, Prisma, Postgres, Hyperliquid, AI agents). Score each on: fit, feasibility, potential value. Keep the top opportunity.",
        expected_output="The best opportunity with: title, problem statement, solution outline, tech fit score (0-1), business fit score (0-1), complexity score (1-5), estimated time to build.",
        agent=analyst,
    )

    return Crew(
        agents=[scout, analyst],
        tasks=[scout_task, analyze_task],
        process=Process.sequential,
        verbose=True,
        memory=True,
    )