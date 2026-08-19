"""POS discounts — line-level and order-level."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos import POSOrder, POSOrderItem
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_product(client, auth_headers, sku="DISC-1", price=100) -> str:
    resp = await client.post("/api/v1/products/", json={
        "name": f"Disc {sku}", "sku": sku, "sale_price": price,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_line_discount_percent(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Disc Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    product_id = await _make_product(client, auth_headers)

    # 2 × 100 with 10% line discount → gross 200, discount 20, net 180, VAT 32.40, total 212.40
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 100, "discount_percent": 10}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert abs(order["subtotal"] - 180.0) < 0.01
    assert abs(order["discount_amount"] - 20.0) < 0.01
    assert abs(order["vat_amount"] - 32.40) < 0.01
    assert abs(order["total"] - 212.40) < 0.01

    async with TestSessionLocal() as s:
        item = (await s.execute(select(POSOrderItem).where(POSOrderItem.pos_order_id == order["id"]))).scalar_one()
        assert item.discount_amount == Decimal("20.00")
        assert item.line_total == Decimal("180.00")


async def test_order_level_discount(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Disc Order Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    product_id = await _make_product(client, auth_headers)

    # 1 × 100 with 10 GEL order discount → net 90, VAT 16.20, total 106.20
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
        "discount_amount": 10,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert abs(order["subtotal"] - 90.0) < 0.01
    assert abs(order["discount_amount"] - 10.0) < 0.01
    assert abs(order["vat_amount"] - 16.20) < 0.01
    assert abs(order["total"] - 106.20) < 0.01
