# MEMORY.md - Harvis Long-Term Memory

*Last updated: 2026-04-04*

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
| **Sentinel** | Genera aplicaciones automáticamente — lee `memory/roadmap.md` |
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

## Sentinel — Arquitectura (2026-04-05)

**Stack:** `LangGraph + LangChain + SQLite + ChromaDB`

**Patrones agentic:** `memory/topics/agentic-design-patterns.md`

**Karpathy Knowledge Loop** (implementado 2026-04-05):
```
Observer (terminal, git, files, chat)
    ↓
raw/ (snapshots JSONL)
    ↓
compiler.py (LLM summaries) → wiki/
    ↓
qa_agent.py (Q&A con memoria de lo que Kike trabaja)
    ↓
lint.py (detecta gaps)
```

**Archivos clave:**
- `observer_knowledge.py` — recoge actividad con sanitización
- `sync_observer.py` — loop completo (cron cada 6h)
- `llm.py` — backend Ollama/Kimi/OpenAI
- `compiler.py`, `qa_agent.py`, `lint.py`

**Arranque manual:**
```bash
cd ~/clawd/projects/sentinel && python3 sync_observer.py
```

**Arranque agente (legacy):**
```bash
cd ~/clawd/projects/sentinel/agent
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
