"""Invoice 2.0: notes, reversal, recurring, installments, allocation, fiscal sync."""
import pytest
from datetime import date, timedelta
from uuid import uuid4

from app.models.invoice import Invoice, InvoiceInstallment, InvoiceNote, PaymentAllocation
from app.models.order import Order
from app.models.receivable import CustomerReceivable, CustomerPayment


async def _make_client(client, auth_headers):
    r = await client.post("/api/v1/clients/", json={
        "client_type": "legal", "name": "ინვოისის კლიენტი", "identification_code": f"{uuid4().int % 900000000 + 100000000}",
    }, headers=auth_headers)
    return r.json()["data"]["id"]


async def _make_invoice(client, auth_headers, cid, db_session=None, test_company=None):
    # order first (with warehouse so it can be confirmed)
    warehouse_id = None
    if db_session and test_company:
        from app.models.warehouse import Warehouse
        wh = Warehouse(company_id=test_company.id, name="ინვოისის საწყობი", code=f"WH-{uuid4().hex[:4]}")
        db_session.add(wh)
        await db_session.commit()
        warehouse_id = str(wh.id)
    r = await client.post("/api/v1/orders/", json={
        "client_id": cid,
        "warehouse_id": warehouse_id,
        "items": [{"product_name": "პროდუქტი", "quantity": 1, "unit_price": 1000}],
        "is_vat_payer": True,
    }, headers=auth_headers)
    oid = r.json()["data"]["id"]
    # order must be confirmed before invoicing
    pr = await client.patch(f"/api/v1/orders/{oid}/status", json={"status": "confirmed"}, headers=auth_headers)
    assert pr.status_code == 200, pr.text
    r = await client.post("/api/v1/invoices/generate", json={
        "order_id": oid, "invoice_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=14)).isoformat(),
        "idempotency_key": f"inv-{uuid4().hex[:12]}",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_credit_debit_notes(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    inv = await _make_invoice(client, auth_headers, cid, db_session, test_company)

    r = await client.post(f"/api/v1/invoices/{inv['id']}/notes", json={
        "note_type": "credit", "amount": 100, "reason": "ფასდაკლება",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["note_type"] == "credit"
    assert r.json()["data"]["status"] == "issued"

    r = await client.post(f"/api/v1/invoices/{inv['id']}/notes", json={
        "note_type": "debit", "amount": 50, "reason": "დამატება",
    }, headers=auth_headers)
    assert r.status_code == 200

    r = await client.get(f"/api/v1/invoices/{inv['id']}/notes", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2


@pytest.mark.asyncio
async def test_reversal_workflow(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    inv = await _make_invoice(client, auth_headers, cid, db_session, test_company)

    r = await client.post(f"/api/v1/invoices/{inv['id']}/reversal", json={"reason": "მომხმარებელმა გააუქმა"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"
    assert r.json()["data"]["credit_note"].startswith("CN-")

    # double reversal → 400
    r = await client.post(f"/api/v1/invoices/{inv['id']}/reversal", json={"reason": "ისევ"}, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_recurring_invoice(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    inv = await _make_invoice(client, auth_headers, cid, db_session, test_company)

    r = await client.post(f"/api/v1/invoices/{inv['id']}/recurring", json={
        "frequency": "monthly", "next_date": (date.today() + timedelta(days=30)).isoformat(),
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["is_recurring"] is True
    assert r.json()["data"]["frequency"] == "monthly"


@pytest.mark.asyncio
async def test_installments(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    inv = await _make_invoice(client, auth_headers, cid, db_session, test_company)

    r = await client.post(f"/api/v1/invoices/{inv['id']}/installments", json={
        "count": 3, "first_due_date": (date.today() + timedelta(days=30)).isoformat(),
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert len(rows) == 3
    total = sum(x["amount"] for x in rows)
    assert abs(total - inv["total"]) < 0.01  # sums to invoice total

    r = await client.get(f"/api/v1/invoices/{inv['id']}/installments", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]) == 3


@pytest.mark.asyncio
async def test_payment_allocation(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    inv = await _make_invoice(client, auth_headers, cid, db_session, test_company)

    # receivable is auto-created by invoice generate — fetch it
    rec = (await db_session.execute(
        __import__("sqlalchemy").select(CustomerReceivable).where(CustomerReceivable.invoice_id == inv["id"])
    )).scalar_one()
    pay = CustomerPayment(
        company_id=test_company.id, receivable_id=rec.id, amount=inv["total"],
        payment_date=date.today(), payment_method="bank_transfer",
        idempotency_key=f"pay-{uuid4().hex[:12]}",
    )
    db_session.add(pay)
    await db_session.commit()

    r = await client.post(f"/api/v1/invoices/{inv['id']}/allocate", json={
        "payment_id": str(pay.id), "amount": inv["total"],
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["allocated"] == inv["total"]

    # receivable now paid (expire identity map to see API's commit)
    db_session.expire_all()
    rec2 = (await db_session.execute(__import__("sqlalchemy").select(CustomerReceivable).where(CustomerReceivable.invoice_id == inv["id"]))).scalar_one()
    assert rec2.status == "paid"
    assert float(rec2.outstanding_amount) == 0


@pytest.mark.asyncio
async def test_fiscal_status_sync(client, auth_headers, db_session, test_company):
    cid = await _make_client(client, auth_headers)
    inv = await _make_invoice(client, auth_headers, cid, db_session, test_company)

    r = await client.patch(f"/api/v1/invoices/{inv['id']}/fiscal-status", json={
        "status": "sent", "error": None,
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["fiscal_status"] == "sent"
    assert r.json()["data"]["synced_at"] is not None

    r = await client.patch(f"/api/v1/invoices/{inv['id']}/fiscal-status", json={
        "status": "rejected", "error": "RS.ge: ფორმატის შეცდომა",
    }, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["fiscal_status"] == "rejected"
