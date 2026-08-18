"""Accounting controls: fiscal positions, consolidation mappings and FX translations."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FiscalPosition(Base):
    """Company-specific fiscal/tax position used for sale and purchase documents."""
    __tablename__ = "fiscal_positions"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_fiscal_position_company_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    tax_type: Mapped[str] = mapped_column(String(30), default="vat_standard", nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("18.0000"), nullable=False)
    sales_tax_account_code: Mapped[str] = mapped_column(String(20), default="2200", nullable=False)
    purchase_tax_account_code: Mapped[str] = mapped_column(String(20), default="5300", nullable=False)
    applies_to: Mapped[str] = mapped_column(String(20), default="both", nullable=False)  # sale|purchase|both
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ConsolidationAccountMapping(Base):
    """Maps a subsidiary GL account to a group reporting account."""
    __tablename__ = "consolidation_account_mappings"
    __table_args__ = (UniqueConstraint("company_id", "source_account_code", name="uq_consolidation_mapping_source"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    source_account_code: Mapped[str] = mapped_column(String(20), nullable=False)
    target_account_code: Mapped[str] = mapped_column(String(20), nullable=False)
    target_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class FxTranslationRate(Base):
    """Locked group reporting translation rate, separate from operational transaction rates."""
    __tablename__ = "fx_translation_rates"
    __table_args__ = (UniqueConstraint("company_id", "target_currency", "rate_date", "method", name="uq_fx_translation_rate"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    target_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    method: Mapped[str] = mapped_column(String(20), default="closing", nullable=False)  # closing|average|historical
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)  # manual|nbg
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
