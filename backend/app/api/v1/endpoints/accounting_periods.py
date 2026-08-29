"""Accounting period close/reopen API."""
import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.accounting_period import AccountingPeriod, AccountingPeriodEvent
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.accounting_period import AccountingPeriodAction, AccountingPeriodEventResponse, AccountingPeriodResponse
from app.schemas.common import ResponseBase
from app.services.accounting_periods import acquire_period_lock

router = APIRouter(prefix="/accounting-periods", tags=["სააღრიცხვო პერიოდები"])


def require_finance_role(user: User) -> None:
    if user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="სააღრიცხვო პერიოდებზე წვდომის უფლება არ გაქვთ")


def month_bounds(year: int, month: int) -> tuple[date, date]:
    if year < 2000 or year > 2200 or month < 1 or month > 12:
        raise HTTPException(status_code=422, detail="წელი ან თვე არასწორია")
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


async def load_period_for_update(db: AsyncSession, company_id, year: int, month: int):
    return (
        await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.company_id == company_id,
                AccountingPeriod.year == year,
                AccountingPeriod.month == month,
            ).with_for_update()
        )
    ).scalar_one_or_none()


@router.get("", response_model=ResponseBase[list[AccountingPeriodResponse]])
async def list_periods(
    year: int | None = Query(None, ge=2000, le=2200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_finance_role(current_user)
    query = select(AccountingPeriod).where(AccountingPeriod.company_id == current_user.company_id)
    if year:
        query = query.where(AccountingPeriod.year == year)
    rows = (await db.execute(query.order_by(AccountingPeriod.year.desc(), AccountingPeriod.month.desc()))).scalars().all()
    return ResponseBase(data=rows)


@router.post("/{year}/{month}/close", response_model=ResponseBase[AccountingPeriodResponse])
async def close_period(
    year: int,
    month: int,
    payload: AccountingPeriodAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_finance_role(current_user)
    start_date, end_date = month_bounds(year, month)
    await acquire_period_lock(db, current_user.company_id, start_date)
    period = await load_period_for_update(db, current_user.company_id, year, month)
    if period and period.status == "closed":
        raise HTTPException(status_code=409, detail="სააღრიცხვო პერიოდი უკვე დახურულია")
    if not period:
        period = AccountingPeriod(company_id=current_user.company_id, year=year, month=month, start_date=start_date, end_date=end_date)
        db.add(period)
        await db.flush()
    period.status = "closed"
    period.close_reason = payload.reason
    period.closed_by = current_user.id
    period.closed_at = utc_now()
    period.reopened_by = None
    period.reopened_at = None
    db.add(AccountingPeriodEvent(company_id=current_user.company_id, period_id=period.id, action="closed", reason=payload.reason, actor_id=current_user.id))
    db.add(AuditLog(company_id=current_user.company_id, user_id=current_user.id, action="accounting_period.closed", entity_type="accounting_period", entity_id=period.id, details=f"{year:04d}-{month:02d}: {payload.reason}"))
    await db.flush()
    await db.refresh(period)
    return ResponseBase(data=period, message="სააღრიცხვო პერიოდი დახურულია")


@router.post("/{year}/{month}/reopen", response_model=ResponseBase[AccountingPeriodResponse])
async def reopen_period(
    year: int,
    month: int,
    payload: AccountingPeriodAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="პერიოდის გახსნა მხოლოდ ადმინისტრატორს შეუძლია")
    start_date, _ = month_bounds(year, month)
    await acquire_period_lock(db, current_user.company_id, start_date)
    period = await load_period_for_update(db, current_user.company_id, year, month)
    if not period:
        raise HTTPException(status_code=404, detail="სააღრიცხვო პერიოდი არ მოიძებნა")
    if period.status == "open":
        raise HTTPException(status_code=409, detail="სააღრიცხვო პერიოდი უკვე ღიაა")
    period.status = "open"
    period.reopened_by = current_user.id
    period.reopened_at = utc_now()
    db.add(AccountingPeriodEvent(company_id=current_user.company_id, period_id=period.id, action="reopened", reason=payload.reason, actor_id=current_user.id))
    db.add(AuditLog(company_id=current_user.company_id, user_id=current_user.id, action="accounting_period.reopened", entity_type="accounting_period", entity_id=period.id, details=f"{year:04d}-{month:02d}: {payload.reason}"))
    await db.flush()
    await db.refresh(period)
    return ResponseBase(data=period, message="სააღრიცხვო პერიოდი ხელახლა გაიხსნა")


@router.get("/{period_id}/history", response_model=ResponseBase[list[AccountingPeriodEventResponse]])
async def period_history(period_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    require_finance_role(current_user)
    period = await db.scalar(select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.company_id == current_user.company_id))
    if not period:
        raise HTTPException(status_code=404, detail="სააღრიცხვო პერიოდი არ მოიძებნა")
    rows = (await db.execute(select(AccountingPeriodEvent).where(AccountingPeriodEvent.period_id == period.id).order_by(AccountingPeriodEvent.created_at))).scalars().all()
    return ResponseBase(data=rows)


# ═══════════════════════ Year closing (Odoo) ══════════════════════════════════

@router.post("/{year}/close-year", response_model=ResponseBase[dict])
async def close_year(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close a fiscal year: zero out all P&L accounts (4xxx/5xxx) into
    retained earnings (3200) with a balanced closing entry.

    Idempotent: if the year is already closed, returns the existing entry.
    """
    require_finance_role(current_user)
    if year < 2000 or year > 2200:
        raise HTTPException(status_code=422, detail="წელი არასწორია")

    from decimal import Decimal
    from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
    from app.services.gl_posting import post_journal_entry, get_account_map

    # Already closed?
    existing = (await db.execute(select(JournalEntry).where(
        JournalEntry.company_id == current_user.company_id,
        JournalEntry.reference_type == "year_closing",
        JournalEntry.entry_date >= date(year, 1, 1),
        JournalEntry.entry_date <= date(year, 12, 31),
    ))).scalar_one_or_none()
    if existing:
        return ResponseBase(data={
            "entry_id": str(existing.id), "entry_number": existing.entry_number,
            "already_closed": True,
        }, message="წელი უკვე დახურულია")

    # Aggregate P&L balances for the year
    rows = (await db.execute(
        select(
            GLAccount.code, GLAccount.account_type,
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0),
        )
        .select_from(GLAccount)
        .join(JournalEntryLine, JournalEntryLine.gl_account_id == GLAccount.id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(
            GLAccount.company_id == current_user.company_id,
            GLAccount.account_type.in_(["income", "expense"]),
            JournalEntry.entry_date >= date(year, 1, 1),
            JournalEntry.entry_date <= date(year, 12, 31),
        )
        .group_by(GLAccount.code, GLAccount.account_type)
    )).all()

    lines: list[tuple[str, Decimal, Decimal]] = []
    net = Decimal("0")
    for code, account_type, debit, credit in rows:
        debit = Decimal(debit)
        credit = Decimal(credit)
        if account_type == "income":
            balance = credit - debit  # income accounts carry credit balances
            if balance > 0:
                lines.append((code, balance, Decimal("0")))  # close: Dr income
            elif balance < 0:
                lines.append((code, Decimal("0"), abs(balance)))
            net += balance
        else:
            balance = debit - credit  # expense accounts carry debit balances
            if balance > 0:
                lines.append((code, Decimal("0"), balance))  # close: Cr expense
            elif balance < 0:
                lines.append((code, abs(balance), Decimal("0")))
            net -= balance

    if not lines:
        return ResponseBase(data={"closed": False, "net_income": 0.0},
                            message="წელს P&L მოძრაობა არ აქვს — დახურვა არ არის საჭირო")

    # Retained earnings side: net income → Cr 3200 (profit) or Dr 3200 (loss)
    if net > 0:
        lines.append(("3200", Decimal("0"), net))
    else:
        lines.append(("3200", abs(net), Decimal("0")))

    entry = await post_journal_entry(
        db, current_user.company_id, current_user,
        entry_date=date(year, 12, 31),
        description=f"წლის დახურვა {year} — P&L → გაუნაწილებელი მოგება",
        reference_type="year_closing",
        reference_id=current_user.id,
        lines=lines,
    )
    await db.commit()
    return ResponseBase(data={
        "entry_id": str(entry.id), "entry_number": entry.entry_number,
        "net_income": float(net), "closed": True,
    }, message=f"წელი {year} დაიხურა — net income {float(net):.2f} ₾ გადავიდა გაუნაწილებელ მოგებაში")
