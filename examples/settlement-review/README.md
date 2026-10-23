# Settlement Review — controlled-integration follow-up demo

A small queue of **synthetic settlement exceptions**. Each one is enriched by a **SIMULATED Risk Vendor** that is reached
over real HTTP with a real OAuth 2.0 `client_credentials` exchange. Demo-user permissions are enforced by the server.
This app stands alone; the existing Ops Workbench (refunds/merchant) app at the repo root is unchanged.

> **SIMULATED vendor — not a live third-party integration.** `vendor/server.py` is a local process that we wrote. It
> runs on `127.0.0.1:9011` and returns fictional scores and reasons. The OAuth token exchange and bearer-protected
> HTTP calls are real; the vendor is not.
>
> **Synthetic data, no money movement.** Every merchant, account and amount is fictional. Approve/Reject only records
> a decision and a history row.
>
> **Demo identity, not SSO.** The three logins below are **PUBLIC SYNTHETIC demo credentials** with local password
> checks and server-side sessions. They are not production identity.

| Username | Password (public, synthetic) | Role | Tenant |
|---|---|---|---|
| `viewer.a` | `viewer-a-demo` | Viewer | Northwind Settlements (tenant A) |
| `operator.a` | `operator-a-demo` | Settlement Operator | Northwind Settlements (tenant A) |
| `operator.b` | `operator-b-demo` | Settlement Operator | Bluefin Payouts (tenant B) |

## Run
```bash
cd examples/settlement-review
SR_RESET=1 scripts/run.sh        # creates .venv if needed; vendor :9011 + app :9010 (loopback only)
# open http://127.0.0.1:9010
```
To change only the app port, use `SR_APP_PORT=8766 SR_RESET=1 scripts/run.sh`. The vendor stays on9011.

`run.sh` generates a random sandbox client secret (`secrets.token_urlsafe(32)`). It is never printed, and it is passed
by environment variable to the vendor and app processes only. `SR_RESET=1` re-seeds the local SQLite database at
startup. There is deliberately **no HTTP reset endpoint**.

## Tests
```bash
.venv/bin/python -m pytest -q tests          # 28 tests: app (TestClient) + vendor OAuth
.venv/bin/python scripts/smoke.py            # real two-process HTTP smoke (starts its own vendor+app on 9011/9010; stop run.sh first)
.venv/bin/pip install playwright && .venv/bin/python scripts/e2e.py artifacts /path/to/chrome   # with run.sh SR_RESET=1 running
```

## Architecture
```
 Browser (HTML/JS, no secrets)                    127.0.0.1:9010  Settlement Review (FastAPI)
 ┌──────────────────────────┐  cookie sr_session  ┌──────────────────────────────────────────────┐
 │ login · queue · detail   │  (HttpOnly,Strict)  │ users.py   server-side roles + tenants       │
 │ access panel · vendor    │ ──────────────────▶ │ sessions   random token, sha256 in SQLite    │
 │ status · decision form   │  X-CSRF-Token on    │ every query: WHERE tenant = session tenant   │
 └──────────────────────────┘  POST               │ decision: BEGIN IMMEDIATE status+history     │
           ▲ score/reasons only                   │ vendor_client.py: token cache, 2s timeout    │
           └───────────────────────────────────── │   fail-closed -> "unavailable"               │
                                                  └──────────────┬───────────────────────────────┘
       scripts/run.sh: random secret ──env──▶ both               │ 1. POST /oauth/token (client_credentials, risk:read)
                                                                 │ 2. GET /v1/risk/{ref}  Authorization: Bearer <opaque>
                                                  ┌──────────────▼───────────────────────────────┐
                                                  │ 127.0.0.1:9011  Risk Vendor (SIMULATED)      │
                                                  │ opaque tokens, TTL 300s, scope check, 401/403│
                                                  └──────────────────────────────────────────────┘
```

## What the server enforces
- **401** when unauthenticated, for a wrong password, for an expired session, and for a session after logout (the
  session row is deleted).
- **Viewer**: own tenant only; account numbers are redacted **on the server** (`•••• 1234`). A decision returns **403**
  even when the request includes forged `X-Role: operator` headers or `"role": "operator"` in the body.
- **Operator**: approve or reject only `open` exceptions in their own tenant; reason must be ≥5 characters (**422**).
  The status update and the history row are written in one `BEGIN IMMEDIATE` transaction on a request-scoped
  SQLite connection (no connection is shared across worker threads). A repeat decision returns
  **409** and adds no history.
- **Cross-tenant IDs** return **404** for detail, history and decision, the same response as a nonexistent ID.
- **CSRF**: every cookie-authenticated POST (decision, logout) needs the per-session `X-CSRF-Token`. Cookies are also
  `SameSite=Strict`.
- **Vendor**: the URL comes from server config (`SR_VENDOR_URL`, default `http://127.0.0.1:9011`); no request input can
  change it. If the vendor is down, returns an error, or rejects the token, the UI shows **"Risk score unavailable"**
  and never a guessed score. Only known OAuth error codes are surfaced; other vendor text is replaced
  with `unrecognized_error`. Malformed vendor JSON is treated as unavailable. The client secret and bearer token never appear in API responses, the HTML or the logs
  (checked by tests and by the smoke test).

## 90-second demo
1. (0–10s) Open `http://127.0.0.1:9010`. Sign in with `operator.a` and a wrong password: "Incorrect username or password".
2. (10–35s) Sign in as `viewer.a`. The vendor pill shows **Connected** and the integration steps are listed. Open
   **SE-1002**: risk score from the simulated vendor, account `•••• 5678` "(redacted by server)", the decision area
   says "View only", and the Access panel lists what this role can and cannot do. Sign out.
3. (35–65s) Sign in as `operator.a`. Open SE-1002: the full synthetic account is visible. Enter a reason, then
   **Reject**. History shows "Rejected by Omar Operator" with the reason. Sign out.
4. (65–90s) Sign in as `operator.b`. Only SE-2xxx rows appear (Bluefin). Optionally stop the vendor process and
   click **Re-check connection**: the pill shows **Unavailable**, and an open exception shows "Risk score unavailable".

## Evidence (captured in this session)
- `pytest -q tests`: **27 passed**, including an 8-thread concurrent double-decision race (exactly one 200, the
  rest 409, one history row), vendor error text that echoes the sandbox secret (mapped to `unrecognized_error`,
  not forwarded), and malformed token/risk JSON (shown as unavailable, never a 500).
- `scripts/smoke.py`: **14/14** checks passed across two real uvicorn processes. Covered: wrong secret 401, missing
  bearer 401, live enrichment, connected status, decision 200, duplicate 409, cross-tenant 404, 10 concurrent HTTP decisions → one 200 / nine 409 / one history row, vendor stopped →
  unavailable (risk and status), and the secret/bearer absent from responses and both process logs.
- `scripts/e2e.py` (Playwright driving locally installed Chrome 137): wrong login rejected, viewer read-only and
  redacted with a forged-role fetch returning 403, operator A reject plus history, the "You cannot" list on the Access panel for both roles (includes cross-tenant), and operator B seeing tenant B only, with
  a fetch of `SE-1002` returning 404. Screenshots and a .webm recording are delivered with the artifact (not committed).

## Comparison note (Power Platform), honest version
Microsoft's custom connector FAQ says the OAuth client-credentials grant is not supported directly by Power Apps custom
connectors: <https://learn.microsoft.com/en-us/connectors/custom-connectors/faq>. That does **not** make this use case
impossible on Power Platform. A common pattern puts an intermediary in front, such as an Azure Function/API or another
backend that holds the credential and performs the exchange. Here the benefit is that the token exchange is ordinary
backend code we can read, test and change directly. The cost is that we own its maintenance and security: secret
storage and rotation, patching, logging hygiene, and availability. No wider product comparison was researched.

## Limitations
Local demo only: cookie `Secure` is off because it runs over HTTP. No rate limiting, lockout or MFA. Vendor tokens are
kept in memory. History is an ordinary SQLite table, not tamper-proof auditing. The vendor is simulated. Governance and
runtime controls are covered in [docs/governance.md](docs/governance.md).

## Independent review after Devin delivery

Devin built this sample and fixed the shared-connection transaction race, vendor error forwarding and access-panel wording during review. Codex then added two small vendor-response guards (reject non-string risk bands and check credential echoes before truncating display text), with regressions that failed on the delivered code. The final local verification passes **28 tests** and **14 real HTTP smoke checks**; the original Devin artifact reports 27 tests. This is a separately timed follow-up to the original prototype, not part of its reported build time.

## Explain the integration in the app

The “Why build this integration in code?” panel compares the direct backend path with a Power Apps custom-connector/intermediary approach. Its **Run a live connection check** button reads the first exception in the signed-in user's tenant and requests its risk result through the backend; it does not decide or update a settlement. The result identifies the simulated vendor and possible token-cache reuse. The panel links to Microsoft's documented client-credentials limitation and explicitly acknowledges that Power Platform can support the scenario through a workaround. Collapse the panel to focus on the queue.
