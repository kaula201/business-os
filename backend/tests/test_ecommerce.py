"""eCommerce — cart, checkout, orders flow."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_ecom_product(client, auth_headers) -> str:
    base = await client.post("/api/v1/products/", json={
        "name": f"Base-{uuid.uuid4().hex[:6]}", "sku": f"SKU-{uuid.uuid4().hex[:6]}",
        "sale_price": 100, "purchase_price": 40,
    }, headers=auth_headers)
    assert base.status_code in (200, 201), base.text
    base_id = base.json()["data"]["id"]

    p = await client.post("/api/v1/ecommerce/products", json={
        "product_id": base_id,
        "name": f"Ecom-{uuid.uuid4().hex[:6]}",
        "slug": f"ecom-{uuid.uuid4().hex[:6]}",
        "price": 120.50,
        "stock_quantity": 10,
    }, headers=auth_headers)
    assert p.status_code in (200, 201), p.text
    return p.json()["data"]["id"]


async def test_cart_add_item_and_get(client, auth_headers):
    pid = await _seed_ecom_product(client, auth_headers)

    cart = await client.post("/api/v1/ecommerce/cart", json={}, headers=auth_headers)
    assert cart.status_code == 201, cart.text
    cart_id = cart.json()["data"]["id"]

    item = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/items", json={
        "ecom_product_id": pid, "quantity": 3,
    }, headers=auth_headers)
    assert item.status_code == 201, item.text
    assert float(item.json()["data"]["unit_price"]) == 120.50

    got = await client.get(f"/api/v1/ecommerce/cart/{cart_id}", headers=auth_headers)
    assert got.status_code == 200, got.text
    data = got.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 3
    assert float(data["subtotal"]) == 361.50


async def test_checkout_creates_order(client, auth_headers):
    pid = await _seed_ecom_product(client, auth_headers)

    cart = await client.post("/api/v1/ecommerce/cart", json={}, headers=auth_headers)
    cart_id = cart.json()["data"]["id"]
    await client.post(f"/api/v1/ecommerce/cart/{cart_id}/items", json={
        "ecom_product_id": pid, "quantity": 2,
    }, headers=auth_headers)

    co = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout", json={
        "shipping_fee": 10, "payment_method": "card",
    }, headers=auth_headers)
    assert co.status_code == 200, co.text
    data = co.json()["data"]
    assert data["order_number"].startswith("ECOMM-")
    assert float(data["total"]) == 251.00  # 2*120.50 + 10

    orders = await client.get("/api/v1/ecommerce/orders", headers=auth_headers)
    assert orders.status_code == 200, orders.text
    assert len(orders.json()["data"]) == 1
    assert orders.json()["data"][0]["status"] == "paid"  # sandbox gateway marks paid
    assert orders.json()["data"][0]["payment_status"] == "paid"


async def test_checkout_empty_cart_rejected(client, auth_headers):
    cart = await client.post("/api/v1/ecommerce/cart", json={}, headers=auth_headers)
    cart_id = cart.json()["data"]["id"]

    co = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout", json={}, headers=auth_headers)
    assert co.status_code == 422, co.text
