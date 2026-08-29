"""Marketplace — app catalog and per-company installations."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MarketplaceApp(Base):
    """A published app in the marketplace catalog (global, not tenant-scoped)."""
    __tablename__ = "marketplace_apps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="other", nullable=False)
    # sales | finance | operations | hr | crm | other
    icon: Mapped[str] = mapped_column(String(50), default="Package", nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    publisher: Mapped[str] = mapped_column(String(200), default="Business OS", nullable=False)
    price: Mapped[float] = mapped_column(default=0, nullable=False)  # 0 = free
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions: Mapped[Any] = mapped_column(JSON, nullable=True)  # module scopes requested
    config_schema: Mapped[Any] = mapped_column(JSON, nullable=True)  # JSON schema for settings
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    installations = relationship("CompanyAppInstallation", back_populates="app", cascade="all, delete-orphan")


class CompanyAppInstallation(Base):
    """A company's installation of a marketplace app."""
    __tablename__ = "company_app_installations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    app_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_apps.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="installed", nullable=False)
    # installed | disabled | uninstalled | trial | expired
    billing_mode: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    # free | one_time | subscription | trial
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    license_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config: Mapped[Any] = mapped_column(JSON, nullable=True)
    installed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    app = relationship("MarketplaceApp", back_populates="installations")


class MarketplacePurchase(Base):
    """A paid purchase of a marketplace app (one-time or subscription)."""
    __tablename__ = "marketplace_purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    app_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_apps.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    billing_mode: Mapped[str] = mapped_column(String(20), default="one_time", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="paid", nullable=False)  # paid, refunded, failed
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    purchased_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
