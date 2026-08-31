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



# ── CMMS Phase 3: parts & tools ──────────────────────────────────────────────

async def test_part_and_part_request_flow(client, auth_headers):
    # create part
    r = await client.post("/api/v1/maintenance/parts", headers=auth_headers, json={
        "part_code": "BRG-001",
        "name": "საკისარი 6204",
        "category": "საკისრები",
        "quantity_on_hand": "10",
        "reorder_level": "3",
        "unit_cost": "12.50",
        "location": "A-1",
        "supplier": "ტექნოიმპორტი",
    })
    assert r.status_code == 201, r.text
    part = r.json()["data"]
    assert part["part_code"] == "BRG-001"
    assert part["is_low"] is False

    # duplicate code rejected
    r2 = await client.post("/api/v1/maintenance/parts", headers=auth_headers, json={
        "part_code": "BRG-001", "name": "დუბლიკატი",
    })
    assert r2.status_code == 409

    # low-stock flag
    r3 = await client.patch(f"/api/v1/maintenance/parts/{part['id']}", headers=auth_headers, json={"quantity_on_hand": "2"})
    assert r3.status_code == 200
    assert r3.json()["data"]["is_low"] is True

    # part request
    r4 = await client.post("/api/v1/maintenance/part-requests", headers=auth_headers, json={
        "part_id": part["id"], "quantity": "2",
    })
    assert r4.status_code == 201, r4.text
    req = r4.json()["data"]
    assert req["status"] == "requested"
    assert req["part_name"] == "საკისარი 6204"

    # issue → decrements stock
    r5 = await client.patch(f"/api/v1/maintenance/part-requests/{req['id']}", headers=auth_headers, json={"status": "issued"})
    assert r5.status_code == 200, r5.text
    assert r5.json()["data"]["issued_at"] is not None

    r6 = await client.get("/api/v1/maintenance/parts", headers=auth_headers)
    updated = next(p for p in r6.json()["data"] if p["id"] == part["id"])
    assert updated["quantity_on_hand"] == "0.00"

    # list with low filter
    r7 = await client.get("/api/v1/maintenance/parts?low=true", headers=auth_headers)
    assert all(p["is_low"] for p in r7.json()["data"])


async def test_tool_issue_and_return_flow(client, auth_headers):
    # create technician
    r = await client.post("/api/v1/maintenance/technicians", headers=auth_headers, json={
        "name": "გიორგი მეფარიშვილი", "specialization": "ელექტრიკოსი", "phone": "599111222", "hourly_rate": "25",
    })
    tech = r.json()["data"]

    # create tool
    r2 = await client.post("/api/v1/maintenance/tools", headers=auth_headers, json={
        "tool_code": "MUL-001", "name": "მულტიმეტრი", "category": "ელექტრო", "quantity": 2,
    })
    assert r2.status_code == 201, r2.text
    tool = r2.json()["data"]
    assert tool["available"] == 2

    # issue to technician
    r3 = await client.post("/api/v1/maintenance/tool-issues", headers=auth_headers, json={
        "tool_id": tool["id"], "technician_id": tech["id"],
    })
    assert r3.status_code == 201, r3.text
    issue = r3.json()["data"]
    assert issue["tool_name"] == "მულტიმეტრი"
    assert issue["technician_name"] == "გიორგი მეფარიშვილი"

    # available decremented
    r4 = await client.get("/api/v1/maintenance/tools", headers=auth_headers)
    updated = next(t for t in r4.json()["data"] if t["id"] == tool["id"])
    assert updated["available"] == 1

    # open issues list
    r5 = await client.get("/api/v1/maintenance/tool-issues?open_only=true", headers=auth_headers)
    assert len(r5.json()["data"]) == 1

    # return
    r6 = await client.post(f"/api/v1/maintenance/tool-issues/{issue['id']}/return", headers=auth_headers)
    assert r6.status_code == 200, r6.text
    assert r6.json()["data"]["returned_at"] is not None

    r7 = await client.get("/api/v1/maintenance/tools", headers=auth_headers)
    updated2 = next(t for t in r7.json()["data"] if t["id"] == tool["id"])
    assert updated2["available"] == 2
    assert updated2["status"] == "available"



# ── CMMS Phase 4: planning & safety ───────────────────────────────────────────

async def test_safety_instruction_and_checklist(client, auth_headers):
    # safety instruction
    r = await client.post("/api/v1/maintenance/safety-instructions", headers=auth_headers, json={
        "title": "ელექტრო სამუშაოების უსაფრთხოება",
        "category": "ელექტრო",
        "content": "გამორთე დენი სამუშაოს დაწყებამდე",
        "is_mandatory": True,
    })
    assert r.status_code == 201, r.text
    assert r.json()["data"]["is_mandatory"] is True

    r2 = await client.get("/api/v1/maintenance/safety-instructions", headers=auth_headers)
    assert len(r2.json()["data"]) == 1

    # checklist with items
    r3 = await client.post("/api/v1/maintenance/checklists", headers=auth_headers, json={
        "name": "ყოველდღიური შემოწმება",
        "category": "ინსპექცია",
        "is_mandatory": True,
        "items": ["შეამოწმე ზეთის დონე", "შეამოწმე წნევა", "შეამოწმე გაჟონვა"],
    })
    assert r3.status_code == 201, r3.text
    assert r3.json()["data"]["item_count"] == 3

    r4 = await client.get("/api/v1/maintenance/checklists", headers=auth_headers)
    assert r4.json()["data"][0]["item_count"] == 3


async def test_work_permit_and_incident_lifecycle(client, auth_headers):
    # work permit
    r = await client.post("/api/v1/maintenance/work-permits", headers=auth_headers, json={
        "permit_number": "WP-001",
        "work_type": "შედუღება",
        "location": "ცეხი 2",
        "risk_level": "high",
    })
    assert r.status_code == 201, r.text
    permit = r.json()["data"]
    assert permit["status"] == "draft"

    # approve → issued_at set
    r2 = await client.patch(f"/api/v1/maintenance/work-permits/{permit['id']}", headers=auth_headers, json={"status": "approved"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["status"] == "approved"
    assert r2.json()["data"]["issued_at"] is not None

    # duplicate permit number rejected
    r3 = await client.post("/api/v1/maintenance/work-permits", headers=auth_headers, json={
        "permit_number": "WP-001", "work_type": "შედუღება",
    })
    assert r3.status_code == 409

    # incident
    r4 = await client.post("/api/v1/maintenance/incidents", headers=auth_headers, json={
        "incident_number": "INC-001",
        "title": "მცირე დამწვრობა",
        "severity": "medium",
        "description": "ტექნიკოსმა ხელი დაიწვა",
    })
    assert r4.status_code == 201, r4.text
    incident = r4.json()["data"]
    assert incident["status"] == "open"

    # resolve with root cause
    r5 = await client.patch(f"/api/v1/maintenance/incidents/{incident['id']}", headers=auth_headers, json={
        "status": "resolved",
        "root_cause": "დამცავი ხელთათმანის გარეშე მუშაობა",
        "corrective_action": "სავალდებულო ხელთათმანები",
    })
    assert r5.status_code == 200, r5.text
    assert r5.json()["data"]["status"] == "resolved"
    assert r5.json()["data"]["root_cause"] is not None

    # filter by status
    r6 = await client.get("/api/v1/maintenance/incidents?status=resolved", headers=auth_headers)
    assert len(r6.json()["data"]) == 1



# ── CMMS Phase 5: costs & analytics ──────────────────────────────────────────

async def test_cost_record_and_budget(client, auth_headers):
    # create asset first
    r = await client.post("/api/v1/maintenance/assets", headers=auth_headers, json={
        "asset_code": "CMP-001", "name": "კომპრესორი 1", "category_id": None, "location_id": None,
    })
    assert r.status_code == 201, r.text
    asset = r.json()["data"]

    # cost record
    r2 = await client.post("/api/v1/maintenance/cost-records", headers=auth_headers, json={
        "asset_id": asset["id"], "cost_type": "parts", "description": "ფილტრი", "amount": "45.50",
    })
    assert r2.status_code == 201, r2.text
    assert r2.json()["data"]["asset_name"] == "კომპრესორი 1"

    r3 = await client.post("/api/v1/maintenance/cost-records", headers=auth_headers, json={
        "asset_id": asset["id"], "cost_type": "labor", "description": "მონტაჟი", "amount": "120.00",
    })
    assert r3.status_code == 201

    # budget
    r4 = await client.post("/api/v1/maintenance/budgets", headers=auth_headers, json={
        "name": "2026 წლის ბიუჯეტი",
        "period_start": "2026-01-01",
        "period_end": "2026-12-31",
        "planned_amount": "1000.00",
    })
    assert r4.status_code == 201, r4.text
    budget = r4.json()["data"]
    assert budget["spent_amount"] == "0"

    # summary
    r5 = await client.get("/api/v1/maintenance/analytics/summary", headers=auth_headers)
    assert r5.status_code == 200, r5.text
    s = r5.json()["data"]
    assert s["total_cost"] == "165.50"
    assert s["parts_cost"] == "45.50"
    assert s["labor_cost"] == "120.00"
    assert s["total_assets"] == 1
    assert s["budget_utilization"] == "16.55"


async def test_reliability_metric(client, auth_headers):
    r = await client.post("/api/v1/maintenance/assets", headers=auth_headers, json={
        "asset_code": "PMP-001", "name": "ტუმბო A", "category_id": None, "location_id": None,
    })
    asset = r.json()["data"]

    r2 = await client.post("/api/v1/maintenance/reliability-metrics", headers=auth_headers, json={
        "asset_id": asset["id"],
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "downtime_hours": "8.5",
        "failures": 2,
        "mttr_hours": "4.25",
        "mtbf_hours": "360.0",
    })
    assert r2.status_code == 201, r2.text
    m = r2.json()["data"]
    assert m["asset_name"] == "ტუმბო A"
    assert m["failures"] == 2

    # filter by asset
    r3 = await client.get(f"/api/v1/maintenance/reliability-metrics?asset_id={asset['id']}", headers=auth_headers)
    assert len(r3.json()["data"]) == 1



# ── CMMS Phase 6: configuration ───────────────────────────────────────────────

async def test_work_type_and_priority_config(client, auth_headers):
    # work type
    r = await client.post("/api/v1/maintenance/config/work-types", headers=auth_headers, json={
        "name": "პრევენციული მოვლა", "code": "PM",
    })
    assert r.status_code == 201, r.text
    assert r.json()["data"]["code"] == "PM"

    # duplicate rejected
    r2 = await client.post("/api/v1/maintenance/config/work-types", headers=auth_headers, json={
        "name": "პრევენციული მოვლა",
    })
    assert r2.status_code == 409

    # priority
    r3 = await client.post("/api/v1/maintenance/config/priorities", headers=auth_headers, json={
        "name": "მაღალი", "level": 1, "color": "red",
    })
    assert r3.status_code == 201, r3.text
    assert r3.json()["data"]["level"] == 1

    r4 = await client.get("/api/v1/maintenance/config/priorities", headers=auth_headers)
    assert len(r4.json()["data"]) == 1


async def test_status_and_numbering_config(client, auth_headers):
    # status config
    r = await client.post("/api/v1/maintenance/config/statuses", headers=auth_headers, json={
        "name": "დასრულებული", "code": "completed", "is_closed": True,
    })
    assert r.status_code == 201, r.text
    assert r.json()["data"]["is_closed"] is True

    # duplicate code rejected
    r2 = await client.post("/api/v1/maintenance/config/statuses", headers=auth_headers, json={
        "name": "დასრულებული 2", "code": "completed",
    })
    assert r2.status_code == 409

    # numbering
    r3 = await client.post("/api/v1/maintenance/config/numbering", headers=auth_headers, json={
        "entity": "order", "prefix": "WO", "next_number": 100,
    })
    assert r3.status_code == 201, r3.text
    assert r3.json()["data"]["next_number"] == 100

    # duplicate entity rejected
    r4 = await client.post("/api/v1/maintenance/config/numbering", headers=auth_headers, json={
        "entity": "order", "prefix": "WO2",
    })
    assert r4.status_code == 409

    r5 = await client.get("/api/v1/maintenance/config/numbering", headers=auth_headers)
    assert len(r5.json()["data"]) == 1
