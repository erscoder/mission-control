"""Build Crew - Ship a revenue-ready MVP in 1-2 weeks, not a polished over-engineered SaaS.

Process (hierarchical): Manager -> Frontend -> Backend -> Code Reviewer -> Security Auditor -> QA.
Bias throughout: ruthlessly narrow scope, monetize from day 1 (Stripe), prove the demand signal
found by research, instrument conversion tracking, ship quality gates that matter.
"""
from typing import Literal, Optional

from crewai import Agent, Crew, Task, Process
from pydantic import BaseModel, Field

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full
from sentinel_v2.tools import (
    ListFilesTool,
    RunShellTool,
    StripeCreateProductTool,
    StripeListProductsTool,
    WriteFileTool,
)


class QAGateReport(BaseModel):
    """Structured output of the QA Lead task.

    Documents the contract the flow's QA gate reads via
    ``sentinel_loop._parse_deploy_result``: ``go_no_go`` and ``build_status``
    drive the promote/reject decision. The model is no longer attached via
    ``output_pydantic`` on the QA task because MiniMax-M2.7 routinely emits
    Prisma schema fragments mixed with JSON, and strict Pydantic parsing
    would raise ``ValidationError`` inside ``crew.kickoff()``, killing the
    whole build attempt for a token-cost zero-info reason. The flow's
    permissive parser plus ``_verify_npm_build`` (deterministic gate) plus
    the QA gate fail-closed branch together provide the safety net.
    """

    go_no_go: Literal["GO", "NO_GO"] = Field(
        description="Final ship verdict. GO only when every required check passes."
    )
    build_status: Literal["clean", "warnings", "fail"] = Field(
        description="Result of `npm run build` across frontend and backend."
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="One-line summaries of issues that forced a NO_GO; empty on GO.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Optional human-readable remarks (coverage, smoke test, telemetry).",
    )


def build_crew(cycle: int = 1) -> Crew:
    """Create the professional build crew with dashboard streaming hooks."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)

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
        # 25 (CrewAI default) so the manager can delegate, evaluate, and refine
        # all 6 tasks (plan, frontend, backend, code review, security audit, QA)
        # without hitting max_iter on a tool_call final-answer. The previous
        # cap of 5 reliably triggered TaskOutput.raw ValidationError on every
        # build attempt, escalated as `blocked_agent_loop`, and burned the
        # full retry budget on the same wall. Token cost grows linearly with
        # complexity but a NO-iteration cap is worse than a permissive one
        # for a 6-task hierarchical crew.
        max_iter=25,
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
            "`<workspace_dir>/frontend/`. Never return code as chat - always write it. The API URL is "
            "injected at deploy time via `NEXT_PUBLIC_API_URL`; use that env var everywhere. The Stripe "
            "publishable key lives in `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`. Static export is preferred "
            "(`output: 'export'` in next.config.mjs) because the frontend ships to Cloudflare Pages.\n\n"
            "STRIPE - HARD RULE: The frontend MUST NOT implement any Stripe webhook handler. The webhook "
            "controller is owned exclusively by the backend (canonical NestJS template at "
            "`backend/src/modules/stripe/stripe.controller.ts`) which validates "
            "`stripe-signature` against `STRIPE_WEBHOOK_SECRET`. Do NOT create "
            "`app/api/stripe/webhook/route.ts`, `pages/api/stripe/webhook.ts`, or any file under "
            "`app/api/webhooks/`. Do NOT read `STRIPE_WEBHOOK_SECRET` or `STRIPE_SECRET_KEY` from "
            "anywhere in the frontend tree. Frontend's Stripe surface is limited to: (a) calling the "
            "backend Checkout Session endpoint via `${process.env.NEXT_PUBLIC_API_URL}/api/stripe/"
            "checkout-session` and redirecting to the returned URL, and (b) loading Stripe.js with "
            "`NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` for client-side card collection only when not using "
            "Checkout. Any frontend file containing webhook signature verification, raw-body parsing, "
            "or a `STRIPE_WEBHOOK_SECRET` reference is an automatic CRITICAL in code review."
        ),
        tools=[write_file, list_files, run_shell],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
        # Frontend writes 30+ files (app/, components/, lib/, hooks/, types/),
        # fetches DESIGN.md via curl, edits tailwind/tsconfig/next configs,
        # and may need install/build runs. Default max_iter=25 routinely
        # exhausts mid-write, MiniMax then emits tool_calls as the forced
        # final answer, and the build attempt crashes with TaskOutput.raw
        # ValidationError.
        max_iter=50,
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
            "2. The backend stack is fixed: NestJS + Prisma + PostgreSQL, multi-stage Node 20 alpine "
            "   container listening on port 8080. Do NOT write a Dockerfile, fly.toml, or "
            "   `backend/package.json` — the deploy crew (and the flow) install the canonical "
            "   pinned versions before you start. Rewriting `package.json` is the #1 cause of "
            "   ERESOLVE peer-dep deadlocks. If you genuinely need an extra dependency, install "
            "   it on top with `run_shell('npm install <pkg>@<version>', subdir='backend')` "
            "   AFTER scaffolding, never by overwriting the file. Your job is application code "
            "   only: src/, prisma/schema.prisma, tsconfig.json, tests, .env.example.\n"
            "3. When the plan calls for paid tiers, you CREATE the real Stripe products using "
            "   `stripe_create_product` (idempotent via draft_id metadata). Then you embed the returned "
            "   `price_ids` directly in your code, no placeholders like `price_XXX`. Before creating, "
            "   call `stripe_list_products` with the draft_id to avoid duplicates on retries.\n"
            "4. The Stripe webhook URL is `<backend_url>/api/stripe/webhook` where <backend_url> is "
            "   injected at deploy time. Do NOT create the webhook yourself; the deploy crew does it "
            "   once the app URL is known.\n"
            "5. Read `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` from env at runtime. List them in "
            "   `.env.example` but never hardcode.\n"
            "6. Tests only on the risky slices: auth, Stripe webhook, core business rule.\n"
        ),
        tools=[write_file, list_files, run_shell, stripe_create_product, stripe_list_products],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
        # Backend writes the most files of any agent (src/, prisma/schema,
        # tests, .env.example) plus calls Stripe APIs and may install extra
        # deps via run_shell. Same default-cap wall as the frontend lead;
        # bump to 50 to keep the sequential build attempt out of the
        # TaskOutput.raw escalation pit.
        max_iter=50,
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

    # ── Six-stage planner chain ──────────────────────────────────────────
    # The build crew's leads (frontend, backend) consistently hallucinated
    # imports, types, and entire modules when handed a single 11-section
    # monolithic plan. Replacing it with six smaller, sequential planning
    # tasks lets each stage constrain agent output and forces internal
    # consistency before any code is written. All six stages reuse
    # `strategic_manager` (same LLM = MiniMax-M2.7); structure, not agent
    # identity, is what reduces hallucination room. Outputs are markdown
    # with strict section headings — no `output_pydantic` because strict
    # JSON parsing crashes `crew.kickoff()` on malformed MiniMax output.

    _shared_inputs_block = (
        "SHARED INPUTS (use literally; do not invent variants):\n"
        "  opportunity        = {opportunity}\n"
        "  operator_capacity  = {operator_capacity}\n"
        "  workspace_dir      = {workspace_dir}\n"
        "  slug               = {slug}\n"
        "  draft_id           = {draft_id}\n"
        "  revision_notes     = {revision_notes}\n"
        "If revision_notes is non-empty, this is a RETRY: read previously written "
        "files via list_files (NOT now, you have no tools — defer to the leads), "
        "patch only the offending sections, do NOT regenerate the workspace.\n"
    )

    plan_architecture = Task(
        description=(
            f"{_shared_inputs_block}\n"
            "Produce the architecture stage of the build plan.\n\n"
            "Rules:\n"
            "- Tech stack is FIXED: backend = NestJS 10 + Prisma 5 + PostgreSQL, "
            "  frontend = Next.js 14 App Router + Tailwind + Radix. Justify any "
            "  deviation in 1 line; otherwise leave the defaults and move on.\n"
            "- The protected pre-baked files MUST appear in the file tree exactly "
            "  at their canonical paths: `backend/{Dockerfile,fly.toml,package.json,"
            "tsconfig.json,tsconfig.build.json,nest-cli.json}`, "
            "`backend/src/{config/stripe.config.ts,modules/stripe/stripe.controller.ts,"
            "prisma/prisma.service.ts,prisma/prisma.module.ts}`, "
            "`frontend/package.json`. Do NOT propose alternative paths or names.\n"
            "- Pick ONE design_template slug from "
            "`src/sentinel_v2/data/design_templates.md`. If unsure, use `linear`.\n\n"
            "Output exactly three top-level markdown sections, in order:\n"
            "  ## File Tree         : `frontend/` then `backend/` paths as a markdown "
            "                          bullet tree, one-line description per file.\n"
            "  ## Tech Stack        : bullet list, each line `<choice> - <one-line "
            "                          justification>`.\n"
            "  ## Design Template   : exactly one line `design_template: <slug>`."
        ),
        expected_output=(
            "Markdown with three sections under the EXACT headings: `## File Tree`, "
            "`## Tech Stack`, `## Design Template`. The Design Template section "
            "MUST contain the literal line `design_template: <slug>`."
        ),
        agent=strategic_manager,
    )

    plan_domain = Task(
        description=(
            f"{_shared_inputs_block}\n"
            "Produce the domain stage of the build plan.\n\n"
            "Rules:\n"
            "- Output the FULL `prisma/schema.prisma` content: datasource, generator, "
            "  every model with fields, indexes, and foreign-key relations.\n"
            "- Datasource MUST be `provider = \"postgresql\"`. Generator MUST be "
            "  `provider = \"prisma-client-js\"`.\n"
            "- Forbid `Json` columns unless the ICP explicitly requires schemaless "
            "  data (justify inline with a `// reason: ...` comment if you use one).\n"
            "- Forbid soft-delete columns (`deletedAt`) unless the ICP demands a "
            "  recovery flow.\n"
            "- After the schema, list TypeScript entity interfaces matching every "
            "  model, with the same field names and types.\n\n"
            "Output, in this exact order with NO prose between them:\n"
            "```prisma\n<full schema.prisma content>\n```\n"
            "```typescript\n<entity interfaces>\n```"
        ),
        expected_output=(
            "Two fenced code blocks: a ```prisma block with the full schema, then a "
            "```typescript block with entity interfaces. No prose, no other sections."
        ),
        agent=strategic_manager,
    )

    plan_services = Task(
        description=(
            f"{_shared_inputs_block}\n"
            "Produce the services stage of the build plan.\n\n"
            "Rules:\n"
            "- List every NestJS provider class needed for the application.\n"
            "- For each class, list method signatures only as `methodName(arg: Type, "
            "  ...): ReturnType`. NO method bodies.\n"
            "- Inject `PrismaService` from `'../../prisma/prisma.service'` (the "
            "  canonical pre-baked path). Reference `stripeConfig` from "
            "  `'../../config/stripe.config'` (a plain config object exposing "
            "  `secretKey`, `webhookSecret`, `productId`, `priceId` only, NOT a "
            "  Stripe SDK client; instantiate `new Stripe(stripeConfig.secretKey, "
            "  {{ apiVersion: '2023-10-16' }})` locally if a service needs the SDK).\n"
            "- DO NOT propose a separate webhooks service / controller; the "
            "  canonical `stripe.controller.ts` is the sole webhook handler.\n\n"
            "Output, in this exact order:\n"
            "```typescript\n<class skeletons with method signatures only>\n```\n"
            "## Dependencies\n"
            "<bullet list of which service injects which, e.g. "
            "`OrdersService -> PrismaService, BillingService`>"
        ),
        expected_output=(
            "One ```typescript fenced block with class skeletons (signatures only) "
            "followed by a `## Dependencies` heading and a bullet list."
        ),
        agent=strategic_manager,
    )

    plan_api = Task(
        description=(
            f"{_shared_inputs_block}\n"
            "Produce the API surface stage of the build plan.\n\n"
            "Rules:\n"
            "- `## Endpoints` is a markdown table with columns "
            "`method | path | auth | request | response | service.method`. "
            "  Use Zod-pseudocode for request/response shapes (e.g. "
            "  `z.object({{ email: z.string().email() }})`).\n"
            "- Auth column values: `public`, `jwt`, `webhook` (Stripe).\n"
            "- Include `GET /api/health` and the canonical `POST /api/stripe/webhook` "
            "  rows; the latter is handled by the protected stripe.controller.ts so "
            "  mark its `service.method` cell `(protected controller)`.\n"
            "- `## Frontend Pages` is a markdown table with columns "
            "`url | purpose | auth-gated?`. Include landing (`/`), pricing, "
            "checkout success/cancel, and the core app journey pages.\n\n"
            "Output exactly two top-level markdown sections under those exact "
            "headings, no other prose."
        ),
        expected_output=(
            "Two markdown tables under the EXACT headings `## Endpoints` and "
            "`## Frontend Pages`. The Endpoints table MUST include the rows "
            "`GET /api/health` and `POST /api/stripe/webhook`."
        ),
        agent=strategic_manager,
    )

    plan_infra = Task(
        description=(
            f"{_shared_inputs_block}\n"
            "Produce the infrastructure stage of the build plan.\n\n"
            "Rules:\n"
            "- `## Auth`: choose JWT or session, list cookie flags (HttpOnly, Secure, "
            "  SameSite=Lax minimum), and enumerate every protected route from "
            "  the API plan.\n"
            "- `## Stripe`: which routes invoke Checkout Session creation, where the "
            "  webhook lands. The webhook handler is `backend/src/modules/stripe/"
            "stripe.controller.ts` (PROTECTED — do not propose changes to it). The "
            "  `STRIPE_*` env vars are injected as Fly secrets by Sentinel; do NOT "
            "  read them with `|| ''` fallbacks.\n"
            "- `## Telemetry`: PostHog event names for every funnel step from the "
            "  Frontend Pages table (e.g. `landing_view`, `pricing_view`, "
            "  `checkout_started`, `checkout_succeeded`, `core_action_completed`).\n"
            "- `## Env Vars`: consolidated list of every env var the app reads at "
            "  runtime, marked `[backend]` or `[frontend]`. The four `STRIPE_*` and "
            "  `DATABASE_URL` are always present on backend.\n\n"
            "Output the four sections in that order, no other prose."
        ),
        expected_output=(
            "Markdown with the EXACT four headings `## Auth`, `## Stripe`, "
            "`## Telemetry`, `## Env Vars`, in that order, each populated."
        ),
        agent=strategic_manager,
    )

    plan_files = Task(
        description=(
            f"{_shared_inputs_block}\n"
            "Produce the file-by-file write plan. This is the AUTHORITATIVE work "
            "order the leads will follow.\n\n"
            "Rules:\n"
            "- Synthesise the prior five planning stages into a single ordered, "
            "  numbered list of files to write.\n"
            "- Group by side: backend files first (in `backend/src/...` order), then "
            "  frontend (in `frontend/{app,components,lib,...}` order). "
            "  Backend follows the dependency order: prisma schema -> entities -> "
            "  services -> controllers/dtos -> auth/middleware -> app.module.ts -> "
            "  main.ts. Frontend follows: lib/utilities -> components -> app/(routes).\n"
            "- SKIP every protected pre-baked file (Dockerfile, fly.toml, "
            "  package.json on either side, tsconfig*.json, nest-cli.json, "
            "  prisma.{service,module}.ts, stripe.{config,controller}.ts).\n"
            "- For each file, one paragraph that names: imports it pulls from where, "
            "  exports it provides, and which prior plan section it implements.\n"
            "- DO NOT include code blocks. The leads write the code; this stage "
            "  only writes the schedule.\n\n"
            "Output a single markdown numbered list. Each item formatted: "
            "`N. <relative_path> - <one paragraph>`. Aim for 25-50 entries total."
        ),
        expected_output=(
            "Markdown numbered list. Each item starts with the index, the "
            "workspace-relative file path, a hyphen, and a one-paragraph scope. "
            "No code blocks, no other top-level headings."
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
            "- Performance budget: LCP under 2s on 3G Fast throttling, no render-blocking resources.\n"
            "- Dependency peer alignment: when you add `eslint` and `@eslint/js`, both MUST share a "
            "  major (`eslint@^9` ↔ `@eslint/js@^9`, never `^10`). Same rule for any `@typescript-eslint/*` "
            "  package: align majors with `eslint`. Mismatched majors cause `ERESOLVE` and `npm install` "
            "  fails. Verify with `npm ls eslint` after install — the dependency tree must resolve "
            "  without `ERESOLVE` errors.\n\n"
            "FRONTEND PROTECTED FILES (DO NOT WRITE / DO NOT MODIFY):\n"
            "- The flow has already pre-baked `frontend/package.json` with the canonical "
            "  Next.js 14 dependency matrix (next@14.2.15, react@18.3.1, eslint@8.57.1, "
            "  eslint-config-next@14.2.15, Tailwind, Radix, Stripe.js, Lucide). Do NOT "
            "  rewrite it. Drifting eslint to v9 while eslint-config-next still requires "
            "  v7 || v8 is the leading cause of ERESOLVE failures at the post-build "
            "  verification gate.\n"
            "- If you genuinely need a NEW dependency not in the canonical matrix, install "
            "  it on top with `run_shell('npm install <pkg>@<version>', subdir='frontend')` "
            "  AFTER scaffolding. Never overwrite the file or change pinned majors.\n\n"
            "OUTPUT a production-ready project tree with tsconfig.json (strict), next.config.mjs, "
            "tailwind.config.ts, app/, components/, lib/, hooks/, types/, .env.example listing "
            "EVERY required env var, and README.md with setup + deploy steps. Do NOT write "
            "package.json (already pre-baked, see above)."
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
            "Implement the server-side API per the plan. The stack is fixed: NestJS + Prisma + "
            "PostgreSQL, listening on port 8080. Write every file under `{workspace_dir}/backend/` "
            "using `write_file`.\n\n"
            "STRIPE PRODUCT CREATION (do this FIRST):\n"
            "- Call `stripe_list_products(draft_id='{draft_id}')` to check for existing products.\n"
            "- If none, call `stripe_create_product` with the draft_id and the pricing tiers from the "
            "  plan (free trial, paid monthly, paid yearly, whatever the plan calls for).\n"
            "- Embed the returned `price_ids` directly in your checkout code. No `price_XXX` placeholders.\n\n"
            "INFRA FILES (DO NOT WRITE):\n"
            "- Do NOT create a Dockerfile, fly.toml, `backend/package.json`, "
            "  `backend/tsconfig.json`, `backend/tsconfig.build.json`, or "
            "  `backend/nest-cli.json`. The flow has already pre-baked the canonical "
            "  NestJS pinned-version package.json, the Dockerfile, fly.toml, and the "
            "  TypeScript + NestJS CLI configs in `{workspace_dir}/backend/` before you "
            "  start. Rewriting any of these is the leading cause of ERESOLVE peer-dep "
            "  failures, missing-tsconfig errors during `nest build`, and will be "
            "  overwritten at deploy time anyway.\n"
            "- If you need an additional dependency that is NOT in the canonical package.json, "
            "  install it on top with "
            "  `run_shell('npm install <pkg>@<version>', subdir='backend')`. The pinned "
            "  versions in package.json are the floor; never downgrade or change them.\n\n"
            "STRIPE PROTECTED FILES (DO NOT WRITE / DO NOT MODIFY):\n"
            "- The flow has already pre-baked `backend/src/config/stripe.config.ts` and "
            "  `backend/src/modules/stripe/stripe.controller.ts`. These enforce fail-fast on "
            "  missing `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` at boot and validate the "
            "  Stripe-Signature header against the live signing secret with no fallback. "
            "  Sentinel itself provisions the Stripe Product + Webhook Endpoint and injects "
            "  the secrets into Fly during the deploy phase; you do NOT need to call any "
            "  `stripe_*` tool from the build agent.\n"
            "- Your AppModule MUST import `StripeWebhookController` from "
            "  `./modules/stripe/stripe.controller` and register it under the controllers "
            "  array. Bootstrap MUST use `NestFactory.create(AppModule, { rawBody: true })` "
            "  so the controller can read the raw payload for signature verification.\n"
            "- NEVER read STRIPE_* env vars with `|| ''` or `|| 'sk_test'` or any other "
            "  fallback. The protected config throws on missing values; that is the contract.\n"
            "- DO NOT create a SEPARATE webhooks module / service / controller. "
            "  Specifically forbidden paths: "
            "  `src/modules/webhooks/`, `src/modules/stripe-webhook/`, "
            "  `src/webhooks/`, `src/stripe-webhook/`, "
            "  `src/services/stripe.service.ts`, `src/services/webhook.service.ts`. "
            "  The canonical `stripe.controller.ts` is the SOLE webhook handler. "
            "  Adding another one duplicates routes, breaks signature verification, "
            "  and reliably fails `nest build` (TS2339 'Property webhooks does not "
            "  exist on type StripeRuntimeConfig' is the typical signature when an "
            "  agent confuses our config object with the Stripe SDK instance).\n"
            "- `stripeConfig` (from `src/config/stripe.config.ts`) exposes ONLY: "
            "  `secretKey`, `webhookSecret`, `productId`, `priceId`. It is NOT the "
            "  Stripe SDK client; do not call `.webhooks.constructEvent()`, "
            "  `.checkout.sessions.create()`, or any other SDK method on it. "
            "  If you need an SDK client, instantiate one inside your service: "
            "  `const stripe = new Stripe(stripeConfig.secretKey, { apiVersion: "
            "  '2023-10-16' });` (the apiVersion literal MUST match stripe@14.25.0 "
            "  typings, see protected stripe.controller.ts for the canonical example).\n\n"
            "PRISMA PROTECTED FILES (DO NOT WRITE / DO NOT MODIFY):\n"
            "- The flow has already pre-baked `backend/src/prisma/prisma.service.ts` and "
            "  `backend/src/prisma/prisma.module.ts`. PrismaService extends PrismaClient with "
            "  OnModuleInit / OnModuleDestroy lifecycle hooks; PrismaModule is @Global() so "
            "  PrismaService is injectable anywhere without per-feature re-imports.\n"
            "- All your services and tests MUST import PrismaService from the canonical path: "
            "  `import { PrismaService } from '../../prisma/prisma.service'` (or the correctly "
            "  relative path from the file's location). NEVER write your own PrismaService or "
            "  PrismaModule alongside; the build verification gate runs `npm run build` and "
            "  TS2307 missing-module errors fail the draft.\n"
            "- Your AppModule MUST register `PrismaModule` in its `imports: [...]` array so the "
            "  global provider is loaded at boot. Without this, runtime DI fails on every "
            "  PrismaService injection even though TypeScript compiles.\n\n"
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
            "- Env vars validated at startup with Zod; fail fast on missing.\n"
            "- Dependency peer alignment: when you add `eslint` and `@eslint/js`, both MUST share a "
            "  major (`eslint@^9` ↔ `@eslint/js@^9`, never `^10`). Same rule for any `@typescript-eslint/*` "
            "  package: align majors with `eslint`. Mismatched majors cause `ERESOLVE` and `npm install` "
            "  fails.\n\n"
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
            "AUTOMATIC CRITICAL TRIGGERS (no judgement call, raise CRITICAL on sight):\n"
            "  a. Any file under `frontend/` that implements a Stripe webhook handler. This "
            "     includes `app/api/stripe/webhook/**`, `pages/api/stripe/webhook**`, "
            "     `app/api/webhooks/**`, or any frontend file calling "
            "     `stripe.webhooks.constructEvent`, parsing `stripe-signature`, or referencing "
            "     `STRIPE_WEBHOOK_SECRET`. The webhook is backend-only (canonical NestJS "
            "     controller at `backend/src/modules/stripe/stripe.controller.ts`).\n"
            "  b. Any env-var read with an empty-string or null fallback when the variable name "
            "     matches `STRIPE_*`, `JWT_*`, `NEXTAUTH_*`, `*_SECRET`, `*_KEY`, or `*_TOKEN`. "
            "     Examples that MUST be flagged CRITICAL: "
            "     `process.env.STRIPE_WEBHOOK_SECRET ?? ''`, "
            "     `process.env.JWT_SECRET || ''`, "
            "     `process.env.STRIPE_SECRET_KEY ?? null`, "
            "     `getEnv('STRIPE_WEBHOOK_SECRET', '')`. Required pattern: read into a const, "
            "     throw on empty at module load (e.g. `if (!secret) throw new Error(...)`), or "
            "     validate via Zod env schema with `.min(1)`.\n"
            "  c. Any backend file that hardcodes a Stripe live or test secret literal "
            "     (`sk_live_*`, `sk_test_*`, `whsec_*`).\n\n"
            "Check per-severity:\n"
            "CRITICAL - missing Stripe webhook signature verification, auth bypass, secrets in code, "
            "  row-level authorization missing on user-owned data reads, client-side env leak, plus "
            "  every trigger listed above.\n"
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
            "Output a final QA gate report. Your final answer MUST be a JSON object that matches "
            "the QAGateReport schema exactly: go_no_go ('GO'|'NO_GO'), build_status "
            "('clean'|'warnings'|'fail'), blocking_issues (list of strings), notes (optional). "
            "Do not wrap the JSON in markdown fences or prose; emit only the object."
        ),
        expected_output=(
            "A JSON object conforming to the QAGateReport Pydantic schema. Keys: go_no_go "
            "('GO' or 'NO_GO'), build_status ('clean', 'warnings', or 'fail'), blocking_issues "
            "(list of strings, empty on GO), notes (optional string). No prose outside the JSON."
        ),
        agent=qa_lead,
    )

    # Pipe each task's output to the next via `context`. The six-stage
    # planner chain hands its synthesised output (`plan_files`) to the leads.
    # Frontend gets a tighter slice (architecture + api + files); backend
    # gets the full plan because it needs domain + services as well as infra.
    # Code review and security audit each see the relevant slice plus the
    # leads' code. QA reads everything plus the file plan.
    plan_domain.context        = [plan_architecture]
    plan_services.context      = [plan_architecture, plan_domain]
    plan_api.context           = [plan_architecture, plan_domain, plan_services]
    plan_infra.context         = [plan_architecture, plan_api]
    plan_files.context         = [plan_architecture, plan_domain, plan_services, plan_api, plan_infra]
    frontend_task.context      = [plan_architecture, plan_api, plan_files]
    backend_task.context       = [plan_architecture, plan_domain, plan_services, plan_api, plan_infra, plan_files]
    code_review_task.context   = [frontend_task, backend_task, plan_files]
    security_audit_task.context = [frontend_task, backend_task, plan_infra]
    qa_task.context            = [code_review_task, security_audit_task, plan_files]

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
            plan_architecture,
            plan_domain,
            plan_services,
            plan_api,
            plan_infra,
            plan_files,
            frontend_task,
            backend_task,
            code_review_task,
            security_audit_task,
            qa_task,
        ],
        # Sequential, not hierarchical. The hierarchical pattern wraps the
        # crew in an LLM "manager" that re-evaluates every task's output and
        # may re-delegate; with MiniMax-M2.7 (tool-call-heavy) the manager
        # routinely exhausts iteration budget mid-orchestration and crashes
        # with TaskOutput.raw ValidationError. Task order here is fixed and
        # deterministic, so a sequential crew is the right shape: each agent
        # runs its task once, output flows down the explicit context chain
        # above, no manager-loop overhead.
        process=Process.sequential,
        verbose=True,
        memory=memory,
    )

    crew = hook_crew_full(crew, phase="build", cycle=cycle)
    return crew
