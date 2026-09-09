"""Inventory valuation — Odoo-depth: AVCO layers + FIFO lots + Standard cost.

Valuation methods:
- standard: product carries a fixed standard_cost; COGS = qty * standard_cost
- avco: weighted-average cost layers (one active layer per product)
- fifo: cost lots consumed in purchase order (oldest first)
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProductCostLayer(Base):
    """Weighted-average cost state per product (one active layer per product).

    quantity_remaining is reduced on outgoing movements; when it reaches zero
    the layer is superseded by the next one.
    """

    __tablename__ = "product_cost_layers"
    __table_args__ = (
        UniqueConstraint("company_id", "product_id", name="uq_product_cost_layer_company_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)

    quantity_remaining: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    weighted_avg_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    # cumulative cost of remaining units = quantity_remaining * weighted_avg_cost
    last_movement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class FifoCostLot(Base):
    """FIFO cost lot — a purchase batch consumed oldest-first on outgoing.

    Each incoming purchase creates a lot with its unit cost; outgoing
    movements consume lots in FIFO order (created_at asc).
    """

    __tablename__ = "fifo_cost_lots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    purchase_receipt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    quantity_remaining: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class ProductValuationConfig(Base):
    """Per-product valuation method (Odoo: standard / avco / fifo)."""

    __tablename__ = "product_valuation_configs"
    __table_args__ = (
        UniqueConstraint("company_id", "product_id", name="uq_product_valuation_config"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(20), default="avco", nullable=False)  # standard | avco | fifo
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    negative_stock_allowed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class InventoryReconciliation(Base):
    """Period-end inventory reconciliation — compare book vs counted value per product."""
    __tablename__ = "inventory_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True)
    reconciliation_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)  # draft / confirmed / posted
    total_book_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    total_counted_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    total_adjustment: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    lines = relationship("ReconciliationLine", back_populates="reconciliation", cascade="all, delete-orphan")


class ReconciliationLine(Base):
    __tablename__ = "reconciliation_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reconciliation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory_reconciliations.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    book_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    counted_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    difference_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    adjustment_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    reconciliation = relationship("InventoryReconciliation", back_populates="lines")
    product = relationship("Product")


class LocationValuation(Base):
    """Per-location inventory value — cost value of stock at each zone."""
    __tablename__ = "location_valuations"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "zone_id", "product_id", name="uq_location_valuation_wh_zone_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False, index=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_zones.id"), nullable=True, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    warehouse = relationship("Warehouse")
    zone = relationship("WarehouseZone")
    product = relationship("Product")
