# MEMORY.md - Harvis Long-Term Memory

*Last updated: 2026-04-11*

## About Kike

**Mission:** "Construir una organización autónoma de agentes IA que trabaja 24/7 — agentes que aprenden, generan ingresos, y crean otros agentes — hasta que mi único trabajo sea decidir qué construir."

**Contact:** Twitter @erscoder41567 | Email erscoder@gmail.com

**Tech Stack:** Next.js, TypeScript, Tailwind, NestJS, PostgreSQL/Prisma, Hyperliquid

---

## 🚨 Reglas Absolutas de Kike

1. **Hablar SIEMPRE en español** — sin excepción
2. **Sin código deprecated** → borrar y actualizar callers
3. **Enums para estados** → nunca literales (`PaperStatus.PENDING`)
4. **TODOS los tests en verde** antes de commit
5. **Build limpio** antes de commit
6. **Tests + Build** después de cada cambio de código
7. **Usar Write/Edit** para ficheros, nunca exec + heredoc
8. **Docker**: `docker compose up -d` siempre, nunca `docker run`
9. **CHANGELOG.md** en cada proyecto — update after EVERY commit with description + reason in English ([YYYY-MM-DD] type: description)
10. **Lucide React** para iconos, nunca emojis

---

## 🤖 Equipo de Agentes

| Agente | Rol |
|--------|-----|
| **Harvis** (yo) | Orchestrator, planifico, coordino, propongo |
| **Sentinel** | HIM — personal swarm AI agents, crea valor económico 24/7 (pre-seed funded) |
| **Codex** | Backend / Python / API |
| **Luna** | Frontend / React / UI |
| **Vector** | QA / Validación |
| **Vega** | Infra / Deploy / Cloud |

---

## 📋 Índice de Temas Detallados

- `memory/topics/projects.md` — Proyectos activos y estado
- `memory/topics/polymarket.md` — Reglas trading Polymarket
- `memory/topics/testing.md` — Reglas testing y cobertura
- `memory/topics/github.md` — Operaciones GitHub
- `memory/topics/linkedin.md` — Guía posts LinkedIn
- `memory/topics/agentic-design-patterns.md` — Patrones agentic (Google Cloud)
- `memory/roadmap.md` — Roadmap financiero y de proyectos (SIRVE A: Harvis + Sentinel)

---

## 🏗️ AI-DLC — Cómo Trabajamos

**Sin hand-offs, co-creación total:**
1. Human + AI co-crean el spec por conversación
2. AI explora el codebase y hace preguntas clarificadoras
3. Success criteria machine-verifiable (tests, types, performance)
4. El mismo sistema que define el spec, también lo construye
5. Quality gates automatic enforcement

---

## 🔴 Docker Regla
`docker compose up -d` siempre. Para: `docker compose down`. Rebuild: `build` → `up -d`.

---

## 🎨 Icon Library
**Lucide React** (`lucide-react`) para TODO. Nunca emojis como iconos.

---

## 🐦 Twitter Style
- Sin em dash — suena a IA
- Frases acabadas en punto
- Delays 2-3 min entre posts

---

## Sentinel = HIM (2026-04-07)

**Product:** HIM — Human Intelligence Machines. Pre-seed funded by 021T, @alexwg, @devontriplett21.
**Mission:** Personal swarm of AI agents autonomously creating economic value 24/7.
**One-liner:** The antidote to AI that only benefits a small group.

**Sentinel Loop:** RESEARCH → MATCH → BUILD → APPROVE → DEPLOY (always running)
- RESEARCH: scout thousands of websites 24/7, hunt for market gaps
- MATCH: deeply research user, map to opportunities
- BUILD: create micro-business drafts autonomously
- APPROVE: user reviews and approves ALL work
- DEPLOY: execute with user budget, create real economic value

**Stack:** LangGraph + LangChain + MemPalace (AAAK memory) + ChromaDB

**Docs:**
- `~/clawd/projects/sentinel/SOUL.md` — Sentinel's identity
- `~/clawd/projects/sentinel/docs/HIM.md` — full product vision
- `~/clawd/projects/sentinel/memory/roadmap.md` — technical + product roadmap
- `memory/topics/agentic-design-patterns.md` — patrones agentic

**Skill Router:**
```python
from skill_router import SkillRouter
router = SkillRouter()
skills = router.route("build a landing page")  # → [ui-ux-pro-max]
skill = router.load_skill("ui-ux-pro-max")   # → content
```

**Archivos clave:**
- `agent/channels/telegram_bot.py` — bot principal
- `agent/research/qa_agent.py` — QA con MemPalace
- `agent/research/llm_http.py` — LLM streaming (MiniMax/Ollama)
- `agent/tools/hyperliquid_tool.py` — precios crypto
- `agent/tools/ta_tool.py` — análisis técnico
- `agent/mempalace_bridge.py` — bridge MemPalace
- `agent/session_memory.py` — memoria de sesión
- `agent/skill_router.py` — router de skills

**Arranque:**
```bash
cd ~/clawd/projects/sentinel && make run
```

**Old Karpathy system (wiki + compiler + lint) — ELIMINADO (2026-04-07). Reemplazado por MemPalace.**
.venv/bin/python main.py --mode full
```

---

## Synapseia — Docker Ollama (2026-04-03)

- Ollama: `0.0.0.0:11434` con `qwen2.5:0.5b` + `all-minilm-l6-v2`
- Nodes acceden via `OLLAMA_URL=http://ollama:11434`
- Research ~30s/paper en containers

---

## Nexus Project

**S10:** Paper Trading Live — 30-day validation con Alpaca. Status: pausado.

## 🤖 claude-session-tools — Viewer Claude Code CLI (2026-04-11)

**Ubicación:** `~/clawd/projects/claude-session-tools/`

**CLI:** `claude-session list|cat|watch|tail|resume`
**Telegram bot:** `python3 telegram_bot.py list|events|watch|poll|stop`

### Uso Telegram
1. Escribe `/sessions` → mando lista con botones inline
2. Click en botón → callback_data `cs:events:<sid>` → mando eventos recientes
3. Botón Watch → `cs:watch:<sid>:<count>` → guardo watch en `watch_state.json`
4. Cron job cada 30s → `poll_watches()` → mando updates a Telegram si hay cambios

### Callback patterns
- `cs:list` → lista de sessions
- `cs:events:<sid>` → eventos recientes
- `cs:watch:<sid>:<last_count>` → iniciar watch
- `cs:stop:<sid>` → parar watch

### Archivos clave
- `cli.py` — CLI tool standalone
- `telegram_bot.py` — Telegram handler
- `parser.py` / `renderer.py` — JSONL parser y rich renderer
- `watch_state.json` — watches activos

### Dependencias
`pip install click rich watchfiles`

---

## Synapseia Network

**Arquitectura:** Research → PeerReview → Discovery (3 stages).
- DiLoCo + HyperparamSearch en background
- Feedback loop: discoveries score ≥8 → reference corpus
- Rewards via Solana SPL transfers

**CHANGELOG:** `CHANGELOG.md` en root — diario de cambios.

---

## 🚀 Sentinel V2 — CrewAI Rewrite (2026-04-23)

**Path:** `/Users/kike/clawd/projects/sentinel-v2/`
**Stack:** CrewAI Flow + CrewAI Memory + CrewAI Agents (Python) + python-telegram-bot
**Difference from V1:** LangGraph→CrewAI Flow, MemPalace→CrewAI Memory, YAML→Python agents

### Arquitectura
```
SentinelLoopFlow (CrewAI Flow)
├── @start start_cycle()
├── @listen run_research() → research_crew (sequential: Scout + Analyst)
├── @listen run_match() → match_crew (sequential: Profile Researcher + Matcher)
├── @listen run_build() → build_crew (hierarchical: Manager delegates → Frontend + Backend + QA)
├── @listen request_approval() → TelegramTool.send_approval_poll()
├── @listen check_approval() → ApprovalState (file-based, polls JSON)
├── @listen run_deploy() → deploy_crew (sequential: Deployment Engineer + QA Verifier)
└── @router route_after_approval()

Tools: TelegramTool (python-telegram-bot v20+)
Memory: CrewAI Memory (LanceDB storage)
```

### Archivos clave
- `src/sentinel_v2/flows/sentinel_loop.py` — SentinelLoopFlow con state machine
- `src/sentinel_v2/crews/*/` — 4 crews (research, match, build, deploy)
- `src/sentinel_v2/tools/telegram_tool.py` — Telegram bot integration
- `src/sentinel_v2/tools/approval_state.py` — File-based approval state
- `src/sentinel_v2/main.py` — CLI: `--mode once|daemon|plot`

### Estado tests (2026-04-23)
- **61 tests passing**: 28 unit + 33 integration
- Unit: `test_approval_state.py` (10), `test_sentinel_loop.py` (18)
- Integration: `test_crews_integration.py` (33)
- Coverage: crew structure, process types, agent counts, state transitions

### Issues known
- `--mode once` necesita OpenAI API key con quota (no funciona con $0 quota)
- `--mode plot` requiere graphviz (no instalado)
- Approval: file-based (`/tmp/sentinel_v2_approval.json`) — funciona bien

### run once test (bloqueado por quota)
```bash
cd ~/clawd/projects/sentinel-v2
cp .env.example .env  # añadir OPENAI_API_KEY
uv run python -m sentinel_v2.main --mode once
```

### Commits sentinel-v2 (en clawd repo)
- `f4cb647` — fix: approval_state get_action returns None; kickoff tests use _methods patch
- `4d123ef` — test: crew integration tests (33 tests, 61 total passing)
