"""Quotations — commercial proposals that convert into sales orders."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Quotation(Base):
    __tablename__ = "quotations"
    __table_args__ = (
        UniqueConstraint("company_id", "quotation_number", name="uq_quotation_company_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    quotation_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    # draft | sent | accepted | rejected | expired | converted
    currency: Mapped[str] = mapped_column(String(3), default="GEL", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship("QuotationItem", back_populates="quotation", cascade="all, delete-orphan",
                         order_by="QuotationItem.line_number")
    client = relationship("Client")


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    __table_args__ = (
        UniqueConstraint("quotation_id", "line_number", name="uq_quotation_item_line"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotations.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    line_number: Mapped[int] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0"), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    quotation = relationship("Quotation", back_populates="items")
    product = relationship("Product")
