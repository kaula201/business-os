"""PO version increments on status change."""
import pytest

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"Ver Supplier {suffix}", "code": f"VE-{suffix}",
        "identification_code": f"VEID-{suffix}", "is_vat_payer": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"VEP-{suffix}", "name": f"Ver Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_warehouse(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/warehouses/", json={
        "code": f"VEW-{suffix}", "name": f"Ver Warehouse {suffix}", "is_default": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_po_version_increments_on_status_change(client, auth_headers, test_company):
    supplier = await _create_supplier(client, auth_headers, "A")
    product = await _create_product(client, auth_headers, "A")
    warehouse = await _create_warehouse(client, auth_headers, "A")

    po = await client.post("/api/v1/purchase-orders/", json={
        "supplier_id": supplier["id"], "warehouse_id": warehouse["id"],
        "items": [{"product_id": product["id"], "quantity": 10, "unit_price": 5}],
    }, headers=auth_headers)
    assert po.status_code in (200, 201), po.text
    po_id = po.json()["data"]["id"]
    assert po.json()["data"]["version"] == 1

    # Approve -> version 2.
    appr = await client.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "approved"}, headers=auth_headers)
    assert appr.status_code == 200, appr.text
    assert appr.json()["data"]["version"] == 2

    # History should have 2 entries (draft + approved).
    hist = await client.get(f"/api/v1/purchase-orders/{po_id}/history", headers=auth_headers)
    assert hist.status_code == 200, hist.text
    assert len(hist.json()["data"]) == 2
