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
