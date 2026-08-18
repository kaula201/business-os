"""Vendor price history / trend."""
import pytest

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"Trend Supplier {suffix}", "code": f"TR-{suffix}",
        "identification_code": f"TRID-{suffix}", "is_vat_payer": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"TRP-{suffix}", "name": f"Trend Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_price_history_records_snapshots_and_trend(client, auth_headers, test_company):
    supplier = await _create_supplier(client, auth_headers, "A")
    product = await _create_product(client, auth_headers, "A")

    # Initial price 50.
    r1 = await client.post("/api/v1/procurement/price-lists", json={
        "supplier_id": supplier["id"], "product_id": product["id"], "price": 50, "currency": "GEL",
    }, headers=auth_headers)
    assert r1.status_code == 201, r1.text

    # Update to 60 -> records a snapshot of the old price (50).
    r2 = await client.post("/api/v1/procurement/price-lists", json={
        "supplier_id": supplier["id"], "product_id": product["id"], "price": 60, "currency": "GEL",
    }, headers=auth_headers)
    assert r2.status_code == 201, r2.text

    # Update to 70 -> records a snapshot of 60.
    r3 = await client.post("/api/v1/procurement/price-lists", json={
        "supplier_id": supplier["id"], "product_id": product["id"], "price": 70, "currency": "GEL",
    }, headers=auth_headers)
    assert r3.status_code == 201, r3.text

    trend = await client.get("/api/v1/procurement/price-trend", params={"supplier_id": supplier["id"]}, headers=auth_headers)
    assert trend.status_code == 200, trend.text
    rows = trend.json()["data"]
    # Two snapshots: 50 and 60 (the current 70 is not yet a snapshot).
    assert len(rows) == 2
    prices = sorted(r["price"] for r in rows)
    assert prices == [50.0, 60.0]
    assert all(r["supplier_id"] == supplier["id"] for r in rows)
