"""Exchange difference (revaluation) API endpoints."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.exchange_difference import ExchangeDifference
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.exchange_difference import (
    ExchangeDifferenceResponse,
    ExchangeDifferenceRunResponse,
)
from app.services.exchange_differences import run_revaluation

router = APIRouter(prefix="/gl/exchange-differences", tags=["მთავარი წიგნი — საკურსო სხვაობა"])


def require_gl_role(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="მთავარი წიგნის ოპერაციები ხელმისაწვდომია მხოლოდ ადმინის/ბუღალტერისთვის")


def _to_response(d: ExchangeDifference) -> ExchangeDifferenceResponse:
    return ExchangeDifferenceResponse(
        id=d.id, company_id=d.company_id, receivable_id=d.receivable_id,
        payable_id=d.payable_id, cash_account_id=d.cash_account_id, bank_account_id=d.bank_account_id,
        currency=d.currency, revaluation_date=d.revaluation_date,
        outstanding_amount=float(d.outstanding_amount), rate=float(d.rate),
        gel_equivalent=float(d.gel_equivalent),
        previous_gel_equivalent=float(d.previous_gel_equivalent) if d.previous_gel_equivalent is not None else None,
        difference=float(d.difference), journal_entry_id=d.journal_entry_id,
        created_at=d.created_at,
    )


@router.post("/run", response_model=ResponseBase[ExchangeDifferenceRunResponse])
async def run_exchange_differences(
    on_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revalue all open foreign-currency receivables and post GL differences."""
    require_gl_role(current_user)
    run_date = on_date or date.today()
    result = await run_revaluation(db, current_user.company_id, run_date, current_user.id)
    add_audit(db, current_user, "exchange_diff.run", "gl", uuid.uuid4(), {
        "on_date": str(run_date),
        "revaluated": result["revaluated"],
        "posted": result["posted_entries"],
    })
    await db.commit()
    return ResponseBase(data=ExchangeDifferenceRunResponse(
        revaluated=result["revaluated"],
        posted_entries=result["posted_entries"],
        total_difference=float(result["total_difference"]),
    ))


@router.get("/", response_model=ResponseBase[PaginatedResponse[ExchangeDifferenceResponse]])
async def list_exchange_differences(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    currency: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    filters = [ExchangeDifference.company_id == current_user.company_id]
    if currency:
        filters.append(ExchangeDifference.currency == currency.upper())
    if date_from:
        filters.append(ExchangeDifference.revaluation_date >= date_from)
    if date_to:
        filters.append(ExchangeDifference.revaluation_date <= date_to)
    total = (await db.execute(select(func.count(ExchangeDifference.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(ExchangeDifference)
            .where(*filters)
            .order_by(ExchangeDifference.revaluation_date.desc(), ExchangeDifference.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_to_response(d) for d in rows],
    ))
