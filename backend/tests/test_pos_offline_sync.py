"""POS offline sync — queued order actually becomes a POS order."""
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.pos import POSOfflineQueue, POSOrder
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _make_product(client, auth_headers) -> str:
    resp = await client.post("/api/v1/products/", json={
        "name": "Offline Product", "sku": "OFF-1", "sale_price": 50,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]["id"]


async def test_offline_sync_creates_order(client, auth_headers, test_company, db_session):
    # open session
    resp = await client.post("/api/v1/pos/sessions", json={"name": "Offline Shift"}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    session_id = resp.json()["data"]["id"]

    product_id = await _make_product(client, auth_headers)

    # queue an offline order (as the frontend would)
    resp = await client.post("/api/v1/pos/offline/queue", params={"device_id": "dev-1"}, json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 50}],
        "payment_method": "cash",
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    queue_id = resp.json()["data"]["id"]

    # sync → real POS order created
    resp = await client.post(f"/api/v1/pos/offline/queue/{queue_id}/sync", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["order_number"].startswith("POS-")
    assert abs(data["total"] - 118.0) < 0.01  # 100 + 18% VAT

    # order persisted
    async with TestSessionLocal() as s:
        order = (await s.execute(select(POSOrder).where(POSOrder.id == data["order_id"]))).scalar_one()
        assert order.total == Decimal("118.00")
        assert str(order.session_id) == session_id
        q = (await s.execute(select(POSOfflineQueue).where(POSOfflineQueue.id == queue_id))).scalar_one()
        assert q.status == "synced"

    # double sync → 409
    resp = await client.post(f"/api/v1/pos/offline/queue/{queue_id}/sync", headers=auth_headers)
    assert resp.status_code == 409, resp.text
