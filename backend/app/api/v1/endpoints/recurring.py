"""Recurring journal entry API endpoints."""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.recurring import RecurringJournalEntry
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.recurring import (
    RecurringJournalEntryCreate,
    RecurringJournalEntryResponse,
    RecurringJournalEntryUpdate,
    RecurringRunResponse,
)
from app.services.recurring_entries import compute_next_run, post_due_entries

router = APIRouter(prefix="/gl/recurring", tags=["მთავარი წიგნი — განმეორებადი"])


def require_gl_role(user: User) -> None:
    if user.role not in (User.Role.ADMIN, User.Role.ACCOUNTANT):
        raise HTTPException(status_code=403, detail="მთავარი წიგნის ოპერაციები ხელმისაწვდომია მხოლოდ ადმინის/ბუღალტერისთვის")


async def _to_response(rec: RecurringJournalEntry) -> RecurringJournalEntryResponse:
    return RecurringJournalEntryResponse(
        id=rec.id, company_id=rec.company_id, name=rec.name, description=rec.description,
        frequency=rec.frequency, interval=rec.interval, day_of_week=rec.day_of_week,
        day_of_month=rec.day_of_month, start_date=rec.start_date, end_date=rec.end_date,
        next_run_date=rec.next_run_date, last_run_date=rec.last_run_date, lines=rec.lines,
        entry_description=rec.entry_description, is_active=rec.is_active,
        total_posted=rec.total_posted, created_at=rec.created_at, updated_at=rec.updated_at,
    )


@router.get("/", response_model=ResponseBase[PaginatedResponse[RecurringJournalEntryResponse]])
async def list_recurring(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    filters = [RecurringJournalEntry.company_id == current_user.company_id]
    if is_active is not None:
        filters.append(RecurringJournalEntry.is_active == is_active)
    total = (await db.execute(select(func.count(RecurringJournalEntry.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(RecurringJournalEntry)
            .where(*filters)
            .order_by(RecurringJournalEntry.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[await _to_response(r) for r in rows],
    ))


@router.post("/", response_model=ResponseBase[RecurringJournalEntryResponse], status_code=201)
async def create_recurring(
    data: RecurringJournalEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)

    # Validate tenant-scoped active accounts
    from app.models.gl import GLAccount
    account_ids = [l.gl_account_id for l in data.lines]
    found = (
        await db.execute(
            select(GLAccount.id).where(
                GLAccount.company_id == current_user.company_id,
                GLAccount.id.in_(account_ids),
                GLAccount.is_active == True,
            )
        )
    ).scalars().all()
    if len(set(account_ids)) != len(set(found)):
        raise HTTPException(status_code=400, detail="ერთი ან მეტი ანგარიში ვერ მოიძებნა ან არააქტიურია")

    # Balance check
    dr = sum(Decimal(str(l.debit_amount or 0)) for l in data.lines)
    cr = sum(Decimal(str(l.credit_amount or 0)) for l in data.lines)
    if dr != cr:
        raise HTTPException(status_code=400, detail=f"ბალანსი არ იყრის თავს: debit={dr}, credit={cr}")

    rec = RecurringJournalEntry(
        company_id=current_user.company_id,
        name=data.name,
        description=data.description,
        frequency=data.frequency,
        interval=data.interval,
        day_of_week=data.day_of_week,
        day_of_month=data.day_of_month,
        start_date=data.start_date,
        end_date=data.end_date,
        entry_description=data.entry_description,
        lines=[{**l.model_dump(), "gl_account_id": str(l.gl_account_id)} for l in data.lines],
        next_run_date=data.start_date,
        created_by=current_user.id,
    )
    db.add(rec)
    await db.flush()
    add_audit(db, current_user, "recurring.created", "recurring", rec.id, {"name": rec.name})
    await db.commit()
    await db.refresh(rec)
    return ResponseBase(data=await _to_response(rec))


@router.get("/{recurring_id}", response_model=ResponseBase[RecurringJournalEntryResponse])
async def get_recurring(
    recurring_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    rec = (
        await db.execute(
            select(RecurringJournalEntry).where(
                RecurringJournalEntry.id == recurring_id,
                RecurringJournalEntry.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="განმეორებადი ჩანაწერი ვერ მოიძებნა")
    return ResponseBase(data=await _to_response(rec))


@router.patch("/{recurring_id}", response_model=ResponseBase[RecurringJournalEntryResponse])
async def update_recurring(
    recurring_id: uuid.UUID,
    data: RecurringJournalEntryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    rec = (
        await db.execute(
            select(RecurringJournalEntry).where(
                RecurringJournalEntry.id == recurring_id,
                RecurringJournalEntry.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="განმეორებადი ჩანაწერი ვერ მოიძებნა")

    if data.name is not None:
        rec.name = data.name
    if data.description is not None:
        rec.description = data.description
    if data.frequency is not None:
        rec.frequency = data.frequency
    if data.interval is not None:
        rec.interval = data.interval
    if data.day_of_week is not None:
        rec.day_of_week = data.day_of_week
    if data.day_of_month is not None:
        rec.day_of_month = data.day_of_month
    if data.end_date is not None:
        rec.end_date = data.end_date
    if data.entry_description is not None:
        rec.entry_description = data.entry_description
    if data.lines is not None:
        rec.lines = [{**l.model_dump(), "gl_account_id": str(l.gl_account_id)} for l in data.lines]
    if data.is_active is not None:
        rec.is_active = data.is_active
    # Recompute next run if schedule fields changed
    if data.frequency is not None or data.interval is not None or data.day_of_week is not None or data.day_of_month is not None:
        base = rec.next_run_date
        rec.next_run_date = compute_next_run(rec, date(base.year, base.month, base.day))

    add_audit(db, current_user, "recurring.updated", "recurring", rec.id, {"name": rec.name})
    await db.commit()
    await db.refresh(rec)
    return ResponseBase(data=await _to_response(rec))


@router.delete("/{recurring_id}", response_model=ResponseBase)
async def delete_recurring(
    recurring_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_gl_role(current_user)
    rec = (
        await db.execute(
            select(RecurringJournalEntry).where(
                RecurringJournalEntry.id == recurring_id,
                RecurringJournalEntry.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="განმეორებადი ჩანაწერი ვერ მოიძებნა")
    await db.delete(rec)
    add_audit(db, current_user, "recurring.deleted", "recurring", rec.id, {"name": rec.name})
    await db.commit()
    return ResponseBase(message="განმეორებადი ჩანაწერი წაშლილია")


@router.post("/run", response_model=ResponseBase[RecurringRunResponse])
async def run_due(
    through_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post all due recurring entries now (manual trigger)."""
    require_gl_role(current_user)
    posted = await post_due_entries(db, current_user.company_id, through_date)
    return ResponseBase(data=RecurringRunResponse(posted=posted))
