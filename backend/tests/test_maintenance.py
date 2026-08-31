"""Maintenance & Repairs — plans, maintenance orders, repair orders lifecycle."""
import uuid
from decimal import Decimal

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


# ── CMMS Phase 1: assets, categories, locations, meters, requests ───────────

async def test_asset_category_location_and_asset_crud(client, auth_headers):
    cat = await client.post("/api/v1/maintenance/asset-categories", json={"name": "ტუმბოები"}, headers=auth_headers)
    assert cat.status_code == 201, cat.text
    cat_id = cat.json()["data"]["id"]

    loc = await client.post("/api/v1/maintenance/locations", json={"name": "ცეხი 1"}, headers=auth_headers)
    assert loc.status_code == 201, loc.text
    loc_id = loc.json()["data"]["id"]

    a = await client.post("/api/v1/maintenance/assets", json={
        "asset_code": "AST-001", "name": "ცენტრიდანული ტუმბო", "category_id": cat_id,
        "location_id": loc_id, "manufacturer": "Grundfos", "serial_number": "SN-A1",
        "purchase_cost": 5000, "warranty_until": "2028-01-01",
    }, headers=auth_headers)
    assert a.status_code == 201, a.text
    asset = a.json()["data"]
    assert asset["asset_code"] == "AST-001"
    assert asset["category_name"] == "ტუმბოები"
    assert asset["location_name"] == "ცეხი 1"

    # Duplicate code rejected
    dup = await client.post("/api/v1/maintenance/assets", json={
        "asset_code": "AST-001", "name": "დუბლიკატი",
    }, headers=auth_headers)
    assert dup.status_code == 409

    # Update + list with search
    up = await client.patch(f"/api/v1/maintenance/assets/{asset['id']}", json={"status": "maintenance"}, headers=auth_headers)
    assert up.status_code == 200, up.text
    assert up.json()["data"]["status"] == "maintenance"

    lst = await client.get("/api/v1/maintenance/assets?search=ტუმბო", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    # Delete
    dl = await client.delete(f"/api/v1/maintenance/assets/{asset['id']}", headers=auth_headers)
    assert dl.status_code == 200


async def test_meter_create_and_update(client, auth_headers):
    a = await client.post("/api/v1/maintenance/assets", json={
        "asset_code": "AST-M1", "name": "კომპრესორი",
    }, headers=auth_headers)
    asset_id = a.json()["data"]["id"]

    m = await client.post("/api/v1/maintenance/meters", json={
        "asset_id": asset_id, "name": "მუშაობის საათები", "unit": "hours", "current_value": 1200,
    }, headers=auth_headers)
    assert m.status_code == 201, m.text
    meter_id = m.json()["data"]["id"]
    assert m.json()["data"]["asset_name"] == "კომპრესორი"

    up = await client.patch(f"/api/v1/maintenance/meters/{meter_id}", json={"current_value": 1300}, headers=auth_headers)
    assert up.status_code == 200, up.text
    assert Decimal(str(up.json()["data"]["current_value"])) == Decimal("1300.00")
    assert up.json()["data"]["last_reading_at"] is not None

    lst = await client.get(f"/api/v1/maintenance/meters?asset_id={asset_id}", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1


async def test_maintenance_request_lifecycle(client, auth_headers):
    a = await client.post("/api/v1/maintenance/assets", json={
        "asset_code": "AST-R1", "name": "ლენტური კონვეიერი",
    }, headers=auth_headers)
    asset_id = a.json()["data"]["id"]

    r = await client.post("/api/v1/maintenance/requests", json={
        "asset_id": asset_id, "title": "უცნაური ხმა ძრავში", "priority": "high",
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    req = r.json()["data"]
    assert req["request_number"].startswith("MR-")
    assert req["asset_name"] == "ლენტური კონვეიერი"
    assert req["status"] == "open"

    up = await client.patch(f"/api/v1/maintenance/requests/{req['id']}", json={"status": "in_progress"}, headers=auth_headers)
    assert up.status_code == 200, up.text
    assert up.json()["data"]["status"] == "in_progress"

    done = await client.patch(f"/api/v1/maintenance/requests/{req['id']}", json={"status": "completed"}, headers=auth_headers)
    assert done.status_code == 200
    assert done.json()["data"]["completed_at"] is not None

    lst = await client.get("/api/v1/maintenance/requests?status=completed", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1


async def test_plan_type_and_order_emergency(client, auth_headers):
    p = await client.post("/api/v1/maintenance/plans", json={
        "name": "ინსპექტირება", "plan_type": "inspection", "interval_days": 90,
    }, headers=auth_headers)
    assert p.status_code == 201, p.text
    assert p.json()["data"]["plan_type"] == "inspection"

    o = await client.post("/api/v1/maintenance/orders", json={
        "asset_name": "გადაუდებელი", "maintenance_type": "emergency", "is_emergency": True, "priority": "urgent",
    }, headers=auth_headers)
    assert o.status_code == 201, o.text
    assert o.json()["data"]["is_emergency"] is True

    lst = await client.get("/api/v1/maintenance/orders?emergency=true", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1


# ── CMMS Phase 2: resources — technicians, teams, contractors, SLA, certificates ──

async def test_technician_and_team_crud(client, auth_headers):
    t = await client.post("/api/v1/maintenance/technicians", json={
        "name": "გიორგი მექანიკოსი", "specialization": "ელექტრო", "hourly_rate": 45,
    }, headers=auth_headers)
    assert t.status_code == 201, t.text
    tech_id = t.json()["data"]["id"]
    assert t.json()["data"]["specialization"] == "ელექტრო"

    team = await client.post("/api/v1/maintenance/teams", json={
        "name": "ელექტრო გუნდი", "leader_id": tech_id,
    }, headers=auth_headers)
    assert team.status_code == 201, team.text
    team_id = team.json()["data"]["id"]

    member = await client.post(f"/api/v1/maintenance/teams/{team_id}/members?technician_id={tech_id}", headers=auth_headers)
    assert member.status_code == 201, member.text

    lst = await client.get("/api/v1/maintenance/teams", headers=auth_headers)
    assert lst.status_code == 200
    found = next(x for x in lst.json()["data"] if x["id"] == team_id)
    assert found["member_count"] == 1

    up = await client.patch(f"/api/v1/maintenance/technicians/{tech_id}", json={"hourly_rate": 50}, headers=auth_headers)
    assert up.status_code == 200, up.text
    assert Decimal(str(up.json()["data"]["hourly_rate"])) == Decimal("50.00")


async def test_contractor_sla_and_certificate(client, auth_headers):
    c = await client.post("/api/v1/maintenance/contractors", json={
        "name": "შპს სერვისი", "contact_person": "ნინო", "specialization": "HVAC", "hourly_rate": 60,
    }, headers=auth_headers)
    assert c.status_code == 201, c.text
    contractor_id = c.json()["data"]["id"]

    sla = await client.post("/api/v1/maintenance/slas", json={
        "name": "კრიტიკული SLA", "priority": "high", "response_hours": 2, "resolution_hours": 8, "contractor_id": contractor_id,
    }, headers=auth_headers)
    assert sla.status_code == 201, sla.text
    assert sla.json()["data"]["contractor_name"] == "შპს სერვისი"

    t = await client.post("/api/v1/maintenance/technicians", json={"name": "თეკლა ტექნიკოსი"}, headers=auth_headers)
    tech_id = t.json()["data"]["id"]

    cert = await client.post("/api/v1/maintenance/certificates", json={
        "technician_id": tech_id, "name": "ელექტროუსაფრთხოება", "expiry_date": "2027-01-01",
    }, headers=auth_headers)
    assert cert.status_code == 201, cert.text
    assert cert.json()["data"]["technician_name"] == "თეკლა ტექნიკოსი"

    lst = await client.get("/api/v1/maintenance/certificates", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1
