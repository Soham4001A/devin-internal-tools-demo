#!/usr/bin/env bash
# Start Ops Workbench as ONE service (API + built UI) on an existing Python 3.10+/Node 20+ dev machine.
# Uses backend/.venv and frontend/node_modules only; no global package changes.
#   scripts/start-demo.sh              # http://localhost:8000
#   PORT=8080 RESET=1 scripts/start-demo.sh   # RESET=1 re-seeds all tools first
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

if ! command -v node >/dev/null 2>&1 && [ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "${NVM_DIR:-$HOME/.nvm}/nvm.sh" >/dev/null && nvm use --silent 22 >/dev/null 2>&1 || nvm use --silent default >/dev/null 2>&1 || true
fi
command -v python3 >/dev/null || { echo "python3 (3.10+) is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "Node 20+ / npm is required" >&2; exit 1; }

cd "$ROOT/backend"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

cd "$ROOT/frontend"
npm ci --no-audit --no-fund --silent
npm run build --silent

cd "$ROOT/backend"
[ "${RESET:-0}" = "1" ] && .venv/bin/python -m app.seed
echo "Ops Workbench (synthetic demo) on http://$HOST:$PORT  — /refunds, /merchant-reviews"
exec .venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT"
