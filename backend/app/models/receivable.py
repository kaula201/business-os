import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CustomerReceivable(Base):
    __tablename__ = "customer_receivables"
    __table_args__ = (
        UniqueConstraint("company_id", "invoice_id", name="uq_customer_receivable_invoice"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    credited_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="unpaid", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    invoice = relationship("Invoice")
    client = relationship("Client")
    payments = relationship("CustomerPayment", back_populates="receivable", order_by="CustomerPayment.created_at")
    credit_notes = relationship("CustomerCreditNote", back_populates="receivable", order_by="CustomerCreditNote.created_at")


class CustomerPayment(Base):
    __tablename__ = "customer_payments"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_customer_payment_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_receivables.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    receivable = relationship("CustomerReceivable", back_populates="payments")
    reversal = relationship("CustomerPaymentReversal", back_populates="payment", uselist=False)


class CustomerPaymentReversal(Base):
    __tablename__ = "customer_payment_reversals"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_customer_payment_reversal_payment"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_customer_payment_reversal_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_payments.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    payment = relationship("CustomerPayment", back_populates="reversal")


class CustomerCreditNote(Base):
    __tablename__ = "customer_credit_notes"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_customer_credit_idempotency"),
        UniqueConstraint("company_id", "credit_note_number", name="uq_customer_credit_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_receivables.id"), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    credit_note_number: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    credit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    receivable = relationship("CustomerReceivable", back_populates="credit_notes")


class CustomerBankReconciliation(Base):
    __tablename__ = "customer_bank_reconciliations"
    __table_args__ = (
        UniqueConstraint("company_id", "idempotency_key", name="uq_customer_bank_reconciliation_idempotency"),
        UniqueConstraint("company_id", "reversal_idempotency_key", name="uq_customer_bank_reconciliation_reversal_idempotency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    bank_transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_transactions.id"), nullable=False, index=True)
    customer_receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_receivables.id"), nullable=False, index=True)
    customer_payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_payments.id"), nullable=False, unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reconciled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reversal_idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    bank_transaction = relationship("BankTransaction")
    receivable = relationship("CustomerReceivable")
    customer_payment = relationship("CustomerPayment")
    reversal = relationship("CustomerBankReconciliationReversal", back_populates="reconciliation", uselist=False)


class CustomerBankReconciliationReversal(Base):
    __tablename__ = "customer_bank_reconciliation_reversals"
    __table_args__ = (
        UniqueConstraint("reconciliation_id", name="uq_customer_bank_reconciliation_reversal_parent"),
        UniqueConstraint("company_id", "idempotency_key", name="uq_customer_bank_reconciliation_reversal_key"),
        Index("ix_cbrr_company", "company_id"),
        Index("ix_cbrr_reconciliation", "reconciliation_id"),
        Index("ix_cbrr_bank_transaction", "bank_transaction_id"),
        Index("ix_cbrr_receivable", "customer_receivable_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    reconciliation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_bank_reconciliations.id"), nullable=False)
    bank_transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_transactions.id"), nullable=False)
    customer_receivable_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_receivables.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    reconciliation = relationship("CustomerBankReconciliation", back_populates="reversal")
