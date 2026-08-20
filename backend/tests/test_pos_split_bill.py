"""POS split bill — one order split into multiple bills."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos import POSOrder
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_split_bill(client, auth_headers, test_company, db_session):
    from app.services.gl_posting import seed_default_accounts
    await seed_default_accounts(db_session, test_company.id)
    await db_session.commit()

    resp = await client.post("/api/v1/pos/sessions", json={"name": "Split Bill Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Pizza", "sku": "SPB-1", "sale_price": 30,
    }, headers=auth_headers)
    p1 = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Wine", "sku": "SPB-2", "sale_price": 20,
    }, headers=auth_headers)
    p2 = resp.json()["data"]["id"]

    # order: 2 pizza + 1 wine = 80 + 18% = 94.40
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [
            {"product_id": p1, "quantity": 2, "unit_price": 30},
            {"product_id": p2, "quantity": 1, "unit_price": 20},
        ],
        "payment_method": "cash",
    }, headers=auth_headers)
    order = resp.json()["data"]

    # split: part A = 1 pizza (35.40), part B = 1 pizza + wine (59.00)
    resp = await client.post(f"/api/v1/pos/orders/{order['id']}/split", json={
        "parts": [
            {"items": [{"product_id": p1, "quantity": 1}]},
            {"items": [{"product_id": p1, "quantity": 1}, {"product_id": p2, "quantity": 1}]},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    parts = resp.json()["data"]["parts"]
    assert len(parts) == 2
    assert abs(parts[0]["total"] - 35.40) < 0.01
    assert abs(parts[1]["total"] - 59.00) < 0.01

    # original marked split
    async with TestSessionLocal() as s:
        o = (await s.execute(select(POSOrder).where(POSOrder.id == order["id"]))).scalar_one()
        assert o.status == "split"

    # quantity mismatch → 409
    resp = await client.post(f"/api/v1/pos/orders/{order['id']}/split", json={
        "parts": [
            {"items": [{"product_id": p1, "quantity": 1}]},
            {"items": [{"product_id": p1, "quantity": 1}]},
        ],
    }, headers=auth_headers)
    assert resp.status_code == 409, resp.text
