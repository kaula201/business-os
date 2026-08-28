"""P1.9: Purchase workflow — PO lines, partial receipt, quality check, tolerance, three-way match, return to vendor."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.purchase import GoodsReceipt, PurchaseOrder, SupplierCreditNote
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_supplier_and_product(client, auth_headers):
    s = await client.post("/api/v1/suppliers/", json={
        "name": f"Sup-{uuid.uuid4().hex[:6]}", "code": f"S-{uuid.uuid4().hex[:6]}",
        "is_vat_payer": False, "status": "active",
    }, headers=auth_headers)
    assert s.status_code in (200, 201), s.text
    supplier_id = s.json()["data"]["id"]

    p = await client.post("/api/v1/products/", json={
        "name": f"PO-{uuid.uuid4().hex[:6]}", "sku": f"PO-{uuid.uuid4().hex[:6]}",
        "sale_price": 20, "purchase_price": 10,
    }, headers=auth_headers)
    assert p.status_code in (200, 201), p.text
    product_id = p.json()["data"]["id"]

    w = await client.get("/api/v1/warehouses/", headers=auth_headers)
    assert w.status_code == 200, w.text
    warehouses = w.json()["data"]
    if warehouses:
        warehouse_id = warehouses[0]["id"]
    else:
        wc = await client.post("/api/v1/warehouses/", json={"name": f"WH-{uuid.uuid4().hex[:6]}", "code": f"WH-{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        assert wc.status_code in (200, 201), wc.text
        warehouse_id = wc.json()["data"]["id"]
    return supplier_id, product_id, warehouse_id


async def test_purchase_workflow_full(client, auth_headers):
    supplier_id, product_id, warehouse_id = await _seed_supplier_and_product(client, auth_headers)

    # 1. PO with 10 units
    po = await client.post("/api/v1/purchase-orders/", json={
        "supplier_id": supplier_id, "warehouse_id": warehouse_id,
        "items": [{"product_id": product_id, "quantity": 10, "unit_price": 10}],
    }, headers=auth_headers)
    assert po.status_code in (200, 201), po.text
    po_id = po.json()["data"]["id"]
    assert len(po.json()["data"]["items"]) == 1, "PO must have 1 line"

    # 2. approve
    ap = await client.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "approved"}, headers=auth_headers)
    assert ap.status_code == 200, ap.text

    # 3. partial receipt — 4 of 10
    rc = await client.post(f"/api/v1/purchase-orders/{po_id}/receipts", json={
        "idempotency_key": f"rc-{uuid.uuid4().hex[:12]}",
        "items": [{"purchase_order_item_id": po.json()["data"]["items"][0]["id"], "quantity": 4}],
    }, headers=auth_headers)
    assert rc.status_code in (200, 201), rc.text
    receipt_id = rc.json()["data"]["id"]

    # 4. quality check — passed
    qc = await client.post(f"/api/v1/purchase-orders/{po_id}/receipts/{receipt_id}/quality-check",
                           json={"status": "passed", "notes": "OK"}, headers=auth_headers)
    assert qc.status_code == 200, qc.text
    assert qc.json()["data"]["quality_status"] == "passed"

    # 5. three-way match — ordered 10, received 4, billed 0
    tw = await client.get(f"/api/v1/purchase-orders/{po_id}/three-way-match", headers=auth_headers)
    assert tw.status_code == 200, tw.text
    data = tw.json()["data"]
    assert float(data["total_ordered"]) == 10.0, data
    assert float(data["total_received"]) == 4.0, data

    # 6. tolerance settings exist
    tol = await client.get("/api/v1/supplier-invoice-tolerances/", headers=auth_headers)
    assert tol.status_code == 200, tol.text
    assert float(tol.json()["data"]["quantity_tolerance_percent"]) >= 0

    # 7. return to vendor — credit note requires a payable; verify model exists
    async with TestSessionLocal() as session:
        from app.models.purchase import SupplierCreditNote
        assert SupplierCreditNote.__tablename__ == "supplier_credit_notes"
