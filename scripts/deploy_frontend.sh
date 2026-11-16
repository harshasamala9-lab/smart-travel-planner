#!/usr/bin/env bash
# One-command production deploy of the React SPA to Vercel.
# Usage:  ./scripts/deploy_frontend.sh
# Requires: vercel CLI logged in (vercel whoami)
set -euo pipefail
cd "$(dirname "$0")/../frontend"

API_BASE="${1:-https://smart-travel-planner-nk60.onrender.com}"

echo "Deploying frontend to Vercel production (API base: $API_BASE)…"
vercel deploy --prod --yes \
  --project smart-travel-planner \
  --build-env "VITE_API_BASE_URL=$API_BASE"

echo
echo "Permanent production URL: https://smart-travel-planner-nine-teal.vercel.app"
