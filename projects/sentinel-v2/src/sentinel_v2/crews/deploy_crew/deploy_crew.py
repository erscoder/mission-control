"""Deploy Crew — Deployer + Verifier (with dashboard hooks)."""
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
        goal="Deploy the approved build to production with CI/CD, environment variables, monitoring, and health checks",
        backstory="You're a deployment specialist who's shipped 100+ applications. You handle: Docker containerization, GitHub Actions CI/CD, environment management (dev/staging/prod), automated testing pipelines, database migrations, SSL/TLS configuration, monitoring setup, health checks, rollback plans. Your deployments are reliable and monitoring-first.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    verifier = Agent(
        role="Production QA Verifier",
        goal="Verify the production deployment is healthy, all services running, endpoints functional, and zero errors",
        backstory="You're the last line of defense before production traffic. You verify: health check endpoints return 200, database connections are healthy, API routes respond correctly, static assets load, no 500 errors, no console errors, functionality smoke tests pass, performance metrics are acceptable. You give final GO/NO-GO for production.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    deploy_task = Task(
        description="Deploy the approved micro-business build to production. Setup: Dockerize the application, GitHub Actions workflow for CI/CD, environment variables template for production, database migration scripts, health check endpoints, SSL/TLS configuration, monitoring stack (logging, metrics, alerting), rollback plan documentation. Ensure: zero-downtime deployment, automated testing before deploy, environment-specific configs, secrets management.",
        expected_output="Deployment package with: Dockerfile (multi-stage for optimization), docker-compose.yml for orchestration, .github/workflows/deploy.yml CI/CD pipeline, .env.example for environment vars, prisma/migrations folder with all migrations, health-check endpoint implementation, monitoring configuration, rollback procedure documentation, deployment checklist.",
        agent=deployer,
    )

    verify_task = Task(
        description="Verify the production deployment is healthy and fully functional. Check: health endpoint (GET /health) returns 200 with uptime/status, database connection ping succeeds, all API routes respond correctly (smoke test critical endpoints), authentication flow works (login/token refresh), data persistence works (create/read operations), static assets load without 404, no console errors in browser, no 5xx errors in logs, performance metrics are acceptable (<500ms p95 for API calls, <3s for page load), rollback is available if needed.",
        expected_output="Production verification report with: health check status (all endpoints), database connectivity status, API route smoke test results (pass/fail), authentication flow verification, data persistence verification, static assets check, error log summary (should be zero), performance metrics summary, final recommendation (PRODUCTION GO / ROLLBACK), rollback trigger conditions.",
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
