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


def _insert(ref, status, hours_ago, tool="refunds"):
    from datetime import datetime, timedelta, timezone
    from app import db
    ts = db.now_iso(datetime.now(timezone.utc) - timedelta(hours=hours_ago))
    conn = db.connect()
    conn.execute("INSERT INTO records(tool, ref, status, data, submitted_at, updated_at) VALUES (?,?,?,?,?,?)",
                 (tool, ref, status, '{"customer": "Boundary Test"}', ts, ts))
    conn.close()


def test_overdue_filter_oldest_first_pending_only(client):
    items = client.get("/api/tools/refunds/records?overdue=true", headers=V).json()["items"]
    assert [i["ref"] for i in items] == ["RF-1007", "RF-1006", "RF-1005", "RF-1004"]
    s = client.get("/api/tools/refunds/summary", headers=V).json()
    assert s["overdue_pending"] == 4 and s["overdue_hours"] == 48
    # RF-1010 (rejected, 70h) and RF-1011 (approved, 120h) are old but never overdue
    for st in ("approved", "rejected"):
        assert client.get(f"/api/tools/refunds/records?overdue=true&status={st}", headers=V).json()["items"] == []
    # combines with search and status filter
    items = client.get("/api/tools/refunds/records?overdue=true&q=skyward", headers=V).json()["items"]
    assert [i["ref"] for i in items] == ["RF-1005"]
    items = client.get("/api/tools/refunds/records?overdue=true&status=pending", headers=V).json()["items"]
    assert len(items) == 4


def test_overdue_48h_boundary(client):
    _insert("RF-B4759", "pending", 47 + 59 / 60)
    _insert("RF-B4801", "pending", 48 + 1 / 60)
    _insert("RF-BAPPR", "approved", 200)
    refs = [i["ref"] for i in client.get("/api/tools/refunds/records?overdue=true", headers=V).json()["items"]]
    assert "RF-B4801" in refs and "RF-B4759" not in refs and "RF-BAPPR" not in refs
    assert client.get("/api/tools/refunds/summary", headers=V).json()["overdue_pending"] == 5


def test_is_overdue_exact_boundary():
    from datetime import datetime, timedelta, timezone
    from app.main import is_overdue
    now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
    at = lambda h, st="pending": {"status": st, "submitted_at": (now - timedelta(hours=h)).isoformat()}
    assert not is_overdue(at(48), now)
    assert is_overdue(at(48 + 1 / 3600), now)
    assert not is_overdue(at(47.99), now)
    assert not is_overdue(at(100, "approved"), now)
    assert not is_overdue(at(100, "rejected"), now)


def test_decided_overdue_leaves_count(client):
    rid = client.get("/api/tools/refunds/records?overdue=true", headers=V).json()["items"][0]["id"]
    client.post(f"/api/tools/refunds/records/{rid}/decision", headers=R,
                json={"action": "reject", "reason": "Outside policy window"})
    assert client.get("/api/tools/refunds/summary", headers=V).json()["overdue_pending"] == 3
    refs = [i["ref"] for i in client.get("/api/tools/refunds/records?overdue=true", headers=V).json()["items"]]
    assert refs == ["RF-1006", "RF-1005", "RF-1004"]
