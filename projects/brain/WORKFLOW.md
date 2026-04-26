# WORKFLOW.md — Brain

## Ingesta X Bookmarks

**Frecuencia:** Cada 6h (cron)
**Método:** Playwright con sesión autenticada de navegador

### Script: `scripts/scrape_x_bookmarks.py`

```bash
python scripts/scrape_x_bookmarks.py
```

**Pasos:**
1. Abre navegador con sesión de X ya autenticada
2. Navega a `x.com/i/bookmarks`
3. Hace scroll hasta cargar todos los tweets
4. Extrae: texto, autor, fecha, URLs, métricas
5. Guarda en `raw/x-bookmarks/YYYY-MM-DD-HH-MM.json`
6. El LLM clasifica cada tweet → actualiza wiki correspondiente

### Routing de tweets a wiki

| Tema | Archivo wiki |
|------|-------------|
| LLMs, prompting, modelos | `wiki/ai-llm.md` |
| Agentes, autonomous AI | `wiki/ai-agents.md` |
| React, Next.js, componentes | `wiki/react-nextjs.md` |
| TypeScript, JavaScript | `wiki/javascript-typescript.md` |
| APIs, databases, backend | `wiki/backend-databases.md` |
| Dev tools, productividad | `wiki/dev-tools.md` |
| Clean Architecture, DDD, patrones | `wiki/architecture.md` |
| CSS, UI, diseño | `wiki/css-design.md` |
| Linux, Docker, DevOps | `wiki/linux-devops.md` |
| Career, productividad developer | `wiki/career.md` |
| Indie hacking, negocio | `wiki/business.md` |

---

## Ingesta LinkedIn Saved Posts

**Frecuencia:** Domingos 9h
**Método:** Playwright + Chrome DevTools Protocol

### Script: `scripts/scrape_linkedin.py`

```bash
python scripts/scrape_linkedin.py
```

**Pasos:**
1. Contenedor Docker con Chromium y sesión de LinkedIn activa
2. Conexión via CDP/Playwright
3. Scroll por la lista de posts guardados
4. Extrae: texto, autor, fecha, links
5. Guarda en `raw/linkedin-saved/YYYY-MM-DD-HH-MM.json`

---

## Ingesta Notas de Voz

**Método:** Telegram → faster-whisper → LLM

### Flujo:
1. Audio OGG/Opus llega via Telegram al OpenClaw del VPS
2. `faster-whisper` transcripción local (CPU)
3. LLM categoriza → guarda en `raw/voice-notes/YYYY-MM-DD-HH-MM-slug.md`
4. Actualiza artículo wiki correspondiente

---

## Feedback Loop

Cada vez que se genera un output (briefing, análisis, informe...):

1. Guardar en `outputs/YYYY-MM-DD-titulo.md`
2. Si contiene insight nuevo → **obligatorio** actualizar wiki
3. Campo obligatorio en el template: `## Artículos wiki actualizados`

```markdown
## Artículos wiki actualizados

| Artículo wiki | Qué se añadió/corrigió | ¿Insight nuevo? |
|---------------|------------------------|----------------|
| wiki/[nombre].md | [descripción] | sí / no |

> Si esta sección está vacía sin justificación, el feedback loop no se completó.
```

---

## Health Check (mensual)

**Frecuencia:** Primer domingo de cada mes

### Script: `scripts/health_check.sh`

```bash
bash scripts/health_check.sh
```

**Checks:**
1. Buscar afirmaciones sin fuente en los artículos
2. Detectar contradicciones entre artículos
3. Temas mencionados que no tienen artículo propio
4. Raw entries sin procesar durante >7 días
5. Links rotos en los artículos wiki

**Output:** Reporte en `outputs/health-check-YYYY-MM-DD.md`
