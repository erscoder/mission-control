# MEMORY.md - Harvis Long-Term Memory

*Last updated: 2026-04-05*

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
9. **CHANGELOG.md** en cada proyecto después de cambios
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

## Synapseia Network

**Arquitectura:** Research → PeerReview → Discovery (3 stages).
- DiLoCo + HyperparamSearch en background
- Feedback loop: discoveries score ≥8 → reference corpus
- Rewards via Solana SPL transfers

**CHANGELOG:** `CHANGELOG.md` en root — diario de cambios.
