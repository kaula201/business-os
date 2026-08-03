# backend/app/schemas/live_chat.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.models.live_chat import ChatSenderType, ChatChannel, ChatStatus


class ChatMessageCreate(BaseModel):
    sender_type: ChatSenderType
    sender_id: UUID
    message: str = Field(..., min_length=1)
    channel: ChatChannel = ChatChannel.WEB
    status: ChatStatus = ChatStatus.DELIVERED
    sent_at: Optional[datetime] = None


class ChatMessageResponse(BaseModel):
    id: UUID
    company_id: UUID
    sender_type: str
    sender_id: UUID
    message: str
    channel: str
    status: str
    sent_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatMessageListResponse(BaseModel):
    id: UUID
    sender_type: str
    sender_id: UUID
    message: str
    channel: str
    status: str
    sent_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
