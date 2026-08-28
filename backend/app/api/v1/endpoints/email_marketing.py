from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.email_marketing import EmailCampaign
from app.models.email_tracking import EmailEvent
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.email_marketing import (
    EmailCampaignCreate,
    EmailCampaignResponse,
    EmailCampaignUpdate,
)
from app.services.email_service import send_email_smtp, smtp_configured

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
        body=data.body,
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


@router.post("/{campaign_id}/send", response_model=ResponseBase[dict])
async def send_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-marketing", "can_edit")),
):
    """Send the campaign to its audience. Real SMTP when configured, else sandbox (email_messages)."""
    result = await db.execute(
        select(EmailCampaign).where(
            EmailCampaign.id == campaign_id,
            EmailCampaign.company_id == current_user.company_id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="კამპანია არ მოიძებნა")
    if campaign.status == "sent":
        raise HTTPException(status_code=400, detail="კამპანია უკვე გაგზავნილია")

    # Audience: explicit email list, or client emails when audience is a client filter.
    raw = campaign.audience or {}
    emails: list[str] = []
    if isinstance(raw, dict):
        if raw.get("emails"):
            emails = [e.strip().lower() for e in raw["emails"] if e and e.strip()]
        elif raw.get("client_ids"):
            from app.models.client import Client

            rows = (await db.execute(
                select(Client).where(
                    Client.id.in_(raw["client_ids"]),
                    Client.company_id == current_user.company_id,
                ).options(selectinload(Client.contacts))
            )).scalars().all()
            for c in rows:
                # Email lives on the primary contact; fall back to the client row.
                email = c.email or (c.contacts[0].email if c.contacts else None)
                if email:
                    emails.append(email.lower())
    elif isinstance(raw, list):
        emails = [e.strip().lower() for e in raw if e and str(e).strip()]

    if not emails:
        raise HTTPException(status_code=422, detail="audience-ში ელფოსტები არ არის მითითებული")

    smtp_on = smtp_configured()
    sent_count = 0
    failed_count = 0
    for email in emails:
        try:
            if smtp_on:
                send_email_smtp(email, campaign.subject, campaign.body)
            else:
                from app.models.email_calendar import EmailMessage

                db.add(EmailMessage(
                    company_id=current_user.company_id,
                    to_email=email, subject=campaign.subject, body=campaign.body,
                    status="sent",
                ))
                await db.flush()
            db.add(EmailEvent(
                company_id=current_user.company_id, campaign_id=campaign.id,
                recipient_email=email, event_type="sent",
            ))
            sent_count += 1
        except Exception:
            failed_count += 1

    campaign.status = "sent"
    campaign.sent_at = func.now()
    await db.commit()
    return ResponseBase(
        data={"sent": sent_count, "failed": failed_count, "mode": "smtp" if smtp_on else "sandbox"},
        message=f"კამპანია გაიგზავნა — {sent_count} მიმღები, {failed_count} შეცდომა",
    )


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
