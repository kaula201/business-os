"""Integrations: API keys, webhooks, webhook events."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[str] = mapped_column(String(500), nullable=False, default="read")  # module scopes: sales.read, inventory.write, *
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rotated_from_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # API P1.8: branch scope, resource-level, allowed IPs, rate limits
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    resource_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # e.g. ["client:uuid1", "product:uuid2"]
    allowed_ips: Mapped[list | None] = mapped_column(JSONB, nullable=True)   # e.g. ["203.0.113.5", "10.0.0.0/8"]
    rate_limit_per_minute: Mapped[int] = mapped_column(default=120, nullable=False)
    rate_window_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rate_window_count: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[str] = mapped_column(String(300), nullable=False, default="invoice.created")  # comma-separated
    secret: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # API P1.8: retry/backoff + signature
    retry_max: Mapped[int] = mapped_column(default=3, nullable=False)
    retry_backoff_seconds: Mapped[int] = mapped_column(default=60, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    webhook_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("webhooks.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|delivered|failed|dead
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    last_response_code: Mapped[int | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # API P1.8: retry/backoff, dead-letter, idempotency
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
