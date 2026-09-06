"""PO 2.0: supplier invoice one-click, scheduled deliveries, backorder, returns, landed cost, price validation, amendments."""
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from decimal import Decimal

from app.models.purchase import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderAmendment, PurchaseReturn,
    PurchaseOrderBackorder, SupplierInvoice, SupplierInvoiceItem,
)
from app.models.wms_ops import LandedCost
from app.models.warehouse import Warehouse
from app.models.procurement import SupplierPriceList
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_warehouse(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        wh = Warehouse(company_id=test_company.id, name="WH-ტესტი", code=f"WH{uuid.uuid4().hex[:4]}", is_active=True)
        session.add(wh)
        await session.commit()
        return str(wh.id)


async def _make_supplier(client, auth_headers):
    r = await client.post("/api/v1/suppliers/", json={
        "name": f"მომწოდებელი {uuid.uuid4().hex[:4]}", "code": f"SUP-{uuid.uuid4().hex[:6]}",
        "email": f"sup-{uuid.uuid4().hex[:6]}@test.ge", "phone": "599000000",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def _make_product(client, auth_headers, purchase_price=50):
    r = await client.post("/api/v1/products/", json={
        "sku": f"PR-{uuid.uuid4().hex[:6]}", "name": "PO2 პროდუქტი",
        "sale_price": 100, "purchase_price": purchase_price, "unit": "ცალი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def _make_po(client, auth_headers, test_company, supplier_id=None, product_id=None, qty=10):
    if supplier_id is None:
        supplier_id = await _make_supplier(client, auth_headers)
    if product_id is None:
        product_id = await _make_product(client, auth_headers)
    wh = await _make_warehouse(client, auth_headers, test_company)
    r = await client.post("/api/v1/purchase-orders/", json={
        "supplier_id": supplier_id, "warehouse_id": wh,
        "items": [{"product_id": product_id, "quantity": qty, "unit_price": 50, "vat_rate": "18"}],
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"], supplier_id


async def test_one_click_supplier_invoice(client, auth_headers, test_company):
    """PO-დან supplier invoice-ის ერთი დაჭერით შექმნა."""
    po_id, _ = await _make_po(client, auth_headers, test_company)

    # approve required
    r = await client.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "approved"}, headers=auth_headers)
    assert r.status_code == 200, r.text

    r2 = await client.post(f"/api/v1/purchase-orders/{po_id}/create-supplier-invoice", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["supplier_invoice_number"].startswith("SINV")
    assert float(d["total"]) > 0

    # idempotency: second call → 409
    r3 = await client.post(f"/api/v1/purchase-orders/{po_id}/create-supplier-invoice", headers=auth_headers)
    assert r3.status_code == 409

    # item rows persisted
    async with TestSessionLocal() as session:
        inv = (await session.execute(select(SupplierInvoice).where(SupplierInvoice.internal_invoice_number == d["supplier_invoice_number"]))).scalar_one()
        items = (await session.execute(select(SupplierInvoiceItem).where(SupplierInvoiceItem.supplier_invoice_id == inv.id))).scalars().all()
        assert len(items) == 1
        assert float(items[0].quantity) == 10.0


async def test_scheduled_deliveries(client, auth_headers, test_company):
    """Scheduled deliveries: create + list."""
    po_id, _ = await _make_po(client, auth_headers, test_company)
    fut = (date.today() + timedelta(days=5)).isoformat()

    r = await client.post(f"/api/v1/purchase-orders/{po_id}/scheduled-deliveries",
                          json={"scheduled_date": fut, "quantity": 5, "note": "პარტია 1"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert float(r.json()["data"]["quantity"]) == 5.0

    r2 = await client.post(f"/api/v1/purchase-orders/{po_id}/scheduled-deliveries",
                           json={"scheduled_date": fut, "quantity": 6}, headers=auth_headers)
    assert r2.status_code == 200, r2.text

    r3 = await client.get(f"/api/v1/purchase-orders/{po_id}/scheduled-deliveries", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert len(r3.json()["data"]) == 2


async def test_backorder(client, auth_headers, test_company):
    """Backorder: ordered > received → backorder quantity 10."""
    po_id, _ = await _make_po(client, auth_headers, test_company, qty=10)
    r = await client.get(f"/api/v1/purchase-orders/{po_id}/backorder", headers=auth_headers)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 1
    assert float(rows[0]["backorder_quantity"]) == 10.0  # 1 item qty 10, received 0


async def test_purchase_return(client, auth_headers, test_company):
    """Purchase return: create with items, stock adjusted back."""
    po_id, _ = await _make_po(client, auth_headers, test_company)
    r = await client.patch(f"/api/v1/purchase-orders/{po_id}", json={"status": "approved"}, headers=auth_headers)

    async with TestSessionLocal() as session:
        po_item = (await session.execute(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == uuid.UUID(po_id)))).scalar_one()
        po_item.received_quantity = Decimal("10")
        await session.commit()
        item_id = str(po_item.id)

    r2 = await client.post(f"/api/v1/purchase-orders/{po_id}/returns", json={
        "reason": "დეფექტი", "return_date": date.today().isoformat(),
        "items": [{"purchase_order_item_id": item_id, "quantity": 4, "reason": "მწყობრიდან გამოსული"}],
    }, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["return_number"].startswith("RET")
    assert float(d["total"]) == pytest.approx(200.0, abs=0.01)  # 4 × 50

    r3 = await client.get(f"/api/v1/purchase-orders/{po_id}/returns", headers=auth_headers)
    assert r3.status_code == 200
    assert len(r3.json()["data"]) == 1

    # received_quantity decreased
    async with TestSessionLocal() as session:
        po_item2 = (await session.execute(select(PurchaseOrderItem).where(PurchaseOrderItem.id == uuid.UUID(item_id)))).scalar_one()
        assert float(po_item2.received_quantity) == 6.0


async def test_landed_cost_link(client, auth_headers, test_company):
    """Landed cost კავშირი PO-ზე: WMS landed_cost ჩანს PO-ს ქვეშ."""
    from decimal import Decimal as D
    po_id, supp_id = await _make_po(client, auth_headers, test_company)
    async with TestSessionLocal() as session:
        lc = LandedCost(
            company_id=test_company.id, purchase_order_id=uuid.UUID(po_id),
            supplier_id=uuid.UUID(supp_id), description="ფრეხტი", total_amount=D("300.50"),
        )
        session.add(lc)
        await session.commit()

    r = await client.get(f"/api/v1/purchase-orders/{po_id}/landed-costs", headers=auth_headers)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["description"] == "ფრეხტი"
    assert float(rows[0]["total_amount"]) == 300.50


async def test_supplier_pricelist_validation(client, auth_headers, test_company):
    """Supplier pricelist validation: PO price vs supplier_price_lists price check."""
    supp_id = await _make_supplier(client, auth_headers)
    prod_id = await _make_product(client, auth_headers, purchase_price=50)
    po_id, _ = await _make_po(client, auth_headers, test_company, supplier_id=supp_id, product_id=prod_id, qty=5)

    # supplier price list entry: price 45 (below PO unit_price 50)
    r = await client.post("/api/v1/procurement/supplier-products", json={
        "supplier_id": supp_id, "product_id": prod_id, "price": 45, "currency": "GEL",
        "min_quantity": 1, "lead_time_days": 3, "priority": 1,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    # validate: endpoint returns price list comparison
    r2 = await client.post(f"/api/v1/purchase-orders/{po_id}/validate-prices", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    rows = r2.json()["data"]
    assert len(rows) == 1


async def test_amendment_version_approval(client, auth_headers, test_company):
    """Amendment/version approval: create pending amendment → approve → PO version bump."""
    po_id, _ = await _make_po(client, auth_headers, test_company)
    r = await client.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "approved"}, headers=auth_headers)

    async with TestSessionLocal() as session:
        po_item = (await session.execute(select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == uuid.UUID(po_id)))).scalar_one()
        item_id = str(po_item.id)

    r2 = await client.post(f"/api/v1/purchase-orders/{po_id}/amendments", json={
        "changes": {"items": [{"purchase_order_item_id": item_id, "quantity": 12, "unit_price": 55}]},
        "note": "რაოდენობის კორექცია",
    }, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    amend_id = r2.json()["data"]["amendment_id"]
    # status change bumps version to 2 → amendment proposes 3
    assert r2.json()["data"]["version"] == 3

    # still pending → PO version unchanged
    async with TestSessionLocal() as session:
        po1 = (await session.execute(select(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(po_id)))).scalar_one()
        assert po1.version == 2

    # approve
    r3 = await client.post(f"/api/v1/purchase-orders/amendments/{amend_id}/approve", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["po_version"] == 3

    # PO item updated
    async with TestSessionLocal() as session:
        po2 = (await session.execute(select(PurchaseOrder).where(PurchaseOrder.id == uuid.UUID(po_id)))).scalar_one()
        assert po2.version == 3
        po_item2 = (await session.execute(select(PurchaseOrderItem).where(PurchaseOrderItem.id == uuid.UUID(item_id)))).scalar_one()
        assert float(po_item2.quantity) == 12.0
        assert float(po_item2.unit_price) == 55.0

    # list
    r4 = await client.get(f"/api/v1/purchase-orders/{po_id}/amendments", headers=auth_headers)
    assert r4.status_code == 200
    assert len(r4.json()["data"]) == 1
    assert r4.json()["data"][0]["status"] == "approved"
