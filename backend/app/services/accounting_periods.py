"""Concurrency-safe accounting-period guard shared by financial mutations."""
import hashlib
from datetime import date
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_period import AccountingPeriod


class AccountingPeriodClosedError(RuntimeError):
    def __init__(self, transaction_date: date):
        self.transaction_date = transaction_date
        super().__init__(f"{transaction_date:%Y-%m} სააღრიცხვო პერიოდი დახურულია")


def period_lock_key(company_id: UUID, transaction_date: date) -> int:
    raw = f"{company_id}:{transaction_date.year:04d}-{transaction_date.month:02d}".encode()
    return int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(), "big", signed=True)


async def acquire_period_lock(db: AsyncSession, company_id: UUID, transaction_date: date) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": period_lock_key(company_id, transaction_date)},
    )


async def ensure_period_open(db: AsyncSession, company_id: UUID, transaction_date: date) -> None:
    await acquire_period_lock(db, company_id, transaction_date)
    closed = await db.scalar(
        select(AccountingPeriod.id).where(
            AccountingPeriod.company_id == company_id,
            AccountingPeriod.year == transaction_date.year,
            AccountingPeriod.month == transaction_date.month,
            AccountingPeriod.status == "closed",
        ).limit(1)
    )
    if closed:
        raise AccountingPeriodClosedError(transaction_date)
