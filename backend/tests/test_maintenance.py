"""Maintenance & Repairs — plans, maintenance orders, repair orders lifecycle."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_maintenance_plan_and_order(client, auth_headers):
    p = await client.post("/api/v1/maintenance/plans", json={
        "name": "ყოველთვიური მოვლა", "interval_days": 30, "next_due_at": "2026-09-24",
    }, headers=auth_headers)
    assert p.status_code == 201, p.text
    plan_id = p.json()["data"]["id"]

    o = await client.post("/api/v1/maintenance/orders", json={
        "plan_id": plan_id, "asset_name": "წარმოების ხაზი 1",
        "maintenance_type": "preventive", "priority": "high", "cost_estimate": 150,
    }, headers=auth_headers)
    assert o.status_code == 201, o.text
    order_id = o.json()["data"]["id"]
    assert o.json()["data"]["order_number"].startswith("MO-")

    up = await client.patch(f"/api/v1/maintenance/orders/{order_id}", json={
        "status": "completed", "actual_cost": 120, "downtime_hours": 2, "resolution_notes": "გაკეთდა",
    }, headers=auth_headers)
    assert up.status_code == 200, up.text
    assert up.json()["data"]["status"] == "completed"

    lst = await client.get("/api/v1/maintenance/orders", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1


async def test_repair_order_lifecycle(client, auth_headers):
    r = await client.post("/api/v1/maintenance/repairs", json={
        "serial_number": "SN-12345", "issue_description": "ეკრანი არ მუშაობს", "estimated_cost": 80,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    repair_id = r.json()["data"]["id"]
    assert r.json()["data"]["repair_number"].startswith("RPR-")

    d = await client.patch(f"/api/v1/maintenance/repairs/{repair_id}", json={
        "status": "diagnosed", "diagnosis": "მატრიცა გაფუჭდა", "final_cost": 95,
    }, headers=auth_headers)
    assert d.status_code == 200, d.text
    assert d.json()["data"]["status"] == "diagnosed"

    c = await client.patch(f"/api/v1/maintenance/repairs/{repair_id}", json={"status": "completed"}, headers=auth_headers)
    assert c.status_code == 200
    assert c.json()["data"]["status"] == "completed"

    lst = await client.get("/api/v1/maintenance/repairs", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1
