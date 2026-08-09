"""Recurring journal entry templates — auto-post on schedule (daily/weekly/monthly)."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RecurringJournalEntry(Base):
    """A template that auto-posts a journal entry on a schedule."""

    __tablename__ = "recurring_journal_entries"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_recurring_journal_company_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Schedule
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # daily | weekly | monthly
    interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # weekly: weekday (0=Mon..6=Sun); monthly: day of month (1..31)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Template: lines stored as JSONB [{gl_account_id, debit_amount, credit_amount, description}]
    lines: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Reference description used when posting
    entry_description: Mapped[str] = mapped_column(String(1000), nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Number of postings so far
    total_posted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
