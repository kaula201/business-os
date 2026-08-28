"""Consolidated accounting — mapping-aware, FX-safe group reporting."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_controls import ConsolidationAccountMapping, FxTranslationRate
from app.models.company import Company
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine


async def get_group_companies(db: AsyncSession, company_id: UUID) -> list[Company]:
    """Companies in the same group as company_id (or just itself if no group)."""
    company = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
    if company is None:
        return []
    if company.company_group_id is None:
        return [company]
    return list((await db.execute(select(Company).where(Company.company_group_id == company.company_group_id))).scalars().all())


def _balance(account_type: str, debit: float, credit: float) -> float:
    if account_type == "income":
        return credit - debit
    if account_type in {"asset", "expense"}:
        return debit - credit
    return credit - debit


async def _consolidation_context(
    db: AsyncSession, company_ids: list[UUID], rate_date: date,
    presentation_currency: str | None, fx_method: str,
) -> tuple[dict[tuple[UUID, str], ConsolidationAccountMapping], dict[UUID, Decimal], str | None]:
    """Resolve account mappings and translation rates before aggregation.

    A report never combines nominal amounts from different currencies. If a
    presentation currency is requested, every non-native company must have a
    persisted translation snapshot on or before the report date.
    """
    mapping_by_source: dict[tuple[UUID, str], ConsolidationAccountMapping] = {}
    companies: list[Company] = []
    # Keep RLS strict: inspect each group company under its own explicit tenant
    # context before the later cross-company GL aggregation clears the scope.
    for company_id in company_ids:
        await db.execute(text("SELECT set_config('app.current_company_id', :cid, true)"), {"cid": str(company_id)})
        company = (await db.execute(select(Company).where(Company.id == company_id))).scalar_one_or_none()
        if company is None:
            continue
        companies.append(company)
        mappings = (await db.execute(select(ConsolidationAccountMapping).where(
            ConsolidationAccountMapping.company_id == company_id,
            ConsolidationAccountMapping.is_active.is_(True),
        ))).scalars().all()
        mapping_by_source.update({(row.company_id, row.source_account_code): row for row in mappings})

    currencies = {company.currency.upper() for company in companies}
    if not presentation_currency:
        if len(currencies) > 1:
            raise ValueError("სხვადასხვა ვალუტის ჯგუფისთვის მიუთითეთ presentation_currency და FX translation rate")
        return mapping_by_source, {company.id: Decimal("1") for company in companies}, next(iter(currencies), None)

    target = presentation_currency.upper()
    rates: dict[UUID, Decimal] = {}
    for company in companies:
        await db.execute(text("SELECT set_config('app.current_company_id', :cid, true)"), {"cid": str(company.id)})
        if company.currency.upper() == target:
            rates[company.id] = Decimal("1")
            continue
        rate_query = select(FxTranslationRate).where(
            FxTranslationRate.company_id == company.id,
            FxTranslationRate.target_currency == target,
            FxTranslationRate.method == fx_method,
        )
        # An "average" translation rate is a period-end snapshot that must be
        # explicitly prepared for this report; never silently reuse an older rate.
        if fx_method == "average":
            rate_query = rate_query.where(FxTranslationRate.rate_date == rate_date)
        else:
            rate_query = rate_query.where(FxTranslationRate.rate_date <= rate_date)
        rate = (await db.execute(rate_query.order_by(FxTranslationRate.rate_date.desc()).limit(1))).scalar_one_or_none()
        if rate is None:
            raise ValueError(f"FX translation rate აკლია: {company.name} → {target} ({fx_method})")
        rates[company.id] = rate.rate
    return mapping_by_source, rates, target


async def _aggregate(
    db: AsyncSession, company_ids: list[UUID], account_types: list[str],
    date_from: date | None, date_to: date, presentation_currency: str | None,
    fx_method: str,
) -> tuple[dict[tuple[str, str, str], dict], str | None]:
    mapping, rates, target = await _consolidation_context(db, company_ids, date_to, presentation_currency, fx_method)
    # GL report aggregation is constrained by caller-derived company_ids. Clear
    # only after all tenant-scoped control rows were read under strict RLS.
    await db.execute(text("SET LOCAL app.current_company_id = ''"))
    conditions = [
        GLAccount.company_id.in_(company_ids),
        GLAccount.account_type.in_(account_types),
        JournalEntry.entry_date <= date_to,
    ]
    if date_from:
        conditions.append(JournalEntry.entry_date >= date_from)
    rows = (await db.execute(
        select(
            GLAccount.company_id, GLAccount.code, GLAccount.name, GLAccount.account_type,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
        )
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(*conditions)
        .group_by(GLAccount.company_id, GLAccount.code, GLAccount.name, GLAccount.account_type)
    )).all()

    aggregate: dict[tuple[str, str, str], dict] = {}
    for company_id, code, name, account_type, debit, credit in rows:
        mapped = mapping.get((company_id, code))
        target_code = mapped.target_account_code if mapped else code
        target_name = mapped.target_name if mapped else name
        target_type = mapped.target_account_type if mapped else account_type
        rate = float(rates[company_id])
        key = (target_code, target_name, target_type)
        row = aggregate.setdefault(key, {"code": target_code, "name": target_name, "account_type": target_type, "total_debit": 0.0, "total_credit": 0.0})
        row["total_debit"] += float(debit) * rate
        row["total_credit"] += float(credit) * rate
    for row in aggregate.values():
        row["total_debit"] = round(row["total_debit"], 2)
        row["total_credit"] = round(row["total_credit"], 2)
        row["balance"] = round(_balance(row["account_type"], row["total_debit"], row["total_credit"]), 2)
    return aggregate, target


async def consolidated_profit_loss(
    db: AsyncSession, company_ids: list[UUID], date_from: date | None, date_to: date,
    presentation_currency: str | None = None, fx_method: str = "average",
) -> dict:
    aggregate, target = await _aggregate(
        db, company_ids, ["income", "expense"], date_from, date_to, presentation_currency, fx_method,
    )
    income_accounts, expense_accounts = [], []
    total_income = total_expenses = 0.0
    for row in sorted(aggregate.values(), key=lambda x: x["code"]):
        if row["account_type"] == "income":
            income_accounts.append(row); total_income += row["balance"]
        else:
            expense_accounts.append(row); total_expenses += row["balance"]
    return {"date_from": date_from, "date_to": date_to, "presentation_currency": target,
            "fx_method": fx_method if target else None, "income_accounts": income_accounts,
            "expense_accounts": expense_accounts, "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2), "net_income": round(total_income - total_expenses, 2)}


async def consolidated_balance_sheet(
    db: AsyncSession, company_ids: list[UUID], as_of_date: date,
    presentation_currency: str | None = None, fx_method: str = "closing",
) -> dict:
    aggregate, target = await _aggregate(
        db, company_ids, ["asset", "liability", "equity"], None, as_of_date, presentation_currency, fx_method,
    )
    asset_accounts, liability_accounts, equity_accounts = [], [], []
    total_assets = total_liabilities = total_equity = 0.0
    for row in sorted(aggregate.values(), key=lambda x: x["code"]):
        if row["account_type"] == "asset":
            asset_accounts.append(row); total_assets += row["balance"]
        elif row["account_type"] == "liability":
            liability_accounts.append(row); total_liabilities += row["balance"]
        else:
            equity_accounts.append(row); total_equity += row["balance"]
    pl = await consolidated_profit_loss(
        db, company_ids, None, as_of_date,
        presentation_currency, "average" if presentation_currency else fx_method,
    )
    net_income = pl["net_income"]
    total_equity += net_income
    return {"as_of_date": as_of_date, "presentation_currency": target,
            "fx_method": fx_method if target else None, "asset_accounts": asset_accounts,
            "liability_accounts": liability_accounts, "equity_accounts": equity_accounts,
            "net_income_included": net_income, "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2), "total_equity": round(total_equity, 2)}


async def intercompany_balances(
    db: AsyncSession, company_ids: list[UUID], as_of_date: date,
    presentation_currency: str | None = None, fx_method: str = "closing",
) -> dict:
    """Per-company balances on the same account code — the intercompany
    reconciliation view (A's receivable should mirror B's payable)."""
    mapping, rates, target = await _consolidation_context(
        db, company_ids, as_of_date, presentation_currency, fx_method,
    )
    await db.execute(text("SET LOCAL app.current_company_id = ''"))
    rows = (await db.execute(
        select(
            GLAccount.company_id, GLAccount.code, GLAccount.name, GLAccount.account_type,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("total_debit"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("total_credit"),
        )
        .select_from(GLAccount)
        .outerjoin(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id.in_(company_ids),
            JournalEntry.entry_date <= as_of_date,
        )
        .group_by(GLAccount.company_id, GLAccount.code, GLAccount.name, GLAccount.account_type)
    )).all()

    companies = {str(c.id): c.name for c in (await db.execute(
        select(Company).where(Company.id.in_(company_ids))
    )).scalars().all()}

    by_code: dict[str, dict] = {}
    for company_id, code, name, account_type, debit, credit in rows:
        rate = float(rates[company_id])
        balance = _balance(account_type, float(debit) * rate, float(credit) * rate)
        row = by_code.setdefault(code, {
            "account_code": code, "account_name": name, "account_type": account_type,
            "balances": {}, "total": 0.0,
        })
        row["balances"][str(company_id)] = {
            "company_id": str(company_id), "company_name": companies.get(str(company_id), "?"),
            "balance": round(balance, 2),
        }
        row["total"] += balance

    items = []
    for code, row in sorted(by_code.items()):
        row["total"] = round(row["total"], 2)
        items.append(row)
    return {
        "as_of_date": as_of_date, "presentation_currency": target,
        "fx_method": fx_method if target else None,
        "companies": [{"id": str(c), "name": n} for c, n in companies.items()],
        "accounts": items,
    }
