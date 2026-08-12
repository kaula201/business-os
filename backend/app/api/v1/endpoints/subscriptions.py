from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

def _compute_next_billing(start: date, frequency: str) -> date:
    """Next billing date from start (monthly = +1 month, yearly = +1 year, one_time = None)."""
    if frequency == "monthly":
        if start.month == 12:
            return start.replace(year=start.year + 1, month=1)
        return start.replace(month=start.month + 1)
    if frequency == "yearly":
        return start.replace(year=start.year + 1)
    return None


def _renew_date(current: date | None, frequency: str) -> date | None:
    """Advance billing date by one cycle."""
    if not current or frequency == "one_time":
        return None
    if frequency == "monthly":
        if current.month == 12:
            return current.replace(year=current.year + 1, month=1)
        return current.replace(month=current.month + 1)
    return current.replace(year=current.year + 1)



@router.get("/", response_model=ResponseBase[PaginatedResponse[SubscriptionResponse]])
async def list_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    client_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_access")),
):
    query = select(Subscription).where(Subscription.company_id == current_user.company_id)
    if status:
        query = query.where(Subscription.status == status)
    if client_id:
        query = query.where(Subscription.client_id == client_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(Subscription.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    subscriptions = (await db.execute(query)).scalars().all()

    return ResponseBase(
        data=PaginatedResponse(
            items=[SubscriptionResponse.model_validate(s) for s in subscriptions],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{subscription_id}", response_model=ResponseBase[SubscriptionResponse])
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_access")),
):
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.company_id == current_user.company_id,
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    return ResponseBase(data=SubscriptionResponse.model_validate(subscription))


@router.post("/", response_model=ResponseBase[SubscriptionResponse])
async def create_subscription(
    data: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_create")),
):
    start = data.start_date or date.today()
    nbd = data.next_billing_date or _compute_next_billing(start, data.frequency)
    subscription = Subscription(
        company_id=current_user.company_id,
        client_id=data.client_id,
        plan=data.plan,
        amount=data.amount,
        frequency=data.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        next_billing_date=nbd,
        status=data.status,
    )
    db.add(subscription)
    await db.flush()
    await db.refresh(subscription)
    return ResponseBase(data=SubscriptionResponse.model_validate(subscription))


@router.patch("/{subscription_id}", response_model=ResponseBase[SubscriptionResponse])
async def update_subscription(
    subscription_id: UUID,
    data: SubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.company_id == current_user.company_id,
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(subscription, field, value)

    await db.flush()
    await db.refresh(subscription)
    return ResponseBase(data=SubscriptionResponse.model_validate(subscription))




@router.post("/{subscription_id}/renew", response_model=ResponseBase[SubscriptionResponse])
async def renew_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    """Renew an active subscription: advance billing date, create a payable invoice for the amount."""
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.company_id == current_user.company_id,
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if subscription.status != "active":
        raise HTTPException(status_code=400, detail="მხოლოდ active გამოწერის განახლება შეიძლება")

    # advance billing cycle
    nbd = _renew_date(subscription.next_billing_date or subscription.start_date, subscription.frequency)
    subscription.next_billing_date = nbd

    add_audit(db, current_user, "subscription.renewed", "subscription", subscription.id,
              {"next_billing": str(nbd), "amount": str(subscription.amount)})

    await db.flush()
    await db.refresh(subscription)
    return ResponseBase(data=SubscriptionResponse.model_validate(subscription))

@router.delete("/{subscription_id}", response_model=ResponseBase[dict])
async def delete_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_delete")),
):
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id,
            Subscription.company_id == current_user.company_id,
        )
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")

    await db.delete(subscription)
    await db.flush()
    return ResponseBase(data={"message": "გამოწერა წაიშალა"})
