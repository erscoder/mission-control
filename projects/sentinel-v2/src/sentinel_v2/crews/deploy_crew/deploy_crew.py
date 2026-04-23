"""Deploy Crew — Deploy the built project to production."""
from crewai import Agent, Crew, Process, Task

from sentinel_v2.config.llm_config import get_minimax_llm


def deploy_crew() -> Crew:
    """Create the deploy crew."""

    minimax_smart = get_minimax_llm("MiniMax-M2.7")
    minimax = get_minimax_llm()

    deployer = Agent(
        role="Deployment Engineer",
        goal="Deploy the project to production with proper infrastructure, monitoring, and observability",
        backstory="You've deployed mission-critical systems. You use Vercel for frontend, Railway/GCP for backend. You set up logs, alerts, and health checks.",
        tools=[],
        llm=minimax_smart,
        verbose=True,
        allow_delegation=False,
    )

    verifier = Agent(
        role="QA Verifier",
        goal="Verify the deployment: URLs are live, endpoints work, database migrations succeed, no errors in logs",
        backstory="You're paranoid about production. You health-check every endpoint, verify database migrations, check error rates. If anything is wrong, you shout.",
        tools=[],
        llm=minimax,
        verbose=True,
        allow_delegation=False,
    )

    deploy_task = Task(
        description="Deploy the project. Frontend to Vercel, backend to Railway or GCP Cloud Run. Set up environment variables, database migrations, run migrations. Include: deployment URLs, environment config used.",
        expected_output="Deployment report with: frontend URL, backend URL, deployment method used, environment variables configured (redacted), database status.",
        agent=deployer,
    )

    verify_task = Task(
        description="Verify the deployment. Test: frontend loads, all API endpoints work, database queries succeed, no 500 errors. If issues found, fix them or rollback. Return final status.",
        expected_output="Verification report with: frontend status (pass/fail), backend endpoints test results, database tests, error logs if any, final verdict (live/needs-rollback).",
        agent=verifier,
    )

    return Crew(
        agents=[deployer, verifier],
        tasks=[deploy_task, verify_task],
        process=Process.sequential,
        verbose=True,
        memory=True,
    )