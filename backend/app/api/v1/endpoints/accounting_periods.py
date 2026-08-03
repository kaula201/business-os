"""Accounting period close/reopen API."""
import calendar
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
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
