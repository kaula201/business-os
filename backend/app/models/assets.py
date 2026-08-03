"""Fixed assets: asset registry, depreciation, disposal."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Numeric, Date, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FixedAsset(Base):
    """Company fixed asset / capital asset."""
    __tablename__ = "fixed_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # building, vehicle, equipment, furniture, computer, other
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    useful_life_years: Mapped[int] = mapped_column(nullable=False)  # years
    depreciation_method: Mapped[str] = mapped_column(String(20), default="straight_line")  # straight_line, declining
    salvage_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    accumulated_depreciation: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    book_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    last_depreciation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, fully_depreciated, disposed
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inventory_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custodian: Mapped[str | None] = mapped_column(String(255), nullable=True)
    impairment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    impairment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_proceeds: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    gl_account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("gl_accounts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    depreciation_entries = relationship("AssetDepreciation", back_populates="asset", cascade="all, delete-orphan")


class AssetDepreciation(Base):
    """Individual depreciation run record."""
    __tablename__ = "asset_depreciations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fixed_assets.id"), nullable=False, index=True)
    depreciation_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    period_label: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "2026-07", "2026 Q3"
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    asset = relationship("FixedAsset", back_populates="depreciation_entries")
