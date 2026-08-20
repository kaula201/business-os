"""POS tips — added on top of the total, not VAT-able."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos import POSOrder
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_tip_added_to_total(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Tip Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Tip Product", "sku": "TIP-1", "sale_price": 100,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    # 100 + 18% VAT = 118, tip 10 → total 128
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
        "tip_amount": 10,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert abs(order["total"] - 128.0) < 0.01
    assert abs(order["tip_amount"] - 10.0) < 0.01
    assert abs(order["vat_amount"] - 18.0) < 0.01  # VAT unchanged by tip

    async with TestSessionLocal() as s:
        o = (await s.execute(select(POSOrder).where(POSOrder.id == order["id"]))).scalar_one()
        assert o.tip_amount == Decimal("10.00")
        assert o.total == Decimal("128.00")
