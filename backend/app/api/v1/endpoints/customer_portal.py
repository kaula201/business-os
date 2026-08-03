from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.customer_portal import PortalUser
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.customer_portal import (
    PortalUserCreate,
    PortalUserResponse,
    PortalUserUpdate,
)

router = APIRouter(prefix="/customer-portal", tags=["Customer Portal"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[PortalUserResponse]])
async def list_portal_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    client_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("customer-portal", "can_access")),
):
    query = select(PortalUser).where(PortalUser.company_id == current_user.company_id)
    if status:
        query = query.where(PortalUser.status == status)
    if client_id:
        query = query.where(PortalUser.client_id == client_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(PortalUser.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    portal_users = (await db.execute(query)).scalars().all()

    return ResponseBase(
        data=PaginatedResponse(
            items=[PortalUserResponse.model_validate(u) for u in portal_users],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{portal_user_id}", response_model=ResponseBase[PortalUserResponse])
async def get_portal_user(
    portal_user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("customer-portal", "can_access")),
):
    result = await db.execute(
        select(PortalUser).where(
            PortalUser.id == portal_user_id,
            PortalUser.company_id == current_user.company_id,
        )
    )
    portal_user = result.scalar_one_or_none()
    if not portal_user:
        raise HTTPException(status_code=404, detail="პორტალის მომხმარებელი არ მოიძებნა")
    return ResponseBase(data=PortalUserResponse.model_validate(portal_user))


@router.post("/", response_model=ResponseBase[PortalUserResponse])
async def create_portal_user(
    data: PortalUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("customer-portal", "can_create")),
):
    portal_user = PortalUser(
        company_id=current_user.company_id,
        client_id=data.client_id,
        email=data.email,
        display_name=data.display_name,
        status=data.status,
    )
    db.add(portal_user)
    await db.flush()
    await db.refresh(portal_user)
    return ResponseBase(data=PortalUserResponse.model_validate(portal_user))


@router.patch("/{portal_user_id}", response_model=ResponseBase[PortalUserResponse])
async def update_portal_user(
    portal_user_id: UUID,
    data: PortalUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("customer-portal", "can_edit")),
):
    result = await db.execute(
        select(PortalUser).where(
            PortalUser.id == portal_user_id,
            PortalUser.company_id == current_user.company_id,
        )
    )
    portal_user = result.scalar_one_or_none()
    if not portal_user:
        raise HTTPException(status_code=404, detail="პორტალის მომხმარებელი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(portal_user, field, value)

    await db.flush()
    await db.refresh(portal_user)
    return ResponseBase(data=PortalUserResponse.model_validate(portal_user))


@router.delete("/{portal_user_id}", response_model=ResponseBase[dict])
async def delete_portal_user(
    portal_user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("customer-portal", "can_delete")),
):
    result = await db.execute(
        select(PortalUser).where(
            PortalUser.id == portal_user_id,
            PortalUser.company_id == current_user.company_id,
        )
    )
    portal_user = result.scalar_one_or_none()
    if not portal_user:
        raise HTTPException(status_code=404, detail="პორტალის მომხმარებელი არ მოიძებნა")

    await db.delete(portal_user)
    await db.flush()
    return ResponseBase(data={"message": "პორტალის მომხმარებელი წაიშალა"})
