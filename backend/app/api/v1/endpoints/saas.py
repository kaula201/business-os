"""SaaS tenant billing endpoints — platform subscription, plans, entitlement.

Distinct from the vendor-internal `/subscriptions` router (which manages a
company's own client subscriptions). This manages the COMPANY'S OWN plan with
the Business OS platform and exposes runtime feature gating for TMS.
"""
from datetime import date, timedelta
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.time import utc_now
from app.models.saas import TenantPlan, TenantSubscription
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.saas import (
    TenantEntitlementResponse,
    TenantPlanCreate,
    TenantPlanResponse,
    TenantSubscribeRequest,
    TenantSubscriptionResponse,
)
from app.services.saas import get_entitlement, is_tms_active

router = APIRouter(prefix="/saas", tags=["SaaS Billing"])


def _next_billing(start: date, frequency: str) -> date:
    if frequency == "yearly":
        return start.replace(year=start.year + 1)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


# ── Plans catalog ──────────────────────────────────────────────────────────


@router.get("/plans", response_model=ResponseBase[list[TenantPlanResponse]])
async def list_plans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Public plan catalog (authenticated) — active plans ordered by sort_order."""
    rows = (await db.execute(
        select(TenantPlan).where(TenantPlan.is_active == True).order_by(TenantPlan.sort_order.asc())
    )).scalars().all()
    return ResponseBase(data=[TenantPlanResponse.model_validate(r) for r in rows])


@router.post("/plans", response_model=ResponseBase[TenantPlanResponse], status_code=201)
async def create_plan(
    data: TenantPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    exists = (await db.execute(
        select(TenantPlan).where(TenantPlan.code == data.code)
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="პლანი ამ კოდით უკვე არსებობს")
    plan = TenantPlan(
        code=data.code, name=data.name, amount=data.amount, frequency=data.frequency,
        feature_limits=data.feature_limits, description=data.description,
        sort_order=data.sort_order,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return ResponseBase(data=TenantPlanResponse.model_validate(plan))


# ── Subscription + entitlement ─────────────────────────────────────────────


@router.get("/entitlement", response_model=ResponseBase[TenantEntitlementResponse])
async def my_entitlement(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The current company's entitlement: plan, status, feature limits, active flag."""
    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not sub:
        return ResponseBase(data=TenantEntitlementResponse(
            subscribed=False, plan_code=None, status=None, trial_ends_at=None,
            feature_limits={"max_drivers": -1, "max_vehicles": -1, "max_trips_month": -1},
            active=True,
        ))
    active = await is_tms_active(db, current_user.company_id)
    return ResponseBase(data=TenantEntitlementResponse(
        subscribed=True, plan_code=sub.plan_code, status=sub.status,
        trial_ends_at=sub.trial_ends_at, feature_limits=sub.feature_limits or {},
        active=active,
    ))


@router.post("/subscribe", response_model=ResponseBase[TenantSubscriptionResponse], status_code=201)
async def subscribe(
    data: TenantSubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """(Re)subscribe the current company to a plan (starts or resets a trial)."""
    plan = (await db.execute(
        select(TenantPlan).where(TenantPlan.code == data.plan_code, TenantPlan.is_active == True)
    )).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="პლანი ვერ მოიძებნა")

    today = date.today()
    existing = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == current_user.company_id)
    )).scalar_one_or_none()

    if existing:
        existing.plan_id = plan.id
        existing.plan_code = plan.code
        existing.frequency = data.frequency
        existing.amount = plan.amount
        existing.feature_limits = dict(plan.feature_limits)
        existing.status = "trial"
        existing.start_date = today
        existing.trial_ends_at = today + timedelta(days=data.trial_days)
        existing.next_billing_date = _next_billing(today, data.frequency)
        existing.cancelled_at = None
        sub = existing
    else:
        sub = TenantSubscription(
            company_id=current_user.company_id, plan_id=plan.id, plan_code=plan.code,
            frequency=data.frequency, amount=plan.amount,
            feature_limits=dict(plan.feature_limits), status="trial",
            start_date=today, trial_ends_at=today + timedelta(days=data.trial_days),
            next_billing_date=_next_billing(today, data.frequency),
        )
        db.add(sub)

    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=TenantSubscriptionResponse.model_validate(sub))


@router.post("/cancel", response_model=ResponseBase[TenantSubscriptionResponse])
async def cancel(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Self-serve cancel: mark the current subscription cancelled (churn)."""
    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status == "cancelled":
        raise HTTPException(status_code=400, detail="გამოწერა უკვე გაუქმებულია")
    sub.status = "cancelled"
    sub.cancelled_at = utc_now()
    sub.end_date = date.today()
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=TenantSubscriptionResponse.model_validate(sub))


# ── Billing lifecycle (simulated payment gateway; swap for a real PSP) ──────


@router.post("/activate", response_model=ResponseBase[TenantSubscriptionResponse])
async def activate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert a trial (or reactivate past_due/expired) into an active subscription.

    Simulates a successful payment capture. In production this endpoint is the
    client-side confirmation step after a PSP checkout session succeeds.
    """
    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status == "cancelled":
        raise HTTPException(status_code=400, detail="გაუქმებული გამოწერა — ხელახლა გამოიწერეთ")

    today = date.today()
    sub.status = "active"
    sub.trial_ends_at = None
    sub.start_date = sub.start_date or today
    # first paid cycle starts today (or the due date if already past it)
    if not sub.next_billing_date or sub.next_billing_date < today:
        sub.next_billing_date = _next_billing(today, sub.frequency)
    sub.last_billed_at = utc_now()
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=TenantSubscriptionResponse.model_validate(sub))


@router.post("/billing/run", response_model=ResponseBase[dict])
async def run_billing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Platform billing scheduler (operator-triggered; cron-able).

    1. Trials past trial_ends_at → expired (no payment captured).
    2. Active subs due (next_billing_date <= today) → simulated charge, advance cycle.
    """
    today = date.today()
    expired = 0
    billed = 0

    # 1. expire lapsed trials
    lapsed = (await db.execute(
        select(TenantSubscription).where(
            TenantSubscription.status == "trial",
            TenantSubscription.trial_ends_at.isnot(None),
            TenantSubscription.trial_ends_at < today,
        )
    )).scalars().all()
    for sub in lapsed:
        sub.status = "expired"
        sub.end_date = sub.trial_ends_at
        expired += 1

    # 2. bill due active subscriptions
    due = (await db.execute(
        select(TenantSubscription).where(
            TenantSubscription.status == "active",
            TenantSubscription.next_billing_date.isnot(None),
            TenantSubscription.next_billing_date <= today,
        )
    )).scalars().all()
    for sub in due:
        # simulated successful charge; a real PSP failure would set past_due
        sub.last_billed_at = utc_now()
        sub.next_billing_date = _next_billing(sub.next_billing_date or today, sub.frequency)
        billed += 1

    await db.commit()
    return ResponseBase(data={"expired_trials": expired, "billed": billed, "due": len(due)})


@router.post("/reactivate", response_model=ResponseBase[TenantSubscriptionResponse])
async def reactivate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-activate an expired/past_due subscription with a new payment (simulated)."""
    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status not in ("expired", "past_due"):
        raise HTTPException(status_code=400, detail="მხოლოდ expired/past_due გამოწერის განახლება შეიძლება")

    today = date.today()
    sub.status = "active"
    sub.trial_ends_at = None
    sub.start_date = today
    sub.next_billing_date = _next_billing(today, sub.frequency)
    sub.last_billed_at = utc_now()
    sub.cancelled_at = None
    await db.commit()
    await db.refresh(sub)
    return ResponseBase(data=TenantSubscriptionResponse.model_validate(sub))


# ── PSP checkout + webhook (provider-agnostic; Stripe when configured) ─────


@router.post("/checkout", response_model=ResponseBase[dict])
async def create_checkout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a checkout session for the current company's pending subscription.

    Returns a `payment_reference` + `gateway`:
      - "stripe": a Stripe PaymentIntent `client_secret` (when STRIPE_SECRET_KEY set)
      - "sandbox": a fake reference (demo mode — complete via /saas/webhook)
    """
    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status == "cancelled":
        raise HTTPException(status_code=400, detail="გაუქმებული გამოწერა — ხელახლა გამოიწერეთ")

    amount_gel = float(sub.amount)
    client_secret = None
    payment_reference = None
    gateway = "sandbox"

    if settings.STRIPE_SECRET_KEY:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            pi = stripe.PaymentIntent.create(
                amount=int(round(amount_gel * 100)), currency="gel",
                payment_method_types=["card"],
                metadata={"company_id": str(current_user.company_id),
                          "subscription_id": str(sub.id), "plan": sub.plan_code},
            )
            payment_reference = pi.id
            client_secret = pi.client_secret
            gateway = "stripe"
        except Exception as e:  # pragma: no cover - live PSP only
            payment_reference = None
            gateway = "sandbox"
            from app.models.payment import PaymentTransaction
            db.add(PaymentTransaction(
                company_id=current_user.company_id, provider="stripe",
                amount=sub.amount, currency="GEL", status="failed",
                error_message=str(e)[:500],
            ))
            await db.commit()
    else:
        payment_reference = f"sbx_{uuid.uuid4().hex[:20]}"

    return ResponseBase(data={
        "gateway": gateway,
        "payment_reference": payment_reference,
        "client_secret": client_secret,
        "amount": amount_gel,
        "currency": "GEL",
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY or None,
    })


@router.post("/webhook", response_model=ResponseBase[dict])
async def saas_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Provider payment webhook. Confirms a payment and activates the subscription.

    Signature: `X-Saas-Signature` = HMAC-SHA256(body). SAAS_WEBHOOK_SECRET is
    required unless APP_ENV is development, test, or sandbox. A missing or
    invalid signature returns 401 and does not activate the subscription.
    Idempotent via `provider_ref`. Unsigned bodies are accepted only in
    relaxed environments when the secret is unset.
    """
    body = await request.body()
    sig = request.headers.get("x-saas-signature")
    secret = (settings.SAAS_WEBHOOK_SECRET or "").strip()
    # Outside development/test/sandbox the signing secret is mandatory.
    if not secret and not settings.is_relaxed_env():
        raise HTTPException(status_code=401, detail="SAAS_WEBHOOK_SECRET აუცილებელია")
    if secret:
        import hashlib, hmac
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(sig.strip(), expected):
            raise HTTPException(status_code=401, detail="არასწორი webhook ხელმოწერა")

    payload = await request.json()
    company_id = payload.get("company_id")
    event = payload.get("event") or payload.get("type")
    provider_ref = payload.get("payment_reference") or payload.get("provider_ref")
    if not company_id or event not in ("payment_succeeded", "charge.succeeded", "payment_intent.succeeded"):
        return ResponseBase(data={"received": True, "ignored": True})

    try:
        cid = UUID(str(company_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="არასწორი company_id")

    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == cid)
    )).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="გამოწერა არ მოიძებნა")
    if sub.status == "cancelled":
        return ResponseBase(data={"received": True, "ignored": True, "reason": "cancelled"})

    from app.models.payment import PaymentTransaction
    if provider_ref:
        dup = (await db.execute(
            select(PaymentTransaction).where(PaymentTransaction.provider_ref == provider_ref)
        )).scalar_one_or_none()
        if dup:
            return ResponseBase(data={"received": True, "duplicate": True})

    db.add(PaymentTransaction(
        company_id=cid, provider="stripe" if settings.STRIPE_SECRET_KEY else "sandbox",
        amount=sub.amount, currency="GEL", status="succeeded",
        provider_ref=provider_ref,
    ))

    today = date.today()
    sub.status = "active"
    sub.trial_ends_at = None
    sub.start_date = sub.start_date or today
    if not sub.next_billing_date or sub.next_billing_date < today:
        sub.next_billing_date = _next_billing(today, sub.frequency)
    sub.last_billed_at = utc_now()

    await db.commit()
    return ResponseBase(data={
        "received": True, "status": "active",
        "subscription_id": str(sub.id), "plan": sub.plan_code,
    })
