"""POS loyalty tiers and coupons."""
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.pos import POSCoupon, POSLoyaltyAccount
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_client(client, auth_headers) -> str:
    resp = await client.post("/api/v1/clients/", json={
        "name": "Loyal Client", "client_type": "individual", "identification_code": f"{uuid4().int % 90000000000 + 10000000000}",
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_loyalty_tier_upgrade(client, auth_headers, test_company, db_session):
    client_id = await _make_client(client, auth_headers)
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Tier Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Tier Product", "sku": "TIER-1", "sale_price": 600,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    # 600 + 18% = 708 points → silver (>= 1000? no, 708 < 1000 → bronze)
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id, "client_id": client_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 600}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    async with TestSessionLocal() as s:
        acc = (await s.execute(select(POSLoyaltyAccount).where(POSLoyaltyAccount.client_id == client_id))).scalar_one()
        assert acc.total_earned == Decimal("708.00")
        assert acc.tier == "bronze"

    # second order → 1416 total → silver
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id, "client_id": client_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 600}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    async with TestSessionLocal() as s:
        acc = (await s.execute(select(POSLoyaltyAccount).where(POSLoyaltyAccount.client_id == client_id))).scalar_one()
        assert acc.total_earned == Decimal("1416.00")
        assert acc.tier == "silver"


async def test_coupon_validate_and_limits(client, auth_headers, test_company, db_session):
    # create coupon 10% / 1 use
    resp = await client.post("/api/v1/pos/coupons", params={
        "code": "SAVE10", "discount_percent": 10, "max_uses": 1,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    # validate → ok
    resp = await client.post("/api/v1/pos/coupons/validate", params={"code": "SAVE10"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["discount_percent"] == 10.0

    # wrong code → 404
    resp = await client.post("/api/v1/pos/coupons/validate", params={"code": "NOPE"}, headers=auth_headers)
    assert resp.status_code == 404, resp.text

    # duplicate code → 409
    resp = await client.post("/api/v1/pos/coupons", params={"code": "SAVE10", "discount_percent": 5}, headers=auth_headers)
    assert resp.status_code == 409, resp.text
