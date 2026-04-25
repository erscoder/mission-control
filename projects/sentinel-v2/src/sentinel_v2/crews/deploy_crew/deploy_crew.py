"""Deploy Crew — ship the backend to fly.io and the frontend to Cloudflare Pages
under ``<slug>.erslabs.net``. Wire Stripe webhooks to the live backend URL.
Fully automated, no manual steps after the first run.
"""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full
from sentinel_v2.tools import (
    CloudflareDnsCnameTool,
    CloudflarePagesAddCustomDomainTool,
    CloudflarePagesCreateTool,
    CloudflarePagesDeployTool,
    CloudflarePagesSetEnvTool,
    FlyAppCreateTool,
    FlyDeployTool,
    FlySecretsSetTool,
    FlyStatusTool,
    ListFilesTool,
    RunShellTool,
    StripeCreateWebhookTool,
    WriteFileTool,
)


def deploy_crew(cycle: int = 1) -> Crew:
    """Create the deploy crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)

    # Shared tool instances
    fly_app_create = FlyAppCreateTool()
    fly_secrets_set = FlySecretsSetTool()
    fly_deploy = FlyDeployTool()
    fly_status = FlyStatusTool()
    cf_pages_create = CloudflarePagesCreateTool()
    cf_pages_deploy = CloudflarePagesDeployTool()
    cf_pages_set_env = CloudflarePagesSetEnvTool()
    cf_dns_cname = CloudflareDnsCnameTool()
    cf_pages_custom_domain = CloudflarePagesAddCustomDomainTool()
    stripe_create_webhook = StripeCreateWebhookTool()
    write_file = WriteFileTool()
    list_files = ListFilesTool()
    run_shell = RunShellTool()

    deployer = Agent(
        role="Deployment Engineer",
        goal=(
            "Ship the MVP to production URLs that accept real payments. Backend on fly.io, frontend on "
            "Cloudflare Pages under <slug>.erslabs.net. Zero manual steps after kickoff."
        ),
        backstory=(
            "You have shipped 100+ indie SaaS products. You know the exact sequence for fly.io + "
            "Cloudflare + Stripe and never deviate from it:\n\n"
            "BACKEND (fly.io):\n"
            "  1. `fly_app_create(app_name='<slug>-api')` — idempotent.\n"
            "  2. Apply Postgres migrations (prisma migrate deploy / drizzle-kit migrate) using "
            "     `run_shell` in `<workspace_dir>/backend/` against the DATABASE_URL the build plan "
            "     requires.\n"
            "  3. `fly_secrets_set(app_name='<slug>-api', secrets={DATABASE_URL, STRIPE_SECRET_KEY, "
            "     … others the backend needs}, stage=True)` so they are present at first boot.\n"
            "  4. `fly_deploy(app_name='<slug>-api', source_dir='<workspace_dir>/backend')` — the "
            "     Dockerfile and fly.toml the backend agent wrote are used. The tool returns "
            "     `https://<slug>-api.fly.dev` as the backend URL.\n"
            "  5. `stripe_create_webhook(url='<backend_url>/api/stripe/webhook', events=["
            "     'checkout.session.completed', 'customer.subscription.created', "
            "     'customer.subscription.updated', 'customer.subscription.deleted', "
            "     'invoice.payment_succeeded', 'invoice.payment_failed'], draft_id='<draft_id>')` — "
            "     returns {endpoint_id, secret}. Save the secret to STRIPE_WEBHOOK_SECRET.\n"
            "  6. `fly_secrets_set(app_name='<slug>-api', secrets={STRIPE_WEBHOOK_SECRET: <secret>})` "
            "     — triggers a new release with the webhook secret now present.\n\n"
            "FRONTEND (Cloudflare Pages + erslabs.net):\n"
            "  7. `cloudflare_pages_create(project_name='<slug>')`.\n"
            "  8. `cloudflare_pages_set_env(project_name='<slug>', env_vars={"
            "     NEXT_PUBLIC_API_URL: '<backend_url>', "
            "     NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY: STRIPE_API_KEY (publishable)})`.\n"
            "  9. `run_shell('npm ci', cwd=<workspace_dir>/frontend)` then "
            "     `run_shell('npm run build', cwd=<workspace_dir>/frontend)`. Next.js static export "
            "     produces `out/`.\n"
            " 10. `cloudflare_pages_deploy(project_name='<slug>', dist_dir='<workspace_dir>/frontend/out')` "
            "     — returns the .pages.dev URL.\n"
            " 11. `cloudflare_dns_cname(subdomain='<slug>', target='<slug>.pages.dev')` — attaches "
            "     <slug>.erslabs.net to the Pages project.\n"
            " 12. `cloudflare_pages_add_custom_domain(project_name='<slug>', "
            "     domain='<slug>.erslabs.net')`.\n\n"
            "You never hardcode secrets into generated code or logs. You never touch `.env` files that "
            "contain live keys. You use the tools idempotently so retries do not create duplicates."
        ),
        tools=[
            fly_app_create,
            fly_secrets_set,
            fly_deploy,
            fly_status,
            cf_pages_create,
            cf_pages_deploy,
            cf_pages_set_env,
            cf_dns_cname,
            cf_pages_custom_domain,
            stripe_create_webhook,
            write_file,
            list_files,
            run_shell,
        ],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    verifier = Agent(
        role="Production QA Verifier",
        goal=(
            "Prove the product WORKS for a paying customer on the LIVE <slug>.erslabs.net URL, "
            "not just that /health returns 200."
        ),
        backstory=(
            "You do not trust green checkmarks. You run `curl -f` against the live frontend domain, "
            "the backend health endpoint, and the Stripe webhook URL (HEAD request). You confirm "
            "the app is HTTPS, no mixed content, no 5xx on the health endpoint, and the fly.io app "
            "status is 'running'. You produce a GO/ROLLBACK decision."
        ),
        tools=[run_shell, fly_status],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    deploy_task = Task(
        description=(
            "INPUT: workspace_dir={workspace_dir}; slug={slug}; draft_id={draft_id}; "
            "erslabs_root={erslabs_root}; stripe_publishable={stripe_publishable}.\n\n"
            "Deploy the build that lives in `{workspace_dir}/` to production. Follow the EXACT sequence "
            "in your backstory — do not skip steps, do not reorder.\n\n"
            "At the end, report:\n"
            "- backend_url (https://<slug>-api.fly.dev)\n"
            "- frontend_url (https://<slug>.{erslabs_root})\n"
            "- stripe_webhook_endpoint_id\n"
            "- cf_pages_project\n"
            "- fly_app_name\n"
            "- any step that failed with the exact tool output"
        ),
        expected_output=(
            "JSON-ish report with backend_url, frontend_url, stripe_webhook_endpoint_id, "
            "cf_pages_project, fly_app_name, and status per step (ok/failed)."
        ),
        agent=deployer,
    )

    verify_task = Task(
        description=(
            "Verify the live deployment for slug={slug} under {erslabs_root}:\n\n"
            "1. Use `run_shell` to curl the frontend at https://{slug}.{erslabs_root}/ and "
            "   confirm it returns HTTP 200 (use curl -o /dev/null -s -w with the status code "
            "   format specifier).\n"
            "2. Use `run_shell` to curl https://{slug}-api.fly.dev/api/health and confirm "
            "   the JSON response contains status 'ok' or equivalent.\n"
            "3. `fly_status(app_name='{slug}-api')` — expect running state, zero crash loops.\n"
            "4. Check the Stripe webhook endpoint id reported by the deployer is present on Stripe.\n\n"
            "Return GO if all checks pass, else ROLLBACK with the failing check and its output."
        ),
        expected_output=(
            "Verification report with http_code, health JSON, fly status summary, webhook present "
            "(bool), go_no_go ('GO'|'ROLLBACK'), and failing_step (string or null)."
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

    crew = hook_crew_full(crew, phase="deploy", cycle=cycle)
    return crew
