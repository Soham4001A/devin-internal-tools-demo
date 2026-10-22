import importlib

import pytest
from fastapi.testclient import TestClient

R = {"X-Demo-Persona": "reviewer"}
V = {"X-Demo-Persona": "viewer"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def pending_id(c):
    return c.get("/api/tools/refunds/records?status=pending", headers=V).json()["items"][0]["id"]


def test_seed_has_12_records_with_old_pending(client):
    items = client.get("/api/tools/refunds/records", headers=V).json()["items"]
    assert len(items) == 12
    s = client.get("/api/tools/refunds/summary", headers=V).json()
    assert s["counts"] == {"pending": 7, "approved": 3, "rejected": 2}


def test_viewer_cannot_decide(client):
    rid = pending_id(client)
    r = client.post(f"/api/tools/refunds/records/{rid}/decision", headers=V,
                    json={"action": "approve", "reason": "looks fine"})
    assert r.status_code == 403
    rec = client.get(f"/api/tools/refunds/records/{rid}", headers=V).json()
    assert rec["record"]["status"] == "pending"
    assert [e["action"] for e in rec["history"]] == ["submitted"]


def test_unknown_persona_rejected(client):
    r = client.get("/api/tools/refunds/records", headers={"X-Demo-Persona": "admin"})
    assert r.status_code == 401


@pytest.mark.parametrize("reason", ["", "  ", "no"])
def test_reason_required(client, reason):
    rid = pending_id(client)
    r = client.post(f"/api/tools/refunds/records/{rid}/decision", headers=R,
                    json={"action": "reject", "reason": reason})
    assert r.status_code == 422
    assert client.get(f"/api/tools/refunds/records/{rid}", headers=V).json()["record"]["status"] == "pending"


def test_approve_records_history_and_blocks_duplicate(client):
    rid = pending_id(client)
    r = client.post(f"/api/tools/refunds/records/{rid}/decision", headers=R,
                    json={"action": "approve", "reason": "Duplicate charge confirmed"})
    assert r.status_code == 200
    body = r.json()
    assert body["record"]["status"] == "approved"
    last = body["history"][-1]
    assert (last["action"], last["actor"], last["reason"], last["to_status"]) == (
        "approve", "Priya Raman", "Duplicate charge confirmed", "approved")
    for action in ("approve", "reject"):
        d = client.post(f"/api/tools/refunds/records/{rid}/decision", headers=R,
                        json={"action": action, "reason": "again please"})
        assert d.status_code == 409
    hist = client.get(f"/api/tools/refunds/records/{rid}", headers=V).json()["history"]
    assert [e["action"] for e in hist] == ["submitted", "approve"]


def test_unknown_action(client):
    rid = pending_id(client)
    r = client.post(f"/api/tools/refunds/records/{rid}/decision", headers=R,
                    json={"action": "refund_now", "reason": "xyz"})
    assert r.status_code == 400


def test_decision_persists_across_app_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "persist.db"))
    from app import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        rid = pending_id(c)
        c.post(f"/api/tools/refunds/records/{rid}/decision", headers=R,
               json={"action": "reject", "reason": "Outside policy window"})
    importlib.reload(main)
    with TestClient(main.app) as c2:
        rec = c2.get(f"/api/tools/refunds/records/{rid}", headers=V).json()
        assert rec["record"]["status"] == "rejected"
        assert rec["history"][-1]["reason"] == "Outside policy window"


def test_search_and_filter(client):
    items = client.get("/api/tools/refunds/records?q=skyward", headers=V).json()["items"]
    assert [i["ref"] for i in items] == ["RF-1005"]
    assert client.get("/api/tools/refunds/records?status=bogus", headers=V).status_code == 400


def test_reset_restores_fixtures(client):
    rid = pending_id(client)
    client.post(f"/api/tools/refunds/records/{rid}/decision", headers=R,
                json={"action": "approve", "reason": "ok fine"})
    assert client.post("/api/demo/reset?tool=refunds").status_code == 200
    s = client.get("/api/tools/refunds/summary", headers=V).json()
    assert s["counts"]["pending"] == 7


def test_records_isolated_by_tool(client):
    from app import db
    conn = db.connect()
    conn.execute("INSERT INTO records(tool, ref, status, data, submitted_at, updated_at)"
                 " VALUES ('other','RF-1001','pending','{}','2026-01-01','2026-01-01')")
    other_id = conn.execute("SELECT id FROM records WHERE tool='other'").fetchone()[0]
    conn.close()
    assert len(client.get("/api/tools/refunds/records", headers=V).json()["items"]) == 12
    assert client.get(f"/api/tools/refunds/records/{other_id}", headers=V).status_code == 404
    r = client.post(f"/api/tools/refunds/records/{other_id}/decision", headers=R,
                    json={"action": "approve", "reason": "cross tool"})
    assert r.status_code == 404
    client.post("/api/demo/reset?tool=refunds")
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM records WHERE tool='other'").fetchone()[0] == 1
    conn.close()
