"""Consolidated accounting — aggregated P&L and Balance Sheet across a company group."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine


async def get_group_companies(db: AsyncSession, company_id: UUID) -> list[Company]:
    """Companies in the same group as company_id (or just itself if no group)."""
    company = (
        await db.execute(select(Company).where(Company.id == company_id))
    ).scalar_one_or_none()
    if company is None:
        return []
    if company.company_group_id is None:
        return [company]
    rows = (
        await db.execute(
            select(Company).where(Company.company_group_id == company.company_group_id)
        )
    ).scalars().all()
    return list(rows)


def _entry(code, name, acct_type, debit, credit) -> dict:
    """Balance semantics: income = credit-debit, expense = debit-credit, asset = debit-credit,
    liability/equity = credit-debit."""
    if acct_type == "income":
        balance = credit - debit
    elif acct_type == "asset":
        balance = debit - credit
    else:  # expense, liability, equity
        balance = debit - credit if acct_type == "expense" else credit - debit
    return {
        "code": code, "name": name, "account_type": acct_type,
        "total_debit": round(debit, 2), "total_credit": round(credit, 2),
        "balance": round(balance, 2),
    }


async def consolidated_profit_loss(
    db: AsyncSession,
    company_ids: list[UUID],
    date_from: date,
    date_to: date,
) -> dict:
    """Aggregate income statement across companies (accounts summed by code).

    RLS note: the request transaction is tenant-pinned via app.current_company_id.
    This report intentionally reads several group companies, so RLS is relaxed
    for this transaction only (SET LOCAL resets at commit). Tenant isolation is
    preserved at the application level because company_ids is derived from the
    caller's own company group.
    """
    await db.execute(text("SET LOCAL app.current_company_id = ''"))
    rows = (
        await db.execute(
            select(
                GLAccount.code, GLAccount.name, GLAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
            )
            .select_from(GLAccount)
            .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
            .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                GLAccount.company_id.in_(company_ids),
                GLAccount.account_type.in_(["income", "expense"]),
                JournalEntry.entry_date >= date_from,
                JournalEntry.entry_date <= date_to,
            )
            .group_by(GLAccount.code, GLAccount.name, GLAccount.account_type)
            .order_by(GLAccount.code)
        )
    ).all()
    income_accounts, expense_accounts = [], []
    total_income = total_expenses = 0.0
    for code, name, acct_type, debit, credit in rows:
        entry = _entry(code, name, acct_type, float(debit), float(credit))
        if acct_type == "income":
            income_accounts.append(entry)
            total_income += entry["balance"]
        else:
            expense_accounts.append(entry)
            total_expenses += entry["balance"]
    net_income = total_income - total_expenses
    return {
        "date_from": date_from, "date_to": date_to,
        "income_accounts": income_accounts,
        "expense_accounts": expense_accounts,
        "total_income": round(total_income, 2),
        "total_expenses": round(total_expenses, 2),
        "net_income": round(net_income, 2),
    }


async def consolidated_balance_sheet(
    db: AsyncSession,
    company_ids: list[UUID],
    as_of_date: date,
) -> dict:
    """Aggregate balance sheet across companies as of a date.

    RLS note: see consolidated_profit_loss — RLS relaxed for this
    transaction only; tenant scope enforced at the application level.
    """
    await db.execute(text("SET LOCAL app.current_company_id = ''"))
    rows = (
        await db.execute(
            select(
                GLAccount.code, GLAccount.name, GLAccount.account_type,
                func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
            )
            .select_from(GLAccount)
            .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
            .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                GLAccount.company_id.in_(company_ids),
                GLAccount.account_type.in_(["asset", "liability", "equity"]),
                JournalEntry.entry_date <= as_of_date,
            )
            .group_by(GLAccount.code, GLAccount.name, GLAccount.account_type)
            .order_by(GLAccount.code)
        )
    ).all()
    asset_accounts, liability_accounts, equity_accounts = [], [], []
    total_assets = total_liabilities = total_equity = 0.0
    for code, name, acct_type, debit, credit in rows:
        entry = _entry(code, name, acct_type, float(debit), float(credit))
        if acct_type == "asset":
            asset_accounts.append(entry)
            total_assets += entry["balance"]
        elif acct_type == "liability":
            liability_accounts.append(entry)
            total_liabilities += entry["balance"]
        else:
            equity_accounts.append(entry)
            total_equity += entry["balance"]

    # Net income (retained earnings) from P&L up to as_of_date
    pl = await consolidated_profit_loss(
        db, company_ids, date(as_of_date.year, as_of_date.month, 1), as_of_date,
    )
    net_income = pl["net_income"]
    total_equity += net_income

    return {
        "as_of_date": as_of_date,
        "asset_accounts": asset_accounts,
        "liability_accounts": liability_accounts,
        "equity_accounts": equity_accounts,
        "net_income_included": net_income,
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "total_equity": round(total_equity, 2),
    }
