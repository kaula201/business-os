from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.email_marketing import EmailCampaign
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.email_marketing import (
    EmailCampaignCreate,
    EmailCampaignResponse,
    EmailCampaignUpdate,
)

router = APIRouter(prefix="/email-campaigns", tags=["Email Marketing"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[EmailCampaignResponse]])
async def list_email_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-marketing", "can_access")),
):
    query = select(EmailCampaign).where(
        EmailCampaign.company_id == current_user.company_id
    )
    if status:
        query = query.where(EmailCampaign.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(EmailCampaign.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    campaigns = (await db.execute(query)).scalars().all()

    return ResponseBase(
        data=PaginatedResponse(
            items=[EmailCampaignResponse.model_validate(c) for c in campaigns],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{campaign_id}", response_model=ResponseBase[EmailCampaignResponse])
async def get_email_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-marketing", "can_access")),
):
    result = await db.execute(
        select(EmailCampaign).where(
            EmailCampaign.id == campaign_id,
            EmailCampaign.company_id == current_user.company_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="კამპანია არ მოიძებნა")
    return ResponseBase(data=EmailCampaignResponse.model_validate(campaign))


@router.post("/", response_model=ResponseBase[EmailCampaignResponse])
async def create_email_campaign(
    data: EmailCampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-marketing", "can_create")),
):
    campaign = EmailCampaign(
        company_id=current_user.company_id,
        name=data.name,
        subject=data.subject,
        audience=data.audience,
        status=data.status,
        scheduled_at=data.scheduled_at,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return ResponseBase(data=EmailCampaignResponse.model_validate(campaign))


@router.patch("/{campaign_id}", response_model=ResponseBase[EmailCampaignResponse])
async def update_email_campaign(
    campaign_id: UUID,
    data: EmailCampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-marketing", "can_edit")),
):
    result = await db.execute(
        select(EmailCampaign).where(
            EmailCampaign.id == campaign_id,
            EmailCampaign.company_id == current_user.company_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="კამპანია არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    await db.flush()
    await db.refresh(campaign)
    return ResponseBase(data=EmailCampaignResponse.model_validate(campaign))


@router.delete("/{campaign_id}", response_model=ResponseBase[dict])
async def delete_email_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-marketing", "can_delete")),
):
    result = await db.execute(
        select(EmailCampaign).where(
            EmailCampaign.id == campaign_id,
            EmailCampaign.company_id == current_user.company_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="კამპანია არ მოიძებნა")

    await db.delete(campaign)
    await db.flush()
    return ResponseBase(data={"message": "კამპანია წაიშალა"})
