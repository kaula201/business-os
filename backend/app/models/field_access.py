"""Field-level access: per-role field visibility rules."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FieldAccessRule(Base):
    __tablename__ = "field_access_rules"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # clients|orders|invoices|...
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # admin|manager|employee|accountant
    field: Mapped[str] = mapped_column(String(100), nullable=False)  # field name
    can_view: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
