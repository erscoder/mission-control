# research_crew.py

"""Research Crew — Demand-driven discovery of paying SaaS opportunities.

We do NOT start from the operator's personal preferences. We start from the
market: signals of paying demand, underserved niches, recurring complaints
with willingness-to-pay evidence. The goal is to find products users will
actually pay for — not ideas that sound cool.
"""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full


def research_crew() -> Crew:
    """Create the demand-research crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)

    # ── Agents ───────────────────────────────────────────────────────────────

    demand_hunter = Agent(
        role="Demand Hunter",
        goal=(
            "Find real, monetizable pain points where people are already paying for bad solutions "
            "or loudly asking for better ones — with concrete evidence, not speculation."
        ),
        backstory=(
            "You are a demand-side researcher who has validated 300+ SaaS ideas by mining real user "
            "complaints, hiring posts, and purchase behavior. You ignore 'cool tech' and chase "
            "signals that money is already changing hands (or trying to). Your favourite sources: "
            "Reddit pain threads in niche subs (r/smallbusiness, r/accounting, r/medicalpractice, "
            "r/realestate, r/fitnessindustry, r/marketingagencies, r/legaladvice), "
            "Twitter/X 'I wish there was a tool for X' threads, Upwork / Freelancer job posts that "
            "keep repeating the same manual task, G2 and Capterra reviews venting at incumbents, "
            "r/SaaS and r/IndieHackers revenue reports (who's making $5k+ MRR and how), "
            "IndieHackers 'Products' leaderboard by new MRR, "
            "Product Hunt comments calling out missing features, "
            "Hacker News 'Ask HN' and 'Show HN' threads and comment demand, "
            "Stack Overflow / Reddit repeated 'how do I automate X' questions, "
            "YouTube tutorial view counts for manual processes (signals automation demand), "
            "job postings listing 'manual process we want to automate'. "
            "You never suggest an idea without citing at least 2 independent demand signals."
        ),
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
        max_iter=4,
    )

    commercial_validator = Agent(
        role="Commercial Validator",
        goal=(
            "Kill ideas that won't make money. Keep only opportunities where paying demand is proven, "
            "the niche is underserved, distribution is achievable for a solo operator, and the "
            "unit economics work."
        ),
        backstory=(
            "You are a go-to-market analyst who has killed 80% of the ideas you've seen. You know "
            "that 'interesting' does not equal 'paying'. You systematically apply: "
            "(1) WTP test - is there evidence someone is already paying (competing product revenue, "
            "high-priced services replacing this pain, hiring budgets)? "
            "(2) ICP sharpness - can you name the exact buyer, their job title, and where to reach them? "
            "(3) Distribution test - can a solo operator with no budget reach 1000 of these buyers "
            "in 90 days (niche subreddit, niche Discord, niche directory, niche Twitter, "
            "narrow Google Ads keyword with sub-$5 CPC)? "
            "(4) Moat test - what keeps this from being a feature of a bigger product in 12 months? "
            "(5) Unit economics - at realistic pricing ($9-$99/mo SaaS, or $500-$5k one-off), "
            "does LTV exceed 3x CAC? "
            "You reject anything that does not pass all five tests. Your bar is brutal."
        ),
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
        max_iter=4,
    )

    # ── Tasks ────────────────────────────────────────────────────────────────

    scout_task = Task(
        description=(
            "Surface 8 demand-backed opportunity candidates for a solo-operator SaaS / micro-app.\n\n"
            "RULES:\n"
            "- Every candidate MUST cite at least 2 independent demand signals (Reddit thread, "
            "hiring post, G2 review, existing product revenue, repeated question on Stack Overflow, etc.).\n"
            "- Prefer boring, unsexy verticals with painful manual work over trendy horizontal tools.\n"
            "- Prefer paid-ads friendly niches (niche subs, industry directories, specific Google keywords).\n"
            "- Exclude: generic 'AI assistant for X', fake trends, ideas already saturated with free OSS alternatives.\n"
            "- Prefer niches where the buyer is a business or professional (higher WTP) over consumer apps.\n"
            "- Prefer problems that waste more than 2 hours/week of the buyer's time OR more than $200/month of their budget.\n\n"
            "OPTIONAL SEED (may be empty): {trend_signals}\n"
            "OPERATOR CAPACITY (not a preference - an execution constraint): {operator_capacity}\n\n"
            "For each candidate, output a structured entry:\n"
            "  - title: 3-6 word product name + one-line tagline\n"
            "  - tagline: one crisp sentence about what it does\n"
            "  - problem: 2-3 sentence description of the pain, written in the voice of the sufferer\n"
            "  - demand_signals: list of 2-5 concrete signals with source and quote when possible\n"
            "  - icp: exact ICP (job title + company size + industry + geography)\n"
            "  - incumbent: who people currently pay / hire to solve this (could be humans)\n"
            "  - willingness_to_pay: evidence of money already flowing (prices paid, hiring rates, subscriptions)\n"
            "  - suggested_price: realistic monthly or one-off price (e.g., $19/mo, $49/mo, $299 setup + $29/mo)\n"
            "  - distribution_hypothesis: 1-2 channels a solo operator could reach 1000 ICPs in 90 days\n"
            "  - complexity: 1-5 (1 = one weekend, 5 = 3+ months)\n"
            "  - tech_stack_fit: how well this fits Next.js + Postgres + Stripe delivery in ~1-2 weeks (0-1)\n"
        ),
        expected_output=(
            "A JSON list of 8 opportunity candidates, each with the fields above. Each demand_signal "
            "entry MUST include a source type (reddit|twitter|producthunt|hn|upwork|g2|hiring|other) "
            "and a short quoted pain statement or stat."
        ),
        agent=demand_hunter,
    )

    validate_task = Task(
        description=(
            "Apply the 5-test commercial filter to the 8 candidates: WTP, ICP, Distribution, Moat, Unit economics.\n\n"
            "For each candidate, score each test 0-1 with a one-line justification. Kill anything scoring "
            "below 0.5 on ANY of WTP, ICP, or Distribution (those are non-negotiable). Compute an overall "
            "commercial_score = weighted average (WTP 0.3, ICP 0.2, Distribution 0.2, Moat 0.15, Unit Econ 0.15).\n\n"
            "Then pick the TOP 3 opportunities by commercial_score. For each of the 3, upgrade the entry with:\n"
            "  - description: a detailed 4-6 sentence product description suitable for a landing page\n"
            "  - problem: 3-5 sentences with buyer voice, quoting at least one real demand signal\n"
            "  - solution: concrete 3-5 sentence solution - exactly what the MVP does in 1 paragraph\n"
            "  - estimated_hours: realistic solo-build hours for a 1-week MVP (target 20-60h)\n"
            "  - kill_risks: top 2 reasons this might fail commercially\n"
            "  - tags: 3-6 short lowercase tags (domain + tech)\n\n"
            "Return ONLY the top 3 as a JSON list, sorted by commercial_score descending. The first "
            "entry is what the build crew will execute."
        ),
        expected_output=(
            "JSON list of exactly 3 opportunities (top ranked by commercial_score). Each has: "
            "title, tagline, problem, solution, description, icp, demand_signals, willingness_to_pay, "
            "suggested_price, distribution_hypothesis, complexity (int 1-5), tech_fit (float 0-1), "
            "commercial_score (float 0-1), estimated_hours (int), kill_risks (list), tags (list)."
        ),
        agent=commercial_validator,
    )

    crew = Crew(
        agents=[demand_hunter, commercial_validator],
        tasks=[scout_task, validate_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )

    crew = hook_crew_full(crew, phase="research", cycle=1)
    return crew
