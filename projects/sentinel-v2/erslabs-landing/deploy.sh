#!/usr/bin/env bash
# deploy.sh — Initial deployment of ErsLabs landing to Cloudflare Pages.
# Run once manually; subsequent deploys happen automatically via Sentinel post-validation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Installing dependencies..."
npm install

echo "==> Building static site..."
npm run build

echo "==> Creating Cloudflare Pages project (if not exists)..."
npx wrangler pages project create erslabs --production-branch main 2>/dev/null || echo "Project already exists"

echo "==> Deploying to Cloudflare Pages..."
npx wrangler pages deploy out --project-name=erslabs

echo "==> Setting custom domains..."
echo "Note: Run these manually in Cloudflare dashboard or via API:"
echo "  1. Add custom domain: erslabs.net"
echo "  2. Add custom domain: www.erslabs.net"
echo "  3. Configure DNS CNAME: @ -> erslabs.pages.dev"
echo "  4. Configure DNS CNAME: www -> erslabs.pages.dev"

echo ""
echo "Done! Site should be live at https://erslabs.pages.dev"
echo "After DNS propagation: https://erslabs.net"
