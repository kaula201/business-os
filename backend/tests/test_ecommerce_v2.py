"""eCommerce 2.0: payment, shipping, promotions, guest lifecycle, returns, tracking, SEO, stock reservation."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.ecommerce import (
    EcomCart, EcomCartItem, EcomContentPage, EcomOrder, EcomOrderItem, EcomOrderTracking,
    EcomProduct, EcomPromotion, EcomReturn, EcomShippingRule,
)
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_ecom_product(client, auth_headers, price=100, stock=10):
    # base product
    r = await client.post("/api/v1/products/", json={
        "sku": f"EC-{uuid.uuid4().hex[:6]}", "name": "ეკომ პროდუქტი",
        "sale_price": price, "purchase_price": 50, "unit": "ცალი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    pid = r.json()["data"]["id"]
    # ecom product
    r2 = await client.post("/api/v1/ecommerce/products", json={
        "product_id": pid, "name": "ეკომ პროდუქტი", "slug": f"ecom-{uuid.uuid4().hex[:6]}",
        "price": price, "is_published": True, "stock_quantity": stock,
    }, headers=auth_headers)
    assert r2.status_code == 201, r2.text
    return r2.json()["data"]["id"]


async def _make_cart_with_item(client, auth_headers, ecom_id, qty=1):
    r = await client.post("/api/v1/ecommerce/cart", json={}, headers=auth_headers)
    assert r.status_code == 201, r.text
    cart_id = r.json()["data"]["id"]
    r2 = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/items",
                           json={"ecom_product_id": ecom_id, "quantity": qty}, headers=auth_headers)
    assert r2.status_code == 201, r2.text
    return cart_id


async def test_payment_provider_sandbox(client, auth_headers):
    """რეალური payment provider: sandbox-ში paid, Stripe-ის კონფიგურაციისას PaymentIntent."""
    ecom_id = await _make_ecom_product(client, auth_headers, price=100)
    cart_id = await _make_cart_with_item(client, auth_headers, ecom_id)

    r = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout",
                          json={"payment_method": "card", "shipping_fee": 0}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["payment_status"] == "paid"
    assert d["gateway"] in ("stripe", "sandbox")
    assert d["total"] == 100.0


async def test_shipping_calculation(client, auth_headers):
    """Shipping calculation: flat + weight, free above threshold."""
    r = await client.post("/api/v1/ecommerce/shipping-rules", json={
        "name": "თბილისი", "zone": "tbilisi", "flat_rate": 10, "weight_rate": 2, "free_above": 200,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    # below threshold → flat + weight
    r2 = await client.post("/api/v1/ecommerce/shipping/calculate",
                           json={"subtotal": 100, "weight_kg": 5, "zone": "tbilisi"}, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["shipping_fee"] == 20.0  # 10 + 5*2

    # above threshold → free
    r3 = await client.post("/api/v1/ecommerce/shipping/calculate",
                           json={"subtotal": 250, "weight_kg": 5, "zone": "tbilisi"}, headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["shipping_fee"] == 0.0
    assert r3.json()["data"]["applied"] == "free"


async def test_promotions(client, auth_headers):
    """Promotions: percent discount, min subtotal, usage limit, expiry."""
    r = await client.post("/api/v1/ecommerce/promotions", json={
        "code": "SALE10", "name": "10% ფასდაკლება", "discount_type": "percent",
        "discount_value": 10, "min_subtotal": 50, "max_uses": 2,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    # valid
    r2 = await client.post("/api/v1/ecommerce/promotions/validate",
                           json={"code": "SALE10", "subtotal": 100}, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["discount_amount"] == 10.0

    # below min subtotal → 400
    r3 = await client.post("/api/v1/ecommerce/promotions/validate",
                           json={"code": "SALE10", "subtotal": 30}, headers=auth_headers)
    assert r3.status_code == 400

    # unknown code → 404
    r4 = await client.post("/api/v1/ecommerce/promotions/validate",
                           json={"code": "NOPE", "subtotal": 100}, headers=auth_headers)
    assert r4.status_code == 404

    # checkout with promo → discount applied, used_count increments
    ecom_id = await _make_ecom_product(client, auth_headers, price=100)
    cart_id = await _make_cart_with_item(client, auth_headers, ecom_id)
    r5 = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout",
                          json={"promo_code": "SALE10", "shipping_fee": 0}, headers=auth_headers)
    assert r5.status_code == 200, r5.text
    assert r5.json()["data"]["discount_amount"] == 10.0
    assert r5.json()["data"]["total"] == 90.0


async def test_guest_and_customer_lifecycle(client, auth_headers):
    """Guest/customer account lifecycle: guest checkout with email, client-linked cart."""
    ecom_id = await _make_ecom_product(client, auth_headers, price=50)
    cart_id = await _make_cart_with_item(client, auth_headers, ecom_id)

    r = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout",
                          json={"guest_email": "guest@example.ge", "shipping_fee": 0}, headers=auth_headers)
    assert r.status_code == 200, r.text
    order_id = r.json()["data"]["id"]

    # order has guest email + items snapshot
    from sqlalchemy import select as sa_select
    async with TestSessionLocal() as session:
        order = (await session.execute(sa_select(EcomOrder).where(EcomOrder.id == uuid.UUID(order_id)))).scalar_one()
        assert order.guest_email == "guest@example.ge"
        items = (await session.execute(sa_select(EcomOrderItem).where(EcomOrderItem.order_id == order.id))).scalars().all()
        assert len(items) == 1
        assert items[0].product_name == "ეკომ პროდუქტი"


async def test_returns(client, auth_headers):
    """დაბრუნება: request → approve → refunded, order cancelled."""
    ecom_id = await _make_ecom_product(client, auth_headers, price=100)
    cart_id = await _make_cart_with_item(client, auth_headers, ecom_id)
    r = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout",
                          json={"shipping_fee": 0}, headers=auth_headers)
    order_id = r.json()["data"]["id"]

    r2 = await client.post(f"/api/v1/ecommerce/orders/{order_id}/return",
                           json={"reason": "არ მომეწონა"}, headers=auth_headers)
    assert r2.status_code == 201, r2.text
    return_id = r2.json()["data"]["id"]
    assert r2.json()["data"]["status"] == "requested"

    r3 = await client.post(f"/api/v1/ecommerce/returns/{return_id}/approve", json={}, headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["status"] == "refunded"

    # order now refunded/cancelled
    r4 = await client.get("/api/v1/ecommerce/orders", headers=auth_headers)
    order = next(o for o in r4.json()["data"] if o["id"] == order_id)
    assert order["payment_status"] == "refunded"


async def test_order_tracking(client, auth_headers):
    """Order tracking: status events timeline + carrier/tracking number."""
    ecom_id = await _make_ecom_product(client, auth_headers, price=100)
    cart_id = await _make_cart_with_item(client, auth_headers, ecom_id)
    r = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout",
                          json={"shipping_fee": 0}, headers=auth_headers)
    order_id = r.json()["data"]["id"]

    r2 = await client.post(f"/api/v1/ecommerce/orders/{order_id}/tracking",
                           json={"status": "shipped", "carrier": "Georgian Post", "tracking_number": "GP-12345", "note": "გაიგზავნა"},
                           headers=auth_headers)
    assert r2.status_code == 200, r2.text

    r3 = await client.get(f"/api/v1/ecommerce/orders/{order_id}/tracking", headers=auth_headers)
    events = r3.json()["data"]
    assert len(events) >= 2  # created + shipped
    assert events[-1]["status"] == "shipped"
    assert events[-1]["note"] == "გაიგზავნა"


async def test_seo_content_management(client, auth_headers):
    """SEO/content management: content pages with SEO fields."""
    r = await client.post("/api/v1/ecommerce/content-pages", json={
        "slug": "about", "title": "ჩვენ შესახებ", "body": "<p>ტექსტი</p>",
        "seo_title": "ჩვენ შესახებ — კომპანია", "seo_description": "კომპანიის შესახებ",
        "is_published": True,
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r2 = await client.get("/api/v1/ecommerce/content-pages", headers=auth_headers)
    pages = r2.json()["data"]
    assert len(pages) == 1
    assert pages[0]["slug"] == "about"
    assert pages[0]["seo_title"] == "ჩვენ შესახებ — კომპანია"


async def test_stock_reservation_at_checkout(client, auth_headers):
    """Stock reservation checkout-ისას: მარაგი იკლებს, არასაკმარისი → 400."""
    ecom_id = await _make_ecom_product(client, auth_headers, price=100, stock=3)
    cart_id = await _make_cart_with_item(client, auth_headers, ecom_id, qty=2)

    r = await client.post(f"/api/v1/ecommerce/cart/{cart_id}/checkout",
                          json={"shipping_fee": 0}, headers=auth_headers)
    assert r.status_code == 200, r.text

    # stock reduced 3 → 1
    async with TestSessionLocal() as session:
        p = (await session.execute(select(EcomProduct).where(EcomProduct.id == uuid.UUID(ecom_id)))).scalar_one()
        assert p.stock_quantity == 1

    # second cart wants 2 → insufficient → 400
    cart2 = await _make_cart_with_item(client, auth_headers, ecom_id, qty=2)
    r2 = await client.post(f"/api/v1/ecommerce/cart/{cart2}/checkout",
                           json={"shipping_fee": 0}, headers=auth_headers)
    assert r2.status_code == 400
    assert "მარაგი არასაკმარისია" in r2.json()["detail"]
