# Brain — Segundo Cerebro IA

Wiki personal que se mantiene sola. Inspirado en [Karpathy's personal knowledge base](https://karpathy.github.io/) y la implementación de Carlos Azaustre.

## Arquitectura

```
brain/
├── INDEX.md              ← índice maestro (actualizar tras cada ingesta)
├── WORKFLOW.md           ← este archivo
├── raw/                  ← fuentes originales sin procesar
│   ├── x-bookmarks/      ← bookmarks de X/Twitter
│   ├── linkedin-saved/   ← posts guardados de LinkedIn
│   └── voice-notes/      ← notas de voz
├── wiki/                 ← artículos compilados por categoría
│   ├── ai-llm.md
│   ├── ai-agents.md
│   ├── javascript-typescript.md
│   ├── react-nextjs.md
│   ├── backend-databases.md
│   ├── dev-tools.md
│   ├── architecture.md
│   ├── content-creation.md
│   ├── career.md
│   ├── css-design.md
│   ├── linux-devops.md
│   └── business.md
└── outputs/              ← respuestas, briefings, informes generados
```

## Fuentes de ingestión

| Fuente | Frecuencia | Método |
|--------|-----------|--------|
| X Bookmarks | Cada 6h | Scraping con Playwright (sesión autenticada) |
| LinkedIn Saved | Domingos 9h | Playwright + CDP |
| Notas de voz | On-demand | Telegram → faster-whisper → LLM |

## Wiki categories

- `ai-llm.md` — LLMs, modelos, prompting
- `ai-agents.md` — Arquitectura de agentes, agentic AI
- `javascript-typescript.md` — JS/TS
- `react-nextjs.md` — React, Next.js, componentes
- `backend-databases.md` — APIs, BDs, servidores
- `dev-tools.md` — Herramientas developer
- `architecture.md` — Patrones, clean code, DDD
- `content-creation.md` — Blogging, YouTube, redes
- `career.md` — Carrera, productividad
- `css-design.md` — CSS, UI/UX
- `linux-devops.md` — Infra, Docker, K8s
- `business.md` — Indie hacking, monetización

## Feedback loop

Cada output que contenga insights nuevos → propagar a la wiki.
Si no actualiza nada, explicar por qué en el campo obligatorio.

## Health check

Primer domingo de cada mes: revisar wiki buscando contradicciones,
afirmaciones sin fuente, y temas sin artículo propio.
