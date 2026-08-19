"""Automated GL posting service — creates journal entries from business events."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.purchase_orders import allocate_document_number
from app.models.gl import GLAccount, JournalEntry, JournalEntryLine
from app.models.user import User
from app.services.accounting_periods import ensure_period_open


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Default Chart of Accounts codes ────────────────────────────────────────
# Standard Georgian COA (სააღრიცხვო ანგარიშთა გეგმა) — simplified subset.

DEFAULT_ACCOUNTS = [
    # Assets (1xxx)
    ("1100", "ძირითადი საშუალებები", "asset"),
    ("1101", "დაგროვილი ამორტიზაცია", "asset"),
    ("1200", "მარაგები", "asset"),
    ("1300", "მოთხოვნები მყიდველებისგან", "asset"),
    ("1310", "მოთხოვნები — ინვოისები", "asset"),
    ("1320", "მოთხოვნები — გადახდილი", "asset"),
    ("1400", "მიმდინარე ანგარიში", "asset"),
    ("1410", "ბანკი — მიმდინარე ანგარიში", "asset"),
    # Liabilities (2xxx)
    ("2100", "ვალდებულებები მომწოდებლების მიმართ", "liability"),
    ("2110", "ვალდებულებები — ინვოისები", "liability"),
    ("2120", "ვალდებულებები — გადახდილი", "liability"),
    ("2200", "დღგ ვალდებულება", "liability"),
    # Equity (3xxx)
    ("3100", "საწესდებო კაპიტალი", "equity"),
    ("3200", "გაუნაწილებელი მოგება", "equity"),
    # Income (4xxx)
    ("4100", "შემოსავალი გაყიდვებიდან", "income"),
    ("4200", "სხვა შემოსავალი", "income"),
    ("4900", "ძირითადი საშუალების ჩამოწერის მოგება", "income"),
    # Expenses (5xxx)
    ("5100", "გაყიდული საქონლის ღირებულება", "expense"),
    ("5200", "საოპერაციო ხარჯები", "expense"),
    ("5500", "ამორტიზაციის ხარჯი", "expense"),
    ("5990", "ძირითადი საშუალების ჩამოწერის ზარალი", "expense"),
    ("5300", "დღგ ხარჯი", "expense"),
]


async def seed_default_accounts(db: AsyncSession, company_id: UUID) -> dict[str, UUID]:
    """Create default COA for a company if not already present. Returns {code: id}."""
    existing = (
        await db.execute(
            select(GLAccount).where(GLAccount.company_id == company_id)
        )
    ).scalars().all()
    if existing:
        return {a.code: a.id for a in existing}
    result = {}
    for code, name, acct_type in DEFAULT_ACCOUNTS:
        account = GLAccount(
            company_id=company_id,
            code=code,
            name=name,
            account_type=acct_type,
        )
        db.add(account)
        await db.flush()
        result[code] = account.id
    return result


async def get_account_map(db: AsyncSession, company_id: UUID) -> dict[str, UUID]:
    """Return {code: id} for all active GL accounts of a company."""
    rows = (
        await db.execute(
            select(GLAccount).where(
                GLAccount.company_id == company_id,
                GLAccount.is_active == True,
            )
        )
    ).scalars().all()
    return {a.code: a.id for a in rows}


async def post_journal_entry(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    entry_date: date,
    description: str,
    reference_type: str,
    reference_id: UUID,
    lines: list[tuple[str, Decimal, Decimal]],
    is_reversal: bool = False,
    reversed_entry_id: UUID | None = None,
) -> JournalEntry:
    """Create a balanced double-entry journal entry.

    Args:
        lines: list of (gl_account_code, debit_amount, credit_amount)
    """
    await ensure_period_open(db, company_id, entry_date)
    accounts = await get_account_map(db, company_id)
    entry_number = await allocate_document_number(db, company_id, "journal_entry", "GL")
    entry = JournalEntry(
        company_id=company_id,
        entry_number=entry_number,
        entry_date=entry_date,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        is_reversal=is_reversal,
        reversed_entry_id=reversed_entry_id,
        created_by=current_user.id,
    )
    db.add(entry)
    await db.flush()

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for line_no, (code, debit, credit) in enumerate(lines, start=1):
        gl_id = accounts.get(code)
        if not gl_id:
            raise ValueError(f"GL account code '{code}' not found for company {company_id}")
        db.add(JournalEntryLine(
            journal_entry_id=entry.id,
            gl_account_id=gl_id,
            line_number=line_no,
            debit_amount=debit,
            credit_amount=credit,
        ))
        total_debit += debit
        total_credit += credit

    if money(total_debit) != money(total_credit):
        raise ValueError(f"Unbalanced journal entry: debit={total_debit} credit={total_credit}")

    await db.flush()
    return entry


# ── Automated posting helpers ────────────────────────────────────────────────


async def post_customer_invoice(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    subtotal: Decimal, vat_amount: Decimal, total: Decimal,
) -> JournalEntry:
    """Invoice issued: Dr AR (1300), Cr Income (4100), Cr VAT (2200)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="ინვოისის გამოწერა",
        reference_type="invoice", reference_id=reference_id,
        lines=[
            ("1300", total, Decimal("0")),
            ("4100", Decimal("0"), subtotal),
            ("2200", Decimal("0"), vat_amount),
        ],
    )


async def post_customer_payment(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Customer payment: Dr Bank/Current (1410), Cr AR (1300)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="კლიენტის გადახდა",
        reference_type="customer_payment", reference_id=reference_id,
        lines=[
            ("1410", amount, Decimal("0")),
            ("1300", Decimal("0"), amount),
        ],
    )


async def post_customer_payment_reversal(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Payment reversal: Dr AR (1300), Cr Bank/Current (1410)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="გადახდის გაუქმება",
        reference_type="customer_payment_reversal", reference_id=reference_id,
        lines=[
            ("1300", amount, Decimal("0")),
            ("1410", Decimal("0"), amount),
        ],
    )


async def post_customer_credit_note(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Credit note: Dr Income (4100), Cr AR (1300)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="კლიენტის Credit Note",
        reference_type="customer_credit_note", reference_id=reference_id,
        lines=[
            ("4100", amount, Decimal("0")),
            ("1300", Decimal("0"), amount),
        ],
    )


async def post_customer_bank_reconciliation(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Bank reconciliation (credit): Dr Bank (1410), Cr AR (1300)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="საბანკო შეჯერება — კლიენტი",
        reference_type="customer_bank_reconciliation", reference_id=reference_id,
        lines=[
            ("1410", amount, Decimal("0")),
            ("1300", Decimal("0"), amount),
        ],
    )


async def post_customer_bank_reconciliation_reversal(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Bank reconciliation reversal: Dr AR (1300), Cr Bank (1410)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="საბანკო შეჯერების გაუქმება",
        reference_type="customer_bank_reconciliation_reversal", reference_id=reference_id,
        lines=[
            ("1300", amount, Decimal("0")),
            ("1410", Decimal("0"), amount),
        ],
    )


async def post_supplier_invoice(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    subtotal: Decimal, vat_amount: Decimal, total: Decimal,
) -> JournalEntry:
    """Supplier invoice: Dr Expense (5100), Dr VAT (5300), Cr AP (2100)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="მომწოდებლის ინვოისი",
        reference_type="supplier_invoice", reference_id=reference_id,
        lines=[
            ("5100", subtotal, Decimal("0")),
            ("5300", vat_amount, Decimal("0")),
            ("2100", Decimal("0"), total),
        ],
    )


async def post_supplier_payment(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Supplier payment: Dr AP (2100), Cr Bank/Current (1410)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="მომწოდებლის გადახდა",
        reference_type="supplier_payment", reference_id=reference_id,
        lines=[
            ("2100", amount, Decimal("0")),
            ("1410", Decimal("0"), amount),
        ],
    )


async def post_supplier_payment_reversal(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Supplier payment reversal: Dr Bank/Current (1410), Cr AP (2100)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="მომწოდებლის გადახდის გაუქმება",
        reference_type="supplier_payment_reversal", reference_id=reference_id,
        lines=[
            ("1410", amount, Decimal("0")),
            ("2100", Decimal("0"), amount),
        ],
    )


async def post_supplier_credit_note(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Supplier credit note: Dr AP (2100), Cr Expense (5100)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="მომწოდებლის Credit Note",
        reference_type="supplier_credit_note", reference_id=reference_id,
        lines=[
            ("2100", amount, Decimal("0")),
            ("5100", Decimal("0"), amount),
        ],
    )


async def post_supplier_bank_reconciliation(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Bank reconciliation (debit): Dr AP (2100), Cr Bank (1410)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="საბანკო შეჯერება — მომწოდებელი",
        reference_type="supplier_bank_reconciliation", reference_id=reference_id,
        lines=[
            ("2100", amount, Decimal("0")),
            ("1410", Decimal("0"), amount),
        ],
    )


async def post_supplier_bank_reconciliation_reversal(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Bank reconciliation reversal: Dr Bank (1410), Cr AP (2100)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="საბანკო შეჯერების გაუქმება",
        reference_type="supplier_bank_reconciliation_reversal", reference_id=reference_id,
        lines=[
            ("1410", amount, Decimal("0")),
            ("2100", Decimal("0"), amount),
        ],
    )


async def post_asset_depreciation(
    db: AsyncSession, company_id: UUID, user: User, *,
    entry_date: date, reference_id: UUID,
    amount: Decimal,
) -> JournalEntry:
    """Asset depreciation: Dr Depreciation expense (5500), Cr Accumulated depreciation (1101)."""
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="ძირითადი საშუალების ამორტიზაცია",
        reference_type="asset_depreciation", reference_id=reference_id,
        lines=[
            ("5500", amount, Decimal("0")),
            ("1101", Decimal("0"), amount),
        ],
    )


async def post_asset_disposal(
    db: AsyncSession, company_id, user: User, *,
    entry_date: date, reference_id: UUID,
    cost: Decimal, accumulated: Decimal, proceeds: Decimal,
) -> JournalEntry:
    """Asset disposal: write off asset + accumulated depreciation, recognize gain/loss.

    Book value = cost - accumulated. Gain/Loss = proceeds - book value.
    Lines (net zero):
      Dr Accumulated depreciation (1101)  accumulated
      Dr Bank/Cash (1410)                 proceeds
      Cr Fixed asset (1100)               cost
      Gain  → Cr 4900 (gain);  Loss → Dr 5990 (loss)
    """
    book_value = cost - accumulated
    gain = proceeds - book_value
    lines = [
        ("1101", accumulated, Decimal("0")),
        ("1410", proceeds, Decimal("0")),
    ]
    if gain > 0:
        lines.append(("4900", Decimal("0"), gain))
    elif gain < 0:
        lines.append(("5990", abs(gain), Decimal("0")))
    lines.append(("1100", Decimal("0"), cost))
    return await post_journal_entry(
        db, company_id, user,
        entry_date=entry_date,
        description="ძირითადი საშუალების ჩამოწერა",
        reference_type="asset_disposal", reference_id=reference_id,
        lines=lines,
    )
