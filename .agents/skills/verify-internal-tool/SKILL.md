---
name: verify-internal-tool
description: Run, test, browser-verify, reset and preview the Ops Workbench internal tools demo (FastAPI + SQLite + Vite React).
---

# Verify Ops Workbench

All data is synthetic. Never add real credentials, customer data or payment execution.

## Setup (once per machine)
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cd ../frontend && npm ci            # Node 20+ (nvm: `source ~/.nvm/nvm.sh && nvm use 22`)
```

## Checks (run all before committing)
```bash
cd backend && .venv/bin/python -m pytest -q        # expect all passed
cd frontend && npm run build && npx eslint src     # expect no errors
```

## Run single-service app (UI + API on :8000)
```bash
cd frontend && npm run build
cd ../backend && .venv/bin/python -m app.seed && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
curl -s localhost:8000/api/tools/refunds/summary -H 'X-Demo-Persona: viewer'
# expect {"total":12,"counts":{"pending":7,"approved":3,"rejected":2},...} right after a reset
```
For a shareable session preview, expose port 8000 with the browser preview tool.

## Browser journey (repeatable; resets refunds data first)
```bash
cd backend && .venv/bin/pip install playwright==1.49.1 && .venv/bin/playwright install chromium
.venv/bin/python ../scripts/e2e.py --shots ../artifacts --video ../artifacts/video --slow 250   # prints "E2E OK"
```
Covers: queue load + counts, search, status filter, viewer view-only, reviewer reason required, approve,
history entry with reason/actor/timestamp, counts update, persistence after reload.
Artifacts directory is not committed except curated images in `docs/`.

## Reset demo data
- `cd backend && .venv/bin/python -m app.seed [--tool refunds]`, or the "Reset demo data" nav button.
- `DEMO_RESET_ENABLED=false` disables the HTTP reset endpoint.

## Expected seed facts
12 refunds: 7 pending (RF-1004..RF-1007 are >48h old), 3 approved, 2 rejected. Ages are relative to reset time.

## Deployment notes
- Backend: any host running `uvicorn app.main:app` from `backend/`, with `DB_PATH` on a persistent volume if decisions must
  survive redeploys (otherwise each redeploy starts from fresh seed data).
- Frontend separately: build with `VITE_API_BASE_URL=https://<backend>` and set backend `CORS_ORIGINS`.
