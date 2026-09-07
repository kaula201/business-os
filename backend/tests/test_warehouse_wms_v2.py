"""Warehouse/WMS 2.0: UoM, reorder rules, putaway, ABC/XYZ, cycle count, aging, expiry, quarantine, consignment, waves, cross-dock, shipments, GS1, lot zones."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.warehouse import (
    Warehouse, WarehouseZone, InventoryBalance, ProductBatch,
    UoM, UoMConversion, WarehouseReorderRule, PutawayStrategy, CycleCountSchedule, ConsignmentStock,
)
from app.models.wms_ops import WavePick, CrossDockOrder, Shipment, LotZoneBalance
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_warehouse(client, auth_headers, test_company, code="WH2"):
    async with TestSessionLocal() as session:
        wh = Warehouse(company_id=test_company.id, name="WMS ტესტი", code=code, is_active=True)
        session.add(wh)
        await session.commit()
        return str(wh.id)


async def _make_zone(client, auth_headers, test_company, wh_id, code="Z1"):
    async with TestSessionLocal() as session:
        zone = WarehouseZone(company_id=test_company.id, warehouse_id=uuid.UUID(wh_id), code=code, name="ზონა 1", zone_type="bin")
        session.add(zone)
        await session.commit()
        return str(zone.id)


async def _make_product(client, auth_headers):
    r = await client.post("/api/v1/products/", json={
        "sku": f"WMS-{uuid.uuid4().hex[:6]}", "name": "WMS პროდუქტი",
        "sale_price": 100, "purchase_price": 50, "unit": "ცალი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def _make_supplier(client, auth_headers):
    r = await client.post("/api/v1/suppliers/", json={
        "name": f"მომწოდებელი {uuid.uuid4().hex[:4]}", "code": f"SUP-{uuid.uuid4().hex[:6]}",
        "email": f"sup-{uuid.uuid4().hex[:6]}@test.ge", "phone": "599000000",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def test_uom_and_conversion(client, auth_headers):
    """UoM + კონვერტაციები: create UoMs, conversion, convert."""
    r1 = await client.post("/api/v1/wms-ops/uoms", json={"code": "PCS", "name": "ცალი", "category": "unit", "is_base": True}, headers=auth_headers)
    assert r1.status_code == 201, r1.text
    pcs_id = r1.json()["data"]["id"]

    r2 = await client.post("/api/v1/wms-ops/uoms", json={"code": "BOX", "name": "ყუთი", "category": "unit"}, headers=auth_headers)
    assert r2.status_code == 201, r2.text
    box_id = r2.json()["data"]["id"]

    r3 = await client.post("/api/v1/wms-ops/uom-conversions", json={"from_uom_id": box_id, "to_uom_id": pcs_id, "factor": 12}, headers=auth_headers)
    assert r3.status_code == 201, r3.text

    r4 = await client.post("/api/v1/wms-ops/uom/convert", json={"from_uom_id": box_id, "to_uom_id": pcs_id, "quantity": 2}, headers=auth_headers)
    assert r4.status_code == 200, r4.text
    assert r4.json()["data"]["quantity"] == 24.0

    r5 = await client.get("/api/v1/wms-ops/uoms", headers=auth_headers)
    assert len(r5.json()["data"]) == 2


async def test_reorder_rule_and_suggestions(client, auth_headers, test_company):
    """Warehouse-specific reorder rule + suggestions."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/wms-ops/reorder-rules", json={
        "warehouse_id": wh, "product_id": pid, "min_quantity": 10, "max_quantity": 100,
        "reorder_quantity": 50, "lead_time_days": 5,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    # no balance → suggestion appears
    r2 = await client.get("/api/v1/wms-ops/reorder/suggestions", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert len(r2.json()["data"]) == 1
    assert r2.json()["data"][0]["suggested_order"] == 50.0


async def test_putaway_strategy(client, auth_headers, test_company):
    """Putaway strategy + directed putaway suggestion."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    zone = await _make_zone(client, auth_headers, test_company, wh)
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/wms-ops/putaway-strategies", json={
        "name": "საკვები → ზონა 1", "priority": 1, "product_id": pid, "zone_id": zone,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r2 = await client.post("/api/v1/wms-ops/putaway/suggest", json={"product_id": pid}, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["zone_id"] == zone


async def test_abc_xyz_and_quarantine(client, auth_headers):
    """ABC/XYZ კლასიფიკაცია + quarantine."""
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/wms-ops/abc-xyz", json={
        "product_id": pid, "abc_class": "A", "xyz_class": "X", "is_quarantine": True,
        "quarantine_reason": "ხარისხის შემოწმება",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["abc_class"] == "A"
    assert d["is_quarantine"] is True

    r2 = await client.get("/api/v1/wms-ops/abc-xyz", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    row = next(p for p in r2.json()["data"] if p["product_id"] == pid)
    assert row["abc_class"] == "A"
    assert row["quarantine_reason"] == "ხარისხის შემოწმება"


async def test_cycle_count_schedule(client, auth_headers, test_company):
    """Cycle-count scheduler."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    r = await client.post("/api/v1/wms-ops/cycle-count-schedules", json={
        "warehouse_id": wh, "abc_class": "A", "frequency_days": 7,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r2 = await client.get("/api/v1/wms-ops/cycle-count-schedules", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    rows = r2.json()["data"]
    assert len(rows) == 1
    assert rows[0]["abc_class"] == "A"
    assert rows[0]["frequency_days"] == 7
    assert rows[0]["next_run_date"] is not None


async def test_stock_aging_and_expiry(client, auth_headers, test_company):
    """Stock aging + expiry alerts."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    pid = await _make_product(client, auth_headers)

    async with TestSessionLocal() as session:
        bal = InventoryBalance(company_id=test_company.id, warehouse_id=uuid.UUID(wh), product_id=uuid.UUID(pid), quantity=Decimal("5"))
        session.add(bal)
        batch = ProductBatch(
            company_id=test_company.id, warehouse_id=uuid.UUID(wh), product_id=uuid.UUID(pid),
            batch_number=f"B-{uuid.uuid4().hex[:6]}", quantity=Decimal("5"),
            expiry_date=date.today() + timedelta(days=10),
        )
        session.add(batch)
        await session.commit()

    r = await client.get("/api/v1/wms-ops/stock-aging", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 1

    r2 = await client.get("/api/v1/wms-ops/expiry-alerts", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert len(r2.json()["data"]) == 1
    assert r2.json()["data"][0]["quantity"] == 5.0


async def test_consignment_stock(client, auth_headers, test_company):
    """Owner/consignment stock."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    pid = await _make_product(client, auth_headers)
    sid = await _make_supplier(client, auth_headers)

    r = await client.post("/api/v1/wms-ops/consignment-stock", json={
        "warehouse_id": wh, "product_id": pid, "owner_id": sid, "quantity": 100, "unit_cost": 30,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["quantity"] == 100.0

    r2 = await client.get("/api/v1/wms-ops/consignment-stock", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    rows = r2.json()["data"]
    assert len(rows) == 1
    assert rows[0]["owner_id"] == sid
    assert rows[0]["unit_cost"] == 30.0


async def test_wave_picking(client, auth_headers, test_company):
    """Wave/batch picking."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    r = await client.post("/api/v1/wms-ops/waves", json={"warehouse_id": wh, "notes": "დილის ტალღა"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    wave_id = r.json()["data"]["id"]
    assert r.json()["data"]["wave_number"].startswith("WAVE")

    r2 = await client.get("/api/v1/wms-ops/waves", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert len(r2.json()["data"]) == 1

    r3 = await client.post(f"/api/v1/wms-ops/waves/{wave_id}/complete", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["status"] == "completed"


async def test_cross_dock(client, auth_headers, test_company):
    """Cross-docking."""
    wh1 = await _make_warehouse(client, auth_headers, test_company, code="WH-A")
    wh2 = await _make_warehouse(client, auth_headers, test_company, code="WH-B")
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/wms-ops/cross-dock-orders", json={
        "source_warehouse_id": wh1, "destination_warehouse_id": wh2,
        "items": [{"product_id": pid, "quantity": 10}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["cross_dock_number"].startswith("XD")

    r2 = await client.get("/api/v1/wms-ops/cross-dock-orders", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert len(r2.json()["data"]) == 1


async def test_shipment_carrier(client, auth_headers, test_company):
    """Shipping/carrier."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    pid = await _make_product(client, auth_headers)

    r = await client.post("/api/v1/wms-ops/shipments", json={
        "warehouse_id": wh, "carrier": "Georgian Post", "tracking_number": "GP-12345",
        "items": [{"product_id": pid, "quantity": 3}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    ship_id = r.json()["data"]["id"]
    assert r.json()["data"]["shipment_number"].startswith("SHP")

    r2 = await client.post(f"/api/v1/wms-ops/shipments/{ship_id}/ship", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["status"] == "shipped"

    r3 = await client.get("/api/v1/wms-ops/shipments", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"][0]["carrier"] == "Georgian Post"


async def test_gs1_barcode_parse(client, auth_headers):
    """GS1 barcode parsing."""
    r = await client.post("/api/v1/wms-ops/gs1/parse", json={
        "barcode": "0101234567890128\x1d10BATCH123\x1d17251231",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["01"] == "01234567890128"
    assert d["10"] == "BATCH123"
    assert d["17"] == "251231"

    r2 = await client.post("/api/v1/wms-ops/gs1/parse", json={"barcode": "NOT-GS1"}, headers=auth_headers)
    assert r2.status_code == 400


async def test_lot_zone_balance(client, auth_headers, test_company):
    """Lot-level zone balances."""
    wh = await _make_warehouse(client, auth_headers, test_company)
    zone = await _make_zone(client, auth_headers, test_company, wh)
    pid = await _make_product(client, auth_headers)

    async with TestSessionLocal() as session:
        batch = ProductBatch(
            company_id=test_company.id, warehouse_id=uuid.UUID(wh), product_id=uuid.UUID(pid),
            batch_number=f"LZ-{uuid.uuid4().hex[:6]}", quantity=Decimal("20"),
        )
        session.add(batch)
        await session.commit()
        batch_id = str(batch.id)

    r = await client.post("/api/v1/wms-ops/lot-zone-balances", json={
        "batch_id": batch_id, "zone_id": zone, "quantity": 20,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r2 = await client.get("/api/v1/wms-ops/lot-zone-balances", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    rows = r2.json()["data"]
    assert len(rows) == 1
    assert rows[0]["quantity"] == 20.0
