from conftest import CID, SECRET


def tok(v, **kw):
    data = {"grant_type": "client_credentials", "client_id": CID, "client_secret": SECRET, "scope": "risk:read", **kw}
    return v.post("/oauth/token", data=data)


def test_valid_token_and_risk(vendor_tc):
    r = tok(vendor_tc)
    assert r.status_code == 200 and r.json()["token_type"] == "Bearer" and r.json()["expires_in"] == 120
    t = r.json()["access_token"]
    rr = vendor_tc.get("/v1/risk/STL-A-7781", headers={"Authorization": f"Bearer {t}"})
    assert rr.status_code == 200 and 0 <= rr.json()["score"] < 100 and rr.json()["simulated"] is True


def test_wrong_secret_and_grant(vendor_tc):
    assert tok(vendor_tc, client_secret="nope").status_code == 401
    assert tok(vendor_tc, client_id="other").status_code == 401
    assert tok(vendor_tc, grant_type="password").json()["error"] == "unsupported_grant_type"
    assert tok(vendor_tc, scope="risk:write").json()["error"] == "invalid_scope"


def test_missing_and_bogus_token(vendor_tc):
    assert vendor_tc.get("/v1/risk/STL-A-7781").status_code == 401
    r = vendor_tc.get("/v1/risk/STL-A-7781", headers={"Authorization": "Bearer made-up"})
    assert r.status_code == 401 and "invalid_token" in r.headers["www-authenticate"]


def test_expired_token(vendor_tc, clock):
    t = tok(vendor_tc).json()["access_token"]
    clock.t += 121
    r = vendor_tc.get("/v1/risk/STL-A-7781", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 401 and r.json()["error_description"] == "token expired"


def test_insufficient_scope(vendor_tc):
    t = tok(vendor_tc, scope="status:read").json()["access_token"]
    r = vendor_tc.get("/v1/risk/STL-A-7781", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403 and r.json()["error"] == "insufficient_scope"


def test_client_refreshes_after_expiry(make_app, clock):
    c = make_app()
    from conftest import login
    login(c, "viewer.a")
    assert c.get("/api/exceptions/SE-1001").json()["risk"]["status"] == "available"
    first = c.app.state.vendor._token
    clock.t += 200
    assert c.get("/api/exceptions/SE-1001").json()["risk"]["status"] == "available"
    assert c.app.state.vendor._token != first
