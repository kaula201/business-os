"""Live Chat model — support/communication chat messages.

ChatMessage records a single message exchanged between a company user and a
customer within the Business OS live chat module.
"""
import uuid
from datetime import datetime

import enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatSenderType(str, enum.Enum):
    USER = "user"
    CUSTOMER = "customer"


class ChatChannel(str, enum.Enum):
    WEB = "web"
    MOBILE = "mobile"


class ChatStatus(str, enum.Enum):
    DELIVERED = "delivered"
    READ = "read"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="web", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="delivered", nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    company = relationship("Company")
