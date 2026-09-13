"""CMMS 2.1 — plan triggers (interval/meter), auto-generated orders, plan parts,
part requests with stock + GL integration, photos, signatures, reminders."""
import uuid
from decimal import Decimal

import pytest

pytestmark = pytest.mark.asyncio


async def _make_part(client, auth_headers, **kw):
    body = {"part_code": kw.get("part_code", f"P-{uuid.uuid4().hex[:6]}"), "name": kw.get("name", "სათადარიგო ნაწილი"),
            "quantity_on_hand": kw.get("quantity_on_hand", 20), "unit_cost": kw.get("unit_cost", 12)}
    if kw.get("product_id"):
        body["product_id"] = str(kw["product_id"])
    r = await client.post("/api/v1/maintenance/parts", json=body, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def _make_asset(client, auth_headers):
    r = await client.post("/api/v1/maintenance/assets", json={"asset_code": f"AST-{uuid.uuid4().hex[:8]}", "name": f"აქტივი-{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def test_plan_interval_trigger_and_auto_generate_order(client, auth_headers):
    """interval_or_meter trigger: due when next_due_at is in the past; auto_generate creates a scheduled order."""
    asset_id = await _make_asset(client, auth_headers)
    body = {"name": "ინტერვალ გეგმა", "plan_type": "preventive", "interval_days": 30,
            "next_due_at": "2020-01-01", "auto_generate": True, "trigger_type": "interval"}
    if asset_id:
        body["asset_id"] = asset_id
    p = await client.post("/api/v1/maintenance/plans", json=body, headers=auth_headers)
    assert p.status_code == 201, p.text
    plan_id = p.json()["data"]["id"]
    assert p.json()["data"]["trigger_type"] == "interval"

    ev = await client.post(f"/api/v1/maintenance/plans/{plan_id}/evaluate", headers=auth_headers)
    assert ev.status_code == 200, ev.text
    data = ev.json()["data"]
    assert data["due"] is True
    assert "interval" in data["reasons"]
    assert data["generated_order_id"] is not None
    assert data["order_number"].startswith("MO-")

    lst = await client.get("/api/v1/maintenance/orders", headers=auth_headers)
    assert lst.status_code == 200
    assert any(o["plan_id"] == plan_id for o in lst.json()["data"])


async def test_plan_meter_trigger(client, auth_headers):
    """meter trigger: due only when the meter current_value crosses the threshold."""
    asset_id = await _make_asset(client, auth_headers)
    m = await client.post("/api/v1/maintenance/meters", json={"asset_id": asset_id, "name": "საათები", "unit": "სთ",
                                                              "current_value": 0}, headers=auth_headers)
    assert m.status_code == 201, m.text
    meter_id = m.json()["data"]["id"]

    p = await client.post("/api/v1/maintenance/plans", json={"name": "მრიცხველ გეგმა", "plan_type": "preventive",
                                                             "trigger_type": "meter", "meter_id": meter_id,
                                                             "meter_threshold": 500, "auto_generate": True}, headers=auth_headers)
    assert p.status_code == 201, p.text
    plan_id = p.json()["data"]["id"]

    # not due yet
    ev1 = await client.post(f"/api/v1/maintenance/plans/{plan_id}/evaluate", headers=auth_headers)
    assert ev1.json()["data"]["due"] is False

    # cross threshold
    up = await client.patch(f"/api/v1/maintenance/meters/{meter_id}", json={"current_value": 520}, headers=auth_headers)
    assert up.status_code == 200, up.text

    ev2 = await client.post(f"/api/v1/maintenance/plans/{plan_id}/evaluate", headers=auth_headers)
    data = ev2.json()["data"]
    assert data["due"] is True
    assert any(r.startswith("meter(") for r in data["reasons"])
    assert data["generated_order_id"] is not None
    assert data["meter_value"] == 520.0


async def test_plan_parts_and_generate_order(client, auth_headers, db_session, test_company):
    """add_plan_part + generate-order creates the order and requested part links."""
    from app.models.product import Product
    product = Product(company_id=test_company.id, name="გეგმის პროდუქტი", sku=f"SKU-{uuid.uuid4().hex[:6]}", sale_price=25, current_stock=10)
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    product_id = product.id

    part_id = await _make_part(client, auth_headers, product_id=product_id)
    p = await client.post("/api/v1/maintenance/plans", json={"name": "პარტს გეგმა", "plan_type": "preventive",
                                                             "interval_days": 45}, headers=auth_headers)
    assert p.status_code == 201, p.text
    plan_id = p.json()["data"]["id"]

    ap = await client.post(f"/api/v1/maintenance/plans/{plan_id}/parts", json={"product_id": str(product_id), "quantity": 3}, headers=auth_headers)
    assert ap.status_code == 201, ap.text

    parts = await client.get(f"/api/v1/maintenance/plans/{plan_id}/parts", headers=auth_headers)
    assert parts.status_code == 200
    assert len(parts.json()["data"]) == 1

    go = await client.post(f"/api/v1/maintenance/plans/{plan_id}/generate-order", headers=auth_headers)
    assert go.status_code == 201, go.text
    assert go.json()["data"]["part_requests"] == 1
    order_id = go.json()["data"]["id"]

    reqs = await client.get(f"/api/v1/maintenance/part-requests", headers=auth_headers)
    assert reqs.status_code == 200
    assert any(r["order_id"] == order_id for r in reqs.json()["data"])


async def test_part_issue_stock_gl_and_product_sync(client, auth_headers, db_session, test_company, test_admin):
    """Issuing a part decrements quantity_on_hand, writes an inventory movement,
    decrements product.current_stock and posts a balanced GL entry (5100/1200)."""
    from app.models.product import Product
    product = Product(company_id=test_company.id, name="საწყობის პროდუქტი", sku=f"SKU-{uuid.uuid4().hex[:6]}", sale_price=25, current_stock=10)
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    product_id = product.id

    r = await client.post("/api/v1/maintenance/parts", json={"part_code": f"PC-{uuid.uuid4().hex[:6]}", "name": "სათადარიგო",
                                                             "quantity_on_hand": 10, "unit_cost": 8, "product_id": str(product_id)}, headers=auth_headers)
    assert r.status_code == 201, r.text
    part_id = r.json()["data"]["id"]

    o = await client.post("/api/v1/maintenance/orders", json={"asset_name": "აქტივი", "maintenance_type": "corrective",
                                                              "priority": "high"}, headers=auth_headers)
    assert o.status_code == 201, o.text
    order_id = o.json()["data"]["id"]

    req = await client.post("/api/v1/maintenance/part-requests", json={"part_id": part_id, "order_id": order_id, "quantity": 3}, headers=auth_headers)
    assert req.status_code == 201, req.text
    req_id = req.json()["data"]["id"]

    issue = await client.patch(f"/api/v1/maintenance/part-requests/{req_id}", json={"status": "issued"}, headers=auth_headers)
    assert issue.status_code == 200, issue.text
    issue_data = issue.json()["data"]
    assert issue_data["status"] == "issued"
    assert float(issue_data.get("issue_value", 0)) == pytest.approx(24.0)  # 3 × 8

    # stock decremented
    parts = await client.get("/api/v1/maintenance/parts", headers=auth_headers)
    part = next(p for p in parts.json()["data"] if p["id"] == part_id)
    assert float(part["quantity_on_hand"]) == 7.0

    # product.current_stock decremented
    await db_session.refresh(product)
    assert product.current_stock == 7.0

    # balanced GL entry posted
    from app.models.gl import JournalEntry, JournalEntryLine
    gl = (await db_session.execute(
        __import__("sqlalchemy").select(JournalEntry).where(JournalEntry.reference_type == "maintenance_part_issue",
                                                            JournalEntry.reference_id == req_id)
    )).scalar_one_or_none()
    assert gl is not None, "GL entry not found"
    lines = (await db_session.execute(
        __import__("sqlalchemy").select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == gl.id)
    )).scalars().all()
    debit_total = sum(l.debit_amount for l in lines)
    credit_total = sum(l.credit_amount for l in lines)
    assert abs(debit_total - credit_total) < Decimal("0.01"), "GL not balanced"
    assert debit_total == pytest.approx(Decimal("24.0")), "GL amount mismatch"
    # 5100 Dr / 1200 Cr
    from app.models.gl import GLAccount
    rows = (await db_session.execute(
        __import__("sqlalchemy").select(GLAccount.code, JournalEntryLine.debit_amount, JournalEntryLine.credit_amount)
        .join(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .where(JournalEntryLine.journal_entry_id == gl.id)
    )).all()
    row_map = {code: (d, c) for code, d, c in rows}
    assert "5100" in row_map and row_map["5100"][0] == 24, f"5100 Dr missing: {row_map}"
    assert "1200" in row_map and row_map["1200"][1] == 24, f"1200 Cr missing: {row_map}"


async def test_part_issue_insufficient_stock_rejected(client, auth_headers):
    part_id = await _make_part(client, auth_headers, quantity_on_hand=2, unit_cost=5)
    o = await client.post("/api/v1/maintenance/orders", json={"asset_name": "აქტივი-2"}, headers=auth_headers)
    order_id = o.json()["data"]["id"]
    req = await client.post("/api/v1/maintenance/part-requests", json={"part_id": part_id, "order_id": order_id, "quantity": 5}, headers=auth_headers)
    assert req.status_code == 201
    req_id = req.json()["data"]["id"]

    issue = await client.patch(f"/api/v1/maintenance/part-requests/{req_id}", json={"status": "issued"}, headers=auth_headers)
    assert issue.status_code == 409, issue.text


async def test_photos_and_signature_flow(client, auth_headers):
    """Technician mobile flow: attach before/after photos, capture signature."""
    o = await client.post("/api/v1/maintenance/orders", json={"asset_name": "აქტივი-3"}, headers=auth_headers)
    assert o.status_code == 201
    order_id = o.json()["data"]["id"]

    ph1 = await client.post(f"/api/v1/maintenance/orders/{order_id}/photos", json={"phase": "before", "url": "https://cdn.x/b.jpg"}, headers=auth_headers)
    assert ph1.status_code == 201, ph1.text
    ph2 = await client.post(f"/api/v1/maintenance/orders/{order_id}/photos", json={"phase": "after", "url": "https://cdn.x/a.jpg"}, headers=auth_headers)
    assert ph2.status_code == 201, ph2.text

    photos = await client.get(f"/api/v1/maintenance/orders/{order_id}/photos", headers=auth_headers)
    assert photos.status_code == 200
    assert len(photos.json()["data"]) == 2
    assert {ph["phase"] for ph in photos.json()["data"]} == {"before", "after"}

    sig = await client.post(f"/api/v1/maintenance/orders/{order_id}/signature", json={"signature_data": "data:image/png;base64,AAA"}, headers=auth_headers)
    assert sig.status_code == 201, sig.text

    sig2 = await client.post(f"/api/v1/maintenance/orders/{order_id}/signature", json={"signature_data": "data:image/png;base64,BBB"}, headers=auth_headers)
    assert sig2.status_code == 201  # update path
    assert sig2.json()["data"].get("updated") is True

    gs = await client.get(f"/api/v1/maintenance/orders/{order_id}/signature", headers=auth_headers)
    assert gs.status_code == 200
    assert gs.json()["data"]["signature_data"] == "data:image/png;base64,BBB"


async def test_reminders_list(client, auth_headers):
    """auto-generated order creates a reminder entry; /reminders returns pending ones."""
    p = await client.post("/api/v1/maintenance/plans", json={"name": "რემინდერ გეგმა", "plan_type": "preventive",
                                                             "interval_days": 60, "next_due_at": "2020-01-01",
                                                             "auto_generate": True, "reminder_days_before": 3,
                                                             "trigger_type": "interval"}, headers=auth_headers)
    assert p.status_code == 201, p.text
    plan_id = p.json()["data"]["id"]

    ev = await client.post(f"/api/v1/maintenance/plans/{plan_id}/evaluate", headers=auth_headers)
    assert ev.json()["data"]["generated_order_id"] is not None

    rem = await client.get("/api/v1/maintenance/reminders", headers=auth_headers)
    assert rem.status_code == 200
    assert len(rem.json()["data"]) >= 1
    assert rem.json()["data"][0]["plan_id"] == plan_id
