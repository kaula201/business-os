"""Leave module models.

NOTE: the mapped class is named ``Leave`` (not ``LeaveRequest``) because
``app/models/hr.py`` already registers a ``LeaveRequest`` class (table
``leave_requests``) in the declarative base; SQLAlchemy forbids two same-named
mapped classes. Table ``leaves`` stays distinct from the HR module's
``leave_requests``.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Leave(Base):
    """A leave request submitted by an employee (linked to a user)."""

    __tablename__ = "leaves"

    class Status:
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"
        CHOICES = [PENDING, APPROVED, REJECTED]

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    leave_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=Status.PENDING, nullable=False, index=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
