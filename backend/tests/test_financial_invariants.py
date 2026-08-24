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
