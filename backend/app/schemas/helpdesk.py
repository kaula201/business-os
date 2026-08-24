# backend/app/schemas/helpdesk.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.models.helpdesk import HelpdeskStatus, HelpdeskPriority


class HelpdeskTicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: HelpdeskPriority = HelpdeskPriority.MEDIUM
    status: HelpdeskStatus = HelpdeskStatus.NEW
    assignee_id: Optional[UUID] = None
    requester_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    pipeline_stage_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    queue_id: Optional[UUID] = None
    attachment_url: Optional[str] = None
    # P1.6 rich fields
    category: Optional[str] = None
    ticket_type: Optional[str] = None
    source_channel: Optional[str] = None
    tags: Optional[list[str]] = None
    related_product_id: Optional[UUID] = None
    related_invoice_id: Optional[UUID] = None
    related_order_id: Optional[UUID] = None


class HelpdeskTicketUpdate(BaseModel):
    subject: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[HelpdeskPriority] = None
    status: Optional[HelpdeskStatus] = None
    assignee_id: Optional[UUID] = None
    requester_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    pipeline_stage_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    queue_id: Optional[UUID] = None
    attachment_url: Optional[str] = None
    category: Optional[str] = None
    ticket_type: Optional[str] = None
    source_channel: Optional[str] = None
    tags: Optional[list[str]] = None
    related_product_id: Optional[UUID] = None
    related_invoice_id: Optional[UUID] = None
    related_order_id: Optional[UUID] = None
    time_spent_minutes: Optional[int] = None
    satisfaction_score: Optional[int] = Field(None, ge=1, le=5)
    satisfaction_comment: Optional[str] = None


class HelpdeskTicketResponse(BaseModel):
    id: UUID
    company_id: UUID
    subject: str
    description: Optional[str]
    priority: str
    status: str
    assignee_id: Optional[UUID]
    assignee_name: Optional[str] = None
    requester_id: Optional[UUID]
    requester_name: Optional[str] = None
    team_id: Optional[UUID] = None
    team_name: Optional[str] = None
    pipeline_stage_id: Optional[UUID] = None
    pipeline_stage_name: Optional[str] = None
    client_id: Optional[UUID] = None
    client_name: Optional[str] = None
    queue_id: Optional[UUID] = None
    queue_name: Optional[str] = None
    attachment_url: Optional[str] = None
    sla_id: Optional[UUID] = None
    response_deadline: Optional[datetime] = None
    resolution_deadline: Optional[datetime] = None
    category: Optional[str] = None
    ticket_type: Optional[str] = None
    source_channel: Optional[str] = None
    tags: Optional[list] = None
    related_product_id: Optional[UUID] = None
    related_invoice_id: Optional[UUID] = None
    related_order_id: Optional[UUID] = None
    time_spent_minutes: int = 0
    satisfaction_score: Optional[int] = None
    satisfaction_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HelpdeskTicketListResponse(BaseModel):
    id: UUID
    subject: str
    priority: str
    status: str
    assignee_name: Optional[str] = None
    requester_name: Optional[str] = None
    team_name: Optional[str] = None
    pipeline_stage_name: Optional[str] = None
    client_name: Optional[str] = None
    queue_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
