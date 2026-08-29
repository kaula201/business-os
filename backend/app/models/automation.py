"""Automation rules: trigger → condition → action automation builder (Odoo-style)."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Odoo-style triggers — extend the domain the engine can react to
KNOWN_TRIGGERS = {
    "invoice_issued", "order_created", "order_confirmed", "order_paid",
    "stock_low", "task_overdue", "client_created", "supplier_invoice_received",
}

# Actions the engine can execute
KNOWN_ACTIONS = {
    "notify",          # in-app notification (target = user id / role)
    "send_email",      # SMTP/sandbox email (target = email / role)
    "create_task",     # spawn a task (task_title, assignee_id, due_date)
    "update_status",   # auto-advance an entity status (status field)
    "webhook",         # fire a stored webhook (target = webhook id or URL)
}


class AutomationRule(Base):
    """trigger + conditions (JSON) + action.

    conditions: list of {"field": "...", "op": "eq|gt|lt|contains|in",
                          "value": ...} evaluated against the event payload.
    """

    __tablename__ = "automation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    conditions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # notify|send_email|create_task|update_status|webhook
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)  # role, email, user id, or webhook id/url
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)      # action params (task_title, subject, status...)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    run_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
