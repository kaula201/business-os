"""Email + calendar endpoints — send email, calendar events CRUD."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.email_calendar import CalendarEvent, EmailMessage
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/email-calendar", tags=["ელ.ფოსტა და კალენდარი"])


# ── Email ─────────────────────────────────────────────────────────────────────

@router.get("/emails", response_model=ResponseBase[list[dict]])
async def list_emails(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-calendar", "can_access")),
):
    result = await db.execute(
        select(EmailMessage).where(EmailMessage.company_id == current_user.company_id).order_by(EmailMessage.created_at.desc()).limit(100)
    )
    return ResponseBase(data=[{
        "id": str(m.id), "to_email": m.to_email, "subject": m.subject,
        "status": m.status, "created_at": m.created_at.isoformat(),
    } for m in result.scalars().all()])


@router.post("/emails", response_model=ResponseBase[dict], status_code=201)
async def send_email(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-calendar", "can_create")),
):
    """Send an email. In sandbox mode the message is stored with status 'sent'."""
    to_email = (data.get("to_email") or "").strip()
    subject = (data.get("subject") or "").strip()
    if not to_email or not subject:
        raise HTTPException(status_code=422, detail="to_email და subject აუცილებელია")

    m = EmailMessage(
        company_id=current_user.company_id,
        to_email=to_email,
        subject=subject,
        body=data.get("body", ""),
        status="sent",
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return ResponseBase(data={"id": str(m.id), "to_email": m.to_email, "subject": m.subject, "status": m.status}, message="ელ.ფოსტა გაიგზავნა")


# ── Calendar ──────────────────────────────────────────────────────────────────

@router.get("/events", response_model=ResponseBase[list[dict]])
async def list_events(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-calendar", "can_access")),
):
    query = select(CalendarEvent).where(CalendarEvent.company_id == current_user.company_id)
    if date_from:
        query = query.where(CalendarEvent.event_date >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(CalendarEvent.event_date <= datetime.fromisoformat(date_to))
    query = query.order_by(CalendarEvent.event_date)
    result = await db.execute(query)
    return ResponseBase(data=[{
        "id": str(e.id), "title": e.title, "description": e.description,
        "event_date": e.event_date.isoformat(), "end_date": e.end_date.isoformat() if e.end_date else None,
        "event_type": e.event_type, "related_to": e.related_to, "related_id": str(e.related_id) if e.related_id else None,
    } for e in result.scalars().all()])


@router.post("/events", response_model=ResponseBase[dict], status_code=201)
async def create_event(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-calendar", "can_create")),
):
    try:
        event_date = datetime.fromisoformat((data.get("event_date") or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="event_date არასწორია")

    e = CalendarEvent(
        company_id=current_user.company_id,
        title=data.get("title", ""),
        description=data.get("description"),
        event_date=event_date,
        end_date=datetime.fromisoformat(data["end_date"].replace("Z", "+00:00")) if data.get("end_date") else None,
        event_type=data.get("event_type", "meeting"),
        related_to=data.get("related_to"),
        related_id=data.get("related_id"),
        created_by=current_user.id,
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return ResponseBase(data={"id": str(e.id), "title": e.title, "event_date": e.event_date.isoformat()}, message="ღონისძიება შეიქმნა")


@router.delete("/events/{event_id}", response_model=ResponseBase[dict])
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("email-calendar", "can_delete")),
):
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id, CalendarEvent.company_id == current_user.company_id)
    )
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="ღონისძიება არ მოიძებნა")
    await db.delete(e)
    await db.commit()
    return ResponseBase(data={"id": str(event_id)}, message="ღონისძიება წაიშალა")
