"""P1-4: WMS — batch + expiry + picking + replenishment E2E."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.product import Product
from app.models.warehouse import ProductBatch, Warehouse
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        wh = Warehouse(company_id=test_company.id, name="WMS WH", code="WMS1", is_active=True)
        prod = Product(company_id=test_company.id, sku=f"WMS-{uuid.uuid4().hex[:6]}",
                       name="WMS Product", sale_price=100, purchase_price=60, current_stock=0, min_stock=5)
        session.add_all([wh, prod])
        await session.commit()
        return {"warehouse_id": str(wh.id), "product_id": str(prod.id)}


async def test_wms_batch_expiry_pick_replenish(client, auth_headers, test_company):
    seeded = await _seed(client, auth_headers, test_company)

    # 1. Batch with expiry 30 days out
    batch = await client.post("/api/v1/wms/batches", json={
        "product_id": seeded["product_id"], "warehouse_id": seeded["warehouse_id"],
        "batch_number": f"B-{uuid.uuid4().hex[:6]}",
        "production_date": "2026-08-01",
        "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
        "quantity": 20, "unit_cost": 60,
    }, headers=auth_headers)
    assert batch.status_code == 201, batch.text
    batch_id = batch.json()["data"]["id"]

    # 2. Batch visible in expiring-soon list (30-day window)
    expiring = await client.get("/api/v1/wms/batches", params={"expiring_soon": True}, headers=auth_headers)
    assert expiring.status_code == 200, expiring.text
    assert any(b["id"] == batch_id for b in expiring.json()["data"]), "batch not in expiring list"

    # 3. Replenishment suggestion (stock 20 >= min 5 → no suggestion)
    sugg = await client.get("/api/v1/wms-ops/replenishment/suggestions", headers=auth_headers)
    assert sugg.status_code == 200, sugg.text
    assert not any(s["product_id"] == seeded["product_id"] for s in sugg.json()["data"]), "no suggestion expected at stock 20"

    # 4. Pick list from batch
    pl = await client.post("/api/v1/wms-ops/pick-lists", json={
        "warehouse_id": seeded["warehouse_id"],
        "items": [{"product_id": seeded["product_id"], "quantity": 5, "batch_number": f"B-{uuid.uuid4().hex[:6]}"}],
    }, headers=auth_headers)
    assert pl.status_code == 201, pl.text
    pick_list_id = pl.json()["data"]["id"]

    # 4b. Pick the item (need the PickListItem id)
    async with TestSessionLocal() as s:
        from app.models.wms_ops import PickListItem
        item = (await s.execute(select(PickListItem).where(PickListItem.pick_list_id == pick_list_id))).scalar_one()
        pick_item_id = str(item.id)
    picked = await client.post(f"/api/v1/wms-ops/pick-lists/{pick_list_id}/pick", json={
        "item_id": pick_item_id, "quantity": 5,
    }, headers=auth_headers)
    assert picked.status_code == 200, picked.text

    # 5. Complete pick → stock decreases
    done = await client.post(f"/api/v1/wms-ops/pick-lists/{pick_list_id}/complete", headers=auth_headers)
    assert done.status_code == 200, done.text

    async with TestSessionLocal() as s:
        prod = (await s.execute(select(Product).where(Product.id == seeded["product_id"]))).scalar_one()
        assert prod.current_stock == 15.0, f"stock={prod.current_stock}"
