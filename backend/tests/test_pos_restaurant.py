"""Restaurant POS: tables, order types, self-ordering (QR)."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos_restaurant import RestaurantTable, SelfOrderSession
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_product(client, auth_headers) -> str:
    resp = await client.post("/api/v1/products/", json={
        "name": "Pizza Margherita", "sku": "PIZZA-1", "sale_price": 25,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_tables_and_order_types(client, auth_headers, test_company, db_session):
    # create table
    resp = await client.post("/api/v1/pos/tables", params={"name": "Table 1", "capacity": 4}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    table = resp.json()["data"]
    assert table["qr_code"].startswith("QR-")

    # occupy / free
    resp = await client.post(f"/api/v1/pos/tables/{table['id']}/occupy", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "occupied"
    resp = await client.post(f"/api/v1/pos/tables/{table['id']}/free", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "free"

    # order type
    resp = await client.post("/api/v1/pos/order-types", params={"code": "dine_in", "name": "ადგილზე"}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    resp = await client.post("/api/v1/pos/order-types", params={"code": "dine_in", "name": "ადგილზე"}, headers=auth_headers)
    assert resp.status_code == 409, resp.text  # duplicate


async def test_self_order_flow(client, auth_headers, test_company, db_session):
    # open POS session
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Restaurant Shift"}, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    # table + self-order session
    resp = await client.post("/api/v1/pos/tables", params={"name": "Table 2", "capacity": 2}, headers=auth_headers)
    table = resp.json()["data"]
    resp = await client.post("/api/v1/pos/self-order/start", params={"table_id": table["id"]}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]["token"]

    # product + submit order
    product_id = await _make_product(client, auth_headers)
    resp = await client.post(f"/api/v1/pos/self-order/{token}/submit", json={
        "items": [{"product_id": product_id, "quantity": 2}],
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["order_number"].startswith("SO-")
    assert abs(data["total"] - 59.0) < 0.01  # 25*2 + 18% VAT

    # table now occupied with the order
    async with TestSessionLocal() as s:
        t = (await s.execute(select(RestaurantTable).where(RestaurantTable.id == table["id"]))).scalar_one()
        assert t.status == "occupied"
        assert t.current_order_id is not None
        so = (await s.execute(select(SelfOrderSession).where(SelfOrderSession.token == token))).scalar_one()
        assert so.status == "closed"
