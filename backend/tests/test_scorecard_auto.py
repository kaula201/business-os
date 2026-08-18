"""Vendor scorecard auto-calculation from goods receipts."""
import pytest

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"Score Supplier {suffix}", "code": f"SC-{suffix}",
        "identification_code": f"SCID-{suffix}", "is_vat_payer": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"SCP-{suffix}", "name": f"Score Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_warehouse(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/warehouses/", json={
        "code": f"SCW-{suffix}", "name": f"Score Warehouse {suffix}", "is_default": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_auto_calculate_scorecard_from_receipts(client, auth_headers, test_company):
    supplier = await _create_supplier(client, auth_headers, "A")
    product = await _create_product(client, auth_headers, "A")
    warehouse = await _create_warehouse(client, auth_headers, "A")

    # Create a PO with expected delivery in the past (so receipt is late).
    po = await client.post("/api/v1/purchase-orders/", json={
        "supplier_id": supplier["id"], "warehouse_id": warehouse["id"],
        "expected_delivery_date": "2026-07-01",
        "items": [{"product_id": product["id"], "quantity": 10, "unit_price": 5}],
    }, headers=auth_headers)
    assert po.status_code in (200, 201), po.text
    po_id = po.json()["data"]["id"]
    po_item_id = po.json()["data"]["items"][0]["id"]

    # Approve the PO so a goods receipt can be posted.
    appr = await client.patch(f"/api/v1/purchase-orders/{po_id}/status", json={"status": "approved"}, headers=auth_headers)
    assert appr.status_code == 200, appr.text

    # Post a goods receipt (received now, after the expected date -> late).
    gr = await client.post(f"/api/v1/purchase-orders/{po_id}/receipts", json={
        "idempotency_key": "score-test-1",
        "items": [{"purchase_order_item_id": po_item_id, "quantity": 10}],
    }, headers=auth_headers)
    assert gr.status_code in (200, 201), gr.text

    # Auto-calculate for the current period.
    period = "2026-08"
    calc = await client.post("/api/v1/procurement/scorecards/auto-calculate", params={"period": period}, headers=auth_headers)
    assert calc.status_code == 200, calc.text
    assert calc.json()["data"]["suppliers_updated"] == 1

    # The receipt was late (received after expected date) -> on-time rate 0.
    scorecards = await client.get("/api/v1/procurement/scorecards", params={"supplier_id": supplier["id"]}, headers=auth_headers)
    assert scorecards.status_code == 200, scorecards.text
    rows = scorecards.json()["data"]
    assert len(rows) == 1
    assert rows[0]["period"] == period
    assert rows[0]["on_time_delivery_rate"] == 0.0
    assert rows[0]["orders_count"] == 1
    assert rows[0]["on_time_orders"] == 0
