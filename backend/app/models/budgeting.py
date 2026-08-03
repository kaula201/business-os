"""Budgeting: budget plans, budget lines, actual vs planned comparison."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Numeric, Date, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BudgetPlan(Base):
    """Budget plan for a period."""
    __tablename__ = "budget_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(20), default="monthly")  # monthly, quarterly, yearly
    scenario: Mapped[str] = mapped_column(String(50), default="base")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, active, closed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    lines = relationship("BudgetLine", back_populates="plan", cascade="all, delete-orphan")


class BudgetLine(Base):
    """Individual budget line for a GL account."""
    __tablename__ = "budget_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("budget_plans.id"), nullable=False, index=True)
    gl_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("gl_accounts.id"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # e.g. "2026-07"
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plan = relationship("BudgetPlan", back_populates="lines")
    gl_account = relationship("GLAccount")
    project = relationship("Project")
