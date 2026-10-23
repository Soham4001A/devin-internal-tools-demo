"""Settlement Review — synthetic demo. No real payments are executed; decisions are only recorded."""
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db
from .users import NOT_PERMITTED, PERMISSIONS, ROLE_LABELS, TENANTS, USERS, User, verify
from .vendor_client import VendorClient, VendorUnavailable

COOKIE = "sr_session"
SESSION_TTL = int(os.environ.get("SR_SESSION_TTL", "1800"))
STATIC = Path(__file__).parent / "static"
log = logging.getLogger("settlement_review")


class LoginIn(BaseModel):
    username: str
    password: str


class DecisionIn(BaseModel):
    action: Literal["approve", "reject"]
    reason: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_app(db_file: str | None = None, vendor: VendorClient | None = None, reset: bool | None = None,
               clock=time.time, secure_cookie: bool = False) -> FastAPI:
    reset = os.environ.get("SR_RESET") == "1" if reset is None else reset
    db.init(db_file, reset=reset)  # reset only via local startup flag; no HTTP reset endpoint
    vendor = vendor or VendorClient()
    app = FastAPI(title="Settlement Review (demo)", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db_file, app.state.vendor = db_file or db.db_path(), vendor

    def get_db():
        # One SQLite connection per request (shared by its dependencies); never shared across worker threads.
        conn = db.connect(db_file)
        try:
            yield conn
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            conn.close()

    # ---- auth -------------------------------------------------------------------------------------------------
    def session(request: Request, conn=Depends(get_db)) -> tuple[User, dict]:
        token = request.cookies.get(COOKIE)
        if not token:
            raise HTTPException(401, "Not signed in")
        row = conn.execute("SELECT * FROM sessions WHERE token_hash=?", (_h(token),)).fetchone()
        if not row or row["expires_at"] <= clock():
            if row:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (row["token_hash"],))
            raise HTTPException(401, "Session expired or invalid")
        user = USERS.get(row["username"])  # role + tenant from server config only
        if not user:
            raise HTTPException(401, "Unknown user")
        return user, dict(row)

    def current_user(s=Depends(session)) -> User:
        return s[0]

    def csrf_user(request: Request, s=Depends(session)) -> User:
        sent = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(sent.encode(), s[1]["csrf"].encode()):
            raise HTTPException(403, "CSRF token missing or invalid")
        return s[0]

    def me_payload(user: User, csrf: str) -> dict:
        return {"username": user.username, "display_name": user.display_name, "role": user.role,
                "role_label": ROLE_LABELS[user.role], "tenant": user.tenant, "tenant_name": TENANTS[user.tenant],
                "can_decide": user.can_decide, "permissions": PERMISSIONS[user.role],
                "not_permitted": NOT_PERMITTED[user.role],
                "csrf_token": csrf, "session_expires_in": SESSION_TTL,
                "how_assigned": "Role and tenant come from the server's demo account table. They cannot be changed "
                                "from this page, request headers or request bodies."}

    @app.post("/api/login")
    def login(body: LoginIn, response: Response, conn=Depends(get_db)):
        user = verify(body.username, body.password)
        if not user:
            raise HTTPException(401, "Incorrect username or password")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (clock(),))
        conn.execute("INSERT INTO sessions VALUES (?,?,?,?)", (_h(token), user.username, csrf, clock() + SESSION_TTL))
        response.set_cookie(COOKIE, token, max_age=SESSION_TTL, httponly=True, samesite="strict",
                            secure=secure_cookie, path="/")
        return me_payload(user, csrf)

    @app.post("/api/logout")
    def logout(response: Response, request: Request, user: User = Depends(csrf_user), conn=Depends(get_db)):
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (_h(request.cookies[COOKIE]),))
        response.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/me")
    def me(s=Depends(session)):
        return me_payload(s[0], s[1]["csrf"])

    # ---- exceptions ------------------------------------------------------------------------------------------
    def shape(row, user: User) -> dict:
        d = dict(row)
        acct = d.pop("account_number")
        d["account_number"] = acct if user.can_decide else "•••• " + acct[-4:]
        d["account_redacted"] = not user.can_decide
        d.pop("tenant")
        return d

    def load(conn, eid: str, user: User):
        row = conn.execute("SELECT * FROM exceptions WHERE id=? AND tenant=?", (eid, user.tenant)).fetchone()
        if not row:
            raise HTTPException(404, "Not found")  # same response for missing and other-tenant IDs
        return row

    @app.get("/api/exceptions")
    def list_exceptions(user: User = Depends(current_user), conn=Depends(get_db)):
        rows = conn.execute("SELECT * FROM exceptions WHERE tenant=? ORDER BY created_at DESC", (user.tenant,))
        items = [shape(r, user) for r in rows]
        return {"tenant_name": TENANTS[user.tenant], "items": items,
                "counts": {s: sum(1 for i in items if i["status"] == s) for s in ("open", "approved", "rejected")}}

    def risk_for(reference: str) -> dict:
        try:
            r = vendor.risk(reference)
            return {"status": "available", "source": "Risk Vendor (SIMULATED)", **r}
        except VendorUnavailable as e:
            log.warning("risk vendor unavailable: %s", e)
            return {"status": "unavailable", "source": "Risk Vendor (SIMULATED)",
                    "message": "Risk score unavailable — the vendor could not be reached or rejected the request. "
                               "No score is shown rather than a guessed one.", "detail": str(e)}

    @app.get("/api/exceptions/{eid}")
    def detail(eid: str, user: User = Depends(current_user), conn=Depends(get_db)):
        row = load(conn, eid, user)
        return {**shape(row, user), "risk": risk_for(row["reference"])}

    @app.get("/api/exceptions/{eid}/history")
    def history(eid: str, user: User = Depends(current_user), conn=Depends(get_db)):
        load(conn, eid, user)
        rows = conn.execute("SELECT actor, action, reason, from_status, to_status, at FROM history "
                            "WHERE exception_id=? AND tenant=? ORDER BY id", (eid, user.tenant))
        return {"items": [dict(r) for r in rows]}

    @app.post("/api/exceptions/{eid}/decision")
    def decide(eid: str, body: DecisionIn, user: User = Depends(csrf_user), conn=Depends(get_db)):
        load(conn, eid, user)
        if not user.can_decide:
            raise HTTPException(403, "Your role (Viewer) cannot approve or reject exceptions")
        reason = body.reason.strip()
        if len(reason) < 5:
            raise HTTPException(422, "A reason of at least 5 characters is required")
        new = "approved" if body.action == "approve" else "rejected"
        conn.execute("BEGIN IMMEDIATE")
        try:
            cur = conn.execute("UPDATE exceptions SET status=? WHERE id=? AND tenant=? AND status='open'",
                               (new, eid, user.tenant))
            if cur.rowcount != 1:
                conn.execute("ROLLBACK")
                raise HTTPException(409, "This exception has already been decided")
            conn.execute("INSERT INTO history (exception_id, tenant, actor, action, reason, from_status, to_status, at)"
                         " VALUES (?,?,?,?,?,?,?,?)", (eid, user.tenant, user.display_name, body.action, reason,
                                                       "open", new, _now()))
            conn.execute("COMMIT")
        except HTTPException:
            raise
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return {"id": eid, "status": new, "note": "Decision recorded only. No payment was moved."}

    # ---- integration status (redacted) -------------------------------------------------------------------------
    @app.get("/api/integration")
    def integration(user: User = Depends(current_user)):
        reachable = vendor.health()
        token_ok, err = False, None
        if reachable:
            try:
                vendor._get_token()
                token_ok = True
            except VendorUnavailable as e:
                err = str(e)
        state = "connected" if reachable and token_ok else "unavailable"
        return {"state": state, "vendor": "Risk Vendor (SIMULATED local service, fictional data)",
                "endpoint": vendor.base_url, "auth": "OAuth 2.0 client_credentials, scope risk:read",
                "credentials_configured": vendor.configured, "token_cached": token_ok,
                "token_seconds_left": vendor.token_seconds_left(), "last_error": err or vendor.last_error,
                "steps": [
                    "The launcher generates a random sandbox client secret and passes it, via environment variables "
                    "only, to the vendor process and this app's backend.",
                    "The backend posts its client ID and secret to the vendor's /oauth/token (grant_type="
                    "client_credentials, scope=risk:read) and receives a short-lived opaque bearer token.",
                    "The token is cached in backend memory and refreshed ~30s before it expires.",
                    "When you open an exception, the backend calls GET /v1/risk/{reference} on the fixed, "
                    "server-configured vendor URL with that token (2s timeout).",
                    "Only the score and reasons are returned to your browser. The secret and the token "
                    "[REDACTED] never leave the server.",
                    "If the vendor is down or rejects the token, the page shows 'unavailable' — never a made-up score.",
                ]}

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/app.js")
    def js():
        return FileResponse(STATIC / "app.js", media_type="text/javascript", headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    return app


def app_factory() -> FastAPI:
    return create_app()
