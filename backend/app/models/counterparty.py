"""Counterparty verification (Georgia) — SRS open-data checks with history."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CounterpartyCheck(Base):
    """A verification record for a counterparty (client/supplier) against
    Georgian public registries: SRS VAT-payer status, taxpayer status,
    registration data. Every check is stored so the history is auditable.
    """

    __tablename__ = "counterparty_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    identification_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="srs", nullable=False)  # srs | public_registry | manual
    status: Mapped[str] = mapped_column(String(30), default="unknown", nullable=False)
    # status values: verified | not_found | unreachable | error
    is_vat_payer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_active_taxpayer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    registration_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
