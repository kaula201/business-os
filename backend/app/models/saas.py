"""SaaS tenant billing — the platform's OWN subscription model.

Distinct from app.models.subscription (which is a vendor's internal client
subscriptions, ERP-internal). Here a Company (tenant) subscribes to the
Business OS platform itself, with feature limits that gate TMS (and future
standalone modules) at runtime.

TenantPlan:     the sellable catalog (tms_starter / tms_pro / tms_enterprise).
TenantSubscription: a company's active/trial/past_due/cancelled subscription,
                    plus a JSONB snapshot of the plan's feature limits.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

TENANT_FREQUENCIES = {"monthly", "yearly"}
TENANT_STATUSES = {"trial", "active", "past_due", "cancelled", "expired"}


class TenantPlan(Base):
    """A sellable platform plan with feature limits (JSONB)."""

    __tablename__ = "tenant_plans"
    __table_args__ = (
        UniqueConstraint("code", name="uq_tenant_plan_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    # e.g. {"max_drivers": 5, "max_vehicles": 10, "max_trips_month": 100,
    #       "geocoder": true, "eta": true, "live_map": true}
    feature_limits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class TenantSubscription(Base):
    """A company's platform subscription (trial → active → past_due/cancelled)."""

    __tablename__ = "tenant_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True, unique=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_plans.id"), nullable=False, index=True
    )
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="trial", nullable=False, index=True)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    # feature-limit snapshot at (re)subscribe time, for stable runtime gating
    feature_limits: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trial_ends_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_billing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_billed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    plan = relationship("TenantPlan")
