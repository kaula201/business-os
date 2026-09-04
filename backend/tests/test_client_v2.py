"""Client 2.0: addresses, groups, relations, statement, merge, credit limit."""
import pytest
from uuid import uuid4

from app.models.client import Client, ClientAddress, ClientGroupDef, ClientRelation
from app.models.order import Order
from app.models.invoice import Invoice
from app.models.receivable import CustomerReceivable


async def _create_client(client, auth_headers, name="შპს ტესტი", code="ID-001", credit_limit=None):
    payload = {
        "client_type": "legal",
        "name": name,
        "identification_code": code,
        "is_vat_payer": True,
    }
    if credit_limit is not None:
        payload["credit_limit"] = credit_limit
    r = await client.post("/api/v1/clients/", json=payload, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_addresses_crud(client, auth_headers):
    c = await _create_client(client, auth_headers, code="ADDR-001")

    # create legal + delivery
    r = await client.post(f"/api/v1/clients/{c['id']}/addresses", json={
        "address_type": "legal", "address_line": "თბილისი, რუსთაველი 12",
        "city": "თბილისი", "is_default": True,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    legal_id = r.json()["data"]["id"]

    r = await client.post(f"/api/v1/clients/{c['id']}/addresses", json={
        "address_type": "delivery", "address_line": "ბათუმი, ფერია 5",
    }, headers=auth_headers)
    assert r.status_code == 200

    # list → 2
    r = await client.get(f"/api/v1/clients/{c['id']}/addresses", headers=auth_headers)
    assert len(r.json()["data"]) == 2

    # delete
    r = await client.delete(f"/api/v1/clients/addresses/{legal_id}", headers=auth_headers)
    assert r.status_code == 200
    r = await client.get(f"/api/v1/clients/{c['id']}/addresses", headers=auth_headers)
    assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_groups_and_assignment(client, auth_headers):
    c = await _create_client(client, auth_headers, code="GRP-001")

    r = await client.post("/api/v1/clients/client-groups", json={"name": "VIP", "color": "#FFD700"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    gid = r.json()["data"]["id"]

    r = await client.post(f"/api/v1/clients/{c['id']}/groups", json=[gid], headers=auth_headers)
    assert r.status_code == 200

    r = await client.get("/api/v1/clients/client-groups", headers=auth_headers)
    groups = r.json()["data"]
    assert any(g["id"] == gid and g["client_count"] == 1 for g in groups)

    r = await client.delete(f"/api/v1/clients/client-groups/{gid}", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_relations(client, auth_headers):
    parent = await _create_client(client, auth_headers, name="მშობელი", code="REL-001")
    branch = await _create_client(client, auth_headers, name="ფილიალი", code="REL-002")

    r = await client.post(f"/api/v1/clients/{parent['id']}/relations", json={
        "related_client_id": branch["id"], "relation_type": "branch",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["related_client_name"] == "ფილიალი"

    # duplicate → 400
    r = await client.post(f"/api/v1/clients/{parent['id']}/relations", json={
        "related_client_id": branch["id"], "relation_type": "branch",
    }, headers=auth_headers)
    assert r.status_code == 400

    # self-link → 400
    r = await client.post(f"/api/v1/clients/{parent['id']}/relations", json={
        "related_client_id": parent["id"], "relation_type": "parent",
    }, headers=auth_headers)
    assert r.status_code == 400

    r = await client.get(f"/api/v1/clients/{parent['id']}/relations", headers=auth_headers)
    assert len(r.json()["data"]) == 1


@pytest.mark.asyncio
async def test_statement(client, auth_headers, db_session, test_company):
    c = await _create_client(client, auth_headers, code="STM-001")

    # create an order + invoice directly in DB (invoice.order_id is NOT NULL)
    order = Order(
        company_id=test_company.id, client_id=c["id"], order_number="ORD-STM-001",
        status="completed", total=1180,
    )
    db_session.add(order)
    await db_session.flush()
    inv = Invoice(
        company_id=test_company.id, client_id=c["id"], order_id=order.id,
        invoice_number="INV-STM-001", order_number="ORD-STM-001", idempotency_key="stm-001", status="issued",
        invoice_date=__import__("datetime").date.today(), due_date=__import__("datetime").date.today(),
        subtotal=1000, vat_amount=180, total=1180,
        seller_name="ტესტ კომპანია", seller_identification_code="TEST-001",
        client_name="შპს ტესტი", client_identification_code="STM-001",
    )
    db_session.add(inv)
    await db_session.flush()
    rec = CustomerReceivable(
        company_id=test_company.id, invoice_id=inv.id, client_id=c["id"],
        invoice_number="INV-STM-001", client_name="შპს ტესტი", currency="GEL",
        original_amount=1180, paid_amount=0, credited_amount=0, outstanding_amount=1180,
        due_date=__import__("datetime").date.today(),
    )
    db_session.add(rec)
    await db_session.commit()

    r = await client.get(f"/api/v1/clients/{c['id']}/statement", headers=auth_headers)
    assert r.status_code == 200, r.text
    st = r.json()["data"]
    assert st["total_invoiced"] == 1180.0
    assert st["closing_balance"] == 1180.0
    assert len(st["lines"]) == 1
    assert st["lines"][0]["type"] == "invoice"


@pytest.mark.asyncio
async def test_merge_clients(client, auth_headers, db_session, test_company):
    src = await _create_client(client, auth_headers, name="დუბლიკატი", code="MRG-001")
    tgt = await _create_client(client, auth_headers, name="ორიგინალი", code="MRG-002")

    # order + invoice on source
    order = Order(
        company_id=test_company.id, client_id=src["id"], order_number="ORD-MRG-001",
        status="completed", total=590,
    )
    db_session.add(order)
    await db_session.flush()
    inv = Invoice(
        company_id=test_company.id, client_id=src["id"], order_id=order.id,
        invoice_number="INV-MRG-001", order_number="ORD-MRG-001", idempotency_key="mrg-001", status="issued",
        invoice_date=__import__("datetime").date.today(), due_date=__import__("datetime").date.today(),
        subtotal=500, vat_amount=90, total=590,
        seller_name="ტესტ კომპანია", seller_identification_code="TEST-001",
        client_name="დუბლიკატი", client_identification_code="MRG-001",
    )
    db_session.add(inv)
    await db_session.commit()

    r = await client.post("/api/v1/clients/merge", json={
        "source_client_ids": [src["id"]], "target_client_id": tgt["id"],
    }, headers=auth_headers)
    assert r.status_code == 200, r.text

    # invoice moved to target (expire identity map so we see the API's commit)
    db_session.expire_all()
    moved = (await db_session.execute(
        __import__("sqlalchemy").select(Invoice).where(Invoice.invoice_number == "INV-MRG-001")
    )).scalar_one()
    assert str(moved.client_id) == tgt["id"]

    # source soft-deleted
    r = await client.get(f"/api/v1/clients/{src['id']}", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_credit_limit_enforcement(client, auth_headers):
    c = await _create_client(client, auth_headers, code="CRL-001", credit_limit=1000)

    # order within limit → ok (590 ≤ 1000)
    r = await client.post("/api/v1/orders/", json={
        "client_id": c["id"],
        "items": [{"product_name": "საქონელი", "quantity": 1, "unit_price": 500}],
        "is_vat_payer": True,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text

    # order exceeding limit (1000*1.18=1180 > 1000) → 400
    r = await client.post("/api/v1/orders/", json={
        "client_id": c["id"],
        "items": [{"product_name": "საქონელი", "quantity": 1, "unit_price": 1000}],
        "is_vat_payer": True,
    }, headers=auth_headers)
    assert r.status_code == 400
    assert "საკრედიტო ლიმიტი" in r.json()["detail"]
