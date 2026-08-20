"""Kitchen display system (KDS) — queue and status updates."""
import pytest
from sqlalchemy import select

from app.models.pos import POSOrder
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def test_kitchen_queue_and_status(client, auth_headers, test_company, db_session):
    resp = await client.post("/api/v1/pos/sessions", json={"name": "KDS Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "KDS Product", "sku": "KDS-1", "sale_price": 30,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 2, "unit_price": 30}],
        "payment_method": "cash",
    }, headers=auth_headers)
    order = resp.json()["data"]

    # new order appears in the kitchen queue
    resp = await client.get("/api/v1/pos/kitchen/queue", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    queue = resp.json()["data"]
    assert any(o["id"] == order["id"] and o["kitchen_status"] == "new" for o in queue)

    # move to preparing → done
    resp = await client.patch(f"/api/v1/pos/orders/{order['id']}/kitchen-status", params={"status": "preparing"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.patch(f"/api/v1/pos/orders/{order['id']}/kitchen-status", params={"status": "done"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text

    # done order leaves the queue
    resp = await client.get("/api/v1/pos/kitchen/queue", headers=auth_headers)
    queue = resp.json()["data"]
    assert not any(o["id"] == order["id"] for o in queue)

    async with TestSessionLocal() as s:
        o = (await s.execute(select(POSOrder).where(POSOrder.id == order["id"]))).scalar_one()
        assert o.kitchen_status == "done"
