# Sentinel V2 — Project Overview

*Last updated: 2026-04-23*

---

## What Is Sentinel V2?

Sentinel V2 is the evolution of Sentinel (HIM — Human Intelligence Machines), a CrewAI-powered agent swarm that autonomously researches, builds, and deploys micro-businesses 24/7, requiring human approval at every cycle.

**Product:** HIM — Human Intelligence Machines
**Goal:** Generate $1M using autonomous AI agents
**User:** Kike (Enrique Rubio)

---

## The Sentinel Loop

```
RESEARCH → MATCH → BUILD → APPROVE → DEPLOY
    ↑                                  │
    └──────────────────────────────────┘  (continuous cycle)
```

1. **RESEARCH** — Scout thousands of websites 24/7, build opportunity database
2. **MATCH** — Research Kike's profile, map opportunities to goals
3. **BUILD** — Create micro-business drafts with hierarchical crew
4. **APPROVE** — Kike reviews and approves everything via the dashboard
5. **DEPLOY** — Execute with approved budget

---

## Architecture

### Systems

```
┌─────────────────────────────────────────────────────────┐
│                    Sentinel V2                          │
├──────────────────┬──────────────────────────────────────┤
│   BACKEND        │   FRONTEND                          │
│   (Python/CrewAI)│   (Next.js 14 + Tailwind)           │
│                  │                                      │
│  SentinelLoopFlow│  dashboard-nextjs/                   │
│       ↓          │   └── src/app/         → layout.tsx  │
│  ┌───────────┐  │       ├── page.tsx      → main view  │
│  │ research  │  │       └── globals.css   → theme      │
│  │ match     │  │                                      │
│  │ build     │  │   src/components/                    │
│  │ deploy    │  │   ├── FlowStatePanel.tsx             │
│  └───────────┘  │   ├── PipelineProgressBar.tsx        │
│       ↓          │   ├── Button.tsx                     │
│  dashboard_state │   └── Card.tsx                       │
│       ↓          │                                      │
│  Socket.IO ─────┼──→ http://localhost:3003             │
│  (port 5173)    │                                      │
│                  │   WEBSOCKET: Socket.IO client         │
└──────────────────┴──────────────────────────────────────┘
```

### Backend Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | CrewAI Flows (`@start`, `@listen`, `@router`) |
| Agents | CrewAI Agents (Python, no YAML) |
| Memory | CrewAI Memory (LanceDB-backed) |
| Crew Process | Sequential + Hierarchical (Manager-led) |
| State | Pydantic BaseModel (`SentinelState`) |
| Dashboard comms | Socket.IO (namespace: `/dashboard`) |
| File-based state | `/tmp/sentinel_v2_*.json` |

### Frontend Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS v3 |
| Component library | Radix UI Themes (`@radix-ui/themes`) |
| Icons | Lucide React |
| Real-time | Socket.IO Client |
| Ports | Dev: 3003, Prod: standard Next.js |

---

## Directory Structure

```
sentinel-v2/
├── docs/                        # ← YOU ARE HERE
│   └── OVERVIEW.md
├── src/sentinel_v2/
│   ├── main.py                  # CLI entry: --mode once/daemon/plot
│   ├── crew_hooks.py            # CrewAI hooks (on_start, on_complete)
│   ├── dashboard_state.py       # State manager → JSON files + Socket.IO
│   ├── flows/
│   │   └── sentinel_loop.py     # SentinelLoopFlow (5-phase loop)
│   ├── crews/
│   │   ├── research_crew/        # Scout → Analyst (sequential)
│   │   ├── match_crew/           # Profile Researcher → Matcher (sequential)
│   │   ├── build_crew/           # Manager → Frontend → Backend → QA (hierarchical)
│   │   └── deploy_crew/         # Deployer → Verifier (sequential)
│   └── dashboard_state.py       # Writes state files consumed by the dashboard
├── dashboard-nextjs/            # Frontend Next.js app
│   ├── src/app/
│   │   ├── layout.tsx           # Theme provider (Radix)
│   │   ├── page.tsx             # Main dashboard page
│   │   └── globals.css          # Tailwind + custom palette
│   ├── src/components/
│   │   ├── FlowStatePanel.tsx
│   │   ├── PipelineProgressBar.tsx
│   │   ├── Button.tsx
│   │   └── Card.tsx
│   └── src/lib/
│       └── config.ts            # BACKEND_URL, WEBSOCKET_NAMESPACE
├── run_dashboard.py             # Legacy Flask dashboard (deprecated)
├── pyproject.toml
└── .env / .env.example
```

---

## Crews

### Research Crew (Sequential)
Scouts the web for market gaps and opportunities.
- **Scout Agent**: Scans websites, identifies opportunities
- **Analyst Agent**: Scores and prioritizes opportunities

### Match Crew (Sequential)
Researches Kike's profile and matches opportunities.
- **Profile Researcher Agent**: Maintains user context
- **Matcher Agent**: Scores fit between opportunity and profile

### Build Crew (Hierarchical)
Creates micro-business drafts.
- **Strategic Manager Agent** (manager): Plans, delegates, reviews
- **Frontend Lead Agent**: Next.js, TypeScript, Tailwind
- **Backend Lead Agent**: NestJS, Prisma, PostgreSQL
- **QA Engineer Agent**: 90%+ coverage, no deprecated code

### Deploy Crew (Sequential)
Deploys approved builds to production.
- **Deployment Engineer Agent**: Vercel/Railway/GCP Cloud Run
- **QA Verifier Agent**: Smoke tests post-deploy

---

## Dashboard (Frontend)

### Running

```bash
cd ~/clawd/projects/sentinel-v2/dashboard-nextjs
npm run dev       # Dev server on :3003
npm run build     # Production build
```

### Backend (for dashboard)

```bash
cd ~/clawd/projects/sentinel-v2
python run_dashboard.py   # Flask + Socket.IO on :5173
```

The dashboard connects to `http://localhost:5173` via Socket.IO (`/dashboard` namespace) and renders:
- **Pipeline Progress Bar** — 5 phases: Research → Match → Build → Approve → Deploy
- **Flow State Panel** — Current cycle, phase, opportunity details
- **Agent Responses** — Real-time agent messages
- **Proposal Review** — Approve/Reject/Revision buttons

---

## Memory System

CrewAI Memory provides:
- `self.remember(content, scope=...)` — Store
- `self.recall(query, scope=..., limit=...)` — Retrieve
- Scope-based storage (`/sentinel/research`, etc.)
- Automatic importance scoring
- Composite retrieval (semantic + recency + importance)
- LanceDB-backed persistence

---

## Environment Variables

```bash
OPENAI_API_KEY=           # GPT-4o access required
SENTINEL_LOG_LEVEL=DEBUG # Optional
BACKEND_URL=http://localhost:5173
```

---

## Known Issues & Pending Work

### 🔴 Radix Themes Not Applying (IN PROGRESS)

**Problem:** The dashboard uses Radix Themes (`@radix-ui/themes`) but the custom teal dark palette defined in `globals.css` doesn't override Radix's default colors in the rendered UI. The theme is loaded (`data-accent-color="teal"` is present), but Tailwind tokens (`--primary`, `--accent`, etc.) don't map to Radix CSS variables.

**What was tried:**
1. Added `@radix-ui/themes/styles.css` import to `layout.tsx`
2. Wrapped app in `<Theme accentColor="teal" appearance="dark" panelBackground="solid">`
3. Defined custom `--teal-*` palette in `globals.css`
4. Remapped Tailwind `--primary` HSL values to teal range

**Root cause:** Tailwind uses `hsl(var(--primary))` which outputs HSL values, while Radix expects direct hex/rgb values via CSS variables. Two separate styling systems that don't automatically sync.

**Possible fixes:**
1. Override Tailwind tokens to use `var(--teal-9)` etc. directly instead of HSL
2. Replace Tailwind components with Radix components (`<Button>`, `<Flex>`, etc.)
3. Use Radix Themes tokens exclusively and remove Tailwind color tokens

### 🟡 Approval Flow
Approval is dashboard-driven: the Flask backend flips draft status (`queued` → `deployed`/`failed`) in `sentinel.db` (SQLite), and the Sentinel flow polls that row via `wait_for_draft_status`. Both processes share the writer in `sentinel_v2.dashboard_state`.

### 🟡 Build Crew Manager
The hierarchical build crew may need the Manager LLM to be `gpt-4o` to handle delegation properly (not `gpt-4o-mini`).

---

## Quick Start

```bash
# 1. Setup
cd ~/clawd/projects/sentinel-v2
cp .env.example .env
# Edit .env with your keys

# 2. Run dashboard (frontend)
cd dashboard-nextjs && npm run dev

# 3. Run backend
cd ~/clawd/projects/sentinel-v2
python run_dashboard.py

# 4. Run Sentinel loop (in another terminal)
uv run python -m sentinel_v2.main --mode once
```

---

## Vs V1

| Feature | V1 | V2 |
|---------|----|----|
| Orchestration | LangGraph | CrewAI Flows |
| Memory | MemPalace | CrewAI Memory (LanceDB) |
| Agent config | YAML | Python |
| Crew process | Sequential only | Sequential + Hierarchical |
| Approval | Telegram poll | Dashboard (Next.js) |
| Dashboard | Flask | Next.js + Tailwind |
