"""PUBLIC SYNTHETIC demo accounts. Local demo login only — NOT SSO, NOT production identity.

Roles and tenant membership come only from this server-side table, never from request headers/body.
"""
import hashlib
import hmac
import secrets
from dataclasses import dataclass

TENANTS = {"tenant-a": "Northwind Settlements (demo tenant A)", "tenant-b": "Bluefin Payouts (demo tenant B)"}
ROLE_LABELS = {"viewer": "Viewer", "operator": "Settlement Operator"}
PERMISSIONS = {
    "viewer": ["View settlement exceptions in your tenant", "View decision history in your tenant",
               "See account numbers redacted (last 4 only)"],
    "operator": ["View settlement exceptions in your tenant", "View decision history in your tenant",
                 "See full synthetic account numbers in your tenant",
                 "Approve or reject open exceptions in your tenant (reason required)"],
}
_CROSS_TENANT = "See or act on any other tenant's exceptions (they return \u201cNot found\u201d)"
NOT_PERMITTED = {
    "viewer": ["Approve or reject exceptions", "See full account numbers", _CROSS_TENANT],
    "operator": [_CROSS_TENANT, "Change your own role or tenant"],
}


@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    role: str
    tenant: str
    salt: bytes
    pw_hash: bytes

    @property
    def can_decide(self) -> bool:
        return self.role == "operator"


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)


def _user(username, display_name, role, tenant, password) -> User:
    salt = secrets.token_bytes(16)
    return User(username, display_name, role, tenant, salt, _hash(password, salt))


# Passwords below are intentionally public synthetic demo credentials (documented in README).
USERS = {u.username: u for u in [
    _user("viewer.a", "Vera Viewer", "viewer", "tenant-a", "viewer-a-demo"),
    _user("operator.a", "Omar Operator", "operator", "tenant-a", "operator-a-demo"),
    _user("operator.b", "Bea Operator", "operator", "tenant-b", "operator-b-demo"),
]}
_DUMMY_SALT = secrets.token_bytes(16)


def verify(username: str, password: str) -> User | None:
    user = USERS.get(username)
    candidate = _hash(password, user.salt if user else _DUMMY_SALT)
    if user and hmac.compare_digest(candidate, user.pw_hash):
        return user
    return None
