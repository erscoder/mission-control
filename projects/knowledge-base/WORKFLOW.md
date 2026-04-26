# WORKFLOW.md — Brain

> Sistema exacto según la implementación de Carlos Azaustre.
> Ref: https://carlosazaustre.es/blog/mi-segundo-cerebro-wiki-ia

## Estructura

```
brain/
├── raw/                    ← contenido sin procesar
│   ├── x-bookmarks/        ← 1055+ bookmarks de X
│   ├── linkedin-saved/     ← posts guardados de LinkedIn
│   ├── voice-notes/        ← notas de voz
│   └── brain-archive/      ← legacy
├── wiki/                   ← 12 artículos mantenidos por IA
│   ├── ai-llm.md           ← AI & LLMs (297 fuentes)
│   ├── ai-agents.md        ← AI Agents (141 fuentes)
│   ├── javascript-typescript.md
│   ├── react-nextjs.md    ← React & Next.js (110 fuentes)
│   ├── backend-databases.md
│   ├── dev-tools.md
│   ├── architecture.md
│   ├── content-creation.md
│   ├── career.md
│   ├── css-design.md
│   ├── linux-devops.md
│   └── business.md
└── outputs/               ← respuestas, briefings, informes
```

---

## Fuente 1: X Bookmarks (cada 6 horas)

### Login inicial (una vez)

```bash
cd ~/clawd/projects/brain
python3 scripts/login_x.py
```

Abre navegador → login manual en X → guarda cookies en `session.json`.

### Sync automático

```bash
python3 scripts/scrape_x_bookmarks.py
python3 scripts/process_bookmarks.py
```

- Scraping: Playwright → `raw/x-bookmarks/YYYY-MM-DD-HH-MM.json`
- LLM clasifica por tema → actualiza `wiki/<categoria>.md`
- Cada tweet: texto + autor + fecha + links + métricas + contexto

### Routing tweets → wiki

| Tema | Archivo |
|------|---------|
| LLMs, modelos, prompting | `wiki/ai-llm.md` |
| Agentes, autonomous AI | `wiki/ai-agents.md` |
| React, Next.js, componentes | `wiki/react-nextjs.md` |
| TypeScript, JavaScript | `wiki/javascript-typescript.md` |
| APIs, databases, backend | `wiki/backend-databases.md` |
| Dev tools, productividad | `wiki/dev-tools.md` |
| Clean Architecture, DDD | `wiki/architecture.md` |
| CSS, UI, diseño | `wiki/css-design.md` |
| Linux, Docker, DevOps | `wiki/linux-devops.md` |
| Career, productividad | `wiki/career.md` |
| Indie hacking, negocio | `wiki/business.md` |
| Blogging, YouTube, redes | `wiki/content-creation.md` |

---

## Fuente 2: LinkedIn Saved Posts (domingos 9h)

**Sin API oficial.** Solución: Docker + Chromium + Chrome DevTools Protocol.

```bash
# Ejecutar en VPS con Docker
docker compose up -d chromium
python3 scripts/scrape_linkedin.py
```

- Contenedor Docker con Chromium y sesión de LinkedIn activa
- Playwright se conecta via CDP al navegador autenticado
- Scroll por la lista de posts guardados → extrae contenido
- Guarda en `raw/linkedin-saved/YYYY-MM-DD-HH-MM.json`

### Docker setup

```yaml
# docker-compose.yml
chromium:
  image: browserless/chrome
  environment:
    - MAX_CONCURRENT_SESSIONS=1
  ports:
    - "3000:3000"
```

---

## Fuente 3: Notas de voz (bajo demanda)

```
Telegram → OpenClaw (VPS)
  → faster-whisper (local, CPU)
  → LLM categoriza
  → raw/voice-notes/YYYY-MM-DD-HH-MM-slug.md
  → wiki/<categoria>.md
```

- Audio OGG/Opus llega via Telegram
- `faster-whisper` transcripción 100% local
- Sin APIs externas de transcripción

---

## Feedback Loop (OBLIGATORIO)

**Regla: todo output generado debe propagarse de vuelta a la wiki.**

Cada briefing, análisis, informe o respuesta larga:

1. Guardar en `outputs/YYYY-MM-DD-titulo.md`
2. **Campo obligatorio** en el template: `## Artículos wiki actualizados`
3. Si no actualiza nada → explicar por qué

```markdown
## Artículos wiki actualizados

| Artículo wiki | Qué se añadió/corrigió | ¿Insight nuevo? |
|---------------|------------------------|----------------|
| wiki/[nombre].md | [descripción] | sí / no |

> Si esta sección está vacía sin justificación, el feedback loop no se completó.
```

**Esto diferencia un sistema de captura de un sistema de aprendizaje.**

---

## Mantenimiento: Health Checks

### Health check (primer domingo de cada mes)

```bash
bash scripts/health_check.sh
```

**Revisa:**
- Contradicciones internas en los artículos
- Afirmaciones sin fuente
- Temas mencionados que no tienen artículo propio
- Raw entries sin procesar >7 días

### Linting (semanal)

```bash
python3 scripts/lint_wiki.py
```

**Detecta:**
- Duplicados entre artículos (palabras en común >20)
- Secciones faltantes en artículos
- Links a artículos que no existen (`[[tema]]` sin artículo)
- Genera informe en `outputs/lint-YYYY-MM-DD.json`

---

## Crons

| Tarea | Schedule | Script |
|-------|----------|--------|
| X bookmarks | `0 */6 * * *` | `sync_x_bookmarks.sh` |
| LinkedIn sync | `0 9 * * 0` | `scrape_linkedin.py` |
| Health check | `0 9 1-7 * 0` | `health_check.sh` |
| Linting | `0 10 * * 1` | `lint_wiki.py` |

---

## Reglas de calidad

1. **Síntesis > almacenamiento.** Un bookmark sin contexto vale poco. Con contexto se vuelve útil.
2. **Fricción mínima.** Si guardar algo requiere más de un paso, no se hace.
3. **El mantenimiento no puede ser manual.** La IA hace el trabajo de auditoría.
4. **12 categorías.** Equilibrio entre granularidad ymanageabilidad.
5. **Feedback loop obligatorio.** Sin propagación no hay aprendizaje.
