"""POS cash rounding — 1 tetri rounding for cash payments (GE law)."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos import POSOrder
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_product(client, auth_headers, sku="RND-1", price=100) -> str:
    resp = await client.post("/api/v1/products/", json={
        "name": f"Rnd {sku}", "sku": sku, "sale_price": float(price),
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_cash_rounding_applied(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Rnd Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    # price 33.33 → 1 × 33.33 → VAT 6.00 → total 39.33 (already 0.01-aligned)
    product_id = await _make_product(client, auth_headers, sku="RND-2", price=33.33)

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 33.33}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    # 33.33 + 18% = 39.3294 → rounded to 39.33, rounding = 0.00
    assert abs(order["total"] - 39.33) < 0.01
    assert abs(order["rounding_amount"] - 0.0) < 0.01


async def test_cash_rounding_rounds_up(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Rnd Up Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    # 3 × 33.33 = 99.99 → VAT 18.00 → total 117.99 (already aligned)
    # 1 × 33.34 → VAT 6.00 → total 39.34
    product_id = await _make_product(client, auth_headers, sku="RND-3", price=33.34)

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 33.34}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    # 33.34 + 18% = 39.3412 → rounded to 39.34, rounding = -0.00
    assert abs(order["total"] - 39.34) < 0.01
