"""SIMULATED "Risk Vendor" service. Real HTTP + OAuth 2.0 client_credentials exchange, fictional data only.

Runs as its own process on 127.0.0.1:9011. Not a live third-party integration.
"""
import hashlib
import hmac
import os
import secrets
import threading
import time
from typing import Callable

from fastapi import FastAPI, Form, Header, HTTPException
from fastapi.responses import JSONResponse

ALLOWED_SCOPES = {"risk:read", "status:read"}
REASONS = [
    "Counterparty first seen in the last 30 days (fictional)",
    "Settlement amount above tenant 90-day median (fictional)",
    "Reference format mismatch vs. scheme template (fictional)",
    "Repeated partial settlements on same batch (fictional)",
    "Beneficiary bank recently changed (fictional)",
    "No prior exceptions for this counterparty (fictional)",
]


def _oauth_error(status: int, error: str, description: str, bearer: bool = False) -> JSONResponse:
    headers = {"WWW-Authenticate": f'Bearer error="{error}"'} if bearer else {}
    return JSONResponse({"error": error, "error_description": description}, status_code=status, headers=headers)


def create_app(client_id: str | None = None, client_secret: str | None = None,
               token_ttl: int | None = None, clock: Callable[[], float] = time.time) -> FastAPI:
    client_id = client_id or os.environ.get("RISK_VENDOR_CLIENT_ID", "")
    client_secret = client_secret or os.environ.get("RISK_VENDOR_CLIENT_SECRET", "")
    ttl = token_ttl or int(os.environ.get("RISK_VENDOR_TOKEN_TTL", "300"))
    if not client_id or not client_secret:
        raise RuntimeError("RISK_VENDOR_CLIENT_ID / RISK_VENDOR_CLIENT_SECRET must be set in the environment")

    tokens: dict[str, tuple[float, frozenset[str]]] = {}
    lock = threading.Lock()
    app = FastAPI(title="Risk Vendor (SIMULATED)", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.tokens = tokens

    @app.get("/health")
    def health():
        return {"status": "ok", "simulated": True}

    @app.post("/oauth/token")
    def token(grant_type: str = Form(""), client_id_in: str = Form("", alias="client_id"),
              client_secret_in: str = Form("", alias="client_secret"), scope: str = Form("risk:read")):
        if grant_type != "client_credentials":
            return _oauth_error(400, "unsupported_grant_type", "only client_credentials is supported")
        ok_id = hmac.compare_digest(client_id_in.encode(), client_id.encode())
        ok_secret = hmac.compare_digest(client_secret_in.encode(), client_secret.encode())
        if not (ok_id and ok_secret):
            return _oauth_error(401, "invalid_client", "client authentication failed")
        requested = frozenset(scope.split()) or frozenset({"risk:read"})
        if not requested <= ALLOWED_SCOPES:
            return _oauth_error(400, "invalid_scope", "requested scope not allowed for this client")
        value = secrets.token_urlsafe(32)  # opaque bearer token
        with lock:
            now = clock()
            for k in [k for k, (exp, _) in tokens.items() if exp <= now]:
                tokens.pop(k, None)
            tokens[value] = (now + ttl, requested)
        return {"access_token": value, "token_type": "Bearer", "expires_in": ttl, "scope": " ".join(sorted(requested))}

    def _require(authorization: str | None, needed: str):
        if not authorization or not authorization.startswith("Bearer "):
            return _oauth_error(401, "invalid_token", "missing bearer token", bearer=True)
        with lock:
            entry = tokens.get(authorization[7:].strip())
        if entry is None:
            return _oauth_error(401, "invalid_token", "unknown token", bearer=True)
        exp, scopes = entry
        if exp <= clock():
            return _oauth_error(401, "invalid_token", "token expired", bearer=True)
        if needed not in scopes:
            return _oauth_error(403, "insufficient_scope", f"{needed} required", bearer=True)
        return None

    @app.get("/v1/risk/{reference}")
    def risk(reference: str, authorization: str | None = Header(None)):
        denied = _require(authorization, "risk:read")
        if denied:
            return denied
        if len(reference) > 64 or not reference.replace("-", "").isalnum():
            raise HTTPException(400, "bad reference")
        h = hashlib.sha256(reference.encode()).digest()
        score = h[0] % 100
        reasons = [REASONS[h[i] % len(REASONS)] for i in (1, 2)]
        band = "high" if score >= 70 else "medium" if score >= 40 else "low"
        return {"reference": reference, "score": score, "band": band, "reasons": sorted(set(reasons)),
                "model": "risk-sim-v1", "simulated": True}

    return app


def app_factory() -> FastAPI:
    return create_app()
