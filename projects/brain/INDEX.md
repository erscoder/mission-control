# INDEX.md — Brain Master Index

> Actualizado: 2026-04-26

## Crons activos

| Cron | Schedule | Script | Estado |
|------|----------|--------|--------|
| X bookmarks | `0 */6 * * *` | `sync_x_bookmarks.sh` | ⏸ pendiente |
| LinkedIn sync | `0 9 * * 0` | `scrape_linkedin.py` | ⏸ pendiente |
| Health check | `0 9 1-7 * 0` | `health_check.sh` | ⏸ pendiente |
| Linting | `0 10 * * 1` | `lint_wiki.py` | ⏸ pendiente |

## Raw entries

| Fuente | Count | Última fecha |
|--------|-------|-------------|
| x-bookmarks/ | 0 | — |
| linkedin-saved/ | 0 | — |
| voice-notes/ | 0 | — |

## Últimos outputs

| Fecha | Output | Wiki actualizada |
|-------|--------|-----------------|

## Próximos pasos

- [ ] Instalar dependencias: `pip install -r requirements.txt`
- [ ] Login X: `python3 scripts/login_x.py`
- [ ] Probar primer sync: `python3 scripts/scrape_x_bookmarks.py --visible`
- [ ] Configurar crons en producción
- [ ] Docker LinkedIn: `docker compose up -d chromium`
