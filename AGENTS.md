# AGENTS.md — Ops Workbench

Synthetic-data internal tools prototype. FastAPI + SQLite backend (`backend/`), Vite React TS frontend (`frontend/`).
Run/test/deploy steps: README.md and `.agents/skills/verify-internal-tool/SKILL.md`.

## Layout
- `backend/app/main.py` — API routes, persona dependency, decision transaction, demo reset, optional SPA serving.
- `backend/app/db.py` — schema (`records`, `events`, both keyed by `tool`), seeding, per-tool reset.
- `backend/app/personas.py` — demo personas and `can_decide`.
- `backend/app/tools/` — per-tool config (`ToolConfig`: statuses, columns, detail fields, search fields, actions, seed).
- `frontend/src/components/` — shared `QueueTable`, `RecordDrawer`, `DecisionPanel`, `HistoryTimeline`, `SummaryBar`.
- `frontend/src/tools/index.ts` — per-tool UI labels (nav, title, search placeholder).
- `scripts/e2e.py` — Playwright browser journey over CDP.

## Invariants (keep them)
- Permissions, reason validation and state transitions are enforced in the backend only; the UI just mirrors them.
- Status change + history event in ONE transaction; repeated decisions → 409, no extra history.
- All SQL filters by `tool`; reset touches one tool.
- Never add real payment execution, real customer data or compliance claims. Keep the demo banner.
- No credentials in git.

## Adding a tool
1. Create `backend/app/tools/<key>.py` with a `ToolConfig` (own statuses/actions/seed) and register it in
   `backend/app/tools/__init__.py`.
2. Add an entry to `frontend/src/tools/index.ts`; make the nav switch `toolKey` (App currently uses the first entry).
3. Add tests mirroring `backend/tests/test_api.py` for the new tool, including isolation from `refunds`.

## Planned next change (not implemented yet)
"Overdue" (pending > 48h) filter/count. Suggested approach: compute server-side in `list_records`/`summary` (e.g.
`overdue=true` query param, `overdue` count), add a stat card + filter option, test with seeded RF-1004..RF-1007.

## Checks before committing
`cd backend && .venv/bin/python -m pytest -q`; `cd frontend && npm run build && npx eslint src`; run `scripts/e2e.py`.
