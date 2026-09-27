"""SaaS entitlement resolution — runtime feature-limit gating.

Returns the active plan's feature_limits for a company, or a permissive default
when the tenant has no subscription (so existing self-hosted/on-prem installs
keep working without a billing record — SaaS gating is opt-in, not breaking).
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saas import TenantSubscription

# A tenant with no subscription row is treated as "unlimited" — this preserves
# existing behaviour for self-hosted deployments. Billing becomes a hard gate
# only when a subscription row exists and is not active/trial.
UNLIMITED = {"max_drivers": -1, "max_vehicles": -1, "max_trips_month": -1,
             "geocoder": True, "eta": True, "live_map": True}


async def get_entitlement(db: AsyncSession, company_id) -> tuple[str | None, dict]:
    """Resolve the active feature limits for a company.

    Returns (status, feature_limits). status ∈ {None, trial, active, past_due,
    cancelled, expired}. None means "no subscription record" (unlimited).
    """
    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == company_id)
    )).scalar_one_or_none()
    if not sub:
        return None, dict(UNLIMITED)
    return sub.status, (sub.feature_limits or dict(UNLIMITED))


async def is_tms_active(db: AsyncSession, company_id) -> bool:
    """True if the tenant can currently use TMS.

    No record → True (self-hosted). Otherwise must be trial or active and not
    past its trial_ends_at.
    """
    sub = (await db.execute(
        select(TenantSubscription).where(TenantSubscription.company_id == company_id)
    )).scalar_one_or_none()
    if not sub:
        return True
    if sub.status == "active":
        return True
    if sub.status == "trial":
        if sub.trial_ends_at is None:
            return True
        return sub.trial_ends_at >= date.today()
    return False


def check_limit(feature_limits: dict, key: str, current_count: int) -> bool:
    """True if current_count is within the plan limit (or the limit is unlimited)."""
    limit = feature_limits.get(key)
    if limit is None or limit == -1:
        return True
    return current_count < int(limit)


# ── Billing scheduler (daily: expire lapsed trials, bill due active subs) ────


async def run_daily_billing(db: AsyncSession) -> dict:
    """Run one billing pass across ALL companies (platform-wide).

    Mirrors the /saas/billing/run endpoint logic but is tenant-agnostic, so it
    can be scheduled. Returns counters. Uses a PostgreSQL advisory lock to stay
    safe under multiple workers.
    """
    from datetime import date as _date
    from app.core.time import utc_now

    today = _date.today()
    expired = billed = 0

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

    due = (await db.execute(
        select(TenantSubscription).where(
            TenantSubscription.status == "active",
            TenantSubscription.next_billing_date.isnot(None),
            TenantSubscription.next_billing_date <= today,
        )
    )).scalars().all()
    for sub in due:
        sub.last_billed_at = utc_now()
        nbd = sub.next_billing_date or today
        if sub.frequency == "yearly":
            sub.next_billing_date = nbd.replace(year=nbd.year + 1)
        elif nbd.month == 12:
            sub.next_billing_date = nbd.replace(year=nbd.year + 1, month=1)
        else:
            sub.next_billing_date = nbd.replace(month=nbd.month + 1)
        billed += 1

    await db.commit()
    return {"expired_trials": expired, "billed": billed, "due": len(due)}


SAAS_BILLING_ADVISORY_LOCK_KEY = 2026092702


async def run_scheduled_billing() -> dict:
    """Run a platform-wide billing pass under a PostgreSQL advisory lock.

    Prevents duplicate workers (e.g. two uvicorn processes) from double-billing.
    """
    import asyncio
    import logging
    from sqlalchemy import text
    from app.core.database import async_session_factory

    logger = logging.getLogger(__name__)
    async with async_session_factory() as lock_db:
        locked = await lock_db.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": SAAS_BILLING_ADVISORY_LOCK_KEY}
        )
        if not locked:
            return {"expired_trials": 0, "billed": 0, "due": 0, "skipped": 1}
        try:
            return await run_daily_billing(lock_db)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled SaaS billing pass failed")
            return {"expired_trials": 0, "billed": 0, "due": 0, "error": 1}
        finally:
            await lock_db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": SAAS_BILLING_ADVISORY_LOCK_KEY})


def seconds_until_next_billing(now=None) -> float:
    """Seconds until the next daily billing run (Asia/Tbilisi local time)."""
    import logging
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from app.core.config import settings

    tz = ZoneInfo(settings.SAAS_BILLING_TIMEZONE)
    current = now.astimezone(tz) if now else datetime.now(tz)
    target = current.replace(
        hour=settings.SAAS_BILLING_HOUR, minute=settings.SAAS_BILLING_MINUTE,
        second=0, microsecond=0,
    )
    if target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds()


async def saas_billing_scheduler_loop() -> None:
    """Long-running daily billing loop (started from app lifespan)."""
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(seconds_until_next_billing())
        try:
            result = await run_scheduled_billing()
            logger.info("Scheduled SaaS billing pass: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled SaaS billing job failed")
