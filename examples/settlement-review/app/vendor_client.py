"""Backend-only client for the SIMULATED Risk Vendor. Secrets/tokens never leave this module."""
import os
import threading
import time

import httpx

DEFAULT_VENDOR_URL = "http://127.0.0.1:9011"


BANDS = {"low", "medium", "high"}
KNOWN_OAUTH_ERRORS = frozenset({"invalid_request", "invalid_client", "invalid_grant", "unauthorized_client",
                                "unsupported_grant_type", "invalid_scope", "invalid_token", "insufficient_scope"})


class VendorUnavailable(Exception):
    """Raised instead of ever returning fabricated risk data."""


class VendorClient:
    def __init__(self, base_url: str | None = None, client_id: str | None = None, client_secret: str | None = None,
                 transport: httpx.BaseTransport | None = None, timeout: float = 2.0, clock=time.time):
        # Fixed, server-configured URL. Nothing in a request can change where we call.
        self.base_url = (base_url or os.environ.get("SR_VENDOR_URL", DEFAULT_VENDOR_URL)).rstrip("/")
        self._client_id = client_id if client_id is not None else os.environ.get("RISK_VENDOR_CLIENT_ID", "")
        self._client_secret = client_secret if client_secret is not None else os.environ.get("RISK_VENDOR_CLIENT_SECRET", "")
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport, follow_redirects=False)
        self._clock = clock
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_exp = 0.0
        self.last_error: str | None = None
        self.last_success_at: float | None = None

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def token_seconds_left(self) -> int:
        return max(0, int(self._token_exp - self._clock())) if self._token else 0

    def _fetch_token(self) -> str:
        if not self.configured:
            raise VendorUnavailable("Vendor client credentials are not configured on the server")
        try:
            r = self._http.post("/oauth/token", data={"grant_type": "client_credentials", "client_id": self._client_id,
                                                      "client_secret": self._client_secret, "scope": "risk:read"})
        except httpx.HTTPError as e:
            raise VendorUnavailable(f"Token endpoint unreachable ({type(e).__name__})") from None
        if r.status_code != 200:
            raise VendorUnavailable(f"Token request rejected: HTTP {r.status_code} {_safe_error(r)}")
        body = _json(r)
        token, ttl = body.get("access_token"), body.get("expires_in", 60)
        if not isinstance(token, str) or not token or not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
            raise VendorUnavailable("Malformed token response")
        self._token, self._token_exp = token, self._clock() + ttl
        return self._token

    def _get_token(self, force: bool = False) -> str:
        with self._lock:
            if force or not self._token or self._token_exp - self._clock() < 30:
                self._token = None
                return self._fetch_token()
            return self._token

    def risk(self, reference: str) -> dict:
        try:
            for attempt in (0, 1):
                token = self._get_token(force=attempt == 1)
                try:
                    r = self._http.get(f"/v1/risk/{reference}", headers={"Authorization": f"Bearer {token}"})
                except httpx.HTTPError as e:
                    raise VendorUnavailable(f"Risk endpoint unreachable ({type(e).__name__})") from None
                if r.status_code == 401 and attempt == 0:
                    continue  # token revoked/expired early: refresh once
                if r.status_code != 200:
                    raise VendorUnavailable(f"Risk request rejected: HTTP {r.status_code} {_safe_error(r)}")
                result = self._parse_risk(_json(r), token)
                self.last_error, self.last_success_at = None, self._clock()
                return result
            raise VendorUnavailable("Risk request rejected after token refresh")
        except VendorUnavailable as e:
            self.last_error = str(e)
            raise

    def _parse_risk(self, data: dict, token: str) -> dict:
        score, band, reasons, model = data.get("score"), data.get("band"), data.get("reasons", []), data.get("model", "")
        if (not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100 or not isinstance(band, str) or band not in BANDS
                or not isinstance(reasons, list) or not all(isinstance(x, str) for x in reasons)
                or not isinstance(model, str)):
            raise VendorUnavailable("Malformed vendor response")
        result = {"score": score, "band": band, "reasons": [x[:200] for x in reasons[:5]], "model": model[:40],
                  "simulated": data.get("simulated") is True}
        blob = repr(data)  # Check the complete response before display truncation can hide part of a credential.
        if (self._client_secret and self._client_secret in blob) or token in blob:
            raise VendorUnavailable("Vendor response rejected (contained credential material)")
        return result

    def health(self) -> bool:
        try:
            return self._http.get("/health").status_code == 200
        except httpx.HTTPError:
            return False


def _json(r: httpx.Response) -> dict:
    try:
        data = r.json()
    except ValueError:
        raise VendorUnavailable("Malformed vendor response (not JSON)") from None
    if not isinstance(data, dict):
        raise VendorUnavailable("Malformed vendor response")
    return data


def _safe_error(r: httpx.Response) -> str:
    """Map vendor errors to known OAuth codes only; never forward arbitrary vendor text."""
    try:
        code = r.json().get("error")
    except Exception:
        code = None
    return code if isinstance(code, str) and code in KNOWN_OAUTH_ERRORS else "unrecognized_error"
