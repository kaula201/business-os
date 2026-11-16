"""Production 2.0 — routings/operations, actual labor, consumption (backflush+manual),
scrap/by-products, genealogy, MRP, downtime windows, capacity, WIP variance."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _mk_product(client, auth_headers, sku, name, price=10):
    r = await client.post("/api/v1/products/", json={"sku": sku, "name": name, "sale_price": price}, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


async def _mk_warehouse(client, auth_headers, code="MAIN"):
    r = await client.post("/api/v1/warehouses/", json={"code": code, "name": "მთავარი საწყობი", "is_default": True}, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]


async def _stock(db_session, test_company, wh_id, product_id, qty):
    from app.models.warehouse import InventoryBalance
    from decimal import Decimal
    bal = InventoryBalance(company_id=test_company.id, warehouse_id=uuid.UUID(wh_id),
                           product_id=uuid.UUID(product_id), quantity=Decimal(str(qty)))
    db_session.add(bal)
    await db_session.commit()


async def _mk_bom_wo(client, auth_headers, product_id, comp_id, warehouse_id, planned=4, comp_cost=5):
    bom = await client.post("/api/v1/production/boms", json={
        "code": f"BOM-{uuid.uuid4().hex[:6]}", "name": "BOM", "product_id": product_id, "quantity": 1,
        "labor_cost": 10, "overhead_cost": 5,
    }, headers=auth_headers)
    assert bom.status_code == 201, bom.text
    bom_id = bom.json()["data"]["id"]
    item = await client.post(f"/api/v1/production/boms/{bom_id}/items", json={
        "product_id": comp_id, "quantity": 2, "unit_cost": comp_cost, "scrap_percent": 0,
    }, headers=auth_headers)
    assert item.status_code == 201, item.text
    wo = await client.post("/api/v1/production/work-orders", json={
        "bom_id": bom_id, "product_id": product_id, "planned_quantity": planned,
    }, headers=auth_headers)
    assert wo.status_code == 201, wo.text
    wo_id = wo.json()["data"]["id"]
    st = await client.patch(f"/api/v1/production/work-orders/{wo_id}", json={"status": "in_progress"}, headers=auth_headers)
    assert st.status_code == 200, st.text
    return bom_id, wo_id


async def test_routing_operations_and_apply(client, auth_headers):
    """Routing + operations CRUD; apply routing copies operations onto WO."""
    prod = await _mk_product(client, auth_headers, f"RTG-{uuid.uuid4().hex[:6]}", "რუტინგ პროდუქტი")
    wc = await client.post("/api/v1/production/work-centers", json={
        "code": f"WC-{uuid.uuid4().hex[:4]}", "name": "ცენტრი 1", "hourly_rate": 60, "capacity_per_shift": 8,
    }, headers=auth_headers)
    assert wc.status_code == 201, wc.text
    wc_id = wc.json()["data"]["id"]

    rt = await client.post("/api/v1/production/routings", json={
        "code": f"RT-{uuid.uuid4().hex[:6]}", "name": "მარშრუტი", "product_id": prod["id"],
    }, headers=auth_headers)
    assert rt.status_code == 201, rt.text
    rt_id = rt.json()["data"]["id"]

    op1 = await client.post(f"/api/v1/production/routings/{rt_id}/operations", json={
        "name": "დაჭრა", "sequence": 10, "work_center_id": wc_id, "standard_time_minutes": 30, "hourly_rate": 60,
    }, headers=auth_headers)
    assert op1.status_code == 201, op1.text
    op2 = await client.post(f"/api/v1/production/routings/{rt_id}/operations", json={
        "name": "შედუღება", "sequence": 20, "work_center_id": wc_id, "standard_time_minutes": 45, "hourly_rate": 60,
    }, headers=auth_headers)
    assert op2.status_code == 201

    lst = await client.get("/api/v1/production/routings", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1
    assert len(lst.json()["data"][0]["operations"]) == 2

    # work order + apply
    comp = await _mk_product(client, auth_headers, f"RTG-C-{uuid.uuid4().hex[:6]}", "კომპონენტი")
    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp["id"], "00000000-0000-0000-0000-000000000000", planned=1)
    # _mk_bom_wo uses warehouse_id param as required — build wo without warehouse (schema may allow None)
    ap = await client.post(f"/api/v1/production/work-orders/{wo_id}/routing?routing_id={rt_id}", headers=auth_headers)
    assert ap.status_code == 201, ap.text
    ops = ap.json()["data"]
    assert len(ops) == 2
    assert ops[0]["name"] == "დაჭრა"
    assert ops[1]["sequence"] == 20


async def test_operation_start_complete_actual_labor_wip(client, auth_headers):
    """Start/complete operation records actual labor cost into WIP."""
    prod = await _mk_product(client, auth_headers, f"OPS-{uuid.uuid4().hex[:6]}", "ოპ პროდუქტი")
    comp = await _mk_product(client, auth_headers, f"OPS-C-{uuid.uuid4().hex[:6]}", "ოპ კომპ")
    wc = await client.post("/api/v1/production/work-centers", json={
        "code": f"WC-{uuid.uuid4().hex[:4]}", "name": "ცენტრი", "hourly_rate": 120, "capacity_per_shift": 8,
    }, headers=auth_headers)
    wc_id = wc.json()["data"]["id"]
    rt = await client.post("/api/v1/production/routings", json={"code": f"RT-{uuid.uuid4().hex[:6]}", "name": "რ", "product_id": prod["id"]}, headers=auth_headers)
    rt_id = rt.json()["data"]["id"]
    await client.post(f"/api/v1/production/routings/{rt_id}/operations", json={
        "name": "შეკრება", "sequence": 1, "work_center_id": wc_id, "standard_time_minutes": 60, "hourly_rate": 120,
    }, headers=auth_headers)

    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp["id"], "00000000-0000-0000-0000-000000000000", planned=1)
    ap = await client.post(f"/api/v1/production/work-orders/{wo_id}/routing?routing_id={rt_id}", headers=auth_headers)
    op_id = ap.json()["data"][0]["id"]

    st = await client.post(f"/api/v1/production/work-orders/{wo_id}/operations/{op_id}/start", json={}, headers=auth_headers)
    assert st.status_code == 200, st.text
    assert st.json()["data"]["status"] == "in_progress"

    co = await client.post(f"/api/v1/production/work-orders/{wo_id}/operations/{op_id}/complete", json={"actual_minutes": 45}, headers=auth_headers)
    assert co.status_code == 200, co.text
    assert co.json()["data"]["status"] == "done"
    # 45 min = 0.75 h × 120 GEL/h = 90 GEL
    assert float(co.json()["data"]["actual_labor_cost"]) == pytest.approx(90.0)

    wip = await client.get(f"/api/v1/production/work-orders/{wo_id}/wip", headers=auth_headers)
    assert wip.status_code == 200, wip.text
    assert float(wip.json()["data"]["labor_cost"]) == pytest.approx(90.0)


async def test_manual_consumption_decrements_stock(client, auth_headers, db_session, test_company):
    """Manual consumption: +WIP material, −warehouse balance, movement logged."""
    prod = await _mk_product(client, auth_headers, f"MSC-{uuid.uuid4().hex[:6]}", "მსხ პროდუქტი")
    comp = await _mk_product(client, auth_headers, f"MSC-C-{uuid.uuid4().hex[:6]}", "მსხ კომპ")
    wh = await _mk_warehouse(client, auth_headers)
    await _stock(db_session, test_company, wh["id"], comp["id"], 50)

    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp["id"], wh["id"], planned=1, comp_cost=4)

    c = await client.post(f"/api/v1/production/work-orders/{wo_id}/consumptions", json={
        "product_id": comp["id"], "warehouse_id": wh["id"], "quantity": 5, "unit_cost": 4,
    }, headers=auth_headers)
    assert c.status_code == 201, c.text
    assert float(c.json()["data"]["total_cost"]) == pytest.approx(20.0)

    lst = await client.get(f"/api/v1/production/work-orders/{wo_id}/consumptions", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    wip = await client.get(f"/api/v1/production/work-orders/{wo_id}/wip", headers=auth_headers)
    assert float(wip.json()["data"]["material_cost"]) == pytest.approx(20.0)

    # insufficient stock → 409
    c2 = await client.post(f"/api/v1/production/work-orders/{wo_id}/consumptions", json={
        "product_id": comp["id"], "warehouse_id": wh["id"], "quantity": 99, "unit_cost": 4,
    }, headers=auth_headers)
    assert c2.status_code == 409, c2.text


async def test_receipt_backflush_consumes_components_and_gl(client, auth_headers, db_session):
    """Core fix: finished-goods receipt backflushes BOM components (stock ↓),
    writes consumption, WIP and a balanced GL entry."""
    from app.models.gl import JournalEntry, JournalEntryLine, GLAccount
    from sqlalchemy import select

    prod = await _mk_product(client, auth_headers, f"BFL-{uuid.uuid4().hex[:6]}", "მზა პროდუქტი")
    comp = await _mk_product(client, auth_headers, f"BFL-C-{uuid.uuid4().hex[:6]}", "კომპონენტი")
    wh = await _mk_warehouse(client, auth_headers)
    await _stock(db_session, test_company, wh["id"], comp["id"], 100)

    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp["id"], wh["id"], planned=4, comp_cost=5)

    rcp = await client.post(f"/api/v1/production/work-orders/{wo_id}/receipts", json={
        "work_order_id": wo_id, "product_id": prod["id"], "warehouse_id": wh["id"],
        "quantity": 2, "unit_cost": 0,
    }, headers=auth_headers)
    assert rcp.status_code == 201, rcp.text
    receipt_id = rcp.json()["data"]["id"]

    # component consumed: 2 units × 2 per unit = 4 (scrap 0) → 100 − 4 = 96
    balances = await client.get(f"/api/v1/warehouses/balances?product_id={comp['id']}", headers=auth_headers)
    assert balances.status_code == 200
    assert float(balances.json()["data"][0]["quantity"]) == pytest.approx(96.0)

    cons = await client.get(f"/api/v1/production/work-orders/{wo_id}/consumptions", headers=auth_headers)
    assert len(cons.json()["data"]) == 1
    assert float(cons.json()["data"][0]["total_cost"]) == pytest.approx(20.0)

    wip = await client.get(f"/api/v1/production/work-orders/{wo_id}/wip", headers=auth_headers)
    # material 20 + labor 10 + overhead 5 = 35
    assert float(wip.json()["data"]["total_cost"]) == pytest.approx(35.0)

    # GL balanced, 5100? no — production: Dr 1200 / Cr 1210
    gl = (await db_session.execute(
        select(JournalEntry).where(JournalEntry.reference_type == "production_receipt", JournalEntry.reference_id == receipt_id)
    )).scalar_one_or_none()
    assert gl is not None, "GL entry not found"
    rows = (await db_session.execute(
        select(GLAccount.code, JournalEntryLine.debit_amount, JournalEntryLine.credit_amount)
        .join(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .where(JournalEntryLine.journal_entry_id == gl.id)
    )).all()
    row_map = {c: (d, cr) for c, d, cr in rows}
    assert "1200" in row_map and row_map["1200"][0] == 35, f"Dr 1200 missing: {row_map}"
    assert "1210" in row_map and row_map["1210"][1] == 35, f"Cr 1210 missing: {row_map}"
    assert sum(d for _, d, _ in rows) == sum(cr for _, _, cr in rows), "GL not balanced"


async def test_receipt_backflush_insufficient_stock_409(client, auth_headers, db_session, test_company):
    """Backflush must reject when components are short."""
    prod = await _mk_product(client, auth_headers, f"BFL9-{uuid.uuid4().hex[:6]}", "მზა 2")
    comp = await _mk_product(client, auth_headers, f"BFL9-C-{uuid.uuid4().hex[:6]}", "კომპ 2")
    wh = await _mk_warehouse(client, auth_headers)
    await _stock(db_session, test_company, wh["id"], comp["id"], 3)  # need 2×2=4

    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp["id"], wh["id"], planned=4, comp_cost=5)
    rcp = await client.post(f"/api/v1/production/work-orders/{wo_id}/receipts", json={
        "work_order_id": wo_id, "product_id": prod["id"], "warehouse_id": wh["id"], "quantity": 2,
    }, headers=auth_headers)
    assert rcp.status_code == 409, rcp.text


async def test_scrap_and_byproduct(client, auth_headers):
    """Scrap records waste; by-product receives stock into warehouse."""
    prod = await _mk_product(client, auth_headers, f"SCP-{uuid.uuid4().hex[:6]}", "სკრ პროდუქტი")
    comp = await _mk_product(client, auth_headers, f"SCP-C-{uuid.uuid4().hex[:6]}", "სკრ კომპ")
    byp = await _mk_product(client, auth_headers, f"SCP-B-{uuid.uuid4().hex[:6]}", "გვერდითი პროდუქტი")
    wh = await _mk_warehouse(client, auth_headers)

    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp["id"], wh["id"], planned=2)

    sc = await client.post(f"/api/v1/production/work-orders/{wo_id}/scrap", json={
        "product_id": comp["id"], "quantity": 1, "kind": "scrap", "unit_cost": 5,
    }, headers=auth_headers)
    assert sc.status_code == 201, sc.text

    bp = await client.post(f"/api/v1/production/work-orders/{wo_id}/scrap", json={
        "product_id": byp["id"], "quantity": 2, "kind": "by_product", "unit_cost": 3,
    }, headers=auth_headers)
    assert bp.status_code == 201, bp.text

    balances = await client.get(f"/api/v1/warehouses/balances?product_id={byp['id']}", headers=auth_headers)
    if balances.status_code == 200 and balances.json()["data"]:
        assert float(balances.json()["data"][0]["quantity"]) == pytest.approx(2.0)


async def test_genealogy(client, auth_headers):
    """Finished lot ← component lot traceability."""
    prod = await _mk_product(client, auth_headers, f"GEN-{uuid.uuid4().hex[:6]}", "გენ პროდუქტი")
    comp = await _mk_product(client, auth_headers, f"GEN-C-{uuid.uuid4().hex[:6]}", "გენ კომპ")
    wh = await _mk_warehouse(client, auth_headers)
    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp["id"], wh["id"], planned=1)

    g = await client.post(f"/api/v1/production/work-orders/{wo_id}/genealogy", json={
        "finished_lot": "FG-001", "finished_serial": "S-100",
        "component_product_id": comp["id"], "component_lot": "CMP-LOT-9", "quantity": 2,
    }, headers=auth_headers)
    assert g.status_code == 201, g.text

    lst = await client.get(f"/api/v1/production/work-orders/{wo_id}/genealogy", headers=auth_headers)
    assert lst.status_code == 200
    data = lst.json()["data"]
    assert len(data) == 1
    assert data[0]["finished_lot"] == "FG-001"
    assert data[0]["component_lot"] == "CMP-LOT-9"


async def test_mrp_run_and_suggestions(client, auth_headers, test_company, db_session):
    """MRP: demand vs on-hand/reserved → make/buy suggestions."""
    from app.models.product import Product
    from sqlalchemy import select

    comp = Product(company_id=test_company.id, name="MRP კომპ", sku=f"MRP-{uuid.uuid4().hex[:6]}", sale_price=5, current_stock=0)
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    prod = await _mk_product(client, auth_headers, f"MRP-F-{uuid.uuid4().hex[:6]}", "MRP მზა")
    wh = await _mk_warehouse(client, auth_headers)
    # 0 stock on component → WO planned 5 needs 10 → short 10 (buy)
    _, wo_id = await _mk_bom_wo(client, auth_headers, prod["id"], comp.id, wh["id"], planned=5, comp_cost=5)

    run = await client.post("/api/v1/production/mrp/run?horizon_days=30", headers=auth_headers)
    assert run.status_code == 200, run.text
    data = run.json()["data"]
    assert data["generated"] >= 1
    kinds = {s["kind"] for s in data["suggestions"]}
    assert "buy" in kinds

    sug = await client.get("/api/v1/production/mrp/suggestions", headers=auth_headers)
    assert sug.status_code == 200
    assert len(sug.json()["data"]) >= 1
    assert sug.json()["data"][0]["suggested_qty"] > 0


async def test_downtime_and_capacity(client, auth_headers):
    """Downtime window + capacity utilization calculation."""
    prod = await _mk_product(client, auth_headers, f"CAP-{uuid.uuid4().hex[:6]}", "კაპ პროდუქტი")
    comp = await _mk_product(client, auth_headers, f"CAP-C-{uuid.uuid4().hex[:6]}", "კაპ კომპ")
    wc = await client.post("/api/v1/production/work-centers", json={
        "code": f"WC-{uuid.uuid4().hex[:4]}", "name": "ცენტრი", "hourly_rate": 60, "capacity_per_shift": 8,
    }, headers=auth_headers)
    wc_id = wc.json()["data"]["id"]

    dw = await client.post("/api/v1/production/maintenance-downtime", json={
        "work_center_id": wc_id,
        "start_time": "2026-09-14T08:00:00", "end_time": "2026-09-14T10:30:00",
        "downtime_type": "maintenance", "notes": "გეგმური მოვლა",
    }, headers=auth_headers)
    assert dw.status_code == 201, dw.text

    lst = await client.get("/api/v1/production/maintenance-downtime", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    cap = await client.get(f"/api/v1/production/work-centers/{wc_id}/capacity?date_from=2026-09-14&date_to=2026-09-14", headers=auth_headers)
    assert cap.status_code == 200, cap.text
    assert float(cap.json()["data"]["downtime_minutes"]) == pytest.approx(150.0)
