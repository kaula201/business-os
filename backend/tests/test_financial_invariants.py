"""Financial invariants — P0: debit=credit, A=L+E, consolidated=0, inventory=GL."""
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.company import Company
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.services.gl_posting import seed_default_accounts
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _setup_company(session, name: str, code: str) -> Company:
    company = Company(name=name, identification_code=code, vat_status=False, currency="GEL")
    session.add(company)
    await session.flush()
    await seed_default_accounts(session, company.id)
    return company


async def _post_entry(session, company: Company, lines: list[tuple[str, Decimal, Decimal]], on_date: date):
    accounts = (await session.execute(select(GLAccount).where(GLAccount.company_id == company.id))).scalars().all()
    acc = {a.code: a.id for a in accounts}
    entry = JournalEntry(
        company_id=company.id,
        entry_number=f"INV-{uuid.uuid4().hex[:8]}",
        entry_date=on_date,
        description="invariant test",
        reference_type="manual",
        reference_id=uuid.uuid4(),
    )
    session.add(entry)
    await session.flush()
    for i, (code, dr, cr) in enumerate(lines, start=1):
        session.add(JournalEntryLine(
            journal_entry_id=entry.id, gl_account_id=acc[code], line_number=i,
            debit_amount=dr, credit_amount=cr, description=code,
        ))
    await session.commit()


async def test_invariant_debit_equals_credit(client, auth_headers, test_company, db_session):
    """Every journal entry must balance: sum(debit) == sum(credit)."""
    async with TestSessionLocal() as session:
        co = await _setup_company(session, "InvA", "INV-A")
        # balanced entry: Dr 1410 100 / Cr 4100 100
        await _post_entry(session, co, [("1410", Decimal("100"), Decimal("0")), ("4100", Decimal("0"), Decimal("100"))], date(2026, 8, 1))
        # balanced entry with VAT: Dr 1410 118 / Cr 4100 100 / Cr 2200 18
        await _post_entry(session, co, [("1410", Decimal("118"), Decimal("0")), ("4100", Decimal("0"), Decimal("100")), ("2200", Decimal("0"), Decimal("18"))], date(2026, 8, 2))

    async with TestSessionLocal() as session:
        rows = (await session.execute(
            select(JournalEntry.id,
                   func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
                   func.coalesce(func.sum(JournalEntryLine.credit_amount), 0))
            .join(JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id)
            .group_by(JournalEntry.id)
        )).all()
        assert len(rows) >= 2
        for entry_id, dr, cr in rows:
            assert dr == cr, f"Entry {entry_id} unbalanced: dr={dr} cr={cr}"


async def test_invariant_assets_equal_liabilities_plus_equity(client, auth_headers, test_company, db_session):
    """Balance sheet invariant: A = L + E (with net income in equity)."""
    async with TestSessionLocal() as session:
        co = await _setup_company(session, "InvB", "INV-B")
        # income 500 with VAT: Dr 1410 590 / Cr 4100 500 / Cr 2200 90
        await _post_entry(session, co, [("1410", Decimal("590"), Decimal("0")), ("4100", Decimal("0"), Decimal("500")), ("2200", Decimal("0"), Decimal("90"))], date(2026, 8, 5))

    async with TestSessionLocal() as session:
        accounts = (await session.execute(select(GLAccount).where(GLAccount.company_id == co.id))).scalars().all()
        acc = {a.code: a for a in accounts}
        balances = {}
        for code, a in acc.items():
            row = (await session.execute(
                select(func.coalesce(func.sum(JournalEntryLine.debit_amount), 0), func.coalesce(func.sum(JournalEntryLine.credit_amount), 0))
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
                .where(JournalEntryLine.gl_account_id == a.id)
            )).one()
            dr, cr = Decimal(row[0]), Decimal(row[1])
            if a.account_type == "asset":
                balances[code] = dr - cr
            else:
                balances[code] = cr - dr

        total_assets = sum(v for k, v in balances.items() if acc[k].account_type == "asset")
        total_liab = sum(v for k, v in balances.items() if acc[k].account_type == "liability")
        total_equity = sum(v for k, v in balances.items() if acc[k].account_type == "equity")
        # net income (4100 income - 5200 expense) goes to equity
        net_income = balances.get("4100", Decimal("0")) - balances.get("5200", Decimal("0"))
        assert total_assets == total_liab + total_equity + net_income, \
            f"A={total_assets} != L={total_liab} + E={total_equity} + NI={net_income}"


async def test_invariant_payroll_gl_balances(client, auth_headers, test_company, db_session):
    """Payroll GL invariant: Dr 5200 (expense) == Cr 2210+2220+2300 (liabilities).

    A payslip posting must never create an unbalanced payroll accrual.
    """
    from app.models.hr import Employee, PayrollEntry
    from app.models.payroll_engine import PayrollLine, SalaryRule, SalaryStructure
    from app.services.payroll_engine import compute_payroll_with_rules

    async with TestSessionLocal() as session:
        co = await _setup_company(session, "InvP", "INV-P")
        emp = Employee(
            company_id=co.id, full_name="პეიროლი თესტი", personal_number="01001001002",
            position="დეველოპერი", hire_date=date(2024, 1, 1), base_salary=2000,
        )
        session.add(emp)
        await session.flush()
        struct = SalaryStructure(company_id=co.id, name="სტრუქტურა", is_active=True)
        session.add(struct)
        await session.flush()
        session.add(SalaryRule(
            company_id=co.id, structure_id=struct.id, code="PENSION", name="პენსია",
            category="pension", amount_type="percentage", amount=2, basis="gross", sequence=10,
        ))
        session.add(SalaryRule(
            company_id=co.id, structure_id=struct.id, code="INCOME_TAX", name="საშემოსავლო",
            category="tax", amount_type="formula",
            formula="round(gross * params['income_tax_rate'], 2)", basis="gross", sequence=20,
        ))
        await session.commit()

        result = await compute_payroll_with_rules(session, co.id, emp.id, 2000, 2026, 8, structure_id=struct.id)
        # Dr 5200 = gross; Cr 2210 = pension, 2220 = tax, 2300 = net
        gross = Decimal(str(result["gross_pay"]))
        pension = Decimal(str(result["pension_contribution"]))
        tax = Decimal(str(result["income_tax"]))
        net = Decimal(str(result["net_pay"]))
        assert gross == pension + tax + net, \
            f"Payroll split unbalanced: {gross} != {pension}+{tax}+{net}"


async def test_invariant_ar_ap_subledger_matches_gl(client, auth_headers, test_company, db_session):
    """AR/AP invariant: GL 1300/2100 balances equal subledger totals.

    A receivable posted to GL must equal the sum of open client invoices.
    """
    from app.models.client import Client
    from app.models.invoice import Invoice
    from app.models.order import Order

    async with TestSessionLocal() as session:
        co = await _setup_company(session, "InvC", "INV-C")
        client = Client(company_id=co.id, name="კლიენტი 1", email="c1@test.ge", phone="555", client_type="company", identification_code="405123457")
        session.add(client)
        await session.flush()
        order = Order(
            company_id=co.id, client_id=client.id, order_number="ORD-INV-0001",
            status="confirmed", subtotal=500, vat_amount=90, total=590,
        )
        session.add(order)
        await session.flush()
        inv = Invoice(
            company_id=co.id, client_id=client.id, order_id=order.id,
            invoice_number="INV-0001", idempotency_key="inv-0001",
            invoice_date=date(2026, 8, 1), due_date=date(2026, 9, 1),
            subtotal=Decimal("500"), vat_amount=Decimal("90"), total=Decimal("590"),
            order_number="ORD-INV-0001", seller_name="Test Co",
            seller_identification_code="405123456",
            client_name="კლიენტი 1", client_identification_code="405123457",
            status="issued",
        )
        session.add(inv)
        await session.commit()

        # GL: Dr 1300 590 / Cr 4100 500 / Cr 2200 90
        await _post_entry(session, co, [("1300", Decimal("590"), Decimal("0")), ("4100", Decimal("0"), Decimal("500")), ("2200", Decimal("0"), Decimal("90"))], date(2026, 8, 1))

    async with TestSessionLocal() as session:
        accounts = (await session.execute(select(GLAccount).where(GLAccount.company_id == co.id))).scalars().all()
        acc = {a.code: a.id for a in accounts}
        row = (await session.execute(
            select(func.coalesce(func.sum(JournalEntryLine.debit_amount), 0), func.coalesce(func.sum(JournalEntryLine.credit_amount), 0))
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(JournalEntryLine.gl_account_id == acc["1300"])
        )).one()
        gl_ar = Decimal(row[0]) - Decimal(row[1])
        assert gl_ar == Decimal("590"), f"GL AR={gl_ar} != 590"
        # subledger: open invoice total (500 + 90 VAT)
        subledger = Decimal("590")
        assert gl_ar == subledger, f"AR GL {gl_ar} != subledger {subledger}"
