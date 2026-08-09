"""Recurring journal entry service — computes next run dates and posts due entries."""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.recurring import RecurringJournalEntry


def compute_next_run(rec: RecurringJournalEntry, from_date: date) -> date:
    """Compute the next run date strictly after from_date for the schedule."""
    interval = max(rec.interval, 1)
    if rec.frequency == "daily":
        return from_date + timedelta(days=interval)
    if rec.frequency == "weekly":
        target_weekday = rec.day_of_week if rec.day_of_week is not None else 0
        nxt = from_date + timedelta(days=1)
        while nxt.weekday() != target_weekday:
            nxt += timedelta(days=1)
        # advance by (interval-1) full weeks
        nxt += timedelta(days=7 * (interval - 1))
        return nxt
    # monthly
    day = rec.day_of_month if rec.day_of_month is not None else 1
    year, month = from_date.year, from_date.month
    # Check the current month first, then advance month by month
    for _ in range(interval * 2 + 1):
        last_day = _days_in_month(year, month)
        candidate = date(year, month, min(day, last_day))
        if candidate > from_date:
            return candidate
        month += 1
        if month > 12:
            month = 1
            year += 1
    return date(from_date.year + interval, from_date.month, 1)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - date(year, month, 1)).days


async def post_due_entries(db: AsyncSession, company_id: uuid.UUID, through_date: date | None = None) -> int:
    """Post all due recurring entries for a company up to through_date (default today).

    Returns the number of journal entries posted.
    """
    through = through_date or date.today()
    recs: Sequence[RecurringJournalEntry] = (
        await db.execute(
            select(RecurringJournalEntry).where(
                RecurringJournalEntry.company_id == company_id,
                RecurringJournalEntry.is_active == True,
                RecurringJournalEntry.next_run_date <= through,
            )
        )
    ).scalars().all()

    posted = 0
    for rec in recs:
        # Fetch accounts once (line ids may be str or UUID)
        account_ids = [l["gl_account_id"] for l in rec.lines]
        raw_ids = [uuid.UUID(str(aid)) for aid in account_ids]
        accounts = (
            await db.execute(
                select(GLAccount).where(
                    GLAccount.company_id == company_id,
                    GLAccount.id.in_(raw_ids),
                    GLAccount.is_active == True,
                )
            )
        ).scalars().all()
        found = {a.id: a for a in accounts}
        # Skip if any line references an unknown/inactive account
        if any(raw not in found for raw in raw_ids):
            rec.next_run_date = compute_next_run(rec, rec.next_run_date)
            continue

        # Build balanced entry: normalize debits/credits
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        normalized = []
        for idx, line in enumerate(rec.lines, start=1):
            dr = Decimal(str(line["debit_amount"] or 0)).quantize(Decimal("0.01"))
            cr = Decimal(str(line["credit_amount"] or 0)).quantize(Decimal("0.01"))
            total_debit += dr
            total_credit += cr
            normalized.append((idx, dr, cr, found[uuid.UUID(str(line["gl_account_id"]))].id, line.get("description")))
        if total_debit != total_credit:
            # skip unbalanced templates silently
            rec.next_run_date = compute_next_run(rec, rec.next_run_date)
            continue

        entry_number = f"RJE-{rec.next_run_date.strftime('%Y%m%d')}-{rec.total_posted + 1:03d}"
        entry = JournalEntry(
            company_id=company_id,
            entry_number=entry_number,
            entry_date=rec.next_run_date,
            description=rec.entry_description,
            reference_type="recurring",
            reference_id=rec.id,
            created_by=rec.created_by,
        )
        db.add(entry)
        await db.flush()
        for line_number, dr, cr, gl_account_id, desc in normalized:
            db.add(JournalEntryLine(
                journal_entry_id=entry.id,
                gl_account_id=gl_account_id,
                line_number=line_number,
                debit_amount=dr,
                credit_amount=cr,
                description=desc,
            ))
        rec.last_run_date = rec.next_run_date
        rec.total_posted += 1
        rec.next_run_date = compute_next_run(rec, rec.next_run_date)
        posted += 1

    if posted:
        await db.commit()
    return posted
