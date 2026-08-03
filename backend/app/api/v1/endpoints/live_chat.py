# backend/app/api/v1/endpoints/live_chat.py
"""Live Chat message management API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.user import User
from app.models.live_chat import ChatMessage
from app.schemas.live_chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatMessageListResponse,
)
from app.schemas.common import ResponseBase, PaginatedResponse

router = APIRouter(prefix="/live-chat", tags=["Live Chat"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[ChatMessageListResponse]])
async def list_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sender_type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("live-chat", "can_access")),
):
    query = select(ChatMessage).where(ChatMessage.company_id == current_user.company_id)
    if sender_type:
        query = query.where(ChatMessage.sender_type == sender_type)
    if status:
        query = query.where(ChatMessage.status == status)
    query = query.order_by(ChatMessage.created_at.desc())

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    messages = result.scalars().all()

    items = [ChatMessageListResponse.model_validate(m) for m in messages]

    return ResponseBase(data=PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    ))


@router.get("/{message_id}", response_model=ResponseBase[ChatMessageResponse])
async def get_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("live-chat", "can_access")),
):
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.company_id == current_user.company_id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="მესიჯი არ მოიძებნა")
    return ResponseBase(data=ChatMessageResponse.model_validate(message))


@router.post("/", response_model=ResponseBase[ChatMessageResponse], status_code=201)
async def create_message(
    data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("live-chat", "can_create")),
):
    message = ChatMessage(
        company_id=current_user.company_id,
        sender_type=data.sender_type.value,
        sender_id=data.sender_id,
        message=data.message,
        channel=data.channel.value,
        status=data.status.value,
        sent_at=data.sent_at,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return ResponseBase(data=ChatMessageResponse.model_validate(message))


@router.delete("/{message_id}", response_model=ResponseBase[dict])
async def delete_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("live-chat", "can_delete")),
):
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.id == message_id,
            ChatMessage.company_id == current_user.company_id,
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="მესიჯი არ მოიძებნა")
    await db.delete(message)
    await db.commit()
    return ResponseBase(data={"id": str(message_id)}, message="მესიჯი წაიშალა")
