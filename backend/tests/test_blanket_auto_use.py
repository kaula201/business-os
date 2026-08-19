"""Blanket order line auto-use in PO."""
import pytest

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"Blanket Supplier {suffix}", "code": f"BL-{suffix}",
        "identification_code": f"BLID-{suffix}", "is_vat_payer": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"BLP-{suffix}", "name": f"Blanket Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_warehouse(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/warehouses/", json={
        "code": f"BLW-{suffix}", "name": f"Blanket Warehouse {suffix}", "is_default": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_blanket_order_price_auto_applied_and_quantity_consumed(client, auth_headers, test_company):
    supplier = await _create_supplier(client, auth_headers, "A")
    product = await _create_product(client, auth_headers, "A")
    warehouse = await _create_warehouse(client, auth_headers, "A")

    # Create a blanket order with agreed price 3.0 for 100 units.
    bo = await client.post("/api/v1/procurement/blanket-orders", json={
        "supplier_id": supplier["id"], "title": "Blanket A",
        "lines": [{"product_id": product["id"], "quantity": 100, "unit_price": 3.0}],
    }, headers=auth_headers)
    assert bo.status_code == 201, bo.text
    bo_id = bo.json()["data"]["id"]

    # Activate it.
    act = await client.post(f"/api/v1/procurement/blanket-orders/{bo_id}/activate", headers=auth_headers)
    assert act.status_code == 200, act.text

    # Create a PO for 10 units at a different (higher) price 5.0.
    po = await client.post("/api/v1/purchase-orders/", json={
        "supplier_id": supplier["id"], "warehouse_id": warehouse["id"],
        "items": [{"product_id": product["id"], "quantity": 10, "unit_price": 5.0}],
    }, headers=auth_headers)
    assert po.status_code in (200, 201), po.text
    po_data = po.json()["data"]
    # Blanket price 3.0 should override the requested 5.0.
    assert float(po_data["items"][0]["unit_price"]) == 3.0
    assert float(po_data["items"][0]["line_subtotal"]) == 30.0

    # The blanket line's used_quantity should have increased by 10.
    blankets = await client.get("/api/v1/procurement/blanket-orders", headers=auth_headers)
    assert blankets.status_code == 200, blankets.text
    rows = blankets.json()["data"]
    assert len(rows) == 1
    assert float(rows[0]["lines"][0]["used_quantity"]) == 10.0
