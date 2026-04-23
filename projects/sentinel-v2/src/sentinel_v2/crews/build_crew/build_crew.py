"""Build Crew — Professional: Manager → Frontend → Backend → Code Reviewer → Security Auditor → QA (with hooks)."""
from crewai import Agent, Crew, Task, Process
from typing import List
import json

from sentinel_v2.config.llm_config import get_minimax_llm
from sentinel_v2.config.embedder_config import get_memory_for_crew_full
from sentinel_v2.crew_hooks import hook_crew_full, hook_agent_output, hook_task_completed


def build_crew() -> Crew:
    """Create the professional build crew with dashboard streaming hooks."""
    
    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    memory = get_memory_for_crew_full(minimax)

    # Strategic Manager
    strategic_manager = Agent(
        role="Strategic Product Manager",
        goal="Plan the micro-business feature-by-feature and delegate to professional specialists",
        backstory="You're a battle-tested product manager. You've shipped 50+ SaaS products. You break down opportunities into actionable specs that frontend and backend execute professionally.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=True,
        max_iter=5,
    )

    # Frontend Lead (Next.js Professional)
    frontend_lead = Agent(
        role="Senior Frontend Engineer",
        goal="Build professional UI/UX using Next.js, TypeScript, Tailwind. Production-grade components, accessible, responsive.",
        backstory="You're a senior frontend engineer with 7+ years of experience. You've built production Next.js applications at scale. You prioritize: clean component architecture, Tailwind utility patterns, excellent UX, and professional code quality.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    # Backend Lead (NestJS Professional)
    backend_lead = Agent(
        role="Senior Backend Engineer",
        goal="Build professional API and business logic using NestJS, Prisma, PostgreSQL. RESTful, type-safe, fully tested.",
        backstory="You're a senior backend architect with 8+ years of experience. You've built 30+ production APIs. You prioritize: clean architecture, proper error handling, enterprise-grade logging, full test coverage, and production-ready code.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    # Code Reviewer Agent — NEW
    code_reviewer = Agent(
        role="Senior Code Reviewer",
        goal="Review all code for bugs, bad practices, incomplete integrations, tech debt, and edge cases",
        backstory="You're a senior code reviewer with 10+ years of experience. You've caught 1000+ bugs and bad practices before production. You check for: null pointer issues, race conditions, incomplete error handling, missing edge cases, bad abstractions, over-engineering, under-engineering, TODO/FIXME comments left in production code, integration compatibility, and architectural soundness.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    # Security Auditor Agent — NEW
    security_auditor = Agent(
        role="Security Engineer",
        goal="Audit code and dependencies for security vulnerabilities and best practices",
        backstory="You're a security specialist with SAST/DAST tools expertise. You check for: package vulnerabilities (npm audit, npm audit --audit-level=high), known CVEs, SQL injection risks, XSS vulnerabilities, authentication/authorization issues, data exposure, insecure dependencies, secrets in code, and OWASP Top 10 violations. You provide actionable remediation steps.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    # QA Lead — Enhanced
    qa_lead = Agent(
        role="QA Engineering Lead",
        goal="Coordinate code review, security audit, and final QA to achieve 90%+ coverage and production quality",
        backstory="You're a QA engineering lead who ensures software is production-ready. You coordinate the review process: code review → security audit → integration testing → coverage verification → final sign-off. You enforce zero warnings in build and strict quality gates.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    # Tasks
    plan_task = Task(
        description="""Break down the opportunity into professional features. Prioritize by value vs effort. Create a comprehensive tech plan:
        
        1. Features list (MVP + v1) with acceptance criteria
        2. Tech stack justification (why Next.js, NestJS, PostgreSQL)
        3. Database schema with proper indexing
        4. API endpoints design (RESTful, versioning plan)
        5. File structure for frontend (Next.js App Router or Pages Router)
        6. File structure for backend (NestJS modules)
        7. State management approach (React Context/Zustand/Redux)
        8. Authentication strategy (JWT, session, OAuth)
        9. Deployment plan (Docker, CI/CD)
        10. Testing strategy (unit, integration, e2e)
        """,
        expected_output="Professional product spec document with: features (prioritized with effort estimates), tech decisions with justifications, database schema (PostgreSQL schema with tables, indexes, relationships), API endpoints (OpenAPI spec format), file structure (trees for frontend and backend).",
        agent=strategic_manager,
    )

    frontend_task = Task(
        description="""Implement a production-grade Next.js frontend. Requirements:
        
        1. Use Next.js (choose App Router or Pages Router and justify)
        2. TypeScript strict mode (no any types)
        3. Tailwind CSS for styling (no custom CSS files)
        4. Responsive design (mobile-first)
        5. Accessibility (ARIA labels, semantic HTML)
        6. State management (Zustand preferred for simplicity)
        7. API integration (error handling, loading states)
        8. Form validation (Zod schema)
        9. SEO optimized (metadata, structured data)
        
        Output: Complete Next.js project with package.json, tsconfig.json, next.config.js, all components, pages, lib wrapper functions, environment variables template.
        """,
        expected_output="Full Next.js production project structure with: app/ or pages/ directory, components/ (organized by feature), lib/ (API wrappers, utilities), hooks/ (custom React hooks), types/ (TypeScript types), styles/ (Tailwind config), package.json with pinned versions, tsconfig.json with strict mode, README with setup and deployment instructions.",
        agent=frontend_lead,
    )

    backend_task = Task(
        description="""Implement a production-grade NestJS backend. Requirements:
        
        1. NestJS with TypeScript
        2. Prisma ORM for PostgreSQL
        3. Proper module structure (feature-based)
        4. DTOs with validation (class-validator)
        5. Exception filters for error handling
        6. Swagger/OpenAPI documentation
        7. Logging (Winston or Nest Logger)
        8. Environment variables with validation (@nestjs/config)
        9. Guards for authentication/authorization
        10. Unit tests for services and controllers
        
        Output: Complete NestJS project with all modules, DTOs, tests, Prisma schema, migrations.
        """,
        expected_output="Full NestJS production project structure with: src/modules/ (one per feature), src/common/ (guards, filters, interceptors, decorators), src/config/ (configuration), prisma/schema.prisma (with migrations), tests/ (unit + e2e), package.json with proper dependencies, nest-cli.json, tsconfig.json, environment variables template, README with setup and deployment instructions.",
        agent=backend_lead,
    )

    code_review_task = Task(
        description="""Review the complete codebase (frontend and backend) for bugs, bad practices, and incomplete work. Check:
        
        1. Code quality: Clean code principles, SOLID principles, DRY
        2. TypeScript: Strict type checking, null safety, proper types
        3. Error handling: Try-catch blocks, proper error messages, no silent failures
        4. Edge cases: Null checks, validation, boundary conditions
        5. Integration: Frontend-backend API calls, proper request/response handling
        6. Performance: Unnecessary re-renders, proper use of React.memo, query optimization
        7. Tech debt: TODO/FIXME/HACK comments in production code
        8. Incomplete features: Placeholder code, empty functions, missing implementations
        9. Bad practices: Console.log in production, hardcoded values, magic numbers
        10. Architecture: Proper separation of concerns, scalability considerations
        
        Output: Code review report with: files reviewed, issues found (with file:line and severity), recommendations, required fixes before production.
        """,
        expected_output="Comprehensive code review report with: executive summary, detailed findings by category (critical, high, medium, low), specific issues with file:line references, recommended fixes with code examples where applicable, pass/fail recommendation for production.",
        agent=code_reviewer,
    )

    security_audit_task = Task(
        description="""Perform security audit on code and dependencies. Check:
        
        1. Dependencies: Run npm audit on both frontend and backend, check for known CVEs, verify package integrity
        2. OWASP Top 10: SQL injection, XSS, CSRF, authentication bypass, authorization flaws, sensitive data exposure
        3. Secrets: No hardcoded secrets (API keys, passwords), check environment variables usage
        4. Input validation: All inputs validated and sanitized (Zod for frontend, class-validator for backend)
        5. Output encoding: Prevent XSS by proper encoding
        6. Authentication: JWT security, token refresh, session management
        7. Authorization: Proper RBAC, JWT claims verification, permission checks
        8. Data exposure: No sensitive data in logs, proper error messages (don't leak info)
        9. Rate limiting: Protection against abuse, throttling
        10. HTTPS enforcement: Secure headers, CSP headers
        
        Output: Security audit report with: vulnerability scan results (npm audit output), identified risks with severity scores, remediation steps for each finding, pass/fail recommendation.
        """,
        expected_output="Professional security audit report with: vulnerability scan summary (critical/high/medium/low counts), detailed findings with CVSS scores (if applicable), step-by-step remediation guide, security best practices recommendations, pass/fail recommendation for production deployment.",
        agent=security_auditor,
    )

    qa_task = Task(
        description="""Coordinate final QA after code review and security audit. Verify:
        
        1. Code review findings have been addressed
        2. Security audit findings have been fixed
        3. Test coverage is 90%+ (statements, lines, functions, branches)
        4. All tests pass (unit + integration + e2e)
        5. Build succeeds with zero warnings
        6. TypeScript strict mode compiles without errors
        7. ESLint passes with zero warnings
        8. Prisma migrations apply successfully
        9. API documentation (Swagger) is complete
        10. README has setup, test, and deployment instructions
        
        Output: Final QA report with: coverage stats (statement/line/function/branch), test results summary, build verification, checklist of quality gates, final sign-off (production ready or blocked).
        """,
        expected_output="Final QA quality gate report with: coverage statistics (90%+ target), test pass rate, build status, TypeScript/ESLint verification, documentation status, quality gate checklist (all must pass), final recommendation (GO/NO-GO for production), any blocking issues with mitigation steps.",
        agent=qa_lead,
    )

    # Create crew
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
    
    # Apply dashboard streaming hooks with phase = "build"
    crew = hook_crew_full(crew, phase="build", cycle=1)
    
    return crew
