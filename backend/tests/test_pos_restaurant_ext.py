"""Restaurant courses, floor plan and ESC/POS printing."""
import base64

import pytest
from sqlalchemy import select

from app.models.pos import POSOrderItem
from app.models.pos_restaurant import RestaurantTable
from app.services.escpos import build_receipt, open_cash_drawer
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_course_on_order_item(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Course Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Soup", "sku": "CRS-1", "sale_price": 20,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 20, "course": "starter"}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    order = resp.json()["data"]

    async with TestSessionLocal() as s:
        item = (await s.execute(select(POSOrderItem).where(POSOrderItem.pos_order_id == order["id"]))).scalar_one()
        assert item.course == "starter"


async def test_table_position(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/tables", params={"name": "T1", "capacity": 2}, headers=auth_headers)
    table = resp.json()["data"]

    resp = await client.patch(f"/api/v1/pos/tables/{table['id']}/position", params={"pos_x": 120, "pos_y": 80}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pos_x"] == 120

    async with TestSessionLocal() as s:
        t = (await s.execute(select(RestaurantTable).where(RestaurantTable.id == table["id"]))).scalar_one()
        assert t.pos_x == 120
        assert t.pos_y == 80


async def test_escpos_stream(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Print Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Print Product", "sku": "PRT-1", "sale_price": 50,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 50}],
        "payment_method": "cash",
    }, headers=auth_headers)
    order = resp.json()["data"]

    resp = await client.get(f"/api/v1/pos/orders/{order['id']}/escpos", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    stream = base64.b64decode(data["escpos_base64"])
    assert stream.startswith(b"\x1b@")  # ESC/POS init
    assert b"Print Product" in stream
    assert data["drawer_base64"]  # cash drawer command present

    # unit-level: build_receipt + drawer
    raw = build_receipt({"order_number": "T-1", "items": [], "subtotal": 0, "vat_amount": 0, "total": 0})
    assert raw.startswith(b"\x1b@")
    assert open_cash_drawer().startswith(b"\x1b@")
