"""Odoo-depth accounting: FIFO/Standard valuation, year closing → retained earnings."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.services.gl_posting import seed_default_accounts
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _seed_product(client, auth_headers, price=10) -> str:
    p = await client.post("/api/v1/products/", json={
        "name": f"VAL-{uuid.uuid4().hex[:6]}", "sku": f"VSKU-{uuid.uuid4().hex[:6]}",
        "sale_price": 20, "purchase_price": price,
    }, headers=auth_headers)
    assert p.status_code in (200, 201), p.text
    return p.json()["data"]["id"]


async def test_fifo_valuation_consumes_oldest_lot(client, auth_headers, test_company):
    pid = await _seed_product(client, auth_headers)

    # set FIFO method
    set_m = await client.post("/api/v1/inventory/valuation/methods", json={
        "product_id": pid, "method": "fifo",
    }, headers=auth_headers)
    assert set_m.status_code == 200, set_m.text

    # incoming: 10 @ 5, then 10 @ 8
    from app.services.inventory_valuation import apply_incoming_movement
    async with TestSessionLocal() as session:
        await apply_incoming_movement(session, test_company.id, uuid.UUID(pid), Decimal("10"), Decimal("5"))
        await apply_incoming_movement(session, test_company.id, uuid.UUID(pid), Decimal("10"), Decimal("8"))
        await session.commit()

    # outgoing 12 → COGS = 10*5 + 2*8 = 66 (FIFO oldest first)
    from app.services.inventory_valuation import apply_outgoing_movement
    async with TestSessionLocal() as session:
        layer, cogs = await apply_outgoing_movement(session, test_company.id, uuid.UUID(pid), Decimal("12"))
        await session.commit()
    assert float(cogs) == 66.0

    # remaining 8 units are from the 8 GEL lot
    async with TestSessionLocal() as session:
        from app.models.cost_layer import FifoCostLot
        lots = (await session.execute(select(FifoCostLot).where(
            FifoCostLot.product_id == uuid.UUID(pid),
        ))).scalars().all()
    assert float(lots[0].quantity_remaining) == 0.0
    assert float(lots[1].quantity_remaining) == 8.0


async def test_standard_valuation_uses_standard_cost(client, auth_headers, test_company):
    pid = await _seed_product(client, auth_headers, price=10)

    set_m = await client.post("/api/v1/inventory/valuation/methods", json={
        "product_id": pid, "method": "standard", "standard_cost": 7.5,
    }, headers=auth_headers)
    assert set_m.status_code == 200, set_m.text

    from app.services.inventory_valuation import apply_incoming_movement, apply_outgoing_movement
    async with TestSessionLocal() as session:
        await apply_incoming_movement(session, test_company.id, uuid.UUID(pid), Decimal("10"), Decimal("10"))
        await session.commit()
        layer, cogs = await apply_outgoing_movement(session, test_company.id, uuid.UUID(pid), Decimal("4"))
        await session.commit()
    # COGS = 4 * 7.5 (standard cost, not purchase price 10)
    assert float(cogs) == 30.0


async def test_year_closing_moves_net_income_to_retained(client, auth_headers, test_company):
    # post a P&L entry: income 1000, expense 400 → net 600
    async with TestSessionLocal() as session:
        accounts = (await session.execute(select(GLAccount).where(
            GLAccount.company_id == test_company.id,
        ))).scalars().all()
        acc = {a.code: a.id for a in accounts}
        entry = JournalEntry(
            company_id=test_company.id,
            entry_number=f"YC-{uuid.uuid4().hex[:6]}",
            entry_date=date(2026, 8, 15),
            description="year closing test",
            reference_type="manual",
            reference_id=uuid.uuid4(),
        )
        session.add(entry)
        await session.flush()
        session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc["4100"], line_number=1,
                                     debit_amount=0, credit_amount=Decimal("1000"), description="income"))
        session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc["5200"], line_number=2,
                                     debit_amount=Decimal("400"), credit_amount=0, description="expense"))
        session.add(JournalEntryLine(journal_entry_id=entry.id, gl_account_id=acc["1410"], line_number=3,
                                     debit_amount=Decimal("600"), credit_amount=0, description="bank"))
        await session.commit()

    resp = await client.post("/api/v1/accounting-periods/2026/close-year", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["closed"] is True
    assert float(data["net_income"]) == 600.0

    # idempotent — second call says already closed
    again = await client.post("/api/v1/accounting-periods/2026/close-year", headers=auth_headers)
    assert again.status_code == 200
    assert again.json()["data"]["already_closed"] is True

    # retained earnings (3200) has 600 credit
    async with TestSessionLocal() as session:
        acc = {a.code: a.id for a in (await session.execute(select(GLAccount).where(
            GLAccount.company_id == test_company.id,
        ))).scalars().all()}
        lines = (await session.execute(select(JournalEntryLine).where(
            JournalEntryLine.gl_account_id == acc["3200"],
        ))).scalars().all()
    assert sum(float(l.credit_amount) for l in lines) == 600.0


async def test_ar_ap_reconciliation_balances(client, auth_headers, test_company):
    """AR/AP subledger reconciliation: GL control accounts vs subledger totals."""
    from app.models.client import Client
    from app.models.purchase import Supplier, SupplierPayable, SupplierInvoice, PurchaseOrder
    from app.models.warehouse import Warehouse
    from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
    from app.models.user import User
    from app.core.security import hash_password

    async with TestSessionLocal() as session:
        # client with balance 500
        cl = Client(company_id=test_company.id, name="Rec Client", client_type="legal",
                    identification_code="REC-1", balance=500)
        session.add(cl)
        # supplier payable outstanding 300
        sup = Supplier(company_id=test_company.id, name="Rec Supplier",
                       code=f"SUP-{uuid.uuid4().hex[:6]}",
                       identification_code="REC-S1")
        session.add(sup)
        await session.flush()
        wh = Warehouse(company_id=test_company.id, code=f"WH-{uuid.uuid4().hex[:4]}", name="Rec WH")
        session.add(wh)
        await session.flush()
        po = PurchaseOrder(company_id=test_company.id, supplier_id=sup.id, warehouse_id=wh.id,
                           purchase_order_number=f"PO-{uuid.uuid4().hex[:8]}",
                           subtotal=300, vat_amount=0, total=300)
        session.add(po)
        await session.flush()
        inv = SupplierInvoice(company_id=test_company.id, supplier_id=sup.id,
                              purchase_order_id=po.id,
                              internal_invoice_number=f"SI-{uuid.uuid4().hex[:8]}",
                              supplier_invoice_number="SI-REC-1",
                              invoice_date=date(2026, 8, 1), due_date=date(2026, 9, 1),
                              subtotal=300, vat_amount=0, total=300)
        session.add(inv)
        await session.flush()
        session.add(SupplierPayable(company_id=test_company.id, supplier_id=sup.id,
                                    supplier_invoice_id=inv.id, due_date=date(2026, 9, 1),
                                    original_amount=300, outstanding_amount=300))
        # GL: AR 1300 Dr 500, AP 2100 Cr 300
        acc = {a.code: a.id for a in (await session.execute(select(GLAccount).where(
            GLAccount.company_id == test_company.id,
        ))).scalars().all()}
        for code, debit, credit in [("1300", 500, 0), ("2100", 0, 300)]:
            e = JournalEntry(company_id=test_company.id,
                             entry_number=f"REC-{uuid.uuid4().hex[:6]}",
                             entry_date=date(2026, 8, 15), description="recon test",
                             reference_type="manual", reference_id=uuid.uuid4())
            session.add(e)
            await session.flush()
            session.add(JournalEntryLine(journal_entry_id=e.id, gl_account_id=acc[code],
                                        line_number=1, debit_amount=Decimal(debit),
                                        credit_amount=Decimal(credit)))
        await session.commit()

    resp = await client.get("/api/v1/analytic/ar-ap-reconciliation", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["ar"]["gl_balance"] == 500.0
    assert data["ar"]["subledger_total"] == 500.0
    assert data["ar"]["in_balance"] is True
    assert data["ap"]["gl_balance"] == 300.0
    assert data["ap"]["subledger_total"] == 300.0
    assert data["ap"]["in_balance"] is True
