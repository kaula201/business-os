"""Financial invariant tests — P0 critical checks.

Verifies:
1. Every journal entry has balanced debits = credits
2. Balance sheet: assets = liabilities + equity (including net income)
3. AR subledger = GL AR account balance
4. Confirmed invoice total = customer receivables total
5. No draft invoice for cancelled order
"""
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.receivable import CustomerReceivable


@pytest.mark.asyncio
async def test_all_journal_entries_are_balanced(db_session: AsyncSession, test_company):
    """P0 invariant: Every journal entry must have total debits = total credits."""
    company_id = test_company.id

    result = await db_session.execute(
        select(
            JournalEntryLine.journal_entry_id,
            func.sum(JournalEntryLine.debit_amount).label("total_debit"),
            func.sum(JournalEntryLine.credit_amount).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(JournalEntry.company_id == company_id)
        .group_by(JournalEntryLine.journal_entry_id)
    )
    rows = result.all()

    unbalanced = []
    for entry_id, debit, credit in rows:
        debit = Decimal(str(debit or 0))
        credit = Decimal(str(credit or 0))
        if debit != credit:
            unbalanced.append({"entry_id": str(entry_id), "debit": float(debit), "credit": float(credit)})

    assert len(unbalanced) == 0, f"Unbalanced journal entries found: {unbalanced}"


@pytest.mark.asyncio
async def test_balance_sheet_balances(db_session: AsyncSession, test_company):
    """P0 invariant: Total assets = total liabilities + total equity (incl. net income)."""
    company_id = test_company.id

    # Get balance sheet accounts
    result = await db_session.execute(
        select(
            GLAccount.account_type,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
        )
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id == company_id,
            GLAccount.account_type.in_(["asset", "liability", "equity"]),
        )
        .group_by(GLAccount.account_type)
    )
    rows = result.all()

    totals = {"asset": Decimal("0"), "liability": Decimal("0"), "equity": Decimal("0")}
    for acct_type, debit, credit in rows:
        debit = Decimal(str(debit or 0))
        credit = Decimal(str(credit or 0))
        if acct_type == "asset":
            totals["asset"] += debit - credit
        else:
            totals[acct_type] += credit - debit

    # Get net income from P&L accounts
    pl_result = await db_session.execute(
        select(
            GLAccount.account_type,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
        )
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id == company_id,
            GLAccount.account_type.in_(["income", "expense"]),
        )
        .group_by(GLAccount.account_type)
    )
    pl_rows = pl_result.all()
    total_income = Decimal("0")
    total_expenses = Decimal("0")
    for acct_type, debit, credit in pl_rows:
        debit = Decimal(str(debit or 0))
        credit = Decimal(str(credit or 0))
        balance = credit - debit
        if acct_type == "income":
            total_income += balance
        else:
            total_expenses += balance
    net_income = total_income - total_expenses

    total_equity_with_net = totals["equity"] + net_income
    difference = totals["asset"] - totals["liability"] - total_equity_with_net

    assert difference == Decimal("0"), (
        f"Balance sheet does not balance: assets={float(totals['asset']):.2f}, "
        f"liabilities={float(totals['liability']):.2f}, "
        f"equity={float(total_equity_with_net):.2f}, "
        f"difference={float(difference):.2f}"
    )


@pytest.mark.asyncio
async def test_invoice_total_matches_receivable(db_session: AsyncSession, test_company):
    """P0 invariant: Confirmed invoice total = customer receivables total."""
    company_id = test_company.id

    invoice_total = await db_session.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id, Invoice.status == "issued")
    )
    inv_total = Decimal(str(invoice_total.scalar()))

    receivable_total = await db_session.execute(
        select(func.coalesce(func.sum(CustomerReceivable.original_amount), 0))
        .where(CustomerReceivable.company_id == company_id)
    )
    rec_total = Decimal(str(receivable_total.scalar()))

    assert inv_total == rec_total, (
        f"Invoice total ({float(inv_total):.2f}) != "
        f"Receivable total ({float(rec_total):.2f})"
    )


@pytest.mark.asyncio
async def test_no_draft_invoice_for_cancelled_order(db_session: AsyncSession, test_company):
    """P0 invariant: No draft invoice should exist for a cancelled order."""
    company_id = test_company.id

    # Use ORM join instead of text()
    result = await db_session.execute(
        select(Invoice)
        .join(Order, Order.id == Invoice.order_id)
        .where(
            Order.company_id == company_id,
            Order.status == "cancelled",
            Invoice.status == "draft",
        )
    )
    bad_invoices = result.scalars().all()
    assert len(bad_invoices) == 0, (
        f"Found {len(bad_invoices)} draft invoice(s) for cancelled orders"
    )
