"""Bank reconciliation rules — automatic matching/categorization of bank transactions."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BankReconciliationRule(Base):
    """A rule that auto-matches or auto-categorizes bank transactions.

    rule_type:
      - amount_date: match a payable/payment with same amount + date window
      - description_contains: text match on transaction description
      - counterparty_equals: text match on counterparty
      - reference_equals: text match on reference
    action:
      - auto_reconcile: automatically reconcile against an open payment/payable
      - categorize: post a GL journal entry to gl_account_id (fee, interest, etc.)
    """

    __tablename__ = "bank_reconciliation_rules"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_bank_reconciliation_rule_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # amount_date | description_contains | counterparty_equals | reference_equals
    action: Mapped[str] = mapped_column(String(30), default="categorize", nullable=False)
    # auto_reconcile | categorize
    match_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # for amount_date: exact amount (positive = credit/incoming, negative = debit/outgoing)
    match_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    date_window_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), default="any", nullable=False)
    # in | out | any
    gl_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("gl_accounts.id"), nullable=True)
    gl_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
