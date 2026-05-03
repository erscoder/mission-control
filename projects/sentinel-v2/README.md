# Sentinel V2 - CrewAI-Powered Agent Swarm for HIM

**Current Status:** 🚧 Development in progress — Underlying architecture is built, working through refinement.

## Overview

Sentinel V2 is a fully refactored version of Sentinel that leverages CrewAI's built-in capabilities for orchestrating the **HIM** (Human Intelligence Machines) agent swarm. This rewrite eliminates external dependencies like MemPalace and LangGraph, using CrewAI's native features for memory, flows, and hierarchical agent orchestration.

### Key Components

- **CrewAI Flows**: Orchestrate the Sentinel Loop with `@start`, `@listen`, `@router`, and `@human_feedback` decorators
- **CrewAI Memory**: Built-in memory for agents (`self.remember()`, `self.recall()`)
- **Hierarchical Crews**: Manager-led crews for complex tasks (using `Process.hierarchical`)
- **Telegram Integration**: Real-time approval and notifications via Telegram bot
- **Native CrewAI Tools**: Direct use of crewai-tools for web search, file operations, and more

## The Sentinel Loop

```
RESEARCH → MATCH → BUILD → APPROVE (human feedback) → DEPLOY
    ↑                                                 │
    └─────────────────────────────────────────────────┘  (continuous)
```

- **RESEARCH**: Scout thousands of websites 24/7 for market gaps and opportunities
- **MATCH**: Research the user and match opportunities to their profile and goals
- **BUILD**: Build micro-business drafts with a hierarchical crew (PM → Frontend → Backend → QA)
- **APPROVE**: Present the draft to the human via Telegram for approval or revision
- **DEPLOY**: Deploy approved builds to production (Vercel/Railway/GCP Cloud Run)

## Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key with GPT-4o access
- Telegram Bot Token (from @BotFather)
- Telegram Chat ID (your personal chat ID — get it from @userinfobot)

### Setup

1. Clone the repository:
   ```bash
   cd /Users/kike/clawd/projects/sentinel-v2
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   uv sync
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. Run Sentinel V2:
   ```bash
   # Daemon mode - REQUIRED to use Docker (sandboxed)
   docker compose up -d sentinel flask
   docker compose logs -f sentinel

   # One-shot debugging on bare mac (controlled inputs only)
   uv run python -m sentinel_v2.main --mode once

   # Visualize the flow graph
   uv run python -m sentinel_v2.main --mode plot
   ```

### Daemon execution policy (sandbox)

The continuous daemon MUST run inside Docker (`docker compose up -d sentinel`). Never run `--mode daemon` directly on the bare mac for any production / continuous use.

Build and deploy crews shell out heavily (npm, prisma, flyctl, rm, mv, cp, ...) and several `subprocess.run` paths bypass `RunShellTool`'s argv validation (`_verify_npm_build`, `fly_tool`, `osv_scanner_tool`, `shared_postgres`). Bare-mac execution re-exposes the entire host filesystem to LLM-driven shell calls. Inside Docker, the only host path the agent can reach is `~/Sentinel/` via the bind-mount in `docker-compose.yml`; every other host path is physically unreachable from the container's mount namespace.

Operator notes:
- Files written by the daemon inside `~/Sentinel/draft_*` are `root:root` on the mac (container runs as root). Cleanup needs `sudo rm -rf ~/Sentinel/draft_X` or `docker exec sentinel rm -rf /root/Sentinel/draft_X`.
- The sandbox protects against agent-driven destructive shell. It does NOT protect against an attacker with shell on the mac (`docker exec sentinel bash` bypasses every guard).
- macOS bind perf: if `npm install` of a large workspace becomes painfully slow, switch the mount to `${HOME}/Sentinel:/root/Sentinel:delegated`. Don't pre-optimize.

## Architecture

### Directory Structure

```
sentinel-v2/
├── src/sentinel_v2/
│   ├── __init__.py
│   ├── main.py                 # Entry point: CLI parsing, daemon mode
│   ├── flows/
│   │   ├── __init__.py
│   │   └── sentinel_loop.py    # The Sentinel Loop Flow
│   ├── crews/
│   │   ├── research_crew/
│   │   │   └── research_crew.py    # Scout → Analyst (sequential)
│   │   ├── match_crew/
│   │   │   └── match_crew.py       # Profile Researcher → Matcher (sequential)
│   │   ├── build_crew/
│   │   │   └── build_crew.py       # Strategic Manager → Frontend → Backend → QA (hierarchical)
│   │   └── deploy_crew/
│   │       └── deploy_crew.py      # Deployer → Verifier (sequential)
│   └── tools/
│       ├── __init__.py
│       └── telegram_tool.py    # Telegram Bot integration
├── pyproject.toml
├── .env.example
├── .env                       # Not in git - contains secrets
└── README.md
```

### Crew Specifications

In Sentinel V2, each crew implements a phase of the Sentinel Loop (for future reference, these will be elaborated in their respective crew docs):

#### Research Crew (Sequential)
- **Scout Agent**: Scans web for opportunities
- **Analyst Agent**: Prioritizes and scores opportunities

#### Match Crew (Sequential)
- **Profile Researcher Agent**: Maintains user profile
- **Matcher Agent**: Matches opportunities to profile

#### Build Crew (Hierarchical)
- **Strategic Manager Agent** (manager): Plans and delegates
- **Frontend Lead Agent**: Builds UI (Next.js, TypeScript, Tailwind)
- **Backend Lead Agent**: Builds API (NestJS, Prisma, PostgreSQL)
- **QA Engineer Agent**: Ensures quality (90%+ coverage, no deprecated code)

#### Deploy Crew (Sequential)
- **Deployment Engineer Agent**: Deploys to production
- **QA Verifier Agent**: Verifies deployment

### Memory System

CrewAI Memory provides intelligent, LLM-analyzed memory with:
- Scope-based storage (e.g., `/sentinel/research`, `/sentinel/approvals`)
- Automatic importance scoring
- Composite retrieval (semantic + recency + importance)
- Consolidation and pruning
- LLM-based query analysis

In the Flow:
- `self.remember(content, scope=...)` - Store in memory
- `self.recall(query, scope=..., limit=...)` - Retrieve from memory

### Telegram Integration

The Telegram bot (`TelegramTool`) provides:
- Bidirectional communication via `/start`, `/status`, and inline buttons
- Approval callbacks for the human feedback step
- Real-time notifications for each phase

## Development

### Adding a New Crew

1. Create a new crew directory under `src/sentinel_v2/crews/`
2. Create `__init__.py` and `crew_name.py`
3. Import and use in `sentinel_loop.py`
4. Add an `@listen` dependency in the Flow

Example:
```python
# src/sentinel_v2/crews/example_crew/example_crew.py
from crewai import Agent, Crew, Process, Task, LLM

def example_crew() -> Crew:
    agent = Agent(
        role="Example Specialist",
        goal="Do something awesome",
        backstory="You're an expert at...",
        tools=[],
        llm=LLM(model="gpt-4o-mini"),
    )
    
    task = Task(
        description="Complete the example task",
        expected_output="The expected output",
        agent=agent,
    )
    
    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
        memory=True,
    )
```

### Testing

Run a single cycle to verify all crews work:
```bash
uv run python -m sentinel_v2.main --mode once
```

### Debugging

Set the log level to DEBUG in `.env`:
```
SENTINEL_LOG_LEVEL=DEBUG
```

## Compared to Sentinel V1

| Feature | Sentinel V1 | Sentinel V2 |
|---------|--------------|--------------|
| Orchestration | LangGraph | CrewAI Flows |
| Memory | MemPalace (external) | CrewAI Memory (built-in) |
| Agent Config | YAML files | Python code |
| Crew Process | Sequential only | Sequential + Hierarchical |
| Telegram | Custom implementation | python-telegram-bot integration |
| Dependencies | Multiple custom tools | CrewAI built-in tools |

## Future Work

- [ ] Add ChromaDB as a Knowledge Source for RAG
- [ ] Implement skill routing from v1
- [ ] Add more crewai-tools integration
- [ ] Optimize memory storage with LanceDB configuration
- [ ] Add metrics and observability
- [ ] Implement self-improvement loops

## License

MIT

---

Built with ❤️ using CrewAI
