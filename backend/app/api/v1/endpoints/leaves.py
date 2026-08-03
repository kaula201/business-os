from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.leave import Leave
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.leave import (
    LeaveApprove,
    LeaveCreate,
    LeaveResponse,
    LeaveUpdate,
)

router = APIRouter(prefix="/leaves", tags=["Leaves"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[LeaveResponse]])
async def list_leaves(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    employee_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("leaves", "can_access")),
):
    query = select(Leave).where(
        Leave.company_id == current_user.company_id
    )
    if status:
        query = query.where(Leave.status == status)
    if employee_id:
        query = query.where(Leave.employee_id == employee_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(Leave.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    leaves = (await db.execute(query)).scalars().all()

    return ResponseBase(
        data=PaginatedResponse(
            items=[LeaveResponse.model_validate(l) for l in leaves],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{leave_id}", response_model=ResponseBase[LeaveResponse])
async def get_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("leaves", "can_access")),
):
    result = await db.execute(
        select(Leave).where(
            Leave.id == leave_id,
            Leave.company_id == current_user.company_id,
        )
    )
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="შვებულება არ მოიძებნა")
    return ResponseBase(data=LeaveResponse.model_validate(leave))


@router.post("/", response_model=ResponseBase[LeaveResponse])
async def create_leave(
    data: LeaveCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("leaves", "can_create")),
):
    days = data.days
    if days is None:
        days = (data.end_date - data.start_date).days + 1
    leave = Leave(
        company_id=current_user.company_id,
        employee_id=data.employee_id,
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        days=days,
        reason=data.reason,
        status=Leave.Status.PENDING,
    )
    db.add(leave)
    await db.flush()
    await db.refresh(leave)
    return ResponseBase(data=LeaveResponse.model_validate(leave))


@router.patch("/{leave_id}", response_model=ResponseBase[LeaveResponse])
async def update_leave(
    leave_id: UUID,
    data: LeaveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("leaves", "can_edit")),
):
    result = await db.execute(
        select(Leave).where(
            Leave.id == leave_id,
            Leave.company_id == current_user.company_id,
        )
    )
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="შვებულება არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(leave, field, value)

    await db.flush()
    await db.refresh(leave)
    return ResponseBase(data=LeaveResponse.model_validate(leave))


@router.patch("/{leave_id}/approve", response_model=ResponseBase[LeaveResponse])
async def approve_leave(
    leave_id: UUID,
    data: LeaveApprove,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("leaves", "can_edit")),
):
    result = await db.execute(
        select(Leave).where(
            Leave.id == leave_id,
            Leave.company_id == current_user.company_id,
        )
    )
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="შვებულება არ მოიძებნა")
    if leave.status != Leave.Status.PENDING:
        raise HTTPException(status_code=400, detail="მხოლოდ დამუშავებული შვებულების განაცხადის დამტკიცებაა შესაძლებელი")

    leave.status = data.status
    if data.reason:
        leave.reason = data.reason

    await db.flush()
    await db.refresh(leave)
    return ResponseBase(data=LeaveResponse.model_validate(leave))


@router.delete("/{leave_id}", response_model=ResponseBase[dict])
async def delete_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("leaves", "can_delete")),
):
    result = await db.execute(
        select(Leave).where(
            Leave.id == leave_id,
            Leave.company_id == current_user.company_id,
        )
    )
    leave = result.scalar_one_or_none()
    if not leave:
        raise HTTPException(status_code=404, detail="შვებულება არ მოიძებნა")

    await db.delete(leave)
    await db.flush()
    return ResponseBase(data={"message": "შვებულება წაიშალა"})
