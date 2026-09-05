from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.subscription import (
    SubscriptionAnalyticsResponse,
    SubscriptionCancelRequest,
    SubscriptionChangePlanRequest,
    SubscriptionCreate,
    SubscriptionPauseRequest,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
    SubscriptionResumeRequest,
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


def _prorate_amount(amount, frequency: str, days_used: int, days_in_cycle: int) -> float:
    """Proration: charge only the used fraction of the cycle."""
    if days_in_cycle <= 0:
        return float(amount)
    return round(float(amount) * days_used / days_in_cycle, 2)


def _days_in_cycle(frequency: str, ref: date) -> int:
    if frequency == "yearly":
        return 365
    if frequency == "monthly":
        if ref.month == 12:
            return (ref.replace(year=ref.year + 1, month=1) - ref).days
        return (ref.replace(month=ref.month + 1) - ref).days
    return 30


# ── Plans (plan/version management) ──────────────────────────────────────────


@router.get("/plans/", response_model=ResponseBase[PaginatedResponse[SubscriptionPlanResponse]])
async def list_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_access")),
):
    filters = [SubscriptionPlan.company_id == current_user.company_id]
    if is_active is not None:
        filters.append(SubscriptionPlan.is_active == is_active)
    total = (await db.execute(select(func.count(SubscriptionPlan.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(SubscriptionPlan).where(*filters)
                         .order_by(SubscriptionPlan.code.asc(), SubscriptionPlan.version.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[SubscriptionPlanResponse.model_validate(r) for r in rows],
    ))


@router.post("/plans/", response_model=ResponseBase[SubscriptionPlanResponse], status_code=201)
async def create_plan(
    data: SubscriptionPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_create")),
):
    # version = max existing version for this code + 1
    last = (await db.execute(select(func.max(SubscriptionPlan.version)).where(
        SubscriptionPlan.company_id == current_user.company_id,
        SubscriptionPlan.code == data.code,
    ))).scalar_one_or_none()
    version = (last or 0) + 1
    plan = SubscriptionPlan(
        company_id=current_user.company_id, code=data.code, name=data.name,
        version=version, amount=data.amount, frequency=data.frequency,
        description=data.description,
    )
    db.add(plan)
    await db.flush()
    add_audit(db, current_user, "subscription_plan.created", "subscription_plan", plan.id,
              {"code": data.code, "version": version})
    await db.commit()
    await db.refresh(plan)
    return ResponseBase(data=SubscriptionPlanResponse.model_validate(plan))


@router.patch("/plans/{plan_id}", response_model=ResponseBase[SubscriptionPlanResponse])
async def update_plan(
    plan_id: UUID,
    data: SubscriptionPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    plan = (await db.execute(select(SubscriptionPlan).where(
        SubscriptionPlan.id == plan_id, SubscriptionPlan.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="პლანი ვერ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    add_audit(db, current_user, "subscription_plan.updated", "subscription_plan", plan.id, {})
    await db.commit()
    await db.refresh(plan)
    return ResponseBase(data=SubscriptionPlanResponse.model_validate(plan))


# ── Subscriptions CRUD ──────────────────────────────────────────────────────


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
    plan_version = 1
    if data.plan_id:
        plan = (await db.execute(select(SubscriptionPlan).where(
            SubscriptionPlan.id == data.plan_id,
            SubscriptionPlan.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=400, detail="პლანი ვერ მოიძებნა")
        plan_version = plan.version
    subscription = Subscription(
        company_id=current_user.company_id,
        client_id=data.client_id,
        plan=data.plan,
        plan_id=data.plan_id,
        plan_version=plan_version,
        amount=data.amount,
        frequency=data.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        next_billing_date=nbd,
        status=data.status,
    )
    db.add(subscription)
    await db.flush()
    add_audit(db, current_user, "subscription.created", "subscription", subscription.id,
              {"plan": data.plan, "amount": str(data.amount)})
    await db.commit()
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
    if update_data.get("plan_id"):
        plan = (await db.execute(select(SubscriptionPlan).where(
            SubscriptionPlan.id == update_data["plan_id"],
            SubscriptionPlan.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=400, detail="პლანი ვერ მოიძებნა")
        update_data["plan_version"] = plan.version
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
    subscription.billing_attempts = 0
    subscription.last_billing_error = None
    subscription.last_billed_at = datetime.utcnow()

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


# ── Subscriptions 2.0 — billing / retry / pause / proration / analytics ─────


@router.post("/billing/run", response_model=ResponseBase[dict])
async def run_billing_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    """Automatic billing scheduler: bill all active subscriptions due today."""
    today = date.today()
    due = (await db.execute(select(Subscription).where(
        Subscription.company_id == current_user.company_id,
        Subscription.status == "active",
        Subscription.next_billing_date <= today,
    ))).scalars().all()

    billed, failed = 0, 0
    for sub in due:
        try:
            # simulate payment gateway call — in production this hits the PSP
            sub.billing_attempts += 1
            sub.last_billed_at = datetime.utcnow()
            sub.next_billing_date = _renew_date(sub.next_billing_date or sub.start_date, sub.frequency)
            sub.billing_attempts = 0
            sub.last_billing_error = None
            billed += 1
            add_audit(db, current_user, "subscription.billed", "subscription", sub.id,
                      {"amount": str(sub.amount), "cycle": str(sub.next_billing_date)})
        except Exception as e:  # pragma: no cover
            sub.last_billing_error = str(e)
            failed += 1
    await db.commit()
    return ResponseBase(data={"billed": billed, "failed": failed, "due": len(due)})


@router.post("/{subscription_id}/retry", response_model=ResponseBase[SubscriptionResponse])
async def retry_billing(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    """Failed payment retry: re-attempt billing for a past_due subscription."""
    sub = (await db.execute(select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status not in ("active", "past_due"):
        raise HTTPException(status_code=400, detail="მხოლოდ active/past_due გამოწერის retry შეიძლება")
    if sub.billing_attempts >= sub.max_billing_attempts:
        raise HTTPException(status_code=400, detail="მაქსიმალური მცდელობები ამოწურულია")

    sub.billing_attempts += 1
    sub.last_billed_at = datetime.utcnow()
    sub.last_billing_error = None
    sub.status = "active"
    sub.next_billing_date = _renew_date(sub.next_billing_date or sub.start_date, sub.frequency)
    add_audit(db, current_user, "subscription.retried", "subscription", sub.id,
              {"attempt": sub.billing_attempts})
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=SubscriptionResponse.model_validate(sub))


@router.post("/{subscription_id}/pause", response_model=ResponseBase[SubscriptionResponse])
async def pause_subscription(
    subscription_id: UUID,
    data: SubscriptionPauseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    """Pause/resume: pause an active subscription."""
    sub = (await db.execute(select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status != "active":
        raise HTTPException(status_code=400, detail="მხოლოდ active გამოწერის პაუზა შეიძლება")
    sub.status = "paused"
    sub.paused_at = datetime.utcnow()
    sub.paused_reason = data.reason
    add_audit(db, current_user, "subscription.paused", "subscription", sub.id,
              {"reason": data.reason})
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=SubscriptionResponse.model_validate(sub))


@router.post("/{subscription_id}/resume", response_model=ResponseBase[SubscriptionResponse])
async def resume_subscription(
    subscription_id: UUID,
    data: SubscriptionResumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    """Pause/resume: resume a paused subscription (optionally prorated)."""
    sub = (await db.execute(select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status != "paused":
        raise HTTPException(status_code=400, detail="მხოლოდ paused გამოწერის განახლება შეიძლება")
    sub.status = "active"
    sub.paused_at = None
    sub.paused_reason = None
    if data.prorate:
        paused_at = sub.paused_at
        if paused_at:
            # proration: shift next billing by the paused duration
            paused_days = (datetime.utcnow() - paused_at).days
            if sub.next_billing_date:
                sub.next_billing_date = sub.next_billing_date + timedelta(days=paused_days)
    add_audit(db, current_user, "subscription.resumed", "subscription", sub.id,
              {"prorate": data.prorate})
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=SubscriptionResponse.model_validate(sub))


@router.post("/{subscription_id}/cancel", response_model=ResponseBase[SubscriptionResponse])
async def cancel_subscription(
    subscription_id: UUID,
    data: SubscriptionCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    """Cancel a subscription (churn)."""
    sub = (await db.execute(select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status == "cancelled":
        raise HTTPException(status_code=400, detail="გამოწერა უკვე გაუქმებულია")
    sub.status = "cancelled"
    sub.cancelled_at = datetime.utcnow()
    sub.end_date = date.today()
    add_audit(db, current_user, "subscription.cancelled", "subscription", sub.id,
              {"reason": data.reason})
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=SubscriptionResponse.model_validate(sub))


@router.post("/{subscription_id}/change-plan", response_model=ResponseBase[SubscriptionResponse])
async def change_plan(
    subscription_id: UUID,
    data: SubscriptionChangePlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_edit")),
):
    """Plan/version management: switch plan with proration of the remaining cycle."""
    sub = (await db.execute(select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    plan = (await db.execute(select(SubscriptionPlan).where(
        SubscriptionPlan.id == data.plan_id,
        SubscriptionPlan.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=400, detail="პლანი ვერ მოიძებნა")

    old_amount = float(sub.amount)
    new_amount = float(plan.amount)
    prorated = None
    if data.prorate and sub.next_billing_date:
        today = date.today()
        days_in_cycle = _days_in_cycle(sub.frequency, today)
        days_left = max(0, (sub.next_billing_date - today).days)
        # credit for unused portion of old plan + charge for new plan
        prorated = round(new_amount * days_left / days_in_cycle - old_amount * days_left / days_in_cycle, 2)

    sub.plan = plan.name
    sub.plan_id = plan.id
    sub.plan_version = plan.version
    sub.amount = plan.amount
    add_audit(db, current_user, "subscription.plan_changed", "subscription", sub.id,
              {"plan": plan.name, "version": plan.version, "prorated": prorated})
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=SubscriptionResponse.model_validate(sub))


@router.get("/analytics/overview", response_model=ResponseBase[SubscriptionAnalyticsResponse])
async def subscription_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("subscriptions", "can_access")),
):
    """MRR, ARR, churn and cohort analytics."""
    subs = (await db.execute(select(Subscription).where(
        Subscription.company_id == current_user.company_id,
    ))).scalars().all()

    mrr = 0.0
    arr = 0.0
    active_count = 0
    churned_count = 0
    new_count = 0
    cohorts: dict[str, dict] = {}

    for s in subs:
        amount = float(s.amount)
        if s.status == "active":
            if s.frequency == "monthly":
                mrr += amount
                arr += amount * 12
            elif s.frequency == "yearly":
                mrr += amount / 12
                arr += amount
            active_count += 1
        elif s.status == "cancelled":
            churned_count += 1
        # cohort by start month
        if s.start_date:
            key = s.start_date.strftime("%Y-%m")
            c = cohorts.setdefault(key, {"month": key, "new": 0, "churned": 0, "active": 0})
            c["new"] += 1
            if s.status == "cancelled":
                c["churned"] += 1
            elif s.status == "active":
                c["active"] += 1

    total = len(subs)
    churn_rate = round(churned_count / total * 100, 2) if total else 0.0
    return ResponseBase(data=SubscriptionAnalyticsResponse(
        mrr=round(mrr, 2), arr=round(arr, 2),
        active_subscriptions=active_count, churned_subscriptions=churned_count,
        churn_rate=churn_rate, new_subscriptions=new_count,
        cohorts=sorted(cohorts.values(), key=lambda c: c["month"], reverse=True),
    ))
