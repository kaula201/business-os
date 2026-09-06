"""Procurement 2.0: requisitions, RFQ→PO, supplier terms, price auto-select, budget, multi-level approval."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.procurement import (
    PurchaseRequisition, PurchaseRequisitionLine, RFQ, RFQLine, SupplierPriceList,
)
from app.models.purchase import PurchaseOrder, PurchaseOrderItem, Supplier
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_supplier(client, auth_headers):
    r = await client.post("/api/v1/suppliers/", json={
        "name": f"მომწოდებელი {uuid.uuid4().hex[:4]}", "code": f"SUP-{uuid.uuid4().hex[:6]}",
        "email": f"sup-{uuid.uuid4().hex[:6]}@test.ge", "phone": "599000000",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def _make_product(client, auth_headers, purchase_price=50):
    r = await client.post("/api/v1/products/", json={
        "sku": f"PR-{uuid.uuid4().hex[:6]}", "name": "შესყიდვის პროდუქტი",
        "sale_price": 100, "purchase_price": purchase_price, "unit": "ცალი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def test_requisition_lifecycle(client, auth_headers):
    """Purchase Requisition: create → submit (department→procurement) → approve."""
    pid = await _make_product(client, auth_headers)
    r = await client.post("/api/v1/procurement/requisitions", json={
        "department": "მარკეტინგი", "priority": "high",
        "lines": [{"product_id": pid, "quantity": 10, "estimated_price": 50}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    req_id = r.json()["data"]["id"]
    assert r.json()["data"]["requisition_number"].startswith("REQ")

    # submit → procurement
    r2 = await client.post(f"/api/v1/procurement/requisitions/{req_id}/submit", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["status"] == "submitted"

    # approve level 1
    r3 = await client.post(f"/api/v1/procurement/requisitions/{req_id}/approve",
                           json={"level": 1}, headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["status"] == "approved"

    # approve level 2 (multi-level)
    r4 = await client.post(f"/api/v1/procurement/requisitions/{req_id}/approve",
                           json={"level": 2}, headers=auth_headers)
    assert r4.status_code == 200, r4.text

    # list
    r5 = await client.get("/api/v1/procurement/requisitions", headers=auth_headers)
    assert r5.status_code == 200, r5.text
    assert len(r5.json()["data"]) == 1


async def test_requisition_budget_check(client, auth_headers):
    """Procurement budget check: no budget → no_budget; with budget → ok/over."""
    pid = await _make_product(client, auth_headers)
    r = await client.post("/api/v1/procurement/requisitions", json={
        "department": "IT", "lines": [{"product_id": pid, "quantity": 5, "estimated_price": 100}],
    }, headers=auth_headers)
    req_id = r.json()["data"]["id"]

    r2 = await client.post(f"/api/v1/procurement/requisitions/{req_id}/budget-check", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["estimated_total"] == 500.0
    assert d["check"] in ("ok", "over_budget", "no_budget")


async def test_supplier_product_terms(client, auth_headers):
    """Supplier-product პირობები: ფასი, ვადა, მინ. რაოდენობა, lead time, პრიორიტეტი."""
    sid = await _make_supplier(client, auth_headers)
    pid = await _make_product(client, auth_headers)
    r = await client.post("/api/v1/procurement/supplier-products", json={
        "supplier_id": sid, "product_id": pid, "price": 45, "currency": "GEL",
        "min_quantity": 5, "lead_time_days": 7, "priority": 1,
        "valid_to": (date.today() + timedelta(days=30)).isoformat(),
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r2 = await client.get(f"/api/v1/procurement/supplier-products?supplier_id={sid}", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    items = r2.json()["data"]
    assert len(items) == 1
    assert items[0]["price"] == 45.0
    assert items[0]["min_quantity"] == 5.0
    assert items[0]["lead_time_days"] == 7
    assert items[0]["priority"] == 1


async def test_price_auto_select(client, auth_headers):
    """ფასების სიიდან PO-ზე ფასის ავტომატური არჩევა: პრიორიტეტით."""
    sid1 = await _make_supplier(client, auth_headers)
    sid2 = await _make_supplier(client, auth_headers)
    pid = await _make_product(client, auth_headers)
    # supplier 2 has priority 0 (preferred), supplier 1 priority 5
    await client.post("/api/v1/procurement/supplier-products", json={
        "supplier_id": sid1, "product_id": pid, "price": 40, "priority": 5,
    }, headers=auth_headers)
    await client.post("/api/v1/procurement/supplier-products", json={
        "supplier_id": sid2, "product_id": pid, "price": 48, "priority": 0, "min_quantity": 5,
    }, headers=auth_headers)

    r = await client.post("/api/v1/procurement/price/auto-select",
                          json={"product_id": pid, "quantity": 10}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["supplier_id"] == sid2  # priority 0 wins
    assert d["price"] == 48.0

    # below min quantity → 400
    r2 = await client.post("/api/v1/procurement/price/auto-select",
                           json={"product_id": pid, "quantity": 2}, headers=auth_headers)
    assert r2.status_code == 400


async def test_rfq_to_po_auto(client, auth_headers, test_company, db_session):
    """RFQ-დან PO-ის ავტომატური შექმნა: award-ის მიხედვით, ფასი supplier price list-იდან."""
    # warehouse required by purchase_orders
    from app.models.warehouse import Warehouse
    async with TestSessionLocal() as session:
        wh = Warehouse(company_id=test_company.id, name="მთავარი საწყობი", code="WH1", is_active=True)
        session.add(wh)
        await session.commit()

    sid = await _make_supplier(client, auth_headers)
    pid = await _make_product(client, auth_headers, purchase_price=50)
    # supplier price list entry
    await client.post("/api/v1/procurement/supplier-products", json={
        "supplier_id": sid, "product_id": pid, "price": 42, "priority": 0,
    }, headers=auth_headers)

    # create RFQ
    r = await client.post("/api/v1/procurement/rfqs", json={
        "title": "RFQ ტესტი", "supplier_id": sid,
        "lines": [{"product_id": pid, "quantity": 10}],
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    rfq_id = r.json()["data"]["id"]

    # create PO from RFQ
    r2 = await client.post(f"/api/v1/procurement/rfqs/{rfq_id}/create-po",
                           json={"supplier_id": sid}, headers=auth_headers)
    assert r2.status_code == 201, r2.text
    po_id = r2.json()["data"]["purchase_order_id"]

    # PO created with price from supplier list (42)
    async with TestSessionLocal() as session:
        po = (await session.execute(select(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(po_id)))).scalar_one()
        assert po.supplier_id == uuid.UUID(sid)
        items = (await session.execute(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po.id))).scalars().all()
        assert len(items) == 1
        assert float(items[0].unit_price) == 42.0
        assert float(items[0].line_total) == pytest.approx(495.6, abs=0.01)  # 42*10 + 18% VAT
