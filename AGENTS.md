# AGENTS.md — Ops Workbench

Synthetic-data internal tools prototype. FastAPI + SQLite backend (`backend/`), Vite React TS frontend (`frontend/`).
Run/test/deploy steps: README.md and `.agents/skills/verify-internal-tool/SKILL.md`.

## Layout
- `backend/app/main.py` — API routes, persona dependency, decision transaction, demo reset, optional SPA serving.
- `backend/app/db.py` — schema (`records`, `events`, both keyed by `tool`), seeding, per-tool reset.
- `backend/app/personas.py` — demo personas and `can_decide`.
- `backend/app/tools/` — per-tool config (`ToolConfig`: statuses, columns, detail fields, search fields, actions, seed,
  `overdue_filter`, `value_field`, `requester_field`). Tools: `refunds.py`, `merchant_reviews.py`.
- `frontend/src/components/` — shared `QueueTable`, `RecordDrawer`, `DecisionPanel`, `HistoryTimeline`, `SummaryBar`.
- `frontend/src/tools/index.ts` — per-tool UI (`path` route, nav, title, banner, placeholders, footnote).
- `frontend/src/App.tsx` — shell (sidebar, persona, reset) + `ToolView` keyed by tool so state never crosses tools.
- `scripts/e2e.py` — Playwright browser journey (both modules). `scripts/start-demo.sh` — venv + build + one service.

## Invariants (keep them)
- Permissions, reason validation and state transitions are enforced in the backend only; the UI just mirrors them.
- Status change + history event in ONE transaction; repeated decisions → 409, no extra history.
- All SQL filters by `tool`; reset touches one tool.
- Never add real payment execution, real customer data or compliance claims. Keep the demo banner.
- No credentials in git.

## Adding a tool
1. Create `backend/app/tools/<key>.py` with a `ToolConfig` (own statuses/actions/seed) and register it in
   `backend/app/tools/__init__.py`.
2. Add a `ToolUi` entry (with `path`) to `frontend/src/tools/index.ts`; sidebar + route are automatic.
3. Add tests like `backend/tests/test_merchant_reviews.py` (seed, 403, 422, 409, history, snapshot isolation, reset).
Merchant Reviews is an operations review mock: never describe it as KYC/KYB/compliance verification.

## Over 48 hours (overdue) rule
Only for tools with `overdue_filter=True` (refunds); others get 400 on `?overdue=true` and `overdue_pending: null`.
Server-side in `main.is_overdue`: status `pending` AND submitted strictly more than `OVERDUE_HOURS` (48) ago.
`GET .../records?overdue=true` (combines with `q`/`status`, oldest first); `summary.overdue_pending` count.
Approved/rejected are never overdue. Tests: `test_overdue_*`, `test_is_overdue_exact_boundary`.

## Checks before committing
`cd backend && .venv/bin/python -m pytest -q`; `cd frontend && npm run build && npx eslint src`; run `scripts/e2e.py`.
