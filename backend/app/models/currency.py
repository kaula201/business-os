"""Multi-currency: exchange rates, currency conversion."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Date, Integer, Index, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CurrencyRate(Base):
    """Exchange rate record for a currency pair on a given date."""
    __tablename__ = "currency_rates"
    __table_args__ = (
        UniqueConstraint("company_id", "from_currency", "to_currency", "rate_date", name="uq_currency_rate"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    from_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    to_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)  # manual, nbg, api
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IntegrationSyncLog(Base):
    """Durable status history for unattended external integration jobs."""
    __tablename__ = "integration_sync_logs"
    __table_args__ = (
        Index("ix_isl_company_integration_started", "company_id", "integration", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    integration: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currencies_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rates_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rates_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
