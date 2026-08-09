"""Exchange difference service — revalues open foreign-currency receivables at the latest rate
and posts the difference to the GL (Dr/Cr exchange difference accounts)."""
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import CurrencyRate
from app.models.exchange_difference import ExchangeDifference
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.receivable import CustomerReceivable


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# GL account codes for exchange differences (same for all companies, seeded if missing)
EXCHANGE_EXPENSE_CODE = "5400"   # საკურსო სხვაობა — ხარჯი (უარყოფითი სხვაობა)
EXCHANGE_INCOME_CODE = "5401"    # საკურსო სხვაობა — შემოსავალი (დადებითი სხვაობა)


async def get_rate_or_none(db: AsyncSession, company_id: uuid.UUID, currency: str, on_date: date) -> Decimal | None:
    """Latest rate for currency->GEL on or before on_date (fallback: any earlier rate)."""
    row = (
        await db.execute(
            select(CurrencyRate.rate)
            .where(
                CurrencyRate.company_id == company_id,
                CurrencyRate.from_currency == currency,
                CurrencyRate.to_currency == "GEL",
                CurrencyRate.rate_date <= on_date,
            )
            .order_by(CurrencyRate.rate_date.desc(), CurrencyRate.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    return Decimal(str(row)) if row is not None else None


async def get_previous_rate_or_none(db: AsyncSession, company_id: uuid.UUID, currency: str, on_date: date) -> Decimal | None:
    """Latest rate strictly BEFORE on_date — used as the previous GEL-equivalent basis."""
    row = (
        await db.execute(
            select(CurrencyRate.rate)
            .where(
                CurrencyRate.company_id == company_id,
                CurrencyRate.from_currency == currency,
                CurrencyRate.to_currency == "GEL",
                CurrencyRate.rate_date < on_date,
            )
            .order_by(CurrencyRate.rate_date.desc(), CurrencyRate.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    return Decimal(str(row)) if row is not None else None


async def run_revaluation(
    db: AsyncSession,
    company_id: uuid.UUID,
    on_date: date,
    user_id: uuid.UUID | None = None,
) -> dict:
    """Revalue all open non-GEL receivables and post GL entries for the differences.

    Returns {"revaluated": n, "posted_entries": n, "total_difference": Decimal}
    """
    # ── Gather open receivables in foreign currency ─────────────────────
    recs = (
        await db.execute(
            select(CustomerReceivable).where(
                CustomerReceivable.company_id == company_id,
                CustomerReceivable.currency != "GEL",
                CustomerReceivable.outstanding_amount > 0,
            )
        )
    ).scalars().all()

    # ── Make sure exchange-difference GL accounts exist ────────────────
    accounts = (
        await db.execute(
            select(GLAccount).where(
                GLAccount.company_id == company_id,
                GLAccount.code.in_([EXCHANGE_EXPENSE_CODE, EXCHANGE_INCOME_CODE]),
            )
        )
    ).scalars().all()
    acc_map = {a.code: a.id for a in accounts}
    if EXCHANGE_EXPENSE_CODE not in acc_map:
        acc = GLAccount(
            company_id=company_id,
            code=EXCHANGE_EXPENSE_CODE,
            name="საკურსო სხვაობა — ხარჯი",
            account_type="expense",
        )
        db.add(acc)
        await db.flush()
        acc_map[EXCHANGE_EXPENSE_CODE] = acc.id
    if EXCHANGE_INCOME_CODE not in acc_map:
        acc = GLAccount(
            company_id=company_id,
            code=EXCHANGE_INCOME_CODE,
            name="საკურსო სხვაობა — შემოსავალი",
            account_type="income",
        )
        db.add(acc)
        await db.flush()
        acc_map[EXCHANGE_INCOME_CODE] = acc.id

    # AR (receivables) account used to mirror the revaluation
    ar_accounts = (
        await db.execute(
            select(GLAccount).where(
                GLAccount.company_id == company_id,
                GLAccount.code.in_(["1310", "1300"]),
            )
        )
    ).scalars().all()
    ar_account_id = next((a.id for a in ar_accounts if a.code == "1310"), None) or (
        ar_accounts[0].id if ar_accounts else None
    )

    # ── Revalue each receivable ─────────────────────────────────────────
    revaluated = 0
    posted_entries = 0
    total_difference = Decimal("0")

    for rec in recs:
        rate = await get_rate_or_none(db, company_id, rec.currency, on_date)
        if rate is None:
            continue  # no rate → skip

        outstanding = money(rec.outstanding_amount)
        gel_equivalent = money(outstanding * rate)

        # Previous GEL equivalent = outstanding converted at the rate in
        # effect before on_date. First run (no prior rate): baseline only.
        previous_rate = await get_previous_rate_or_none(db, company_id, rec.currency, on_date)
        if previous_rate is None:
            # First revaluation → record baseline, post nothing
            db.add(ExchangeDifference(
                company_id=company_id,
                receivable_id=rec.id,
                currency=rec.currency,
                revaluation_date=on_date,
                outstanding_amount=outstanding,
                rate=rate,
                gel_equivalent=gel_equivalent,
                previous_gel_equivalent=None,
                difference=Decimal("0"),
                created_by=user_id,
            ))
            revaluated += 1
            continue

        previous_gel = money(outstanding * previous_rate)
        difference = gel_equivalent - previous_gel
        if difference == 0:
            continue  # no change → no entry

        # ── Post GL entry ────────────────────────────────────────────────
        entry_number = f"FX-{on_date.strftime('%Y%m%d')}-{posted_entries + 1:03d}"
        entry = JournalEntry(
            company_id=company_id,
            entry_number=entry_number,
            entry_date=on_date,
            description=f"საკურსო სხვაობა {rec.currency} — {rec.invoice_number}",
            reference_type="exchange_difference",
            reference_id=rec.id,
            created_by=user_id,
        )
        db.add(entry)
        await db.flush()

        if difference > 0:
            # gain: Dr AR, Cr income
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=ar_account_id, line_number=1,
                debit_amount=abs(difference), credit_amount=0,
                description=f"საკურსო სხვაობა {rec.currency}",
            ))
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=acc_map[EXCHANGE_INCOME_CODE], line_number=2,
                debit_amount=0, credit_amount=abs(difference),
                description=f"საკურსო სხვაობა {rec.currency}",
            ))
        else:
            # loss: Dr expense, Cr AR
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=acc_map[EXCHANGE_EXPENSE_CODE], line_number=1,
                debit_amount=abs(difference), credit_amount=0,
                description=f"საკურსო სხვაობა {rec.currency}",
            ))
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=ar_account_id, line_number=2,
                debit_amount=0, credit_amount=abs(difference),
                description=f"საკურსო სხვაობა {rec.currency}",
            ))

        db.add(ExchangeDifference(
            company_id=company_id,
            receivable_id=rec.id,
            currency=rec.currency,
            revaluation_date=on_date,
            outstanding_amount=outstanding,
            rate=rate,
            gel_equivalent=gel_equivalent,
            previous_gel_equivalent=previous_gel,
            difference=difference,
            journal_entry_id=entry.id,
            created_by=user_id,
        ))
        revaluated += 1
        posted_entries += 1
        total_difference += difference

    if posted_entries:
        await db.commit()
    return {"revaluated": revaluated, "posted_entries": posted_entries, "total_difference": total_difference}
