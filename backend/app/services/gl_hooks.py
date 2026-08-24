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
    tax_account_code: str = "2200",
) -> None:
    """Invoice issued with document-snapshotted VAT liability account."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=invoice_date,
        description=f"ინვოისი {invoice_number} — გაყიდვა",
        reference_type="invoice",
        reference_id=invoice_id,
        lines=[
            ("1310", total, Decimal("0")),           # Dr მოთხოვნები — ინვოისები
            ("4100", Decimal("0"), subtotal),         # Cr შემოსავალი გაყიდვებიდან
            (tax_account_code, Decimal("0"), vat_amount),  # Cr Fiscal-position VAT liability
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


async def post_sale_cogs_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    order_id: UUID,
    order_number: str,
    entry_date: date,
    cogs_amount: Decimal,
) -> None:
    """Sale COGS: Dr COGS (5100) / Cr Inventory (1200) — Odoo-style at shipping."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=entry_date,
        description=f"გაყიდული საქონლის ღირებულება {order_number}",
        reference_type="order_cogs",
        reference_id=order_id,
        lines=[
            ("5100", cogs_amount, Decimal("0")),   # Dr COGS
            ("1200", Decimal("0"), cogs_amount),    # Cr მარაგები
        ],
    )


async def post_payslip_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    payslip_id: UUID,
    payslip_number: str,
    period_date: date,
    gross_pay: Decimal,
    pension_contribution: Decimal,
    income_tax: Decimal,
    net_pay: Decimal,
) -> None:
    """Payslip: Dr Salary expense (5200) / Cr Pension (2210), Tax (2220), Net payable (2300)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=period_date,
        description=f"ხელფასი {payslip_number}",
        reference_type="payslip",
        reference_id=payslip_id,
        lines=[
            ("5200", gross_pay, Decimal("0")),                    # Dr ხელფასის ხარჯი
            ("2210", Decimal("0"), pension_contribution),          # Cr პენსიის ვალდებულება
            ("2220", Decimal("0"), income_tax),                    # Cr საშემოსავლო გადასახადი
            ("2300", Decimal("0"), net_pay),                       # Cr გადასახდელი ხელფასი
        ],
    )


async def post_goods_receipt_gl(
    db: AsyncSession,
    company_id: UUID,
    current_user: User,
    *,
    receipt_id: UUID,
    receipt_number: str,
    receipt_date: date,
    subtotal: Decimal,
) -> None:
    """Goods receipt: Dr Inventory (1200) / Cr Goods-in-transit (2110)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=receipt_date,
        description=f"საქონლის მიღება {receipt_number}",
        reference_type="goods_receipt",
        reference_id=receipt_id,
        lines=[
            ("1200", subtotal, Decimal("0")),   # Dr მარაგები
            ("2110", Decimal("0"), subtotal),    # Cr ვალდებულებები — ინვოისები
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
    tax_account_code: str = "5300",
) -> None:
    """Supplier invoice: close goods-in-transit (2110), create AP (2100)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=invoice_date,
        description=f"მომწოდებლის ინვოისი {internal_invoice_number}",
        reference_type="supplier_invoice",
        reference_id=invoice_id,
        lines=[
            ("2110", subtotal, Decimal("0")),          # Dr იხურება მიღებული საქონელი
            (tax_account_code, vat_amount, Decimal("0")), # Dr Fiscal-position VAT input
            ("2100", Decimal("0"), total),              # Cr ვალდებულებები მომწოდებლების მიმართ
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
    """Supplier payment: Dr AP (2100) / Cr Bank (1410)."""
    await post_journal_entry(
        db, company_id, current_user,
        entry_date=payment_date,
        description=f"მომწოდებლის გადახდა — {internal_invoice_number}",
        reference_type="supplier_payment",
        reference_id=payment_id,
        lines=[
            ("2100", amount, Decimal("0")),            # Dr ვალდებულებები მომწოდებლების მიმართ
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
