"""P1-1: Quote → Order → Delivery → Invoice → Payment → GL — full sales pipeline E2E."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.client import Client
from app.models.gl import GLAccount, JournalEntryLine
from app.models.product import Product
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed(client, auth_headers, test_company):
    async with TestSessionLocal() as session:
        cust = Client(company_id=test_company.id, name="Pipe Client", client_type="legal",
                      identification_code=f"PIPE-{uuid.uuid4().hex[:6]}", vat_status=True, status="active")
        prod = Product(company_id=test_company.id, sku=f"PIPE-SKU-{uuid.uuid4().hex[:6]}",
                       name="Pipe Product", sale_price=100, purchase_price=60, current_stock=10)
        session.add_all([cust, prod])
        await session.commit()
        return {"client_id": str(cust.id), "product_id": str(prod.id)}


async def test_full_sales_pipeline_to_gl(client, auth_headers, test_company):
    seeded = await _seed(client, auth_headers, test_company)

    # 1. Quote
    q = await client.post("/api/v1/quotations/", json={
        "client_id": seeded["client_id"], "quotation_date": "2026-08-11", "items": [
            {"product_id": seeded["product_id"], "description": "P", "quantity": 2, "unit_price": 100},
        ],
    }, headers=auth_headers)
    assert q.status_code == 201, q.text
    qid = q.json()["data"]["id"]

    # 2. Accept + convert → Order
    await client.patch(f"/api/v1/quotations/{qid}/status", json={"status": "accepted"}, headers=auth_headers)
    conv = await client.post(f"/api/v1/quotations/{qid}/convert", headers=auth_headers)
    assert conv.status_code == 200, conv.text
    order_id = conv.json()["data"]["order_id"]

    # 3. Complete order → auto invoice draft
    comp = await client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "completed"}, headers=auth_headers)
    assert comp.status_code == 200, comp.text

    # 4. Invoice exists for the order
    invs = await client.get("/api/v1/invoices/", params={"order_id": order_id}, headers=auth_headers)
    assert invs.status_code == 200, invs.text
    items = invs.json()["data"]["items"]
    assert len(items) >= 1, "invoice not auto-created from order"
    invoice_id = items[0]["id"]

    # 5. Issue invoice → GL posting (Dr 1310 / Cr 4100 / Cr 2200)
    issued = await client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=auth_headers)
    assert issued.status_code == 200, issued.text

    # 6. Payment → GL (Dr 1410 / Cr 1310) — via receivable payment endpoint
    recv = await client.get("/api/v1/customer-receivables/", params={"invoice_id": invoice_id}, headers=auth_headers)
    assert recv.status_code == 200, recv.text
    recv_items = recv.json()["data"]["items"]
    assert len(recv_items) >= 1, "receivable not created from invoice"
    receivable_id = recv_items[0]["id"]
    pay = await client.post(f"/api/v1/customer-receivables/{receivable_id}/payments", json={
        "amount": 236, "payment_date": "2026-08-12", "payment_method": "bank",
        "idempotency_key": f"pipe-pay-{uuid.uuid4().hex[:8]}",
    }, headers=auth_headers)
    assert pay.status_code in (200, 201), pay.text

    # 7. GL verification: 1310 cleared, 1410 has 236, 4100 has 200, 2200 has 36
    async with TestSessionLocal() as s:
        accounts = (await s.execute(select(GLAccount).where(GLAccount.company_id == test_company.id))).scalars().all()
        acc = {a.code: a for a in accounts}
        balances = {}
        for code, a in acc.items():
            row = (await s.execute(
                select(
                    func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
                    func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
                ).where(JournalEntryLine.gl_account_id == a.id)
            )).one()
            dr, cr = Decimal(row[0]), Decimal(row[1])
            # asset/expense: debit - credit; income/liability/equity: credit - debit
            balances[code] = dr - cr if a.account_type in ("asset", "expense") else cr - dr

        assert balances.get("1410", Decimal("0")) == Decimal("236.00"), f"1410={balances.get('1410')}"
        assert balances.get("1310", Decimal("0")) == Decimal("0.00"), f"1310={balances.get('1310')} (should be cleared)"
        assert balances.get("4100", Decimal("0")) == Decimal("200.00"), f"4100={balances.get('4100')}"
        assert balances.get("2200", Decimal("0")) == Decimal("36.00"), f"2200={balances.get('2200')}"
