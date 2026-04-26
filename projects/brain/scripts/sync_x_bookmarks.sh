#!/usr/bin/env bash
# sync_x_bookmarks.sh — Sync X bookmarks and update wiki
# Run via cron: 0 */6 * * * cd /path/to/brain && bash scripts/sync_x_bookmarks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "[$(date)] [*] Starting X bookmarks sync..."

# 1. Scrape new bookmarks
echo "[$(date)] [*] Scraping X bookmarks..."
python3 scripts/scrape_x_bookmarks.py --scroll-limit 20

# 2. Process with LLM
echo "[$(date)] [*] Processing bookmarks with LLM..."
python3 scripts/process_bookmarks.py

# 3. Update INDEX.md (simple stat update)
echo "[$(date)] [+] X bookmarks sync complete"

# 4. Update timestamp in INDEX.md
python3 - <<'PYEOF'
import re
from pathlib import Path
from datetime import datetime

index = Path("INDEX.md")
content = index.read_text()

today = datetime.now().strftime("%Y-%m-%d")
content = re.sub(
    r'\*\*Última actualización:\*\* \d{4}-\d{2}-\d{2}',
    f'**Última actualización:** {today}',
    content
)
index.write_text(content)
PYEOF

echo "[$(date)] [+] Done!"
