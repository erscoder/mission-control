#!/usr/bin/env bash
# health_check.sh — Monthly wiki health check
# Run: bash scripts/health_check.sh

set -euo pipefail

DATE=$(date +%Y-%m-%d)
REPORT_FILE="outputs/health-check-${DATE}.md"

echo "[*] Brain Health Check — $DATE"

# Count raw entries without processing
unprocessed_x=$(find raw/x-bookmarks -name "*.json" -mtime +7 | wc -l | tr -d ' ')
unprocessed_li=$(find raw/linkedin-saved -name "*.json" -mtime +7 | wc -l | tr -d ' ')

# Count wiki articles
wiki_count=$(find wiki -name "*.md" | wc -l | tr -d ' ')
wiki_total_lines=$(find wiki -name "*.md" -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || echo 0)

# Check for articles with no sources
empty_articles=$(grep -L "Fuentes procesadas" wiki/*.md 2>/dev/null | wc -l | tr -d ' ' || echo 0)

# Check for broken links in wiki (simple check)
broken_links=$(grep -r "http.*http" wiki/ 2>/dev/null | wc -l | tr -d ' ' || echo 0)

# Check for articles without "Última actualización"
stale_articles=$(grep -L "Última actualización" wiki/*.md 2>/dev/null | wc -l | tr -d ' ' || echo 0)

# Generate report
cat > "$REPORT_FILE" << EOF
# Brain Health Check — $DATE

## Estadísticas generales

| Métrica | Valor |
|---------|-------|
| Artículos wiki | $wiki_count |
| Líneas totales wiki | $wiki_total_lines |
| Raw X sin procesar (>7 días) | $unprocessed_x |
| Raw LinkedIn sin procesar (>7 días) | $unprocessed_li |
| Artículos vacíos (sin fuentes) | $empty_articles |
| Artículos sin fecha actualización | $stale_articles |

## Revisión de contenido

### Artículos sin actualizar (>30 días)

$(find wiki -name "*.md" -mtime +30 -exec basename {} \; 2>/dev/null | sed 's/^/  - /' || echo "  Ninguno")

### Posibles problemas detectados

$(if [ "$stale_articles" -gt 0 ]; then
  echo "  ⚠️  $stale_articles artículos sin fecha de última actualización"
  echo "  ⚠️  Revisar manualmente: $(grep -l "Última actualización" wiki/*.md 2>/dev/null | wc -l | tr -d ' ') artículos con fecha"
else
  echo "  ✅ Sin problemas de fecha"
fi)

$(if [ "$unprocessed_x" -gt 0 ]; then
  echo "  ⚠️  $unprocessed_x archivos de X sin procesar"
else
  echo "  ✅ Raw X al día"
fi)

$(if [ "$empty_articles" -gt 0 ]; then
  echo "  ⚠️  $empty_articles artículos sin contenido de fuentes"
else
  echo "  ✅ Todos los artículos tienen fuentes"
fi)

## Acciones recomendadas

1. $(if [ "$unprocessed_x" -gt 0 ]; then echo "Procesar $unprocessed_x raw entries de X"; else echo "No hay raw de X pendientes"; fi)
2. $(if [ "$stale_articles" -gt 0 ]; then echo "Revisar $stale_articles artículos sin fecha"; else echo "Artículos al día"; fi)
3. Hacer scroll manual por la wiki para verificar contenido

---

*Health check ejecutado: $(date -u +%Y-%m-%dT%H:%M:%SZ)*
EOF

echo "[+] Reporte guardado: $REPORT_FILE"
cat "$REPORT_FILE"
