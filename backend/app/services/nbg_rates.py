"""National Bank of Georgia rate ingestion and unattended scheduling."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.time import utc_now
from app.models.company import Company
from app.models.currency import CurrencyRate, IntegrationSyncLog

logger = logging.getLogger(__name__)
NBG_API_URL = "https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies/ka/json/"
NBG_ADVISORY_LOCK_KEY = 2026072901


class NBGSyncError(RuntimeError):
    pass


async def fetch_nbg_rates(rate_date: date | None = None, attempts: int = 3) -> dict[str, Any]:
    params = {"date": rate_date.isoformat()} if rate_date else None
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(NBG_API_URL, params=params)
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, list) or not payload or not isinstance(payload[0].get("currencies"), list):
                raise ValueError("invalid NBG payload")
            return payload[0]
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(2 ** attempt)
    raise NBGSyncError("ეროვნული ბანკის კურსების მიღება ვერ მოხერხდა") from last_error


async def apply_nbg_rates(
    db: AsyncSession,
    company_id: UUID,
    payload: dict[str, Any],
    created_by: UUID | None = None,
) -> dict[str, Any]:
    try:
        effective_date = datetime.fromisoformat(str(payload["date"]).replace("Z", "+00:00")).date()
        currencies = payload["currencies"]
    except (KeyError, TypeError, ValueError) as exc:
        raise NBGSyncError("ეროვნული ბანკის პასუხის ფორმატი არასწორია") from exc

    existing_rows = (
        await db.execute(
            select(CurrencyRate).where(
                CurrencyRate.company_id == company_id,
                CurrencyRate.rate_date == effective_date,
            )
        )
    ).scalars().all()
    existing = {(row.from_currency, row.to_currency): row for row in existing_rows}
    created = updated = 0

    for item in currencies:
        try:
            code = str(item.get("code", "")).upper()
            quantity = Decimal(str(item.get("quantity", 0)))
            official_rate = Decimal(str(item.get("rate", 0)))
        except (TypeError, ValueError):
            continue
        if len(code) != 3 or quantity <= 0 or official_rate <= 0 or code == "GEL":
            continue
        direct = (official_rate / quantity).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        inverse = (Decimal("1") / direct).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        for from_currency, to_currency, value in ((code, "GEL", direct), ("GEL", code, inverse)):
            row = existing.get((from_currency, to_currency))
            if row:
                row.rate = value
                row.source = "nbg"
                row.created_by = created_by
                updated += 1
            else:
                row = CurrencyRate(
                    company_id=company_id,
                    created_by=created_by,
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate_date=effective_date,
                    rate=value,
                    source="nbg",
                )
                db.add(row)
                existing[(from_currency, to_currency)] = row
                created += 1
    await db.flush()
    return {
        "rate_date": effective_date,
        "currencies_received": len(currencies),
        "rates_created": created,
        "rates_updated": updated,
    }


def add_sync_log(
    db: AsyncSession,
    company_id: UUID,
    result: dict[str, Any],
    trigger: str,
    started_at: datetime,
) -> None:
    db.add(IntegrationSyncLog(
        company_id=company_id,
        integration="nbg",
        status="success",
        trigger=trigger,
        effective_date=result["rate_date"],
        currencies_received=result["currencies_received"],
        rates_created=result["rates_created"],
        rates_updated=result["rates_updated"],
        started_at=started_at,
        completed_at=utc_now(),
    ))


async def _record_failure(company_id: UUID, started_at: datetime, message: str) -> None:
    async with async_session_factory() as db:
        db.add(IntegrationSyncLog(
            company_id=company_id,
            integration="nbg",
            status="failed",
            trigger="scheduled",
            error_message=message[:500],
            started_at=started_at,
            completed_at=utc_now(),
        ))
        await db.commit()


async def run_scheduled_nbg_sync() -> dict[str, int]:
    """Sync all active companies once; a PostgreSQL lock prevents duplicate workers."""
    async with async_session_factory() as lock_db:
        locked = await lock_db.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": NBG_ADVISORY_LOCK_KEY}
        )
        if not locked:
            return {"companies_synced": 0, "companies_failed": 0, "skipped": 1}
        try:
            company_ids = list((await lock_db.execute(select(Company.id).where(Company.is_active.is_(True)))).scalars())
            try:
                payload = await fetch_nbg_rates()
            except NBGSyncError as exc:
                for company_id in company_ids:
                    await _record_failure(company_id, utc_now(), str(exc))
                return {"companies_synced": 0, "companies_failed": len(company_ids), "skipped": 0}

            synced = failed = 0
            for company_id in company_ids:
                started_at = utc_now()
                try:
                    async with async_session_factory() as db:
                        result = await apply_nbg_rates(db, company_id, payload)
                        add_sync_log(db, company_id, result, "scheduled", started_at)
                        await db.commit()
                    # Notify live clients that rates changed (no manual refresh needed)
                    from app.core.ws import manager
                    await manager.broadcast(str(company_id), "rates_updated", {
                        "source": "nbg_scheduled",
                        "rate_date": str(result.get("rate_date", "")),
                    })
                    synced += 1
                except Exception:
                    logger.exception("Scheduled NBG sync failed for company %s", company_id)
                    await _record_failure(company_id, started_at, "კურსების შენახვა ვერ მოხერხდა")
                    failed += 1
            return {"companies_synced": synced, "companies_failed": failed, "skipped": 0}
        finally:
            await lock_db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": NBG_ADVISORY_LOCK_KEY})


def seconds_until_next_run(now: datetime | None = None) -> float:
    timezone = ZoneInfo(settings.NBG_SYNC_TIMEZONE)
    current = now.astimezone(timezone) if now else datetime.now(timezone)
    target = current.replace(
        hour=settings.NBG_SYNC_HOUR,
        minute=settings.NBG_SYNC_MINUTE,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds()


async def nbg_scheduler_loop() -> None:
    while True:
        await asyncio.sleep(seconds_until_next_run())
        try:
            result = await run_scheduled_nbg_sync()
            logger.info("Scheduled NBG sync completed: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled NBG sync job failed")
