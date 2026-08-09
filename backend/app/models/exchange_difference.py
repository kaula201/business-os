"""Exchange difference (revaluation) logs — currency revaluation of open receivables."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExchangeDifference(Base):
    """One revaluation line: a receivable revalued at a new rate on a run date."""

    __tablename__ = "exchange_differences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_receivables.id"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    revaluation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gel_equivalent: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    previous_gel_equivalent: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    difference: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
