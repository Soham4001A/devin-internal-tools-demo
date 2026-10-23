import httpx
from conftest import SECRET, login


def test_unauthenticated_401(client):
    for m, p in [("get", "/api/me"), ("get", "/api/exceptions"), ("get", "/api/exceptions/SE-1001"),
                 ("get", "/api/exceptions/SE-1001/history"), ("get", "/api/integration")]:
        assert getattr(client, m)(p).status_code == 401
    assert client.post("/api/exceptions/SE-1001/decision", json={"action": "approve", "reason": "fine"}).status_code == 401


def test_incorrect_login_401(client):
    assert client.post("/api/login", json={"username": "operator.a", "password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"username": "nobody", "password": "x"}).status_code == 401
    assert "sr_session" not in client.cookies


def test_cookie_flags(client):
    r = client.post("/api/login", json={"username": "viewer.a", "password": "viewer-a-demo"})
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=strict" in sc and "max-age=1800" in sc
    assert client.cookies["sr_session"] not in r.text  # session token not echoed in body


def test_viewer_cannot_decide_even_with_forged_role(client):
    h = login(client, "viewer.a")
    forged = {**h, "X-Role": "operator", "X-User-Role": "operator", "X-Tenant": "tenant-b"}
    r = client.post("/api/exceptions/SE-1001/decision", headers=forged,
                    json={"action": "approve", "reason": "looks fine", "role": "operator", "tenant": "tenant-b"})
    assert r.status_code == 403
    assert client.get("/api/exceptions/SE-1001/history").json()["items"] == []
    assert client.get("/api/exceptions/SE-1001").json()["status"] == "open"
    assert client.get("/api/me", headers=forged).json()["role"] == "viewer"


def test_viewer_sees_redacted_account(client):
    login(client, "viewer.a")
    items = client.get("/api/exceptions").json()["items"]
    assert items and all(i["account_number"].startswith("•••• ") and i["account_redacted"] for i in items)
    assert "GB00DEMO" not in client.get("/api/exceptions").text + client.get("/api/exceptions/SE-1001").text


def test_tenant_isolation(client):
    h = login(client, "operator.b")
    ids = {i["id"] for i in client.get("/api/exceptions").json()["items"]}
    assert ids == {"SE-2001", "SE-2002", "SE-2003"}
    assert client.get("/api/exceptions/SE-1001").status_code == 404
    assert client.get("/api/exceptions/SE-1001/history").status_code == 404
    assert client.post("/api/exceptions/SE-1001/decision", headers=h,
                       json={"action": "reject", "reason": "cross tenant"}).status_code == 404
    assert client.get("/api/exceptions/SE-9999").status_code == 404  # same as missing
    login(client, "viewer.a")
    assert client.get("/api/exceptions/SE-2001").status_code == 404
    assert client.get("/api/exceptions/SE-1001").json()["status"] == "open"


def test_operator_success_duplicate_and_audit_persistence(client, make_app):
    h = login(client, "operator.a")
    assert client.post("/api/exceptions/SE-1002/decision", headers=h, json={"action": "approve", "reason": "  "}).status_code == 422
    r = client.post("/api/exceptions/SE-1002/decision", headers=h, json={"action": "reject", "reason": "Duplicate batch confirmed"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    r2 = client.post("/api/exceptions/SE-1002/decision", headers=h, json={"action": "approve", "reason": "try again"})
    assert r2.status_code == 409
    hist = client.get("/api/exceptions/SE-1002/history").json()["items"]
    assert len(hist) == 1 and hist[0]["actor"] == "Omar Operator" and hist[0]["to_status"] == "rejected"
    # persisted in SQLite: a fresh connection sees it
    import sqlite3
    path = client.app.state.db_file
    rows = sqlite3.connect(path).execute("SELECT status FROM exceptions WHERE id='SE-1002'").fetchall()
    assert rows == [("rejected",)]
    assert client.get("/api/exceptions/SE-1001").json()["account_number"] == "GB00DEMO00001234"  # operator: full


def test_csrf_required_for_writes(client):
    login(client, "operator.a")
    assert client.post("/api/exceptions/SE-1001/decision", json={"action": "approve", "reason": "fine fine"}).status_code == 403
    assert client.post("/api/exceptions/SE-1001/decision", headers={"X-CSRF-Token": "nope"},
                       json={"action": "approve", "reason": "fine fine"}).status_code == 403
    assert client.post("/api/logout").status_code == 403


def test_logout_invalidates_session(client):
    h = login(client, "operator.a")
    token = client.cookies["sr_session"]
    assert client.post("/api/logout", headers=h).status_code == 200
    client.cookies.set("sr_session", token)  # replay the old cookie
    assert client.get("/api/exceptions").status_code == 401


def test_session_expiry(client, clock):
    login(client, "viewer.a")
    clock.t += 1801
    assert client.get("/api/exceptions").status_code == 401


def test_risk_enrichment_and_no_secret_leak(client):
    h = login(client, "operator.a")
    bodies = []
    for p in ["/api/me", "/api/exceptions", "/api/exceptions/SE-1001", "/api/exceptions/SE-1001/history", "/api/integration"]:
        r = client.get(p)
        assert r.status_code == 200
        bodies.append(r.text + str(r.headers))
    d = client.get("/api/exceptions/SE-1001").json()
    assert d["risk"]["status"] == "available" and isinstance(d["risk"]["score"], int)
    bodies.append(client.post("/api/exceptions/SE-1001/decision", headers=h, json={"action": "approve", "reason": "ok fine"}).text)
    token = client.app.state.vendor._token
    assert token
    for b in bodies:
        assert SECRET not in b and token not in b and "client_secret" not in b


def test_vendor_outage_fails_closed(make_app):
    def down(req):
        raise httpx.ConnectError("refused")
    c = make_app(transport=httpx.MockTransport(down))
    login(c, "operator.a")
    risk = c.get("/api/exceptions/SE-1001").json()["risk"]
    assert risk["status"] == "unavailable" and "score" not in risk
    assert c.get("/api/integration").json()["state"] == "unavailable"


def test_vendor_500_fails_closed(make_app):
    c = make_app(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"error": "boom"})))
    login(c, "viewer.a")
    risk = c.get("/api/exceptions/SE-1001").json()["risk"]
    assert risk["status"] == "unavailable" and "score" not in risk


def test_wrong_client_secret_fails_closed(make_app):
    c = make_app(secret="wrong-secret")
    login(c, "viewer.a")
    risk = c.get("/api/exceptions/SE-1001").json()["risk"]
    assert risk["status"] == "unavailable" and "invalid_client" in risk["detail"] and "wrong-secret" not in str(risk)


def test_no_reset_endpoint(client):
    login(client, "operator.a")
    for p in ["/api/reset", "/api/admin/reset"]:
        assert client.post(p).status_code in (404, 405)


def test_concurrent_double_decision_one_wins(make_app):
    import threading
    from fastapi.testclient import TestClient
    base = make_app()
    for eid in ["SE-1001", "SE-1003", "SE-1004"]:
        clients = [TestClient(base.app) for _ in range(8)]
        headers = [login(c, "operator.a") for c in clients]
        barrier, results = threading.Barrier(len(clients)), []

        def go(c, h, i):
            barrier.wait()
            r = c.post(f"/api/exceptions/{eid}/decision", headers=h,
                       json={"action": "approve" if i % 2 else "reject", "reason": f"concurrent {i}"})
            results.append(r.status_code)

        ts = [threading.Thread(target=go, args=(c, h, i)) for i, (c, h) in enumerate(zip(clients, headers))]
        [t.start() for t in ts], [t.join() for t in ts]
        assert sorted(results) == [200] + [409] * 7, results
        login(base, "operator.a")
        hist = base.get(f"/api/exceptions/{eid}/history").json()["items"]
        assert len(hist) == 1
        assert base.get(f"/api/exceptions/{eid}").json()["status"] == hist[0]["to_status"]
    # no stuck transaction: a later normal decision still works
    h = login(base, "operator.a")
    assert base.post("/api/exceptions/SE-1002/decision", headers=h, json={"action": "approve", "reason": "after race"}).status_code == 200


def test_vendor_error_text_echoing_secret_not_forwarded(make_app):
    echo = f"bad client {SECRET} token=abc"
    c = make_app(transport=httpx.MockTransport(
        lambda r: httpx.Response(401, json={"error": echo, "error_description": echo})))
    login(c, "operator.a")
    texts = [c.get("/api/exceptions/SE-1001").text, c.get("/api/integration").text]
    risk = c.get("/api/exceptions/SE-1001").json()["risk"]
    assert risk["status"] == "unavailable" and "unrecognized_error" in risk["detail"]
    assert all(SECRET not in t and "bad client" not in t for t in texts)


def test_vendor_known_error_code_mapped(make_app):
    c = make_app(transport=httpx.MockTransport(
        lambda r: httpx.Response(400, json={"error": "invalid_scope", "error_description": SECRET})))
    login(c, "viewer.a")
    risk = c.get("/api/exceptions/SE-1001").json()["risk"]
    assert "invalid_scope" in risk["detail"] and SECRET not in str(risk)


def test_vendor_risk_body_echoing_credentials_rejected(make_app, vendor_tc):
    real = __import__("conftest").bridge(vendor_tc)

    def handler(req):
        if req.url.path == "/oauth/token":
            return real.handle_request(req)
        return httpx.Response(200, json={"score": 10, "band": "low", "reasons": [f"echo {SECRET}"], "model": "m"})
    c = make_app(transport=httpx.MockTransport(handler))
    login(c, "viewer.a")
    r = c.get("/api/exceptions/SE-1001")
    assert r.status_code == 200 and r.json()["risk"]["status"] == "unavailable" and SECRET not in r.text


def test_malformed_vendor_json_fails_closed(make_app, vendor_tc):
    real = __import__("conftest").bridge(vendor_tc)
    bad_risk = [b"not json", b"[1,2]", b'{"score": "90", "band": "low"}', b'{"score": 500, "band": "low"}',
                b'{"score": 10, "band": "<b>x</b>", "reasons": []}', b'{"score": true, "band": "low"}', b'{"score": 10, "band": []}', b'{"score": 10, "band": {}}']
    bad_token = [b"<html>", b'{"token_type": "Bearer"}', b'{"access_token": 5, "expires_in": 60}',
                 b'{"access_token": "abc", "expires_in": "soon"}']
    cases = [("risk", b) for b in bad_risk] + [("token", b) for b in bad_token]
    for where, payload in cases:
        def handler(req, where=where, payload=payload):
            is_token = req.url.path == "/oauth/token"
            if (where == "token") == is_token:
                return httpx.Response(200, content=payload, headers={"content-type": "application/json"})
            return real.handle_request(req)
        c = make_app(transport=httpx.MockTransport(handler))
        login(c, "operator.a")
        r = c.get("/api/exceptions/SE-1001")
        assert r.status_code == 200, (where, payload, r.text)
        risk = r.json()["risk"]
        assert risk["status"] == "unavailable" and "score" not in risk, (where, payload)
        assert c.get("/api/integration").status_code == 200


def test_access_panel_lists_restrictions_for_every_role(client):
    for user in ["viewer.a", "operator.a", "operator.b"]:
        login(client, user)
        cannot = client.get("/api/me").json()["not_permitted"]
        assert any("other tenant" in x for x in cannot), (user, cannot)
        assert any("Approve or reject" in x for x in cannot) == (user == "viewer.a")


def test_vendor_credential_echo_rejected_before_truncation(make_app, vendor_tc):
    real = __import__("conftest").bridge(vendor_tc)
    for field in ["model", "reasons"]:
        def handler(req, field=field):
            if req.url.path == "/oauth/token":
                return real.handle_request(req)
            payload = {"score": 10, "band": "low", "reasons": [], "model": "m"}
            payload[field] = ("prefix-" + SECRET) if field == "model" else ["x" * 190 + SECRET]
            return httpx.Response(200, json=payload)
        c = make_app(transport=httpx.MockTransport(handler))
        login(c, "viewer.a")
        response = c.get("/api/exceptions/SE-1001")
        assert response.status_code == 200
        assert response.json()["risk"]["status"] == "unavailable"
        assert "test-secret" not in response.text
