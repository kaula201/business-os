"""Email tracking + e-signature API."""
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.email_marketing import EmailCampaign
from app.models.email_tracking import EmailEvent
from app.models.signature import SignatureRequest
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.email_tracking import (
    CampaignStatsResponse,
    EmailEventCreate,
    EmailEventResponse,
    SignatureRequestCreate,
    SignatureRequestResponse,
    SignatureSignRequest,
)

router = APIRouter(tags=["კომუნიკაცია"])


# ── Email tracking ───────────────────────────────────────────────────────────

@router.post("/email-events/", response_model=ResponseBase[EmailEventResponse], status_code=201)
async def record_email_event(
    data: EmailEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = (await db.execute(select(EmailCampaign).where(
        EmailCampaign.id == data.campaign_id,
        EmailCampaign.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="კამპანია ვერ მოიძებნა")
    event = EmailEvent(
        company_id=current_user.company_id, campaign_id=data.campaign_id,
        recipient_email=data.recipient_email, event_type=data.event_type,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return ResponseBase(data=EmailEventResponse(
        id=event.id, company_id=event.company_id, campaign_id=event.campaign_id,
        recipient_email=event.recipient_email, event_type=event.event_type,
        occurred_at=event.occurred_at,
    ))


@router.get("/email-campaigns/{campaign_id}/stats", response_model=ResponseBase[CampaignStatsResponse])
async def campaign_stats(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = (await db.execute(select(EmailCampaign).where(
        EmailCampaign.id == campaign_id,
        EmailCampaign.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="კამპანია ვერ მოიძებნა")

    counts = {}
    for et in ("sent", "opened", "clicked"):
        counts[et] = (await db.execute(select(func.count(EmailEvent.id)).where(
            EmailEvent.company_id == current_user.company_id,
            EmailEvent.campaign_id == campaign_id,
            EmailEvent.event_type == et,
        ))).scalar_one()

    sent = counts["sent"]
    open_rate = (counts["opened"] / sent * 100) if sent else 0
    click_rate = (counts["clicked"] / sent * 100) if sent else 0
    return ResponseBase(data=CampaignStatsResponse(
        campaign_id=campaign_id, sent=sent, opened=counts["opened"],
        clicked=counts["clicked"], open_rate=round(open_rate, 1),
        click_rate=round(click_rate, 1),
    ))


@router.get("/email-events/", response_model=ResponseBase[PaginatedResponse[EmailEventResponse]])
async def list_email_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    campaign_id: uuid.UUID | None = None,
    event_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [EmailEvent.company_id == current_user.company_id]
    if campaign_id:
        filters.append(EmailEvent.campaign_id == campaign_id)
    if event_type:
        filters.append(EmailEvent.event_type == event_type)
    total = (await db.execute(select(func.count(EmailEvent.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(EmailEvent).where(*filters)
                         .order_by(EmailEvent.occurred_at.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[EmailEventResponse(
            id=e.id, company_id=e.company_id, campaign_id=e.campaign_id,
            recipient_email=e.recipient_email, event_type=e.event_type,
            occurred_at=e.occurred_at,
        ) for e in rows],
    ))


# ── E-signature ──────────────────────────────────────────────────────────────

def _sig_response(r: SignatureRequest) -> SignatureRequestResponse:
    return SignatureRequestResponse(
        id=r.id, company_id=r.company_id, document_name=r.document_name,
        document_url=r.document_url, signer_name=r.signer_name, signer_email=r.signer_email,
        status=r.status, signed_at=r.signed_at, signed_by_email=r.signed_by_email,
        message=r.message, created_at=r.created_at, updated_at=r.updated_at,
    )


@router.get("/signature-requests/", response_model=ResponseBase[PaginatedResponse[SignatureRequestResponse]])
async def list_signature_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [SignatureRequest.company_id == current_user.company_id]
    if status:
        filters.append(SignatureRequest.status == status)
    total = (await db.execute(select(func.count(SignatureRequest.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(SignatureRequest).where(*filters)
                         .order_by(SignatureRequest.created_at.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size, items=[_sig_response(r) for r in rows],
    ))


@router.post("/signature-requests/", response_model=ResponseBase[SignatureRequestResponse], status_code=201)
async def create_signature_request(
    data: SignatureRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = secrets.token_urlsafe(24)
    req = SignatureRequest(
        company_id=current_user.company_id, document_name=data.document_name,
        document_url=data.document_url, signer_name=data.signer_name,
        signer_email=data.signer_email, signing_token=token, message=data.message,
        created_by=current_user.id,
    )
    db.add(req)
    await db.flush()
    add_audit(db, current_user, "signature_request.created", "signature_request", req.id,
              {"document": req.document_name, "signer": req.signer_email})
    await db.commit()
    await db.refresh(req)
    return ResponseBase(data=_sig_response(req))


@router.post("/signature-requests/sign", response_model=ResponseBase[SignatureRequestResponse])
async def sign_request(
    data: SignatureSignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sign or decline a request by token + signer email (the signer acts)."""
    req = (await db.execute(select(SignatureRequest).where(
        SignatureRequest.signing_token == data.token,
    ).with_for_update())).scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="მოთხოვნა ვერ მოიძებნა")
    if req.signer_email.lower() != data.signer_email.lower():
        raise HTTPException(status_code=403, detail="ხელმოწერის უფლება მხოლოდ მითითებულ ხელმომწერს აქვს")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail="მოთხოვნა უკვე დამუშავებულია")

    req.status = "signed" if data.decision == "sign" else "declined"
    req.signed_by_email = data.signer_email
    req.signed_at = utc_now()
    add_audit(db, current_user, "signature_request.signed", "signature_request", req.id,
              {"decision": data.decision})
    await db.commit()
    await db.refresh(req)
    return ResponseBase(data=_sig_response(req))
