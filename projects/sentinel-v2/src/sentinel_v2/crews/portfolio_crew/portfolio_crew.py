"""Portfolio Crew — maintain the ErsLabs landing portfolio.

Reads erslabs-landing/data/portfolio.json, appends the newly validated app,
and writes the updated file.
"""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full
from sentinel_v2.tools import ListFilesTool, WriteFileTool


def portfolio_crew(cycle: int = 1) -> Crew:
    """Create the portfolio maintenance crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    memory = get_memory_for_crew_full(minimax)

    list_files = ListFilesTool()
    write_file = WriteFileTool()

    maintainer = Agent(
        role="Portfolio Maintainer",
        goal=(
            "Keep the ErsLabs portfolio up to date by adding newly validated apps "
            "to the portfolio.json data file."
        ),
        backstory=(
            "You maintain the public portfolio of ErsLabs, an AI lab that builds apps "
            "by listening to real problems. When a new app is validated, you add it to "
            "the portfolio JSON file with clean, accurate metadata."
        ),
        tools=[list_files, write_file],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
        max_iter=4,
    )

    update_task = Task(
        description=(
            "Add a newly validated app to the ErsLabs portfolio.\n\n"
            "INPUT:\n"
            "- slug: {slug}\n"
            "- title: {title}\n"
            "- tagline: {tagline}\n"
            "- problem: {problem}\n"
            "- url: {url}\n"
            "- tags: {tags}\n"
            "- deployed_at: {deployed_at}\n\n"
            "STEPS:\n"
            "1. Read erslabs-landing/data/portfolio.json\n"
            "2. Check if slug already exists — if so, update the entry\n"
            "3. If not, append a new entry with all fields\n"
            "4. Write the updated JSON back to erslabs-landing/data/portfolio.json\n"
            "5. Ensure valid JSON formatting"
        ),
        expected_output=(
            "Confirmation that portfolio.json was updated with the new app entry."
        ),
        agent=maintainer,
    )

    crew = Crew(
        agents=[maintainer],
        tasks=[update_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )

    crew = hook_crew_full(crew, phase="portfolio", cycle=cycle)
    return crew
