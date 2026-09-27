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
