"""Notifications endpoints — list, mark read, unread count."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/notifications", tags=["ნოტიფიკაციები"])


@router.get("/", response_model=ResponseBase[list[dict]])
async def list_notifications(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return ResponseBase(data=[{
        "id": str(n.id), "type": n.type, "title": n.title,
        "message": n.message, "link": n.link, "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    } for n in result.scalars().all()])


@router.get("/unread-count", response_model=ResponseBase[dict])
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )).scalar() or 0
    return ResponseBase(data={"count": count})


@router.post("/{notification_id}/read", response_model=ResponseBase[dict])
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="ნოტიფიკაცია არ მოიძებნა")
    notification.is_read = True
    await db.commit()
    return ResponseBase(data={"id": str(notification_id)}, message="წაკითხულად მოინიშნა")


@router.post("/read-all", response_model=ResponseBase[dict])
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )
    for n in result.scalars().all():
        n.is_read = True
    await db.commit()
    return ResponseBase(data={"ok": True}, message="ყველა წაკითხულად მოინიშნა")
