# PROGRESS.md — Brain

**Última actualización:** 2026-04-26

## Estado

- [x] Crear estructura de carpetas
- [x] README + INDEX + WORKFLOW
- [x] Scripts base (scraping, process, health_check)
- [ ] Login en X (guardar session.json)
- [ ] Primer sync de bookmarks
- [ ] Configurar crons en producción
- [ ] LinkedIn scraping (CDP)
- [ ] Integración notas de voz

## Crons pendientes

| Cron | Schedule | Script |
|------|----------|--------|
| X bookmarks | `0 */6 * * *` | `sync_x_bookmarks.sh` |
| Health check | `0 9 1-7 * 0` | `health_check.sh` |
