#!/usr/bin/env bash
# Clarity — build the UI, then serve everything from the API on :8000.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$root/frontend"
[ -d node_modules ] || npm install
npm run build

cd "$root/backend"
echo "Clarity on http://127.0.0.1:8000"
exec python -m clarity.api
