#!/usr/bin/env bash
# Local launcher: starts the SIMULATED Risk Vendor on 127.0.0.1:9011 and Settlement Review on 127.0.0.1:9010.
# A random sandbox client secret is generated here and handed to only these two child processes via env.
# Usage: scripts/run.sh            (SR_RESET=1 scripts/run.sh re-seeds the local SQLite db at startup)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PY" ]; then python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; PY=.venv/bin/python; fi
APP_PORT="${SR_APP_PORT:-9010}"
CID="settlement-review-local"
SECRET="$("$PY" -c 'import secrets;print(secrets.token_urlsafe(32))')"   # never printed
mkdir -p data
env RISK_VENDOR_CLIENT_ID="$CID" RISK_VENDOR_CLIENT_SECRET="$SECRET" \
  "$PY" -m uvicorn vendor.server:app_factory --factory --host 127.0.0.1 --port 9011 > data/vendor.log 2>&1 &
VPID=$!
trap 'kill $VPID 2>/dev/null || true' EXIT
echo "Risk Vendor (SIMULATED) on http://127.0.0.1:9011 (log: data/vendor.log)"
echo "Settlement Review on    http://127.0.0.1:$APP_PORT"
env RISK_VENDOR_CLIENT_ID="$CID" RISK_VENDOR_CLIENT_SECRET="$SECRET" SR_VENDOR_URL="http://127.0.0.1:9011" \
  SR_RESET="${SR_RESET:-0}" "$PY" -m uvicorn app.main:app_factory --factory --host 127.0.0.1 --port "$APP_PORT"
