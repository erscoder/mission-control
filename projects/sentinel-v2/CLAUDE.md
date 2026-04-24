# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sentinel V2 is a CrewAI-powered autonomous agent swarm that runs a continuous loop: **RESEARCH → MATCH → BUILD → APPROVE (human) → DEPLOY**. It scouts the web for micro-business opportunities, matches them to Kike's profile, builds MVPs via hierarchical agent crews, and deploys approved builds.

## Run Commands

```bash
# Python environment (uses uv)
python -m venv .venv && source .venv/bin/activate
uv sync

# Run Sentinel
uv run python -m sentinel_v2.main --mode once     # Single cycle
uv run python -m sentinel_v2.main --mode daemon    # Continuous loop (default)
uv run python -m sentinel_v2.main --mode plot     # Visualize flow graph

# Tests
pytest                          # All tests
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests
pytest tests/e2e/              # E2E tests
pytest -v --cov=sentinel_v2     # With coverage

# Dashboard (separate Next.js app)
cd dashboard-nextjs
npm install
npm run dev
```

## Architecture

### Sentinel Loop Flow (CrewAI Flows)
The core orchestration uses CrewAI Flows (`src/sentinel_v2/flows/sentinel_loop.py`) with:
- `@start` decorator for the entry point
- `@listen` for phase transitions (each phase listens to the previous)
- `@router` for conditional routing after approval
- `SentinelState` (Pydantic BaseModel) for flow state
- `self.remember()` / `self.recall()` for CrewAI memory

**Phase flow:**
```
run_research → run_match → run_build → request_approval → check_approval
                                                                  ↓
                                                            route_after_approval
                                                                  ↓
                                                          run_deploy OR stop
```

### State Files (dashboard integration)
The flow writes state to JSON files read by the Next.js dashboard:
- `/tmp/sentinel_v2_state.json` — cycle, phase, opportunity, deployment info
- `/tmp/sentinel_v2_agent_messages.json` — agent streaming messages
- `/tmp/sentinel_v2_approval.json` — human approval state

### Crews (in `src/sentinel_v2/crews/`)
Each crew returns a `CrewAI Crew` instance with agents and tasks:

- **research_crew** (sequential): Scout → Analyst. Web research for 5 opportunities, ranked to 3.
- **match_crew** (sequential): Profile Researcher → Matcher. User profile enrichment + match scoring.
- **build_crew** (hierarchical): Strategic Manager → Frontend Lead → Backend Lead → Code Reviewer → Security Auditor → QA Lead. Hierarchical process with the manager delegating.
- **deploy_crew** (sequential): Deployment Engineer → QA Verifier.

### LLM Configuration
LLMs are configured in `src/sentinel_v2/config/llm_config.py`:
- `get_minimax_llm()` — default MiniMax provider
- `get_minimax_llm("MiniMax-M2.7")` — smarter variant for complex tasks (strategic manager, code reviewer)

### Dashboard (Next.js)
`dashboard-nextjs/` is a separate Next.js app with:
- Flask backend (`dashboard/app.py`) with Socket.IO for real-time WebSocket updates
- Radix UI + custom teal theme with Tailwind
- Polls state files and streams agent messages via WebSocket

## Key Files

| File | Purpose |
|------|---------|
| `src/sentinel_v2/flows/sentinel_loop.py` | Main Flow class, all 5 phases |
| `src/sentinel_v2/flows/state.py` | `SentinelState` Pydantic model |
| `src/sentinel_v2/crews/*/` | One directory per crew |
| `src/sentinel_v2/dashboard_state.py` | Dashboard state writer |
| `src/sentinel_v2/config/llm_config.py` | MiniMax LLM providers |
| `src/sentinel_v2/crew_hooks.py` | Dashboard streaming hooks for crews |

## Environment Variables

Key variables in `.env`:
- `OPENAI_API_KEY` — required for CrewAI
- `MINIMAX_API_KEY`, `MINIMAX_API_URL` — MiniMax LLM
- `JINA_API_KEY` — embeddings for memory
- `SENTINEL_LOOP_INTERVAL_HOURS` — daemon sleep between cycles (default: 1)
- `SENTINEL_APPROVAL_TIMEOUT_SECONDS` — approval poll timeout (default: 3600)
- `SENTINEL_SHUTDOWN` — set to "1" to gracefully stop daemon
