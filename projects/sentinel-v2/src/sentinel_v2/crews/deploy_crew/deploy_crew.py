"""Deploy Crew - Ship to Vercel + Neon (or equivalent PaaS) with Stripe live, telemetry on,
and a one-minute rollback. No k8s, no hand-rolled CI/CD. Fast time-to-first-dollar.
"""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full


def deploy_crew() -> Crew:
    """Create the deploy crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)

    deployer = Agent(
        role="Deployment Engineer",
        goal=(
            "Push the MVP to a production-ready URL that accepts real payments within a single "
            "deployment cycle. Zero manual steps after the first run."
        ),
        backstory=(
            "You ship indie SaaS products weekly. Your defaults: Vercel for the Next.js frontend and "
            "API routes, Neon or Supabase for Postgres, GitHub Actions to run tests and migrations on "
            "every push to main, Sentry for error tracking, PostHog/Plausible for product analytics, "
            "Stripe in live mode with webhooks wired to the production URL. You avoid Docker/k8s for "
            "MVPs unless there is a hard reason. You enforce zero-downtime via Vercel's atomic "
            "deploys; rollback is `vercel rollback <deployment>`. You wire a pre-deploy step that "
            "runs prisma migrate deploy + smoke tests before promoting."
        ),
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    verifier = Agent(
        role="Production QA Verifier",
        goal=(
            "Prove the product WORKS for a paying customer in production, not just that /health is 200."
        ),
        backstory=(
            "You do not trust green checkmarks. You run the three paid-user journeys on the LIVE "
            "production URL: (1) signup + email verification, (2) Stripe Checkout completes with a "
            "test-mode card OR a controlled live micro-charge, and the webhook provisions access, "
            "(3) the core value action executes end-to-end. You verify error rate < 0.5% over the "
            "first 5 minutes, p95 latency under your SLOs (typically 300ms for API, 2.5s LCP for "
            "landing), no console errors in Chrome and Safari, no 5xx in server logs, PostHog events "
            "firing for every funnel step, Sentry connected and receiving a test event. You produce "
            "a GO / ROLLBACK decision backed by evidence."
        ),
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    deploy_task = Task(
        description=(
            "Deploy the approved build to production with minimum moving parts. Deliverables:\n\n"
            "1. vercel.json (or equivalent) with the correct build/install commands and output dir.\n"
            "2. Production database provisioned (Neon/Supabase) with migrations applied via "
            "   `prisma migrate deploy` (or `drizzle-kit migrate`).\n"
            "3. All env vars set in Vercel (separate preview vs production). .env.example documents "
            "   every required var. No secrets committed to git.\n"
            "4. Stripe live-mode wired: products + prices created, webhook endpoint registered to "
            "   the production URL, STRIPE_WEBHOOK_SECRET set server-side.\n"
            "5. Auth provider configured for production domain (OAuth callbacks, email templates).\n"
            "6. Sentry (frontend + backend) connected; source maps uploaded.\n"
            "7. PostHog (or Plausible) production project key set client-side via NEXT_PUBLIC_*.\n"
            "8. GitHub Actions: PR workflow runs typecheck + lint + unit tests + build; main workflow "
            "   triggers Vercel deploy via vercel CLI with the prod token.\n"
            "9. Custom domain configured with HTTPS; www -> apex redirect or vice versa; HSTS on.\n"
            "10. Rollback procedure documented: exact `vercel rollback` commands and the last known-"
            "    good deployment hash, plus DB rollback steps if a migration is involved.\n\n"
            "Output a deployment package: config files, migration commands run, env var checklist, "
            "Stripe setup checklist, Sentry/PostHog keys placeholder, GitHub Actions workflows, "
            "rollback runbook."
        ),
        expected_output=(
            "Production deployment artifacts: vercel.json (or platform equivalent), database "
            "migration status, env var checklist (populated), Stripe products+prices+webhook ids "
            "(or placeholders with TODOs), Sentry DSN setup, analytics project id setup, "
            "GitHub Actions workflows (.github/workflows/ci.yml and deploy.yml), custom domain "
            "config, and ROLLBACK.md with exact commands."
        ),
        agent=deployer,
    )

    verify_task = Task(
        description=(
            "Verify the live production URL across three paid-user journeys and infrastructure health. "
            "Return a concrete GO/ROLLBACK with evidence.\n\n"
            "CHECKS:\n"
            "1. /api/health returns 200 with { status, uptime_seconds, db, version }.\n"
            "2. DB connectivity: a read and write against a test row succeed and roll back cleanly.\n"
            "3. Auth: signup, email verification (or magic link), login, session refresh, logout.\n"
            "4. Stripe: create a Checkout Session, complete with a controlled test card in live mode "
            "   (or a real $0.50 charge that we refund), observe webhook delivery, observe user "
            "   provisioning in DB.\n"
            "5. Core value action: execute the primary user journey end-to-end, confirm artifact "
            "   produced / state changed as expected.\n"
            "6. Logs: no 5xx, no unhandled exceptions, no secrets in logs.\n"
            "7. Performance: p95 API latency under 500ms; LCP under 2.5s on mobile emulation; first "
            "   paint under 1s.\n"
            "8. Errors: Sentry receives a test event; browser console clean in Chrome + Safari + "
            "   mobile Safari emulation.\n"
            "9. Telemetry: PostHog receives events for landing_view, signup_started, signup_completed, "
            "   checkout_started, checkout_completed, core_action_success.\n"
            "10. Rollback readiness: confirm `vercel rollback` dry-run works against last-good deploy.\n"
        ),
        expected_output=(
            "Production verification report with: health JSON, DB check result, auth results (per "
            "step), Stripe checkout proof (session id + webhook id), core-action proof, error log "
            "summary, performance numbers (p50/p95 API, LCP, FCP), telemetry events observed, "
            "Sentry test event id, go_no_go ('GO' | 'ROLLBACK'), rollback_command (string)."
        ),
        agent=verifier,
    )

    crew = Crew(
        agents=[deployer, verifier],
        tasks=[deploy_task, verify_task],
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )

    crew = hook_crew_full(crew, phase="deploy", cycle=1)
    return crew
