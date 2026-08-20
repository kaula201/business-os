"""Client price lists — client-specific prices override sale price at POS."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos_pricelist import ClientPriceList
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_client(client, auth_headers) -> str:
    resp = await client.post("/api/v1/clients/", json={
        "name": "PL Client", "client_type": "individual", "identification_code": "PL-001",
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_client_price_override(client, auth_headers, test_company, db_session):
    client_id = await _make_client(client, auth_headers)
    resp = await client.post("/api/v1/pos/sessions", json={"name": "PL Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "PL Product", "sku": "PL-1", "sale_price": 100,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    # set client-specific price 80
    resp = await client.post("/api/v1/pos/price-lists", params={
        "client_id": client_id, "product_id": product_id, "price": 80,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text

    # order with client → price 80 (not 100): 80 + 18% = 94.40
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "client_id": client_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]
    assert abs(order["subtotal"] - 80.0) < 0.01
    assert abs(order["total"] - 94.40) < 0.01

    # without client → default price 100
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 100}],
        "payment_method": "cash",
    }, headers=auth_headers)
    order2 = resp.json()["data"]
    assert abs(order2["subtotal"] - 100.0) < 0.01

    # delete price → back to default
    resp = await client.get("/api/v1/pos/price-lists", params={"client_id": client_id}, headers=auth_headers)
    pl_id = resp.json()["data"][0]["id"]
    resp = await client.delete(f"/api/v1/pos/price-lists/{pl_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
