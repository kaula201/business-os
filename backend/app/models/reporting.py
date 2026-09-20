"""Reporting: saved reports, scheduled delivery, dimensions."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SavedReport(Base):
    __tablename__ = "saved_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # revenue|pivot|custom
    config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON config
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("saved_reports.id"), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # daily|weekly|monthly
    recipients: Mapped[str] = mapped_column(Text, nullable=False, default="")  # comma-separated emails
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ReportDimension(Base):
    __tablename__ = "report_dimensions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # branch|product|manager
    label: Mapped[str] = mapped_column(String(100), nullable=False)


class MetricDefinition(Base):
    """Authoritative metric registry (REQ-RPT-01 / Dashboard).

    Each KPI is defined once with a formula version, source, refresh interval
    and the roles allowed to see it. The same code is used by dashboard cards,
    reports and drill-downs — one source of truth.
    """
    __tablename__ = "metric_definitions"
    __table_args__ = (
        UniqueConstraint("company_id", "code", "formula_version", name="uq_metric_definition_company_code_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    formula_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    allowed_roles: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # empty/None = all roles
    refresh_interval: Mapped[int] = mapped_column(Integer, default=60, nullable=False)  # seconds
    grain: Mapped[str | None] = mapped_column(String(50), nullable=True)  # day|month|order|invoice
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
