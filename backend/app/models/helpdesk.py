"""Helpdesk model — support ticket management."""
import uuid
from datetime import datetime

import enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class HelpdeskStatus(str, enum.Enum):
    NEW = "new"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class HelpdeskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class HelpdeskTicket(Base):
    __tablename__ = "helpdesk_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    requester_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("helpdesk_teams.id"), nullable=True, index=True)
    pipeline_stage_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("helpdesk_pipeline_stages.id"), nullable=True, index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True, index=True)
    queue_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("helpdesk_queues.id"), nullable=True, index=True)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sla_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("helpdesk_slas.id"), nullable=True, index=True)
    response_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # P1.6: rich ticket fields
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)   # bug, feature, question, incident
    ticket_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # support, sales, billing, technical
    source_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)  # email, portal, phone, chat, api
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    related_product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    related_invoice_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    related_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    time_spent_minutes: Mapped[int] = mapped_column(default=0, nullable=False)
    satisfaction_score: Mapped[int | None] = mapped_column(nullable=True)  # 1..5
    satisfaction_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    company = relationship("Company")
    assignee = relationship("User", foreign_keys=[assignee_id])
    requester = relationship("User", foreign_keys=[requester_id])
    team = relationship("HelpdeskTeam", foreign_keys=[team_id])
    pipeline_stage = relationship("HelpdeskPipelineStage", foreign_keys=[pipeline_stage_id])
    client = relationship("Client", foreign_keys=[client_id])
    queue = relationship("HelpdeskQueue", foreign_keys=[queue_id])
