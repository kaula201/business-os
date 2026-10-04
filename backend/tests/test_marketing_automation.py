"""Marketing automation — campaign send (sandbox), stats, automation triggers."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _create_campaign(client, auth_headers, **overrides) -> dict:
    payload = {
        "name": f"Campaign-{uuid.uuid4().hex[:6]}",
        "subject": "სატესტო კამპანია",
        "body": "გამარჯობა! ეს არის ტესტური შეთავაზება.",
        "audience": {"emails": ["a@test.ge", "b@test.ge"]},
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/email-campaigns/", json=payload, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_campaign_create_with_body(client, auth_headers):
    data = await _create_campaign(client, auth_headers)
    assert data["status"] == "draft"
    assert data["body"] == "გამარჯობა! ეს არის ტესტური შეთავაზება."


async def test_campaign_send_sandbox_and_stats(client, auth_headers):
    data = await _create_campaign(client, auth_headers)
    camp_id = data["id"]

    resp = await client.post(f"/api/v1/email-campaigns/{camp_id}/send", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    send = resp.json()["data"]
    assert send["sent"] == 2
    assert send["mode"] == "sandbox"  # SMTP არ არის კონფიგურირებული ტესტ გარემოში

    # Double send rejected
    again = await client.post(f"/api/v1/email-campaigns/{camp_id}/send", headers=auth_headers)
    assert again.status_code == 400

    stats = await client.get(f"/api/v1/email-campaigns/{camp_id}/stats", headers=auth_headers)
    assert stats.status_code == 200, stats.text
    s = stats.json()["data"]
    assert s["sent"] == 2
    assert s["open_rate"] == 0

    events = await client.get("/api/v1/email-events/?campaign_id=" + camp_id, headers=auth_headers)
    assert events.status_code == 200
    assert events.json()["data"]["total"] == 2


async def test_campaign_send_with_client_ids(client, auth_headers):
    # Create two clients with emails
    client_ids = []
    for i in range(2):
        c = await client.post("/api/v1/clients/", json={
            "client_type": "legal",
            "name": f"Client-{uuid.uuid4().hex[:6]}",
            "identification_code": f"{uuid.uuid4().int % 900000000 + 100000000}",
            "email": f"c{i}@test.ge",
        }, headers=auth_headers)
        assert c.status_code in (200, 201), c.text
        client_ids.append(c.json()["data"]["id"])

    data = await _create_campaign(client, auth_headers, audience={"client_ids": client_ids})
    resp = await client.post(f"/api/v1/email-campaigns/{data['id']}/send", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["sent"] == 2


async def test_automation_trigger_runs_rules(client, auth_headers):
    # notify rule + create_task rule + send_email rule
    r1 = await client.post("/api/v1/automations/", json={
        "name": "ინვოისის შეტყობინება", "trigger": "invoice_issued", "action": "notify",
        "target": "admin@test.ge",
    }, headers=auth_headers)
    assert r1.status_code == 201, r1.text

    r2 = await client.post("/api/v1/automations/", json={
        "name": "დავალების შექმნა", "trigger": "invoice_issued", "action": "create_task",
    }, headers=auth_headers)
    assert r2.status_code == 201, r2.text

    r3 = await client.post("/api/v1/automations/", json={
        "name": "კლიენტის მეილი", "trigger": "client_created", "action": "send_email",
        "target": "marketing@test.ge",
    }, headers=auth_headers)
    assert r3.status_code == 201, r3.text

    fire = await client.post("/api/v1/automations/trigger/invoice_issued", json={
        "entity": "invoice", "entity_id": str(uuid.uuid4()), "details": "ინვოისი 1000₾",
    }, headers=auth_headers)
    assert fire.status_code == 200, fire.text
    fired = fire.json()["data"]
    assert fired["matched_rules"] == 2
    assert len(fired["executed"]) == 2

    # Tasks were created
    tasks = await client.get("/api/v1/tasks/", headers=auth_headers)
    assert tasks.status_code == 200, tasks.text
    task_items = tasks.json()["data"]
    if isinstance(task_items, dict):  # paginated
        task_items = task_items.get("items", [])
    assert any(t["title"].startswith("[ავტომატური]") for t in task_items)

    # Unknown trigger rejected
    bad = await client.post("/api/v1/automations/trigger/nope", json={}, headers=auth_headers)
    assert bad.status_code == 422
