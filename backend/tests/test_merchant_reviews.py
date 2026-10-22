"""Merchant Reviews module: own data/decisions/history/reset, isolated from refunds."""
import importlib

import pytest
from fastapi.testclient import TestClient

R = {"X-Demo-Persona": "reviewer"}
V = {"X-Demo-Persona": "viewer"}
MR = "/api/tools/merchant_reviews"
RF = "/api/tools/refunds"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def snapshot(c, base):
    items = c.get(f"{base}/records", headers=V).json()["items"]
    return [(i["ref"], i["status"], i["updated_at"],
             tuple((e["action"], e["reason"]) for e in c.get(f"{base}/records/{i['id']}", headers=V).json()["history"]))
            for i in items]


def mr_id(c, ref):
    return next(i["id"] for i in c.get(f"{MR}/records", headers=V).json()["items"] if i["ref"] == ref)


def test_seed_eight_cases_with_merchant_fields_only(client):
    items = client.get(f"{MR}/records", headers=V).json()["items"]
    assert len(items) == 8
    assert {i["ref"] for i in items} == {f"MR-200{n}" for n in range(1, 9)}
    s = client.get(f"{MR}/summary", headers=V).json()
    assert s["counts"] == {"pending": 5, "approved": 2, "rejected": 1}
    assert s["overdue_pending"] is None and s["pending_amount_usd"] is None
    cfg = client.get(MR).json()
    keys = {c["key"] for c in cfg["columns"]} | {f["key"] for f in cfg["detail_fields"]}
    assert {"merchant_name", "business_category", "submitted_at", "owner", "missing_documents", "status"} <= keys
    assert not keys & {"customer", "amount_usd", "reason", "merchant"}
    assert cfg["features"] == {"overdue_filter": False, "value_summary": False}
    assert all("amount_usd" not in i and "customer" not in i for i in items)
    hist = client.get(f"{MR}/records/{mr_id(client, 'MR-2001')}", headers=V).json()["history"]
    assert hist[0]["actor"] == "Saltmarsh Ceramics Studio"


def test_overdue_filter_not_enabled_for_merchants(client):
    assert client.get(f"{MR}/records?overdue=true", headers=V).status_code == 400
    assert len(client.get(f"{RF}/records?overdue=true", headers=V).json()["items"]) == 4


def test_viewer_denied_and_nothing_written(client):
    before_rf = snapshot(client, RF)
    rid = mr_id(client, "MR-2003")
    r = client.post(f"{MR}/records/{rid}/decision", headers=V, json={"action": "approve", "reason": "looks fine"})
    assert r.status_code == 403
    rec = client.get(f"{MR}/records/{rid}", headers=V).json()
    assert rec["record"]["status"] == "pending"
    assert [e["action"] for e in rec["history"]] == ["submitted"]
    assert snapshot(client, RF) == before_rf


@pytest.mark.parametrize("reason", ["", "   ", "ok"])
def test_reason_required(client, reason):
    rid = mr_id(client, "MR-2004")
    r = client.post(f"{MR}/records/{rid}/decision", headers=R, json={"action": "reject", "reason": reason})
    assert r.status_code == 422
    assert client.get(f"{MR}/records/{rid}", headers=V).json()["record"]["status"] == "pending"


def test_decision_history_duplicate_and_refunds_untouched(client):
    before_rf = snapshot(client, RF)
    rf_summary = client.get(f"{RF}/summary", headers=V).json()
    rid = mr_id(client, "MR-2002")
    r = client.post(f"{MR}/records/{rid}/decision", headers=R,
                    json={"action": "approve", "reason": "All onboarding documents present."})
    assert r.status_code == 200
    last = r.json()["history"][-1]
    assert (last["action"], last["actor"], last["actor_role"], last["reason"], last["from_status"], last["to_status"]) == (
        "approve", "Priya Raman", "reviewer", "All onboarding documents present.", "pending", "approved")
    assert client.post(f"{MR}/records/{rid}/decision", headers=R,
                       json={"action": "reject", "reason": "changed mind"}).status_code == 409
    hist = client.get(f"{MR}/records/{rid}", headers=V).json()["history"]
    assert [e["action"] for e in hist] == ["submitted", "approve"]
    assert client.get(f"{MR}/summary", headers=V).json()["counts"]["approved"] == 3
    assert snapshot(client, RF) == before_rf
    assert client.get(f"{RF}/summary", headers=V).json() == rf_summary


def test_refund_decision_does_not_touch_merchants(client):
    before_mr = snapshot(client, MR)
    rid = client.get(f"{RF}/records?status=pending", headers=V).json()["items"][0]["id"]
    assert client.post(f"{RF}/records/{rid}/decision", headers=R,
                       json={"action": "reject", "reason": "Outside policy"}).status_code == 200
    assert snapshot(client, MR) == before_mr


def test_cross_tool_ids_and_search_are_scoped(client):
    rf_id = client.get(f"{RF}/records", headers=V).json()["items"][0]["id"]
    mr_ids = {i["id"] for i in client.get(f"{MR}/records", headers=V).json()["items"]}
    assert rf_id not in mr_ids
    assert client.get(f"{MR}/records/{rf_id}", headers=V).status_code == 404
    assert client.post(f"{MR}/records/{rf_id}/decision", headers=R,
                       json={"action": "approve", "reason": "cross tool"}).status_code == 404
    assert client.get(f"{MR}/records?q=skyward", headers=V).json()["items"] == []
    assert client.get(f"{RF}/records?q=saltmarsh", headers=V).json()["items"] == []
    assert [i["ref"] for i in client.get(f"{MR}/records?q=insurance", headers=V).json()["items"]] == ["MR-2003"]
    assert [i["ref"] for i in client.get(f"{MR}/records?q=kayak&status=pending", headers=V).json()["items"]] == ["MR-2003"]


def test_reset_is_per_tool(client):
    rid = mr_id(client, "MR-2005")
    client.post(f"{MR}/records/{rid}/decision", headers=R, json={"action": "reject", "reason": "Docs overdue"})
    rf_rid = client.get(f"{RF}/records?status=pending", headers=V).json()["items"][0]["id"]
    client.post(f"{RF}/records/{rf_rid}/decision", headers=R, json={"action": "approve", "reason": "Confirmed"})
    rf_after_decision = snapshot(client, RF)

    assert client.post("/api/demo/reset?tool=merchant_reviews").status_code == 200
    assert client.get(f"{MR}/summary", headers=V).json()["counts"] == {"pending": 5, "approved": 2, "rejected": 1}
    assert snapshot(client, RF) == rf_after_decision

    mr_after_reset = snapshot(client, MR)
    assert client.post("/api/demo/reset?tool=refunds").status_code == 200
    assert client.get(f"{RF}/summary", headers=V).json()["counts"]["pending"] == 7
    assert snapshot(client, MR) == mr_after_reset
