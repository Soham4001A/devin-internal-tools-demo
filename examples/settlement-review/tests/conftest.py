import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app  # noqa: E402
from app.vendor_client import VendorClient  # noqa: E402
from vendor.server import create_app as create_vendor  # noqa: E402

CID, SECRET = "settlement-review-test", "test-secret-" + "x" * 24


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def bridge(vendor_tc: TestClient):
    """httpx transport forwarding to the vendor ASGI app (exercises real OAuth logic in-process)."""
    def handler(req: httpx.Request) -> httpx.Response:
        r = vendor_tc.request(req.method, req.url.path, headers=dict(req.headers), content=req.content)
        return httpx.Response(r.status_code, headers=r.headers, content=r.content)
    return httpx.MockTransport(handler)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def vendor_tc(clock):
    return TestClient(create_vendor(CID, SECRET, token_ttl=120, clock=clock))


@pytest.fixture
def make_app(tmp_path, vendor_tc, clock):
    def make(transport=None, secret=SECRET):
        vc = VendorClient("http://vendor.test", CID, secret, transport=transport or bridge(vendor_tc), clock=clock)
        return TestClient(create_app(str(tmp_path / "t.db"), vendor=vc, reset=True, clock=clock))
    return make


@pytest.fixture
def client(make_app):
    return make_app()


def login(c: TestClient, user: str) -> dict:
    r = c.post("/api/login", json={"username": user, "password": user.replace(".", "-") + "-demo"})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}
