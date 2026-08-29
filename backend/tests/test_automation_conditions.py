"""Automation engine: conditions evaluation, new triggers/actions, run stats."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_automation_conditions_gate_execution(client, auth_headers):
    """Rule with conditions runs only when the payload matches."""
    resp = await client.post("/api/v1/automations/", json={
        "name": "დიდი შეკვეთა", "trigger": "order_created",
        "conditions": [{"field": "amount", "op": "gte", "value": 1000}],
        "action": "send_email", "target": "admin@demo.ge",
        "payload": {"subject": "დიდი შეკვეთა!"},
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    # amount 500 → condition fails → skipped
    small = await client.post("/api/v1/automations/trigger/order_created", json={
        "amount": 500, "entity": "order", "entity_id": "x",
    }, headers=auth_headers)
    assert small.status_code == 200
    assert small.json()["data"]["executed"] == []
    assert small.json()["data"]["skipped_conditions"] == 1

    # amount 2500 → condition passes → executed
    big = await client.post("/api/v1/automations/trigger/order_created", json={
        "amount": 2500, "entity": "order", "entity_id": "y",
    }, headers=auth_headers)
    assert big.status_code == 200
    assert len(big.json()["data"]["executed"]) == 1
    assert big.json()["data"]["skipped_conditions"] == 0

    # run_count tracked
    lst = await client.get("/api/v1/automations/", headers=auth_headers)
    rule = next(r for r in lst.json()["data"] if r["name"] == "დიდი შეკვეთა")
    assert rule["run_count"] == 1
    assert rule["last_run_at"] is not None


async def test_automation_meta_vocabulary(client, auth_headers):
    meta = await client.get("/api/v1/automations/meta", headers=auth_headers)
    assert meta.status_code == 200
    data = meta.json()["data"]
    assert "order_created" in data["triggers"]
    assert "order_confirmed" in data["triggers"]
    assert "supplier_invoice_received" in data["triggers"]
    assert "update_status" in data["actions"]
    assert "webhook" in data["actions"]
    assert "gte" in data["operators"]
    assert "contains" in data["operators"]


async def test_automation_unknown_trigger_rejected(client, auth_headers):
    resp = await client.post("/api/v1/automations/trigger/not_a_trigger", json={}, headers=auth_headers)
    assert resp.status_code == 422

    resp2 = await client.post("/api/v1/automations/", json={
        "name": "x", "trigger": "nope", "action": "notify",
    }, headers=auth_headers)
    assert resp2.status_code == 422
