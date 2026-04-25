# match_crew.py

"""Match Crew - Commercial qualification of a single opportunity.

This crew is NOT about matching to a personal profile. It is about qualifying
an opportunity against execution capacity and commercial viability BEFORE we
spend build cycles on it. Think of it as the Go/No-Go gate between research
and build.
"""
from crewai import Agent, Crew, Process, Task

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full


def match_crew(cycle: int = 1) -> Crew:
    """Create the commercial qualification crew."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)

    # ── Agents ───────────────────────────────────────────────────────────────

    customer_intel = Agent(
        role="Customer Intelligence Analyst",
        goal=(
            "Sharpen the ICP so the build team and the go-to-market pitch speak directly "
            "to one specific buyer, not 'everyone'."
        ),
        backstory=(
            "You've built ICPs for 100+ SaaS companies. You know that vague personas ship vague "
            "products. You force specificity: exact job title, company size bracket, annual revenue "
            "bracket, geography, the tool they currently use, the URL of the community they lurk in, "
            "the dollar amount they spend today on the problem. You also identify 3-5 anti-personas "
            "(who this product is NOT for) to keep the product focused."
        ),
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    qualifier = Agent(
        role="Opportunity Qualifier",
        goal=(
            "Make a crisp Go / Modify / Kill decision on the opportunity using evidence, "
            "not enthusiasm."
        ),
        backstory=(
            "You are the last gate before build capacity is committed. You have killed dozens of "
            "'exciting' ideas because the math did not work. Your checklist is strict: "
            "(1) paying demand evidence is concrete, not hand-waved; "
            "(2) the ICP is specific enough to target with sub-$5 CPC or free community posts; "
            "(3) the MVP truly fits operator_capacity (typically 1-2 weeks of solo build); "
            "(4) distribution is testable in week 1, not 'build it and they will come'; "
            "(5) pricing is realistic ($9-$299/mo or $200-$2000 one-off); "
            "(6) there is a defensible reason this should not be a weekend-feature of a bigger tool."
        ),
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    # ── Tasks ────────────────────────────────────────────────────────────────

    icp_task = Task(
        description=(
            "You are given one opportunity: {opportunity}\n"
            "And the operator capacity: {operator_capacity}\n\n"
            "Produce a sharp ICP profile:\n"
            "  - icp_title: e.g. 'Solo bookkeeper running a firm with 10-50 SMB clients in the US'\n"
            "  - job_title: specific role(s)\n"
            "  - company_size: e.g. 'solo to 10 employees'\n"
            "  - geography: primary and secondary markets\n"
            "  - current_spend: what this buyer spends today on the problem (hours, dollars, tools)\n"
            "  - where_to_reach: 3-5 concrete channels (subreddit URL, Slack community, directory, "
            "conference, Twitter hashtag, specific search keyword)\n"
            "  - pain_trigger: the exact moment that makes this buyer want to pay (e.g., 'end of month', "
            "'client asks for X', 'regulator notice')\n"
            "  - anti_personas: 3-5 buyer segments this product is NOT for (and why).\n"
            "Return structured JSON."
        ),
        expected_output="JSON with keys: icp_title, job_title, company_size, geography, current_spend, where_to_reach, pain_trigger, anti_personas.",
        agent=customer_intel,
    )

    qualify_task = Task(
        description=(
            "Given the opportunity {opportunity} and the ICP profile from the previous step, "
            "make a Go/Modify/Kill decision.\n\n"
            "Score each dimension 0-1 with a one-sentence justification:\n"
            "  - paying_demand (is there real evidence money is changing hands?)\n"
            "  - icp_sharpness (can we target them in week 1?)\n"
            "  - mvp_feasibility (fits operator_capacity?)\n"
            "  - distribution_testability (can we get 10 conversations in week 1?)\n"
            "  - pricing_realism (pricing hypothesis is defensible)\n"
            "  - moat (why this does not get eaten by a bigger tool in 12 months)\n\n"
            "Compute qualification_score = weighted mean (paying_demand 0.30, icp_sharpness 0.20, "
            "mvp_feasibility 0.15, distribution_testability 0.15, pricing_realism 0.10, moat 0.10).\n\n"
            "Make the final recommendation:\n"
            "  - 'proceed' if qualification_score >= 0.70 AND paying_demand >= 0.60\n"
            "  - 'modify' if 0.55 <= qualification_score < 0.70 (propose specific changes)\n"
            "  - 'kill' otherwise"
        ),
        expected_output=(
            "JSON with: qualification_score (0-1), paying_demand, icp_sharpness, mvp_feasibility, "
            "distribution_testability, pricing_realism, moat (all 0-1 with per-field justification), "
            "recommendation ('proceed'|'modify'|'kill'), reasoning (2-3 sentences), "
            "suggested_modifications (string, only if recommendation is 'modify'), "
            "profile (echo of the ICP profile), score (alias for qualification_score)."
        ),
        agent=qualifier,
    )

    crew = Crew(
        agents=[customer_intel, qualifier],
        tasks=[icp_task, qualify_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )

    crew = hook_crew_full(crew, phase="match", cycle=cycle)
    return crew
