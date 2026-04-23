"""Build Crew — Hierarchical: Build SMB (Strategic Manager -> Frontend -> Backend -> QA)."""
from crewai import Agent, Crew, Task, Process

from sentinel_v2.config.llm_config import get_minimax_llm


def build_crew() -> Crew:
    """Create the hierarchical build crew."""

    minimax = get_minimax_llm()
    minimax_smart = get_minimax_llm("MiniMax-M2.7")

    # Strategic Manager — plans and delegates
    strategic_manager = Agent(
        role="Strategic Product Manager",
        goal="Plan the micro-business feature-by-feature and delegate to specialists",
        backstory="You're a battle-tested product manager. You've shipped 50+ SaaS products. You break down opportunities into actionable specs that frontend and backend execute.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=True,
        max_iter=5,
    )

    # Frontend Specialist
    frontend_lead = Agent(
        role="Frontend Lead",
        goal="Build the UI/UX using Next.js, TypeScript, Tailwind. Reusable components, accessible, responsive.",
        backstory="You're a frontend expert. You know Next.js inside out. You prioritize: clean component architecture, Tailwind utility patterns, Lucide icons (never emojis), and excellent UX.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    # Backend Specialist
    backend_lead = Agent(
        role="Backend Lead",
        goal="Build the API and business logic using NestJS, Prisma, PostgreSQL. RESTful, type-safe, tested.",
        backstory="You're a backend architect. You've built 30+ production APIs. You prioritize: clean architecture, Prisma for ORM, proper error handling, and full test coverage.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    # QA Specialist
    qa_lead = Agent(
        role="QA Engineer",
        goal="Review code, write tests, ensure quality standards: 90% coverage, no deprecated code, TypeScript strict",
        backstory="You're a quality crusader. You've caught 1000+ bugs before production. You enforce: comprehensive tests, zero deprecated code, and strict TypeScript.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    # Task definitions
    plan_task = Task(
        description="Break down the opportunity into features. Prioritize by value vs effort. Create a tech plan for frontend and backend teams. Include: MVP features, v1 features, tech stack choice, database schema draft, API endpoints list.",
        expected_output="Product spec document with: features (prioritized), tech decisions, database schema (text description), API endpoints (list), file structure plan.",
        agent=strategic_manager,
    )

    frontend_task = Task(
        description="Implement the UI components. Use Next.js page router, TypeScript, Tailwind, Lucide React icons. Create a complete, functional frontend with all MVP features.",
        expected_output="Full Next.js project structure with: pages/ directory, components/, lib/, styles/. All TypeScript files, no any types. README with setup instructions.",
        agent=frontend_lead,
    )

    backend_task = Task(
        description="Implement the API using NestJS. Prisma models, services, controllers, DTOs, error handling. Include tests for critical paths. Connect to PostgreSQL.",
        expected_output="Full NestJS project structure with: src/modules/, src/common/, prisma/schema.prisma, tests/. All TypeScript, full DTOs, 90%+ coverage.",
        agent=backend_lead,
    )

    qa_task = Task(
        description="Review the complete codebase from frontend and backend. Enforce standards: 90% test coverage, no deprecated code, strict TypeScript, no console.log in production. Fix any issues found.",
        expected_output="QA report with: coverage stats, issues found (with file:line), fixes applied, final sign-off (pass/fail).",
        agent=qa_lead,
    )

    return Crew(
        agents=[strategic_manager, frontend_lead, backend_lead, qa_lead],
        tasks=[plan_task, frontend_task, backend_task, qa_task],
        process=Process.hierarchical,
        verbose=True,
        memory=True,
        manager_llm=minimax_smart,
    )