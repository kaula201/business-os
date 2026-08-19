"""Exchange difference service — revalues open foreign-currency receivables, payables,
cash and bank balances at the latest rate and posts the difference to the GL."""
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.banking import BankAccount, BankTransaction
from app.models.cash import CashAccount
from app.models.currency import CurrencyRate
from app.models.exchange_difference import ExchangeDifference
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.purchase import SupplierPayable
from app.models.receivable import CustomerReceivable


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# GL account codes for exchange differences (same for all companies, seeded if missing)
EXCHANGE_EXPENSE_CODE = "5400"   # საკურსო სხვაობა — ხარჯი (უარყოფითი სხვაობა)
EXCHANGE_INCOME_CODE = "5401"    # საკურსო სხვაობა — შემოსავალი (დადებითი სხვაობა)

# Mirror account per balance type (asset/liability side of the revaluation)
MIRROR_CODES = {
    "receivable": ["1310", "1300"],
    "payable": ["1410", "1400"],
    "cash": ["1400"],
    "bank": ["1410"],
}


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

    # AP / cash / bank mirror accounts
    ap_accounts = (
        await db.execute(
            select(GLAccount).where(
                GLAccount.company_id == company_id,
                GLAccount.code.in_(["2110", "2100"]),
            )
        )
    ).scalars().all()
    ap_account_id = next((a.id for a in ap_accounts if a.code == "2110"), None) or (
        ap_accounts[0].id if ap_accounts else None
    )
    cash_accounts = (
        await db.execute(
            select(GLAccount).where(
                GLAccount.company_id == company_id,
                GLAccount.code.in_(["1400", "1410"]),
            )
        )
    ).scalars().all()
    cash_account_id = next((a.id for a in cash_accounts if a.code == "1400"), None) or (
        cash_accounts[0].id if cash_accounts else None
    )
    bank_accounts = (
        await db.execute(
            select(GLAccount).where(
                GLAccount.company_id == company_id,
                GLAccount.code.in_(["1410", "1400"]),
            )
        )
    ).scalars().all()
    bank_account_id = next((a.id for a in bank_accounts if a.code == "1410"), None) or (
        bank_accounts[0].id if bank_accounts else None
    )

    # ── Revalue each receivable ─────────────────────────────────────────
    revaluated = 0
    posted_entries = 0
    total_difference = Decimal("0")
    entry_counter = 0

    def _post_entry(
        description: str,
        reference_type: str,
        reference_id: uuid.UUID,
        mirror_account_id,
        difference: Decimal,
    ) -> JournalEntry:
        nonlocal entry_counter
        entry_counter += 1
        entry_number = f"FX-{on_date.strftime('%Y%m%d')}-{entry_counter:03d}"
        entry = JournalEntry(
            company_id=company_id,
            entry_number=entry_number,
            entry_date=on_date,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=user_id,
        )
        db.add(entry)
        return entry

    def add_lines(entry: JournalEntry, mirror_account_id, difference: Decimal, currency: str) -> None:
        """Gain: Dr mirror, Cr income. Loss: Dr expense, Cr mirror."""
        if difference > 0:
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=mirror_account_id, line_number=1,
                debit_amount=abs(difference), credit_amount=0,
                description=f"საკურსო სხვაობა {currency}",
            ))
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=acc_map[EXCHANGE_INCOME_CODE], line_number=2,
                debit_amount=0, credit_amount=abs(difference),
                description=f"საკურსო სხვაობა {currency}",
            ))
        else:
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=acc_map[EXCHANGE_EXPENSE_CODE], line_number=1,
                debit_amount=abs(difference), credit_amount=0,
                description=f"საკურსო სხვაობა {currency}",
            ))
            db.add(JournalEntryLine(
                journal_entry_id=entry.id, gl_account_id=mirror_account_id, line_number=2,
                debit_amount=0, credit_amount=abs(difference),
                description=f"საკურსო სხვაობა {currency}",
            ))

    async def revalue_row(
        *,
        reference_kind: str,
        row_id: uuid.UUID,
        currency: str,
        outstanding: Decimal,
        label: str,
        mirror_account_id,
    ) -> None:
        """Shared revaluation for one balance row. Mutates counters via closure."""
        nonlocal revaluated, posted_entries, total_difference
        rate = await get_rate_or_none(db, company_id, currency, on_date)
        if rate is None:
            return
        outstanding = money(outstanding)
        gel_equivalent = money(outstanding * rate)
        previous_rate = await get_previous_rate_or_none(db, company_id, currency, on_date)
        if previous_rate is None:
            # First revaluation → record baseline, post nothing
            db.add(ExchangeDifference(
                company_id=company_id,
                currency=currency,
                revaluation_date=on_date,
                outstanding_amount=outstanding,
                rate=rate,
                gel_equivalent=gel_equivalent,
                previous_gel_equivalent=None,
                difference=Decimal("0"),
                created_by=user_id,
                **{f"{reference_kind}_id": row_id},
            ))
            revaluated += 1
            return
        previous_gel = money(outstanding * previous_rate)
        difference = gel_equivalent - previous_gel
        # Liabilities move opposite to assets: a stronger FX rate increases
        # the GEL value of a payable (loss), while for assets it is a gain.
        if reference_kind == "payable":
            difference = -difference
        if difference == 0:
            return
        entry = _post_entry(
            description=f"საკურსო სხვაობა {currency} — {label}",
            reference_type="exchange_difference",
            reference_id=uuid.uuid4(),
            mirror_account_id=mirror_account_id,
            difference=difference,
        )
        await db.flush()
        add_lines(entry, mirror_account_id, difference, currency)
        db.add(ExchangeDifference(
            company_id=company_id,
            currency=currency,
            revaluation_date=on_date,
            outstanding_amount=outstanding,
            rate=rate,
            gel_equivalent=gel_equivalent,
            previous_gel_equivalent=previous_gel,
            difference=difference,
            journal_entry_id=entry.id,
            created_by=user_id,
            **{f"{reference_kind}_id": row_id},
        ))
        revaluated += 1
        posted_entries += 1
        total_difference += difference

    for rec in recs:
        await revalue_row(
            reference_kind="receivable", row_id=rec.id, currency=rec.currency,
            outstanding=rec.outstanding_amount, label=rec.invoice_number,
            mirror_account_id=ar_account_id,
        )

    # ── Payables ───────────────────────────────────────────────────────
    pays = (
        await db.execute(
            select(SupplierPayable).where(
                SupplierPayable.company_id == company_id,
                SupplierPayable.currency_code != "GEL",
                SupplierPayable.outstanding_amount > 0,
                SupplierPayable.status.in_(["unpaid", "partially_paid"]),
            )
        )
    ).scalars().all()
    for p in pays:
        await revalue_row(
            reference_kind="payable", row_id=p.id, currency=p.currency_code,
            outstanding=p.outstanding_amount, label=f"Payable {str(p.supplier_invoice_id)[:8]}",
            mirror_account_id=ap_account_id,
        )

    # ── Cash accounts ─────────────────────────────────────────────────
    cash = (
        await db.execute(
            select(CashAccount).where(
                CashAccount.company_id == company_id,
                CashAccount.currency != "GEL",
                CashAccount.balance != 0,
            )
        )
    ).scalars().all()
    for c in cash:
        await revalue_row(
            reference_kind="cash_account", row_id=c.id, currency=c.currency,
            outstanding=c.balance, label=c.name,
            mirror_account_id=cash_account_id,
        )

    # ── Bank accounts ─────────────────────────────────────────────────
    banks = (
        await db.execute(
            select(BankAccount).where(
                BankAccount.company_id == company_id,
                BankAccount.currency != "GEL",
            )
        )
    ).scalars().all()
    for b in banks:
        # Bank balance = debit transactions - credit transactions
        debit = await db.scalar(
            select(func.coalesce(func.sum(BankTransaction.amount), 0)).where(
                BankTransaction.bank_account_id == b.id,
                BankTransaction.direction == "debit",
            )
        )
        credit = await db.scalar(
            select(func.coalesce(func.sum(BankTransaction.amount), 0)).where(
                BankTransaction.bank_account_id == b.id,
                BankTransaction.direction == "credit",
            )
        )
        balance = Decimal(str((debit or 0) - (credit or 0)))
        if balance == 0:
            continue
        await revalue_row(
            reference_kind="bank_account", row_id=b.id, currency=b.currency,
            outstanding=balance, label=b.account_name,
            mirror_account_id=bank_account_id,
        )

    if posted_entries:
        await db.commit()
    return {"revaluated": revaluated, "posted_entries": posted_entries, "total_difference": total_difference}
