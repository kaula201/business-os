# backend/app/api/v1/endpoints/helpdesk.py
"""Helpdesk ticket management API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.user import User
from app.models.helpdesk import HelpdeskTicket
from app.models.helpdesk_ext import (
    HelpdeskQueue, HelpdeskSla, HelpdeskEscalation, CannedReply, KnowledgeArticle, FieldServiceJob, EmailIntakeRule,
)
from app.schemas.helpdesk import (
    HelpdeskTicketCreate,
    HelpdeskTicketUpdate,
    HelpdeskTicketResponse,
    HelpdeskTicketListResponse,
)
from app.schemas.common import ResponseBase, PaginatedResponse

router = APIRouter(prefix="/helpdesk", tags=["Helpdesk"])


def _enrich_ticket(ticket: HelpdeskTicket) -> HelpdeskTicketResponse:
    resp = HelpdeskTicketResponse.model_validate(ticket)
    resp.assignee_name = ticket.assignee.full_name if ticket.assignee else None
    resp.requester_name = ticket.requester.full_name if ticket.requester else None
    return resp


@router.get("/", response_model=ResponseBase[PaginatedResponse[HelpdeskTicketListResponse]])
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    query = select(HelpdeskTicket).where(HelpdeskTicket.company_id == current_user.company_id).options(
        selectinload(HelpdeskTicket.assignee), selectinload(HelpdeskTicket.requester)
    )
    if status:
        query = query.where(HelpdeskTicket.status == status)
    if priority:
        query = query.where(HelpdeskTicket.priority == priority)
    query = query.order_by(HelpdeskTicket.created_at.desc())

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tickets = result.scalars().all()

    items = []
    for t in tickets:
        li = HelpdeskTicketListResponse.model_validate(t)
        li.assignee_name = t.assignee.full_name if t.assignee else None
        li.requester_name = t.requester.full_name if t.requester else None
        items.append(li)

    return ResponseBase(data=PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    ))


@router.get("/{ticket_id}", response_model=ResponseBase[HelpdeskTicketResponse])
async def get_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(HelpdeskTicket).where(
            HelpdeskTicket.id == ticket_id,
            HelpdeskTicket.company_id == current_user.company_id,
        ).options(selectinload(HelpdeskTicket.assignee), selectinload(HelpdeskTicket.requester))
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="ტიკეტი არ მოიძებნა")
    return ResponseBase(data=_enrich_ticket(ticket))


@router.post("/", response_model=ResponseBase[HelpdeskTicketResponse], status_code=201)
async def create_ticket(
    data: HelpdeskTicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    ticket = HelpdeskTicket(
        company_id=current_user.company_id,
        subject=data.subject,
        description=data.description,
        priority=data.priority.value,
        status=data.status.value,
        assignee_id=data.assignee_id,
        requester_id=data.requester_id,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ResponseBase(data=_enrich_ticket(ticket))


@router.put("/{ticket_id}", response_model=ResponseBase[HelpdeskTicketResponse])
async def update_ticket(
    ticket_id: UUID,
    data: HelpdeskTicketUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_edit")),
):
    result = await db.execute(
        select(HelpdeskTicket).where(
            HelpdeskTicket.id == ticket_id,
            HelpdeskTicket.company_id == current_user.company_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="ტიკეტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None and field in ("priority", "status"):
            setattr(ticket, field, value.value)
        else:
            setattr(ticket, field, value)

    await db.commit()
    await db.refresh(ticket)
    return ResponseBase(data=_enrich_ticket(ticket))


@router.delete("/{ticket_id}", response_model=ResponseBase[dict])
async def delete_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_delete")),
):
    result = await db.execute(
        select(HelpdeskTicket).where(
            HelpdeskTicket.id == ticket_id,
            HelpdeskTicket.company_id == current_user.company_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="ტიკეტი არ მოიძებნა")
    await db.delete(ticket)
    await db.commit()
    return ResponseBase(data={"id": str(ticket_id)}, message="ტიკეტი წაიშალა")


# ── Queues ──────────────────────────────────────────────────────────────────────

@router.get("/queues", response_model=ResponseBase[list[dict]])
async def list_queues(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(HelpdeskQueue).where(HelpdeskQueue.company_id == current_user.company_id).order_by(HelpdeskQueue.name)
    )
    return ResponseBase(data=[{"id": str(q.id), "name": q.name, "description": q.description, "is_active": q.is_active} for q in result.scalars().all()])


@router.post("/queues", response_model=ResponseBase[dict], status_code=201)
async def create_queue(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    q = HelpdeskQueue(company_id=current_user.company_id, name=data.get("name", ""), description=data.get("description"))
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return ResponseBase(data={"id": str(q.id), "name": q.name}, message="რიგი შეიქმნა")


# ── SLAs ───────────────────────────────────────────────────────────────────────

@router.get("/slas", response_model=ResponseBase[list[dict]])
async def list_slas(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(HelpdeskSla).where(HelpdeskSla.company_id == current_user.company_id).order_by(HelpdeskSla.priority)
    )
    return ResponseBase(data=[{"id": str(s.id), "name": s.name, "priority": s.priority, "response_hours": s.response_hours, "resolution_hours": s.resolution_hours, "is_active": s.is_active} for s in result.scalars().all()])


@router.post("/slas", response_model=ResponseBase[dict], status_code=201)
async def create_sla(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    s = HelpdeskSla(
        company_id=current_user.company_id,
        name=data.get("name", ""),
        priority=data.get("priority", "medium"),
        response_hours=int(data.get("response_hours", 24)),
        resolution_hours=int(data.get("resolution_hours", 72)),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return ResponseBase(data={"id": str(s.id), "name": s.name}, message="SLA შეიქმნა")


# ── Escalations ─────────────────────────────────────────────────────────────────

@router.get("/escalations", response_model=ResponseBase[list[dict]])
async def list_escalations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(HelpdeskEscalation).where(HelpdeskEscalation.company_id == current_user.company_id).order_by(HelpdeskEscalation.created_at.desc())
    )
    return ResponseBase(data=[{"id": str(e.id), "ticket_id": str(e.ticket_id), "level": e.level, "reason": e.reason, "created_at": e.created_at.isoformat()} for e in result.scalars().all()])


@router.post("/escalations", response_model=ResponseBase[dict], status_code=201)
async def create_escalation(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    e = HelpdeskEscalation(
        company_id=current_user.company_id,
        ticket_id=data.get("ticket_id"),
        level=int(data.get("level", 1)),
        reason=data.get("reason"),
    )
    db.add(e)
    await db.commit()
    await db.refresh(e)
    return ResponseBase(data={"id": str(e.id), "ticket_id": str(e.ticket_id), "level": e.level}, message="ესკალაცია შეიქმნა")


# ── Canned replies ─────────────────────────────────────────────────────────────

@router.get("/canned-replies", response_model=ResponseBase[list[dict]])
async def list_canned_replies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(CannedReply).where(CannedReply.company_id == current_user.company_id).order_by(CannedReply.title)
    )
    return ResponseBase(data=[{"id": str(c.id), "title": c.title, "body": c.body, "category": c.category} for c in result.scalars().all()])


@router.post("/canned-replies", response_model=ResponseBase[dict], status_code=201)
async def create_canned_reply(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    c = CannedReply(company_id=current_user.company_id, title=data.get("title", ""), body=data.get("body", ""), category=data.get("category"))
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return ResponseBase(data={"id": str(c.id), "title": c.title}, message="მზა პასუხი შეიქმნა")


# ── Knowledge base ──────────────────────────────────────────────────────────────

@router.get("/knowledge", response_model=ResponseBase[list[dict]])
async def list_knowledge(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(KnowledgeArticle).where(KnowledgeArticle.company_id == current_user.company_id).order_by(KnowledgeArticle.title)
    )
    return ResponseBase(data=[{"id": str(k.id), "title": k.title, "content": k.content, "category": k.category, "is_published": k.is_published} for k in result.scalars().all()])


@router.post("/knowledge", response_model=ResponseBase[dict], status_code=201)
async def create_knowledge(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    k = KnowledgeArticle(company_id=current_user.company_id, title=data.get("title", ""), content=data.get("content", ""), category=data.get("category"))
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return ResponseBase(data={"id": str(k.id), "title": k.title}, message="სტატია შეიქმნა")


# ── Field service ──────────────────────────────────────────────────────────────

@router.get("/field-service", response_model=ResponseBase[list[dict]])
async def list_field_service(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(FieldServiceJob).where(FieldServiceJob.company_id == current_user.company_id).order_by(FieldServiceJob.scheduled_date)
    )
    return ResponseBase(data=[{"id": str(f.id), "ticket_id": str(f.ticket_id) if f.ticket_id else None, "technician_id": str(f.technician_id) if f.technician_id else None, "scheduled_date": f.scheduled_date.isoformat() if f.scheduled_date else None, "status": f.status, "address": f.address} for f in result.scalars().all()])


@router.post("/field-service", response_model=ResponseBase[dict], status_code=201)
async def create_field_service(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    f = FieldServiceJob(
        company_id=current_user.company_id,
        ticket_id=data.get("ticket_id"),
        technician_id=data.get("technician_id"),
        client_id=data.get("client_id"),
        scheduled_date=data.get("scheduled_date"),
        status=data.get("status", "scheduled"),
        address=data.get("address"),
        notes=data.get("notes"),
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    return ResponseBase(data={"id": str(f.id), "status": f.status}, message="საველე სამუშაო შეიქმნა")


# ── Email intake ────────────────────────────────────────────────────────────────

@router.get("/email-intake", response_model=ResponseBase[list[dict]])
async def list_email_intake(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_access")),
):
    result = await db.execute(
        select(EmailIntakeRule).where(EmailIntakeRule.company_id == current_user.company_id).order_by(EmailIntakeRule.mailbox)
    )
    return ResponseBase(data=[{"id": str(r.id), "mailbox": r.mailbox, "queue_id": str(r.queue_id) if r.queue_id else None, "priority": r.priority, "is_active": r.is_active} for r in result.scalars().all()])


@router.post("/email-intake", response_model=ResponseBase[dict], status_code=201)
async def create_email_intake(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("helpdesk", "can_create")),
):
    r = EmailIntakeRule(company_id=current_user.company_id, mailbox=data.get("mailbox", ""), queue_id=data.get("queue_id"), priority=data.get("priority", "medium"))
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return ResponseBase(data={"id": str(r.id), "mailbox": r.mailbox}, message="წესი შეიქმნა")
