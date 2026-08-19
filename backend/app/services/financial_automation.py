"""Scheduled financial automation — monthly period-close tasks.

Runs on a configurable day-of-month for every active company:
1. Depreciation accrual (all active assets) — each posts its own GL entry
2. FX balance revaluation (receivables, payables, cash, bank)
3. Deferred recognition (due periods)

A PostgreSQL advisory lock guarantees a single worker across replicas,
mirroring the NBG sync scheduler pattern.
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.company import Company
from app.models.deferred import DeferredRecognition
from app.models.user import User

logger = logging.getLogger(__name__)

FINANCIAL_AUTO_LOCK_KEY = 827_341_005  # arbitrary unique key
FINANCE_TIMEZONE = "Asia/Tbilisi"
FINANCE_DAY = 1  # run on the 1st of each month at 03:00


# ── Per-company jobs ──────────────────────────────────────────────────────────

async def run_depreciation_job(db, company_id, on_date, admin_user) -> dict:
    from app.models.assets import AssetDepreciation, FixedAsset
    from app.services.gl_posting import post_asset_depreciation

    period_label = f"{on_date.year}-{on_date.month:02d}"
    assets = (await db.execute(
        select(FixedAsset).where(
            FixedAsset.company_id == company_id,
            FixedAsset.status == "active",
        )
    )).scalars().all()
    existing = set((await db.execute(
        select(AssetDepreciation.asset_id).where(
            AssetDepreciation.company_id == company_id,
            AssetDepreciation.period_label == period_label,
        )
    )).scalars().all())

    posted = 0
    for asset in assets:
        if asset.id in existing:
            continue
        depreciable = asset.purchase_cost - asset.salvage_value
        if depreciable <= 0:
            continue
        amount = (depreciable / Decimal(asset.useful_life_years * 12)).quantize(Decimal("0.01"))
        if amount <= 0:
            continue
        dep = AssetDepreciation(
            company_id=company_id, asset_id=asset.id,
            depreciation_date=on_date, amount=amount, period_label=period_label,
        )
        db.add(dep)
        await db.flush()
        await post_asset_depreciation(
            db, company_id, admin_user,
            entry_date=on_date, reference_id=dep.id, amount=amount,
        )
        asset.accumulated_depreciation += amount
        asset.book_value = asset.purchase_cost - asset.accumulated_depreciation
        asset.last_depreciation_date = on_date
        if asset.book_value <= 0:
            asset.book_value = Decimal("0")
            asset.status = "fully_depreciated"
        posted += 1
    await db.flush()
    return {"depreciation_posted": posted}


async def run_fx_revaluation_job(db, company_id, on_date, user_id) -> dict:
    from app.services.exchange_differences import run_revaluation
    result = await run_revaluation(db, company_id, on_date, user_id)
    return {"fx_revaluated": result["revaluated"], "fx_posted": result["posted_entries"]}


async def run_deferred_job(db, company_id, on_date, admin_user) -> dict:
    from app.models.deferred import DeferredSchedule
    from app.models.gl import GLAccount
    from app.services.gl_posting import post_journal_entry

    rows = (await db.execute(
        select(DeferredRecognition).where(
            DeferredRecognition.company_id == company_id,
            DeferredRecognition.status == "pending",
            DeferredRecognition.recognition_date <= on_date,
        ).order_by(DeferredRecognition.recognition_date)
    )).scalars().all()
    recognized = 0
    for item in rows:
        schedule = (await db.execute(
            select(DeferredSchedule).where(DeferredSchedule.id == item.schedule_id)
        )).scalar_one()
        accounts = (await db.execute(
            select(GLAccount).where(GLAccount.id.in_([schedule.source_gl_account_id, schedule.recognition_gl_account_id]))
        )).scalars().all()
        amap = {a.id: a for a in accounts}
        source, target = amap[schedule.source_gl_account_id], amap[schedule.recognition_gl_account_id]
        amount = item.amount
        lines = [(target.code, amount, Decimal("0")), (source.code, Decimal("0"), amount)] \
            if schedule.deferral_type == "expense" \
            else [(source.code, amount, Decimal("0")), (target.code, Decimal("0"), amount)]
        entry = await post_journal_entry(
            db, company_id, admin_user,
            entry_date=item.recognition_date,
            description=f"{schedule.name} — პერიოდი {item.period_no}",
            reference_type="deferred_recognition", reference_id=item.id, lines=lines,
        )
        item.status = "recognized"
        item.journal_entry_id = entry.id
        item.recognized_by = admin_user.id
        item.recognized_at = datetime.now(ZoneInfo(FINANCE_TIMEZONE)).replace(tzinfo=None)
        recognized += 1
    if recognized:
        await db.flush()
    return {"deferred_recognized": recognized}


async def run_financial_automation_for_company(db, company_id) -> dict:
    """Run the full monthly close for one company in the provided session."""
    admin_user = (await db.execute(
        select(User).where(User.company_id == company_id, User.role == User.Role.ADMIN)
    )).scalars().first()
    if not admin_user:
        admin_user = (await db.execute(
            select(User).where(User.company_id == company_id)
        )).scalars().first()
    if not admin_user:
        return {"company": str(company_id), "skipped": True, "reason": "no_user"}

    on_date = datetime.now(ZoneInfo(FINANCE_TIMEZONE)).date()
    results = {}
    results.update(await run_depreciation_job(db, company_id, on_date, admin_user))
    results.update(await run_fx_revaluation_job(db, company_id, on_date, admin_user.id))
    results.update(await run_deferred_job(db, company_id, on_date, admin_user))
    await db.commit()
    return {"company": str(company_id), **results}


# ── Scheduled loop (mirrors nbg_scheduler_loop) ──────────────────────────────

def seconds_until_next_financial_run(now: datetime | None = None) -> float:
    tz = ZoneInfo(FINANCE_TIMEZONE)
    current = now.astimezone(tz) if now else datetime.now(tz)
    target = current.replace(day=FINANCE_DAY, hour=3, minute=0, second=0, microsecond=0)
    if target <= current:
        if current.month == 12:
            target = target.replace(year=current.year + 1, month=1)
        else:
            target = target.replace(month=current.month + 1)
    return (target - current).total_seconds()


async def financial_scheduler_loop() -> None:
    while True:
        await asyncio.sleep(seconds_until_next_financial_run())
        try:
            async with async_session_factory() as lock_db:
                locked = await lock_db.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": FINANCIAL_AUTO_LOCK_KEY}
                )
                if not locked:
                    logger.info("Financial automation skipped (lock held)")
                    continue
                try:
                    company_ids = list((await lock_db.execute(
                        select(Company.id).where(Company.is_active.is_(True))
                    )).scalars())
                finally:
                    await lock_db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": FINANCIAL_AUTO_LOCK_KEY})
            for company_id in company_ids:
                try:
                    async with async_session_factory() as db:
                        result = await run_financial_automation_for_company(db, company_id)
                    logger.info("Financial automation: %s", result)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Financial automation failed for company %s", company_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled financial automation job failed")
