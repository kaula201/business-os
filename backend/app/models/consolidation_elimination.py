"""Intercompany consolidation eliminations with approval/reversal audit trail."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConsolidationElimination(Base):
    __tablename__ = "consolidation_eliminations"
    __table_args__ = (UniqueConstraint("company_id", "idempotency_key", name="uq_consolidation_elimination_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    counterparty_company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    elimination_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source_revenue_account_code: Mapped[str] = mapped_column(String(20), nullable=False)
    source_expense_account_code: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True)
    reversal_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
