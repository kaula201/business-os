"""POS split payment — one order paid with multiple methods."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos_extended import GiftCard, POSPayment
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_product(client, auth_headers) -> str:
    resp = await client.post("/api/v1/products/", json={
        "name": "Split Product", "sku": "SPL-1", "sale_price": 100,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_split_payment_cash_plus_gift_card(client, auth_headers, test_company, db_session):
    # gift card 50
    resp = await client.post("/api/v1/pos/gift-cards", params={"amount": 50}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    card = resp.json()["data"]

    resp = await client.post("/api/v1/pos/sessions", json={"name": "Split Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    product_id = await _make_product(client, auth_headers)

    # order 118 = 68 cash + 50 gift card
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
        "payments": [
            {"method": "cash", "amount": 68},
            {"method": "gift_card", "amount": 50, "gift_card_id": card["id"]},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert abs(order["total"] - 118.0) < 0.01

    # two payment rows + gift card balance reduced
    async with TestSessionLocal() as s:
        pays = (await s.execute(select(POSPayment).where(POSPayment.order_id == order["id"]))).scalars().all()
        assert len(pays) == 2
        methods = {p.payment_method: p.amount for p in pays}
        assert methods["cash"] == Decimal("68.00")
        assert methods["gift_card"] == Decimal("50.00")
        gc = (await s.execute(select(GiftCard).where(GiftCard.id == card["id"]))).scalar_one()
        assert gc.balance == Decimal("0.00")
        assert gc.status == "redeemed"


async def test_split_payment_mismatch_rejected(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Split Bad Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    product_id = await _make_product(client, auth_headers)

    # payments sum 100 ≠ order total 118 → 409
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
        "payments": [{"method": "cash", "amount": 100}],
    }, headers=auth_headers)
    assert resp.status_code == 409, resp.text
