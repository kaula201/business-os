"""Quality Control — Odoo-depth: control points, inspections, tests, alerts."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QualityCheck(Base):
    """A product quality inspection record."""

    __tablename__ = "quality_checks"

    class Status:
        PASS = "pass"
        FAIL = "fail"
        PENDING = "pending"
        CHOICES = [PASS, FAIL, PENDING]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    control_point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_control_points.id"), nullable=True, index=True
    )
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    checked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=Status.PENDING, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QualityControlPoint(Base):
    """Where quality is checked: on receipt, production, delivery, or a specific operation."""
    __tablename__ = "quality_control_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    point_type: Mapped[str] = mapped_column(String(30), default="receipt", nullable=False)
    # receipt | production | delivery | operation
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True
    )
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_centers.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class QualityTest(Base):
    """A test attached to a control point: measure, pass/fail, or tolerance check."""
    __tablename__ = "quality_tests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    control_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_control_points.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    test_type: Mapped[str] = mapped_column(String(20), default="pass_fail", nullable=False)
    # pass_fail | measure | tolerance
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)  # for measure
    min_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    tolerance_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class QualityTestResult(Base):
    """Result of running a test on a quality check."""
    __tablename__ = "quality_test_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_checks.id"), nullable=False, index=True
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_tests.id"), nullable=False, index=True
    )
    measured_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class QualityAlert(Base):
    """A quality problem raised from a failed check or manually."""
    __tablename__ = "quality_alerts"

    class Status:
        OPEN = "open"
        IN_PROGRESS = "in_progress"
        DONE = "done"
        CANCELLED = "cancelled"
        CHOICES = [OPEN, IN_PROGRESS, DONE, CANCELLED]

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="quality_check", nullable=False)
    # quality_check | manual | supplier | customer
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True, index=True
    )
    check_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quality_checks.id"), nullable=True, index=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    # low | medium | high | critical
    status: Mapped[str] = mapped_column(String(20), default=Status.OPEN, nullable=False, index=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
