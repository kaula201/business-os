"""Replenishment depth: safety stock and lead time."""
import pytest

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"Repl Supplier {suffix}", "code": f"RE-{suffix}",
        "identification_code": f"REID-{suffix}", "is_vat_payer": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"REP-{suffix}", "name": f"Repl Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_warehouse(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/warehouses/", json={
        "code": f"REW-{suffix}", "name": f"Repl Warehouse {suffix}", "is_default": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_replenishment_uses_safety_stock_and_lead_time(client, auth_headers, test_company):
    supplier = await _create_supplier(client, auth_headers, "A")
    product = await _create_product(client, auth_headers, "A")
    warehouse = await _create_warehouse(client, auth_headers, "A")

    # Rule: min 0, safety_stock 5, lead_time 7 days. On-hand is 0 -> below safety stock.
    rule = await client.post("/api/v1/wms-ops/replenishment-rules", json={
        "warehouse_id": warehouse["id"], "product_id": product["id"], "supplier_id": supplier["id"],
        "min_quantity": 0, "max_quantity": 20, "reorder_quantity": 10,
        "safety_stock": 5, "lead_time_days": 7,
    }, headers=auth_headers)
    assert rule.status_code == 201, rule.text

    # Suggestions should trigger because on-hand (0) < safety_stock (5).
    sugg = await client.get("/api/v1/wms-ops/replenishment/suggestions", headers=auth_headers)
    assert sugg.status_code == 200, sugg.text
    assert len(sugg.json()["data"]) == 1

    # Auto-replenish creates a PO with expected delivery = today + lead_time (7 days).
    ar = await client.post("/api/v1/procurement/auto-replenish", headers=auth_headers)
    assert ar.status_code == 200, ar.text
    data = ar.json()["data"]
    assert data["created"] is True
    po_id = data["purchase_order_id"]

    po = await client.get(f"/api/v1/purchase-orders/{po_id}", headers=auth_headers)
    assert po.status_code == 200, po.text
    po_data = po.json()["data"]
    assert po_data["status"] == "draft"
    assert len(po_data["items"]) == 1
    assert float(po_data["items"][0]["quantity"]) == 10.0
    # expected_delivery_date should be ~7 days from today.
    from datetime import date, timedelta
    expected = date.today() + timedelta(days=7)
    assert po_data["expected_delivery_date"] == expected.isoformat()
