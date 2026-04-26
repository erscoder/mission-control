"""Build Crew - Ship a revenue-ready MVP in 1-2 weeks, not a polished over-engineered SaaS.

Process (hierarchical): Manager -> Frontend -> Backend -> Code Reviewer -> Security Auditor -> QA.
Bias throughout: ruthlessly narrow scope, monetize from day 1 (Stripe), prove the demand signal
found by research, instrument conversion tracking, ship quality gates that matter.
"""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full
from sentinel_v2.data.deploy_templates import load_templates as _load_deploy_templates
from sentinel_v2.tools import (
    ListFilesTool,
    RunShellTool,
    StripeCreateProductTool,
    StripeListProductsTool,
    WriteFileTool,
)


def build_crew(cycle: int = 1) -> Crew:
    """Create the professional build crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)
    deploy_templates = _load_deploy_templates()

    # Shared tool instances
    write_file = WriteFileTool()
    list_files = ListFilesTool()
    run_shell = RunShellTool()
    stripe_create_product = StripeCreateProductTool()
    stripe_list_products = StripeListProductsTool()

    # ── Agents ───────────────────────────────────────────────────────────────

    strategic_manager = Agent(
        role="Strategic Product Manager",
        goal=(
            "Ship a paying MVP in 1-2 weeks. Cut everything that is not on the direct path from "
            "ICP to paid conversion. Enforce a single headline value proposition."
        ),
        backstory=(
            "You have shipped 50+ SaaS micro-products. You have learned the hard way that every extra "
            "feature delays first revenue by a week. You are ruthless with scope. Your rules: "
            "one ICP, one headline pain, one call-to-action, one paid tier (plus a free trial if it "
            "reduces friction). No marketing page animations, no dashboards the user will not use in "
            "week 1, no settings page if defaults work. You obsess over the funnel: landing -> signup "
            "-> activation -> paid. Everything else is a distraction."
        ),
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=True,
        max_iter=5,
    )

    frontend_lead = Agent(
        role="Senior Frontend Engineer",
        goal=(
            "Ship a Next.js 14 app with App Router, Tailwind, Radix primitives, and a tight conversion-"
            "focused landing page plus the core app screens. Mobile-first. Accessible. Fast."
        ),
        backstory=(
            "You are a senior product engineer who has shipped Next.js apps with Stripe checkout, "
            "Supabase auth, and analytics instrumentation baked in from day 1. You default to App Router, "
            "Server Components for data fetching, Tailwind + Radix UI for components, next-safe-action "
            "for typed server actions, Zod for form validation, and react-hook-form for complex forms. "
            "You ship dark-mode-by-default, responsive, accessible (WCAG AA). PostHog or Plausible wired "
            "for funnel telemetry.\n\n"
            "DESIGN SYSTEM: The plan includes a `design_template` slug. Before writing any component, "
            "fetch the full design system by running:\n"
            "  run_shell: curl -sL https://getdesign.md/<slug>/design-md\n"
            "This returns a DESIGN.md with color palette, typography, spacing, shadows, and component "
            "styles. Save it to `<workspace_dir>/frontend/DESIGN.md` with write_file. Then use those "
            "exact tokens (colors, fonts, spacing scale, border-radius, shadows) in your Tailwind config "
            "and components. Never hardcode visual values — always derive from the design system.\n\n"
            "HOW YOU WORK: you materialize every file to disk using the `write_file` tool under "
            "`<workspace_dir>/frontend/`. Never return code as chat — always write it. The API URL is "
            "injected at deploy time via `NEXT_PUBLIC_API_URL`; use that env var everywhere. The Stripe "
            "publishable key lives in `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`. Static export is preferred "
            "(`output: 'export'` in next.config.mjs) because the frontend ships to Cloudflare Pages."
        ),
        tools=[write_file, list_files, run_shell],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    backend_lead = Agent(
        role="Senior Backend Engineer",
        goal=(
            "Ship a typed, tested, Stripe-integrated API that the frontend can consume safely. "
            "Pragmatic over enterprise. Create REAL Stripe products and embed their price IDs."
        ),
        backstory=(
            "You are a senior backend engineer who has shipped 30+ production APIs for indie SaaS. You "
            "prefer small, boring, fast code. Your defaults: Next.js Route Handlers + Drizzle + "
            "PostgreSQL for simple CRUD, or NestJS + Prisma if the plan explicitly needs structure. "
            "Either way: strict TypeScript, Zod on every input, proper HTTP status codes, structured "
            "logging with request IDs, a /health endpoint, rate limiting on public endpoints, Stripe "
            "Checkout + webhook signature verification on day 1, row-level authorization everywhere.\n\n"
            "HOW YOU WORK:\n"
            "1. You materialize every file to disk with `write_file` under `<workspace_dir>/backend/`. "
            "   Never return code as chat.\n"
            "2. The backend ships to fly.io, so you MUST produce a Dockerfile and fly.toml in "
            "   `<workspace_dir>/backend/` matching the chosen stack. Use the DEPLOY TEMPLATES "
            "   below as a starting point — adapt to the actual stack but keep the structure.\n"
            "3. When the plan calls for paid tiers, you CREATE the real Stripe products using "
            "   `stripe_create_product` (idempotent via draft_id metadata). Then you embed the returned "
            "   `price_ids` directly in your code — no placeholders like `price_XXX`. Before creating, "
            "   call `stripe_list_products` with the draft_id to avoid duplicates on retries.\n"
            "4. The Stripe webhook URL is `<backend_url>/api/stripe/webhook` where <backend_url> is "
            "   injected at deploy time. Do NOT create the webhook yourself — the deploy crew does it "
            "   once the app URL is known.\n"
            "5. Read `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` from env at runtime. List them in "
            "   `.env.example` but never hardcode.\n"
            "6. Tests only on the risky slices: auth, Stripe webhook, core business rule.\n\n"
            "## DEPLOY TEMPLATES\n"
            "Pick the template closest to your stack, copy it into `<workspace_dir>/backend/`, "
            "and adapt. Replace `{{SLUG}}` in fly.toml with the actual slug. "
            "DO NOT write Dockerfiles from scratch — always start from these templates.\n\n"
            f"{deploy_templates}"
        ),
        tools=[write_file, list_files, run_shell, stripe_create_product, stripe_list_products],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    code_reviewer = Agent(
        role="Senior Code Reviewer",
        goal="Block obvious bugs, broken integrations, and scope creep before they reach QA.",
        backstory=(
            "You have caught 1000+ production-breaking bugs in PR review. You look for: null/undefined "
            "slips, missing await, race conditions, leaky error handlers, hard-coded secrets, forgotten "
            "Stripe webhook signature checks, permissive CORS, missing auth on protected routes, "
            "off-by-one in pagination, SQL N+1 queries, dangling TODO/FIXME/HACK, dead code, "
            "over-engineering (abstractions with a single caller), and under-engineering (duplicated "
            "logic in 3 files). You report severity (critical / high / medium / low) and a concrete fix.\n\n"
            "HOW YOU WORK: you read the code from disk using `list_files` and reviewing key files "
            "(the frontend and backend agents already wrote them to `<workspace_dir>/`)."
        ),
        tools=[list_files, run_shell],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    security_auditor = Agent(
        role="Security Engineer",
        goal="Prevent the five attacks that kill indie SaaS first: auth bypass, Stripe webhook forgery, "
             "secrets leaks, XSS/SQLi in public forms, over-privileged OAuth scopes.",
        backstory=(
            "You audit code with an attacker mindset. You check: dependency CVEs (npm audit --omit=dev "
            "--audit-level=high), OWASP Top 10 coverage, Stripe webhook signature verification, "
            "correct use of cryptographic primitives, secrets in git history, client-side env leakage, "
            "unsafe JSON parsing, SSRF in any fetch-by-URL endpoints, row-level authorization on every "
            "DB read, open redirects, unsafe iframe embedding, permissive CORS/CSP, HTTPS and HSTS "
            "enforcement, cookie flags (HttpOnly, Secure, SameSite=Lax min), JWT secret rotation. "
            "You provide CVSS severity and the exact fix, not vague advice.\n\n"
            "HOW YOU WORK: run `npm audit --omit=dev --audit-level=high` via `run_shell` inside the "
            "workspace backend and frontend dirs. Read suspect files via `list_files`."
        ),
        tools=[list_files, run_shell],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    qa_lead = Agent(
        role="QA Engineering Lead",
        goal="Enforce the quality gates that matter for a paying MVP; do not block on cosmetic issues.",
        backstory=(
            "You run the gate between build and deploy. You focus on: does signup work, does Stripe "
            "checkout complete, does the webhook grant access, does the core value action succeed end-"
            "to-end on Chrome + Safari + mobile? Your coverage target is 80% on business-critical "
            "modules (payments, auth, core workflow) and 40-60% overall; you do not waste time chasing "
            "100%. Build must be green, TypeScript strict must compile, ESLint must pass on new files, "
            "Playwright smoke must pass the three paid-user journeys: signup -> checkout -> core action.\n\n"
            "HOW YOU WORK: run `npm run build`, `npm test`, `npx tsc --noEmit`, `npx eslint .` inside "
            "`<workspace_dir>/backend/` and `<workspace_dir>/frontend/` via `run_shell`, and verify each "
            "exit code in the final report."
        ),
        tools=[list_files, run_shell],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    # ── Tasks ────────────────────────────────────────────────────────────────

    plan_task = Task(
        description=(
            "INPUT: opportunity = {opportunity}; operator_capacity = {operator_capacity}; "
            "workspace_dir = {workspace_dir}; slug = {slug}; draft_id = {draft_id}.\n\n"
            "REVISION FEEDBACK (if any): {revision_notes}\n"
            "If revision feedback is provided, this is NOT a fresh build. The workspace "
            "already has previous code. Focus ONLY on the feedback. Read existing files "
            "first, then make surgical changes. Do not rebuild from scratch.\n\n"
            "Produce a 1-page shipping plan. Rules:\n"
            "- MVP must be shippable in 20-60 engineering hours.\n"
            "- Scope MUST cut to ONE headline value prop and ONE primary user journey.\n"
            "- Stripe Checkout is included from day 1. No free-forever; free trial only if friction "
            "  is unacceptable without it.\n"
            "- Event tracking (PostHog or Plausible) must instrument every funnel step.\n"
            "- Do NOT plan admin dashboards, settings pages, or teams/orgs unless explicitly justified "
            "  by the ICP and the headline value prop.\n\n"
            "Deliverables:\n"
            "1. One-line value proposition (the headline for the landing page).\n"
            "2. ICP statement (echo from qualification).\n"
            "3. Primary user journey in 5-7 steps, from landing page to first paid action.\n"
            "4. MVP feature list (max 8 items). Mark each: [core | nice-to-have | cut].\n"
            "5. Tech stack decision with one-line justification per choice.\n"
            "6. **Design template slug** — pick ONE slug from the design template index at "
            "   `src/sentinel_v2/data/design_templates.md`. Match the app domain to the table. "
            "   If unsure, use `linear.app`. Output the slug as `design_template: <slug>`.\n"
            "7. PostgreSQL schema: tables + columns + indexes + FK relationships (keep it tight).\n"
            "8. API surface: endpoints, methods, auth, request/response shapes (Zod/DTO pseudocode).\n"
            "9. Pricing: one paid tier + trial length + Stripe product/price IDs as env vars.\n"
            "10. Telemetry plan: event names for every funnel step.\n"
            "11. Risk list: 3 things that could break the ship-in-2-weeks timeline, with mitigations.\n"
        ),
        expected_output=(
            "A concrete shipping plan in structured markdown (or JSON) with the 11 sections above. "
            "MUST include `design_template: <slug>` with a valid slug from the index. "
            "The Feature list MUST be <= 8 items. The schema MUST be in DDL or Prisma schema syntax. "
            "The API surface MUST be in OpenAPI-style YAML or a terse table."
        ),
        agent=strategic_manager,
    )

    frontend_task = Task(
        description=(
            "Implement the Next.js 14 (App Router) frontend per the plan. Write every file to disk "
            "under `{workspace_dir}/frontend/` using the `write_file` tool (never return code as chat).\n\n"
            "STEP 0 — DESIGN SYSTEM (do this FIRST):\n"
            "The plan contains a `design_template` slug. Fetch the design system:\n"
            "  run_shell: curl -sL https://getdesign.md/<slug>/design-md\n"
            "Save the output to `{workspace_dir}/frontend/DESIGN.md` with write_file. Extract the color "
            "palette, font family, font scale, spacing, shadows, and border-radius tokens. Wire them into "
            "tailwind.config.ts `theme.extend`. All components MUST use these tokens — no hardcoded hex "
            "values, font names, or spacing values outside the design system.\n\n"
            "HARD REQUIREMENTS:\n"
            "- TypeScript strict (no `any`, no `@ts-ignore` without a comment justifying it).\n"
            "- Tailwind + Radix UI primitives (Dialog, Dropdown, Toast). No custom CSS files.\n"
            "- Responsive mobile-first. Dark mode by default.\n"
            "- Accessibility: semantic HTML, ARIA where needed, keyboard navigable, focus-visible.\n"
            "- Landing page: headline, subhead, 3 benefit bullets, social proof slot, pricing block, "
            "  primary CTA above the fold, FAQ, footer. Conversion-optimized, not art-directed.\n"
            "- Stripe Checkout integration via hosted Checkout (not custom card form).\n"
            "- Auth: Supabase auth or NextAuth with email+magic-link; protect core routes with middleware.\n"
            "- Server Components for all data fetching; Client Components only when needed.\n"
            "- Zod schemas shared with backend; `next-safe-action` for mutations.\n"
            "- PostHog SDK wired; call `capture()` on every funnel step named in the plan.\n"
            "- Lucide icons; no emojis in UI copy.\n"
            "- Performance budget: LCP under 2s on 3G Fast throttling, no render-blocking resources.\n\n"
            "OUTPUT a production-ready project tree with package.json (pinned majors), tsconfig.json "
            "(strict), next.config.mjs, tailwind.config.ts, app/, components/, lib/, hooks/, types/, "
            ".env.example listing EVERY required env var, and README.md with setup + deploy steps."
        ),
        expected_output=(
            "Full Next.js 14 App Router project. Directory tree and key files (page.tsx, layout.tsx, "
            "components, lib/stripe.ts, lib/posthog.ts, middleware.ts, schemas, types) must be present. "
            "Stripe checkout flow + webhook handler is present in the frontend route handlers OR handed "
            "off to the backend task - pick one and wire it end-to-end."
        ),
        agent=frontend_lead,
    )

    backend_task = Task(
        description=(
            "Implement the server-side API per the plan. Default to Next.js Route Handlers for a single-"
            "service app; only use NestJS if the plan explicitly needs it. Write every file under "
            "`{workspace_dir}/backend/` using `write_file`.\n\n"
            "STRIPE PRODUCT CREATION (do this FIRST):\n"
            "- Call `stripe_list_products(draft_id='{draft_id}')` to check for existing products.\n"
            "- If none, call `stripe_create_product` with the draft_id and the pricing tiers from the "
            "  plan (free trial, paid monthly, paid yearly — whatever the plan calls for).\n"
            "- Embed the returned `price_ids` directly in your checkout code. No `price_XXX` placeholders.\n\n"
            "DEPLOY ARTIFACTS (required for fly.io):\n"
            "- `Dockerfile` — COPY from the deploy templates in your backstory instructions. "
            "  Adapt the template to the chosen stack. DO NOT write from scratch.\n"
            "- `fly.toml` — COPY from the deploy templates. Replace `{{SLUG}}` with `{slug}`. "
            "  Must have app name `{slug}-api`, health check on /api/health, internal_port 8080.\n\n"
            "HARD REQUIREMENTS:\n"
            "- Strict TypeScript throughout.\n"
            "- Zod (or class-validator if NestJS) on every input, including query params.\n"
            "- Prisma (or Drizzle) with PostgreSQL; provide schema, initial migration, and seed.\n"
            "- Stripe: Checkout Session creation endpoint + webhook endpoint with raw-body signature "
            "  verification. Webhook grants access / provisions the user. Never trust client.\n"
            "- Auth: JWT or session cookie (HttpOnly, Secure, SameSite=Lax). Row-level authorization "
            "  enforced in every query that touches user-owned data.\n"
            "- Rate limit public endpoints (60 req/min per IP minimum, lower for auth endpoints).\n"
            "- Structured logging with request IDs (pino or Nest logger). No console.log in prod paths.\n"
            "- /api/health endpoint returning uptime, DB ping, version.\n"
            "- Tests for the three risky slices only: auth, Stripe webhook handling, core business rule. "
            "  Use Vitest (or Jest if NestJS). Coverage target: 80% on these modules.\n"
            "- Env vars validated at startup with Zod; fail fast on missing.\n\n"
            "OUTPUT: complete server code, prisma/schema.prisma, migrations, seed, tests, and a README "
            "section documenting every API route with method, auth requirement, request, response, "
            "and error cases."
        ),
        expected_output=(
            "Backend source tree with routes/handlers, services, Prisma schema + migration, Stripe "
            "checkout + webhook implementation, auth middleware, rate limiter, logging, /health, and "
            "a test suite for payments + auth + core rule. All env vars documented in .env.example."
        ),
        agent=backend_lead,
    )

    code_review_task = Task(
        description=(
            "Review EVERY file produced by frontend_lead and backend_lead.\n\n"
            "Check per-severity:\n"
            "CRITICAL - missing Stripe webhook signature verification, auth bypass, secrets in code, "
            "  row-level authorization missing on user-owned data reads, client-side env leak.\n"
            "HIGH - unvalidated inputs, missing await, unhandled promise rejections, SQL N+1, CORS too "
            "  open, rate limit missing on public endpoints, tokens in URLs, PII in logs.\n"
            "MEDIUM - TypeScript `any` abuse, dead code, duplicated logic, dangling TODO/FIXME, over-"
            "  engineered abstractions with one caller, missing error boundaries in React.\n"
            "LOW - inconsistent naming, magic numbers, stale comments, unused imports.\n\n"
            "Output a code review report. Every issue MUST include file:line, severity, a one-line "
            "explanation, and a concrete fix (code snippet if small). Count issues by severity. "
            "Block (NO-GO) if ANY critical issue remains unresolved."
        ),
        expected_output=(
            "Markdown or JSON report with: executive summary, issue count by severity, itemized "
            "findings (file:line + severity + fix), files_reviewed (int), issues_count (int), "
            "go_no_go ('GO' only if zero critical and <=2 high remain)."
        ),
        agent=code_reviewer,
    )

    security_audit_task = Task(
        description=(
            "Attacker-mindset audit. Run the following specific checks and report findings.\n\n"
            "1. Stripe: webhook uses `stripe.webhooks.constructEvent` with STRIPE_WEBHOOK_SECRET; raw "
            "   body passed untouched; idempotency handled; event types narrowly switched.\n"
            "2. Auth: password/OTP flows use constant-time compare; JWT has exp and aud claims; refresh "
            "   tokens are rotated; sessions are invalidated on password change.\n"
            "3. Authorization: every DB read on user-owned data is scoped by user_id/org_id; no IDOR "
            "   surface in REST paths.\n"
            "4. Inputs: every body/query/param is Zod/class-validator gated; no raw string concat into "
            "   SQL; Prisma parameters only.\n"
            "5. XSS: no dangerouslySetInnerHTML without DOMPurify; all user text rendered safely; no "
            "   inline scripts served.\n"
            "6. Secrets: none in repo; .env not committed; client-only env vars prefixed correctly "
            "   (NEXT_PUBLIC_*) and only for non-sensitive values.\n"
            "7. Headers: HSTS, CSP (no unsafe-inline in prod), X-Content-Type-Options, Referrer-Policy.\n"
            "8. Dependencies: `npm audit --omit=dev --audit-level=high` clean.\n"
            "9. CORS: explicit allowlist; credentials only to trusted origins.\n"
            "10. Rate limit + bot protection on signup, login, and password reset.\n\n"
            "Output a security audit report. For EVERY finding: CVSS severity, OWASP category, one-"
            "sentence impact, exact remediation. Block (NO-GO) if any CRITICAL finding remains."
        ),
        expected_output=(
            "Security audit report (markdown or JSON) with: vulnerability_count_by_severity "
            "(critical/high/medium/low), findings (each with CVSS, OWASP, impact, fix), "
            "npm_audit_summary, go_no_go ('GO' only with zero critical)."
        ),
        agent=security_auditor,
    )

    qa_task = Task(
        description=(
            "Run the final ship gate. Verify:\n\n"
            "1. Code review issues: all CRITICAL and HIGH resolved.\n"
            "2. Security audit: zero CRITICAL findings open.\n"
            "3. TypeScript strict compiles clean on both sides.\n"
            "4. ESLint passes on changed/new files.\n"
            "5. Prisma (or Drizzle) migrations apply cleanly to a fresh DB.\n"
            "6. Test suite passes; coverage >= 80% on payments + auth + core business modules; "
            "   overall coverage >= 50%.\n"
            "7. Build completes with zero warnings.\n"
            "8. Playwright smoke test passes three journeys: signup, checkout->webhook->provisioned, "
            "   core value action end-to-end.\n"
            "9. Funnel telemetry events fire at each step (verified via PostHog capture log).\n"
            "10. README has: setup, env vars list, deploy steps, rollback steps, known issues.\n\n"
            "Output a final QA gate report with per-check status, metrics, and a single GO / NO-GO."
        ),
        expected_output=(
            "QA gate report with: coverage_percent (number), tests_passed (int), tests_total (int), "
            "issues_count (int), build_status ('clean'|'warnings'|'fail'), playwright_smoke "
            "('pass'|'fail'), funnel_events_ok (bool), go_no_go ('GO'|'NO-GO'), blocking_issues (list)."
        ),
        agent=qa_lead,
    )

    crew = Crew(
        agents=[
            strategic_manager,
            frontend_lead,
            backend_lead,
            code_reviewer,
            security_auditor,
            qa_lead,
        ],
        tasks=[
            plan_task,
            frontend_task,
            backend_task,
            code_review_task,
            security_audit_task,
            qa_task,
        ],
        process=Process.hierarchical,
        verbose=True,
        memory=memory,
        manager_llm=minimax_smart,
    )

    crew = hook_crew_full(crew, phase="build", cycle=cycle)
    return crew
