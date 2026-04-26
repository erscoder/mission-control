"""Social Response Crew — compose platform-adapted replies for source communities.

Compose-only: generates response text for the user to manually post.
Does NOT publish anything automatically.
"""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full


def social_response_crew(cycle: int = 1) -> Crew:
    """Create the social response crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    memory = get_memory_for_crew_full(minimax)

    responder = Agent(
        role="Social Response Specialist",
        goal=(
            "Compose helpful, genuine community responses that share a new solution "
            "to a problem people were complaining about — without sounding spammy or promotional."
        ),
        backstory=(
            "You are a community member who genuinely helps people. You've spent years "
            "in Reddit, Hacker News, and Twitter communities. You know each platform's "
            "tone: Reddit is casual and values honesty, Twitter is concise and punchy, "
            "Hacker News is technical and skeptical of self-promotion. "
            "You NEVER sound like a marketer. You sound like someone who built something "
            "because the problem annoyed you too. You always include the direct link to "
            "the solution and acknowledge the original pain point."
        ),
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

    compose_task = Task(
        description=(
            "Given a validated app and the source URLs where the problem was originally "
            "discovered, compose one response per source URL.\n\n"
            "INPUT:\n"
            "- app_title: {app_title}\n"
            "- app_url: {app_url}\n"
            "- problem: {problem}\n"
            "- solution: {solution}\n"
            "- source_urls: {source_urls}\n\n"
            "RULES:\n"
            "- One response per source_url\n"
            "- Detect the platform from the URL (reddit.com → Reddit, twitter.com/x.com → Twitter, "
            "news.ycombinator.com → HN, etc.)\n"
            "- Adapt tone to each platform\n"
            "- Include the app_url naturally in the response\n"
            "- Keep responses under 280 chars for Twitter, under 500 words for Reddit/HN\n"
            "- Sound like a genuine community member, NOT a marketer\n"
            "- Reference the specific pain point from the original post\n\n"
            "OUTPUT: A JSON list of objects, each with:\n"
            "  - source_url: the original URL\n"
            "  - platform: detected platform name\n"
            "  - response_text: the composed response"
        ),
        expected_output=(
            "JSON list of [{source_url, platform, response_text}] — one entry per source URL. "
            "Each response_text is platform-appropriate and includes the app URL."
        ),
        agent=responder,
    )

    crew = Crew(
        agents=[responder],
        tasks=[compose_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )

    crew = hook_crew_full(crew, phase="social_response", cycle=cycle)
    return crew
