# backend/app/api/v1/endpoints/quality_control.py
"""Quality Control API."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.quality_control import QualityCheck
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.quality_control import QualityCheckCreate, QualityCheckResponse, QualityCheckUpdate

router = APIRouter(prefix="/quality-control", tags=["Quality Control"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[QualityCheckResponse]])
async def list_quality_checks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_access")),
):
    query = select(QualityCheck).where(QualityCheck.company_id == current_user.company_id)
    if product_id:
        query = query.where(QualityCheck.product_id == product_id)
    if status:
        query = query.where(QualityCheck.status == status)
    query = query.order_by(QualityCheck.created_at.desc())

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()
    return ResponseBase(
        data=PaginatedResponse(
            items=[QualityCheckResponse.model_validate(q) for q in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{check_id}", response_model=ResponseBase[QualityCheckResponse])
async def get_quality_check(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_access")),
):
    result = await db.execute(
        select(QualityCheck).where(
            QualityCheck.id == check_id,
            QualityCheck.company_id == current_user.company_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="ხარისხის შემოწმება არ მოიძებნა")
    return ResponseBase(data=QualityCheckResponse.model_validate(check))


@router.post("/", response_model=ResponseBase[QualityCheckResponse], status_code=201)
async def create_quality_check(
    data: QualityCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_create")),
):
    check = QualityCheck(
        company_id=current_user.company_id,
        product_id=data.product_id,
        checked_by=data.checked_by,
        status=data.status,
        notes=data.notes,
        checked_at=data.checked_at,
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)
    return ResponseBase(data=QualityCheckResponse.model_validate(check))


@router.put("/{check_id}", response_model=ResponseBase[QualityCheckResponse])
async def update_quality_check(
    check_id: UUID,
    data: QualityCheckUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_edit")),
):
    result = await db.execute(
        select(QualityCheck).where(
            QualityCheck.id == check_id,
            QualityCheck.company_id == current_user.company_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="ხარისხის შემოწმება არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(check, field, value)
    await db.commit()
    await db.refresh(check)
    return ResponseBase(data=QualityCheckResponse.model_validate(check))


@router.delete("/{check_id}", response_model=ResponseBase[dict])
async def delete_quality_check(
    check_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("quality-control", "can_delete")),
):
    result = await db.execute(
        select(QualityCheck).where(
            QualityCheck.id == check_id,
            QualityCheck.company_id == current_user.company_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="ხარისხის შემოწმება არ მოიძებნა")
    await db.delete(check)
    await db.commit()
    return ResponseBase(data={"id": str(check_id)}, message="ხარისხის შემოწმება წაიშალა")
