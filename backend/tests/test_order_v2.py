"""Order 2.0: backorder, carrier/route, drop-ship, RMA, serial/lot, picking, credit-limit approval."""
import pytest
from uuid import uuid4

from app.models.order import Order, OrderFulfillment, OrderItem, OrderReturn


async def _make_client(client, auth_headers):
    r = await client.post("/api/v1/clients/", json={
        "client_type": "legal", "name": "შეკვეთის კლიენტი", "identification_code": f"ORD-{uuid4().hex[:6]}",
    }, headers=auth_headers)
    return r.json()["data"]["id"]


async def _make_order(client, auth_headers, cid):
    r = await client.post("/api/v1/orders/", json={
        "client_id": cid,
        "items": [{"product_name": "პროდუქტი A", "quantity": 2, "unit_price": 500}],
        "is_vat_payer": True,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_backorder_management(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    o = await _make_order(client, auth_headers, cid)

    r = await client.patch(f"/api/v1/orders/{o['id']}/backorder", json={
        "backorder_status": "partial", "backorder_quantity": 1,
        "backorder_eta": "2026-10-01T00:00:00",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["backorder_status"] == "partial"
    assert r.json()["data"]["backorder_quantity"] == 1


@pytest.mark.asyncio
async def test_fulfillment_carrier_and_picking(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    o = await _make_order(client, auth_headers, cid)

    # attach fulfillment (warehouse needed)
    from app.models.warehouse import Warehouse
    wh = Warehouse(company_id=test_company.id, name="მთავარი საწყობი", code="WH1")
    db_session.add(wh)
    await db_session.flush()
    f = OrderFulfillment(company_id=test_company.id, order_id=o["id"], warehouse_id=wh.id)
    db_session.add(f)
    await db_session.commit()

    # picking
    r = await client.patch(f"/api/v1/orders/{o['id']}/fulfillment", json={
        "picked_at": "2026-09-05T10:00:00", "packed_at": "2026-09-05T11:00:00",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text

    # carrier + tracking → status auto shipping
    r = await client.patch(f"/api/v1/orders/{o['id']}/fulfillment", json={
        "carrier": "Georgian Post", "tracking_number": "GP-12345",
        "shipping_method": "standard", "shipped_at": "2026-09-05T12:00:00",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["carrier"] == "Georgian Post"
    assert r.json()["data"]["tracking_number"] == "GP-12345"

    # delivered → completed
    r = await client.patch(f"/api/v1/orders/{o['id']}/fulfillment", json={
        "delivered_at": "2026-09-06T10:00:00",
    }, headers=auth_headers)
    assert r.status_code == 200
    order = (await db_session.execute(__import__("sqlalchemy").select(Order).where(Order.id == o["id"]))).scalar_one()
    assert order.status == "completed"


@pytest.mark.asyncio
async def test_drop_shipping(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    o = await _make_order(client, auth_headers, cid)

    from app.models.purchase import Supplier
    sup = Supplier(company_id=test_company.id, name="მიმწოდებელი", code="SUP-001", identification_code="SUP-001")
    db_session.add(sup)
    await db_session.commit()

    r = await client.patch(f"/api/v1/orders/{o['id']}/drop-ship", json={
        "is_drop_ship": True, "drop_ship_supplier_id": str(sup.id),
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["is_drop_ship"] is True
    assert r.json()["data"]["drop_ship_supplier_id"] == str(sup.id)


@pytest.mark.asyncio
async def test_rma_return_flow(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    o = await _make_order(client, auth_headers, cid)

    # create return
    r = await client.post(f"/api/v1/orders/{o['id']}/returns", json={
        "reason": "დეფექტური პროდუქტი",
        "items": [{"product_id": None, "quantity": 1, "refund_amount": 590}],
        "refund_amount": 590,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    rid = r.json()["data"]["id"]
    assert r.json()["data"]["status"] == "requested"

    # list
    r = await client.get("/api/v1/orders/order-returns", headers=auth_headers)
    assert r.status_code == 200
    assert any(x["id"] == rid for x in r.json()["data"])

    # approve → restock
    r = await client.patch(f"/api/v1/orders/returns/{rid}", json={"status": "approved"}, headers=auth_headers)
    assert r.status_code == 200
    r = await client.patch(f"/api/v1/orders/returns/{rid}", json={"status": "restocked"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["restocked"] is True


@pytest.mark.asyncio
async def test_serial_lot_selection(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    o = await _make_order(client, auth_headers, cid)
    item_id = o["items"][0]["id"]

    from app.models.product import Product
    from app.models.warehouse import ProductBatch, Warehouse
    wh = Warehouse(company_id=test_company.id, name="საწყობი 2", code="WH2")
    db_session.add(wh)
    await db_session.flush()
    prod = Product(company_id=test_company.id, name="სერიული პროდუქტი", sku="SR-001")
    db_session.add(prod)
    await db_session.flush()
    batch = ProductBatch(company_id=test_company.id, warehouse_id=wh.id, product_id=prod.id, batch_number="LOT-001", quantity=10)
    db_session.add(batch)
    await db_session.commit()

    r = await client.patch(f"/api/v1/orders/items/{item_id}/serial-lot", json={
        "serial_numbers": ["SN-001", "SN-002"], "lot_id": str(batch.id),
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["serial_numbers"] == ["SN-001", "SN-002"]
    assert r.json()["data"]["lot_id"] == str(batch.id)


@pytest.mark.asyncio
async def test_credit_limit_approval(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    o = await _make_order(client, auth_headers, cid)

    r = await client.post(f"/api/v1/orders/{o['id']}/credit-limit-approval", json={"approved": True}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["credit_limit_approved"] is True

    # reject → 400
    r = await client.post(f"/api/v1/orders/{o['id']}/credit-limit-approval", json={"approved": False}, headers=auth_headers)
    assert r.status_code == 400
