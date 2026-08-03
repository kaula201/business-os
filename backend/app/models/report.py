"""Reports: export scope preferences for the Reports module.

Stores per-company defaults used by the Reports UI/export endpoints
(e.g. which date range and export scope the reports default to).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReportPreference(Base):
    """Per-company settings for the Reports module."""

    __tablename__ = "report_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    # Default report date range: 7d, 30d, 90d, 12m (12 months), or all
    default_date_range: Mapped[str] = mapped_column(String(10), default="30d", nullable=False)
    # Default export scope: "current" (current company only) or "all" (all companies
    # the current user's tenant can see). Reports are always company-scoped in this
    # system, so this currently only affects future multi-tenant exports; stored
    # so the frontend export controls reflect a durable user preference.
    default_export_scope: Mapped[str] = mapped_column(String(10), default="current", nullable=False)
    # Whether the revenue chart groups by month (true) or day (false) by default.
    group_by_month: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company = relationship("Company", backref="report_preferences")
