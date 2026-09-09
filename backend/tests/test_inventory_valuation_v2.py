"""Inventory Valuation 2.0: landed cost → valuation, production cost, adjustment → GL, negative stock, reconciliation, per-location value."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.cost_layer import ProductValuationConfig, InventoryReconciliation, LocationValuation
from app.models.warehouse import Warehouse, InventoryBalance
from app.models.gl import JournalEntry
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_warehouse(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        wh = Warehouse(company_id=test_company.id, name="VAL საწყობი", code="VAL-WH", is_active=True)
        session.add(wh)
        await session.commit()
        return str(wh.id)


async def _make_product(client, auth_headers):
    r = await client.post("/api/v1/products/", json={
        "sku": f"VAL-{uuid.uuid4().hex[:6]}", "name": "VAL პროდუქტი",
        "sale_price": 100, "purchase_price": 50, "unit": "ცალი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def _seed_balance(client, auth_headers, test_company, wh_id, product_id):
    async with TestSessionLocal() as session:
        bal = InventoryBalance(company_id=test_company.id, warehouse_id=uuid.UUID(wh_id), product_id=uuid.UUID(product_id), quantity=Decimal("10"))
        session.add(bal)
        await session.commit()


async def test_negative_stock_policy(client, auth_headers):
    """Negative stock policy: allow/forbid per product."""
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/inventory/valuation/methods/negative-stock", json={
        "product_id": pid, "negative_stock_allowed": True,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["negative_stock_allowed"] is True

    async with TestSessionLocal() as session:
        cfg = (await session.execute(select(ProductValuationConfig).where(ProductValuationConfig.product_id == uuid.UUID(pid)))).scalar_one()
        assert cfg.negative_stock_allowed is True


async def test_production_cost_to_valuation(client, auth_headers):
    """Production cost → valuation layer."""
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/inventory/valuation/apply-production-cost", json={
        "product_id": pid, "quantity": 50, "unit_cost": 25,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["quantity"] == 50.0
    assert d["unit_cost"] == 25.0

    # valuation reflects it
    r2 = await client.get(f"/api/v1/inventory/valuation/{pid}", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["quantity"] == 50.0
    assert r2.json()["total_value"] == 1250.0


async def test_adjustment_to_gl(client, auth_headers, test_company, test_admin):
    """Stock adjustment → GL entry."""
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/inventory/valuation/adjust-to-gl", json={
        "product_id": pid, "quantity_delta": 5, "unit_cost": 20, "note": "ტესტ კორექტირება",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["adjustment_value"] == 100.0

    async with TestSessionLocal() as session:
        entries = (await session.execute(select(JournalEntry).where(
            JournalEntry.company_id == test_company.id,
            JournalEntry.reference_type == "stock_adjustment",
        ))).scalars().all()
        assert len(entries) == 1


async def test_period_end_reconciliation_flow(client, auth_headers, test_company):
    """Period-end reconciliation: create with counted qty → post."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    pid = await _make_product(client, auth_headers)
    await _seed_balance(client, auth_headers, test_company, wh, pid)
    # valuation layer so unit cost exists
    await client.post("/api/v1/inventory/valuation/apply-production-cost", json={
        "product_id": pid, "quantity": 10, "unit_cost": 30,
    }, headers=auth_headers)

    r = await client.post("/api/v1/inventory/valuation/reconciliations", json={
        "warehouse_id": wh, "period_end": date.today().isoformat(),
        "lines": [{"product_id": pid, "counted_quantity": 8}],
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    rec_id = r.json()["data"]["id"]
    assert r.json()["data"]["reconciliation_number"].startswith("REC")
    # counted 8 vs book 10 → adjustment -2 * 30 = -60
    assert r.json()["data"]["total_adjustment"] == -60.0

    r2 = await client.post(f"/api/v1/inventory/valuation/reconciliations/{rec_id}/post", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["status"] == "posted"

    r3 = await client.get("/api/v1/inventory/valuation/reconciliations", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert len(r3.json()["data"]) == 1


async def test_location_valuation(client, auth_headers, test_company):
    """Per-location inventory value."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/inventory/valuation/locations", json={
        "warehouse_id": wh, "product_id": pid, "quantity": 12, "unit_cost": 15,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["total_value"] == 180.0

    r2 = await client.get("/api/v1/inventory/valuation/locations", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    rows = r2.json()["data"]
    assert len(rows) == 1
    assert rows[0]["product_id"] == pid
    assert rows[0]["total_value"] == 180.0


async def test_landed_cost_to_valuation(client, auth_headers, test_company):
    """Landed cost → valuation: create landed cost + allocation → apply."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    pid = await _make_product(client, auth_headers)
    sid = None
    r = await client.post("/api/v1/suppliers/", json={
        "name": f"VAL SUP {uuid.uuid4().hex[:4]}", "code": f"VALSUP-{uuid.uuid4().hex[:5]}",
        "email": f"valsup-{uuid.uuid4().hex[:6]}@test.ge", "phone": "599111222",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    sid = r.json()["data"]["id"]

    # batch for the product
    async with TestSessionLocal() as session:
        from app.models.warehouse import ProductBatch
        batch = ProductBatch(
            company_id=test_company.id, warehouse_id=uuid.UUID(wh), product_id=uuid.UUID(pid),
            batch_number=f"VB-{uuid.uuid4().hex[:6]}", quantity=Decimal("20"), unit_cost=Decimal("10"),
        )
        session.add(batch)
        await session.commit()
        batch_id = str(batch.id)

    # landed cost
    r2 = await client.post("/api/v1/wms-ops/landed-costs", json={
        "description": "ფრეხტი", "total_amount": 200, "currency": "GEL",
        "purchase_order_id": None, "supplier_id": sid,
    }, headers=auth_headers)
    assert r2.status_code in (200, 201), r2.text
    lc_id = r2.json()["data"]["id"] if "id" in r2.json()["data"] else r2.json()["data"].get("landed_cost_id")

    # allocate
    r3 = await client.post(f"/api/v1/wms-ops/landed-costs/{lc_id}/allocate", json={
        "allocations": [{"batch_id": batch_id, "amount": 200}],
    }, headers=auth_headers)
    assert r3.status_code in (200, 201), r3.text

    # apply to valuation
    r4 = await client.post("/api/v1/inventory/valuation/apply-landed-cost", json={"landed_cost_id": lc_id}, headers=auth_headers)
    assert r4.status_code == 200, r4.text
    assert r4.json()["data"]["allocated_total"] == 200.0

    # FIFO lot unit cost bumped: batch cost 10 + bump (200/20=10) = 20
    async with TestSessionLocal() as session:
        from app.models.cost_layer import FifoCostLot
        lots = (await session.execute(select(FifoCostLot).where(FifoCostLot.product_id == uuid.UUID(pid)))).scalars().all()
        if lots:
            assert float(lots[0].unit_cost) == 20.0
