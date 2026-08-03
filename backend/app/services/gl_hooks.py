"""GL posting hooks — called from business endpoints to auto-create journal entries."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.gl_posting import post_journal_entry


async def post_invoice_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    invoice_id: UUID,
    invoice_number: str,
    invoice_date: date,
    total: Decimal,
    vat_amount: Decimal,
    subtotal: Decimal,
) -> None:
    """Invoice issued: Dr AR (1310) / Cr Revenue (4100) + Cr VAT (2200)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=invoice_date,
        description=f"ინვოისი {invoice_number} — გაყიდვა",
        reference_type="invoice",
        reference_id=invoice_id,
        lines=[
            ("1310", total, Decimal("0")),           # Dr მოთხოვნები — ინვოისები
            ("4100", Decimal("0"), subtotal),         # Cr შემოსავალი გაყიდვებიდან
            ("2200", Decimal("0"), vat_amount),       # Cr დღგ ვალდებულება
        ],
    )


async def post_customer_payment_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    payment_id: UUID,
    receivable_id: UUID,
    invoice_number: str,
    payment_date: date,
    amount: Decimal,
) -> None:
    """Customer payment: Dr Bank (1410) / Cr AR (1310)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=payment_date,
        description=f"კლიენტის გადახდა — {invoice_number}",
        reference_type="customer_payment",
        reference_id=payment_id,
        lines=[
            ("1410", amount, Decimal("0")),           # Dr ბანკი
            ("1310", Decimal("0"), amount),            # Cr მოთხოვნები — ინვოისები
        ],
    )


async def post_customer_payment_reversal_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    reversal_id: UUID,
    payment_id: UUID,
    invoice_number: str,
    reversal_date: date,
    amount: Decimal,
) -> None:
    """Reverse customer payment: Dr AR (1310) / Cr Bank (1410)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=reversal_date,
        description=f"გადახდის გაუქმება — {invoice_number}",
        reference_type="customer_payment_reversal",
        reference_id=reversal_id,
        is_reversal=True,
        reversed_entry_id=payment_id,
        lines=[
            ("1310", amount, Decimal("0")),            # Dr მოთხოვნები
            ("1410", Decimal("0"), amount),             # Cr ბანკი
        ],
    )


async def post_customer_credit_note_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    credit_note_id: UUID,
    receivable_id: UUID,
    invoice_number: str,
    credit_date: date,
    amount: Decimal,
) -> None:
    """Customer credit note: Dr Other Income (4200) / Cr AR (1310)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=credit_date,
        description=f"Credit Note — {invoice_number}",
        reference_type="customer_credit_note",
        reference_id=credit_note_id,
        lines=[
            ("4200", amount, Decimal("0")),            # Dr სხვა შემოსავალი (negative revenue)
            ("1310", Decimal("0"), amount),             # Cr მოთხოვნები
        ],
    )


async def post_customer_bank_reconciliation_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    reconciliation_id: UUID,
    payment_id: UUID,
    invoice_number: str,
    reconciliation_date: date,
    amount: Decimal,
) -> None:
    """Bank reconciliation: Dr Bank (1410) / Cr AR (1310)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=reconciliation_date,
        description=f"საბანკო შეჯერება — {invoice_number}",
        reference_type="customer_bank_reconciliation",
        reference_id=reconciliation_id,
        lines=[
            ("1410", amount, Decimal("0")),            # Dr ბანკი
            ("1310", Decimal("0"), amount),             # Cr მოთხოვნები
        ],
    )


async def post_customer_bank_reconciliation_reversal_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    reversal_id: UUID,
    reconciliation_id: UUID,
    invoice_number: str,
    reversal_date: date,
    amount: Decimal,
) -> None:
    """Reverse bank reconciliation: Dr AR (1310) / Cr Bank (1410)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=reversal_date,
        description=f"საბანკო შეჯერების გაუქმება — {invoice_number}",
        reference_type="customer_bank_reconciliation_reversal",
        reference_id=reversal_id,
        is_reversal=True,
        reversed_entry_id=reconciliation_id,
        lines=[
            ("1310", amount, Decimal("0")),            # Dr მოთხოვნები
            ("1410", Decimal("0"), amount),             # Cr ბანკი
        ],
    )


async def post_supplier_invoice_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    invoice_id: UUID,
    internal_invoice_number: str,
    invoice_date: date,
    total: Decimal,
    vat_amount: Decimal,
    subtotal: Decimal,
) -> None:
    """Supplier invoice: Dr Expense (5100) + Dr VAT (5300) / Cr AP (2110)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=invoice_date,
        description=f"მომწოდებლის ინვოისი {internal_invoice_number}",
        reference_type="supplier_invoice",
        reference_id=invoice_id,
        lines=[
            ("5100", subtotal, Decimal("0")),          # Dr გაყიდული საქონლის ღირებულება
            ("5300", vat_amount, Decimal("0")),         # Dr დღგ ხარჯი
            ("2110", Decimal("0"), total),              # Cr ვალდებულებები — ინვოისები
        ],
    )


async def post_supplier_payment_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    payment_id: UUID,
    payable_id: UUID,
    internal_invoice_number: str,
    payment_date: date,
    amount: Decimal,
) -> None:
    """Supplier payment: Dr AP (2110) / Cr Bank (1410)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=payment_date,
        description=f"მომწოდებლის გადახდა — {internal_invoice_number}",
        reference_type="supplier_payment",
        reference_id=payment_id,
        lines=[
            ("2110", amount, Decimal("0")),            # Dr ვალდებულებები
            ("1410", Decimal("0"), amount),             # Cr ბანკი
        ],
    )


async def post_supplier_payment_reversal_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    reversal_id: UUID,
    payment_id: UUID,
    internal_invoice_number: str,
    reversal_date: date,
    amount: Decimal,
) -> None:
    """Reverse supplier payment: Dr Bank (1410) / Cr AP (2110)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=reversal_date,
        description=f"მომწოდებლის გადახდის გაუქმება — {internal_invoice_number}",
        reference_type="supplier_payment_reversal",
        reference_id=reversal_id,
        is_reversal=True,
        reversed_entry_id=payment_id,
        lines=[
            ("1410", amount, Decimal("0")),            # Dr ბანკი
            ("2110", Decimal("0"), amount),             # Cr ვალდებულებები
        ],
    )


async def post_supplier_credit_note_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    credit_note_id: UUID,
    payable_id: UUID,
    internal_invoice_number: str,
    credit_date: date,
    amount: Decimal,
) -> None:
    """Supplier credit note: Dr AP (2110) / Cr COGS (5100)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=credit_date,
        description=f"Supplier Credit Note — {internal_invoice_number}",
        reference_type="supplier_credit_note",
        reference_id=credit_note_id,
        lines=[
            ("2110", amount, Decimal("0")),            # Dr ვალდებულებები
            ("5100", Decimal("0"), amount),             # Cr გაყიდული საქონლის ღირებულება
        ],
    )


async def post_supplier_bank_reconciliation_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    reconciliation_id: UUID,
    payment_id: UUID,
    internal_invoice_number: str,
    reconciliation_date: date,
    amount: Decimal,
) -> None:
    """Supplier bank reconciliation: Dr AP (2110) / Cr Bank (1410)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=reconciliation_date,
        description=f"საბანკო შეჯერება — {internal_invoice_number}",
        reference_type="supplier_bank_reconciliation",
        reference_id=reconciliation_id,
        lines=[
            ("2110", amount, Decimal("0")),            # Dr ვალდებულებები
            ("1410", Decimal("0"), amount),             # Cr ბანკი
        ],
    )


async def post_supplier_bank_reconciliation_reversal_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    reversal_id: UUID,
    reconciliation_id: UUID,
    internal_invoice_number: str,
    reversal_date: date,
    amount: Decimal,
) -> None:
    """Reverse supplier bank reconciliation: Dr Bank (1410) / Cr AP (2110)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=reversal_date,
        description=f"საბანკო შეჯერების გაუქმება — {internal_invoice_number}",
        reference_type="supplier_bank_reconciliation_reversal",
        reference_id=reversal_id,
        is_reversal=True,
        reversed_entry_id=reconciliation_id,
        lines=[
            ("1410", amount, Decimal("0")),            # Dr ბანკი
            ("2110", Decimal("0"), amount),             # Cr ვალდებულებები
        ],
    )
