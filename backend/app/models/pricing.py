"""Price lists — client-specific pricing (price per product, optional min quantity)."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PriceList(Base):
    __tablename__ = "price_lists"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_price_list_company_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="GEL", nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # PriceList 2.0 — rule engine
    valid_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="თარიღით მოქმედება — დაწყება")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="თარიღით მოქმედება — დასრულება")
    segment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("client_group_defs.id"), nullable=True, comment="კლიენტის სეგმენტი (VIP, Wholesale...)")
    pricing_method: Mapped[str] = mapped_column(String(20), default="fixed", nullable=False, comment="fixed | cost_plus_markup")
    markup_percent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False, comment="cost + markup ფორმულა")
    min_margin_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True, comment="მარჟის მინიმალური ზღვარი")
    approval_required: Mapped[bool] = mapped_column(default=False, nullable=False, comment="approval, თუ ფასი მინიმუმზე დაბალია")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship("PriceListItem", back_populates="price_list", cascade="all, delete-orphan")
    segment = relationship("ClientGroupDef")


class PriceListItem(Base):
    __tablename__ = "price_list_items"
    __table_args__ = (
        UniqueConstraint("price_list_id", "product_id", "min_quantity", "currency", name="uq_price_list_item_product_qty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    price_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("price_lists.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("1"), nullable=False)
    # PriceList 2.0 — per-item rule overrides
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True, comment="ვალუტის მიხედვით ფასი (override)")
    margin_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True, comment="item-ის მარჟა")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    price_list = relationship("PriceList", back_populates="items")
    product = relationship("Product")
