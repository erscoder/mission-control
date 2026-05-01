"""Deploy Crew: ship the backend to fly.io and the frontend to Cloudflare Pages
under the canonical {frontend_url}. Wire Stripe webhooks to the live backend URL.
Fully automated, no manual steps after the first run.
"""
import os

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
    WriteFileTool,
)


def deploy_crew(cycle: int = 1) -> Crew:
    """Create the deploy crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    # SENTINEL_DEPLOY_NO_MEMORY=1 disables long-term crew memory for the deploy
    # crew. Use this when validating a fix that the agent's memory might shadow
    # (e.g. a previously learned wrong association between slug and subdomain).
    use_memory = os.environ.get("SENTINEL_DEPLOY_NO_MEMORY", "0") != "1"
    memory = get_memory_for_crew_full(minimax) if use_memory else False

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
    write_file = WriteFileTool()
    list_files = ListFilesTool()
    run_shell = RunShellTool()

    deployer = Agent(
        role="Deployment Engineer",
        goal=(
            "Ship the MVP to the canonical production URLs that accept real payments. "
            "Backend on fly.io as the pre-assigned app name. Frontend on Cloudflare Pages "
            "under the pre-assigned project name and custom domain. Zero manual steps."
        ),
        backstory=(
            "You have shipped 100+ indie SaaS products. You NEVER invent names. "
            "Every name you pass to a tool comes from your task inputs LITERALLY:\n"
            "  - Fly app name: backend_app_name (already includes the -api suffix)\n"
            "  - Cloudflare Pages project name: cf_project_name\n"
            "  - DNS subdomain label: slug\n"
            "  - Final frontend URL: frontend_url\n"
            "  - Final backend URL: backend_url\n"
            "If a tool rejects a name, the fix is NEVER to guess a different name. "
            "Re-read the input variables and use those.\n\n"
            "BACKEND (fly.io):\n"
            "  1. `fly_app_create(app_name=backend_app_name)`. Idempotent.\n"
            "  2. Apply Postgres migrations (prisma migrate deploy / drizzle-kit migrate) "
            "     using `run_shell` in `<workspace_dir>/backend/` against the DATABASE_URL "
            "     the build plan requires.\n"
            "  3. `fly_secrets_set(app_name=backend_app_name, secrets={"
            "     DATABASE_URL: <db_url>, "
            "     STRIPE_SECRET_KEY: stripe_secret_key, "
            "     STRIPE_WEBHOOK_SECRET: stripe_webhook_secret, "
            "     STRIPE_PRODUCT_ID: stripe_product_id, "
            "     STRIPE_PRICE_ID: stripe_price_id, "
            "     ...other non-secret env vars}, stage=True)`. The Stripe values "
            "     above are pre-provisioned by Sentinel and passed to you as "
            "     literal task inputs; substitute them verbatim, do NOT generate "
            "     placeholder values, do NOT call any stripe_* API yourself, do "
            "     NOT skip any of the four STRIPE_* keys. They MUST be staged in "
            "     this same release so the first boot of the app does not crash on "
            "     the canonical `stripe.config.ts` env validation.\n"
            "  4. `fly_deploy(app_name=backend_app_name, source_dir='<workspace_dir>/backend')`. "
            "     The Dockerfile and fly.toml are pre-baked from the canonical NestJS "
            "     template before you start; do NOT inspect, edit, or rewrite them. Just "
            "     deploy. The tool returns the backend URL; verify it equals backend_url. "
            "     If not, you passed the wrong app name in step 1.\n"
            "  5. STRIPE PROVISIONING IS NOT YOUR JOB beyond the staging in step 3. "
            "     Sentinel already created the Stripe Product + Webhook Endpoint "
            "     before kicking off this crew. Do NOT call any `stripe_*` tool. "
            "     Do NOT create a webhook endpoint by hand. The pre-baked "
            "     controller at `backend/src/modules/stripe/stripe.controller.ts` "
            "     validates the signature against the `STRIPE_WEBHOOK_SECRET` you "
            "     just staged.\n\n"
            "FRONTEND (Cloudflare Pages + erslabs.net):\n"
            "  6. BUILD STEP. Verify `<workspace_dir>/frontend/out/` exists with `list_files`. "
            "     If it does NOT exist:\n"
            "       a. `run_shell('npm ci', cwd='<workspace_dir>/frontend')`\n"
            "       b. `run_shell('npm run build', cwd='<workspace_dir>/frontend')`\n"
            "       c. List `<workspace_dir>/frontend/out/` again. If still missing, the "
            "          frontend has no static export configured. Inspect "
            "          `frontend/next.config.mjs` and add `output: 'export'` if missing, "
            "          then re-run the build. Without an `out/` directory you CANNOT "
            "          deploy to Cloudflare Pages.\n"
            "     Do NOT proceed past this step until `out/` is populated.\n"
            "  7. `cloudflare_pages_create(project_name=cf_project_name)`.\n"
            "  8. `cloudflare_pages_set_env(project_name=cf_project_name, env_vars={"
            "     NEXT_PUBLIC_API_URL: backend_url, "
            "     NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY: stripe_publishable})`.\n"
            "  9. `cloudflare_pages_deploy(project_name=cf_project_name, "
            "     dist_dir='<workspace_dir>/frontend/out')`.\n"
            " 10. `cloudflare_dns_cname(subdomain=slug, target=f'{cf_project_name}.pages.dev')`. "
            "     Attaches frontend_url to the Pages project.\n"
            " 11. `cloudflare_pages_add_custom_domain(project_name=cf_project_name, "
            "     domain=f'{slug}.{erslabs_root}')`.\n\n"
            "You never hardcode secrets into generated code or logs. You never touch `.env` "
            "files that contain live keys. You use the tools idempotently so retries do not "
            "create duplicates."
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
            "Prove the product WORKS for a paying customer on the LIVE frontend_url, "
            "not just that /health returns 200."
        ),
        backstory=(
            "You do not trust green checkmarks. You run `curl -f` against the live frontend "
            "domain, the backend health endpoint, and the Stripe webhook URL (HEAD). You "
            "confirm HTTPS, no mixed content, no 5xx on /health, and the fly.io app status "
            "is 'running'. You produce a GO/ROLLBACK decision."
        ),
        tools=[run_shell, fly_status],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    deploy_task = Task(
        description=(
            "INPUTS (use these LITERALLY, do not invent variations):\n"
            "  workspace_dir   = {workspace_dir}\n"
            "  slug            = {slug}\n"
            "  backend_app_name= {backend_app_name}\n"
            "  backend_url     = {backend_url}\n"
            "  cf_project_name = {cf_project_name}\n"
            "  frontend_url    = {frontend_url}\n"
            "  erslabs_root    = {erslabs_root}\n"
            "  stripe_publishable      = {stripe_publishable}\n"
            "  stripe_idempotency_key  = {stripe_idempotency_key}\n\n"
            "PREVIOUS ATTEMPT FEEDBACK (if any): {deploy_feedback}\n"
            "If feedback is provided, this is a RETRY. Read the error carefully, diagnose "
            "the root cause using `list_files` and `run_shell`, fix the underlying issue "
            "(e.g. fix Dockerfile, fly.toml, missing deps, run npm build), then re-deploy. "
            "Do NOT repeat the same mistake.\n\n"
            "Deploy the build that lives in `{workspace_dir}/` to production. Follow the "
            "EXACT 12-step sequence in your backstory. Do not skip steps, do not reorder.\n\n"
            "NOTE: `<workspace_dir>/backend/fly.toml` and `<workspace_dir>/backend/Dockerfile` "
            "have already been written from the canonical NestJS template before you start. "
            "Do not inspect, edit, or rewrite them. They are correct.\n\n"
            "HARD RULES:\n"
            "- The DNS subdomain you pass to `cloudflare_dns_cname` is exactly `{slug}`. "
            "  Never anything that starts with 'draft', 'cycle', or any compound name.\n"
            "- The Cloudflare Pages project name is exactly `{cf_project_name}`.\n"
            "- The Fly app name is exactly `{backend_app_name}`.\n"
            "- The final frontend URL you report MUST equal `{frontend_url}`. If you report "
            "  any other URL, the deploy is considered failed.\n\n"
            "At the end, report:\n"
            "- backend_url (must equal {backend_url})\n"
            "- frontend_url (must equal {frontend_url})\n"
            "- stripe_webhook_endpoint_id\n"
            "- cf_pages_project (must equal {cf_project_name})\n"
            "- fly_app_name (must equal {backend_app_name})\n"
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
            "Verify the live deployment for the canonical URLs:\n\n"
            "1. `run_shell('curl -o /dev/null -s -w \"%{{http_code}}\" {frontend_url}/')` "
            "   and confirm it returns 200. If DNS does not resolve, the deploy never "
            "   completed; report ROLLBACK with the exact curl output.\n"
            "2. `run_shell('curl -fsS {backend_url}/api/health')` and confirm the JSON "
            "   response contains status 'ok' or equivalent.\n"
            "3. `fly_status(app_name='{backend_app_name}')` and expect a running state "
            "   with zero crash loops. If the app is 'pending' with zero machines, the "
            "   fly_deploy step never actually ran successfully; that is a ROLLBACK.\n"
            "4. Check the Stripe webhook endpoint id reported by the deployer is present.\n\n"
            "Return GO if all checks pass, else ROLLBACK with the failing check and its "
            "exact tool output (do not paraphrase)."
        ),
        expected_output=(
            "Verification report with http_code, health JSON, fly status summary, "
            "webhook present (bool), go_no_go ('GO'|'ROLLBACK'), failing_step (string|null)."
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
