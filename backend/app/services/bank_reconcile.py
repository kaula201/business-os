"""Auto-reconcile a bank transaction against an open supplier payable (rules-driven)."""
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.banking import BankReconciliation, BankTransaction
from app.models.purchase import SupplierPayable, SupplierPayment
from app.models.user import User
from app.services.gl_hooks import post_supplier_bank_reconciliation_gl


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def auto_reconcile_transaction(
    db: AsyncSession,
    company_id: uuid.UUID,
    txn: BankTransaction,
    gl_account_id: uuid.UUID | None,  # unused for supplier path (kept for interface parity)
    user_id: uuid.UUID | None,
    *,
    window_start: date,
    window_end: date,
) -> bool:
    """Match an unmatched debit bank transaction to the best open supplier payable.

    Selection: amount == transaction amount AND invoice date within [window_start, window_end],
    oldest payable first. Returns True if reconciled.
    """
    if txn.direction != "debit":
        return False

    # Actor must exist for audit + GL hooks (they need company_id + id)
    from app.models.user import User as _U
    actor = await db.get(_U, user_id) if user_id else None
    if actor is None:
        return False

    # Find candidate open payables whose invoice date falls in the window
    from app.models.purchase import SupplierInvoice

    candidates = (
        await db.execute(
            select(SupplierPayable)
            .join(SupplierInvoice, SupplierInvoice.id == SupplierPayable.supplier_invoice_id)
            .options(selectinload(SupplierPayable.supplier_invoice))
            .where(
                SupplierPayable.company_id == company_id,
                SupplierPayable.outstanding_amount > 0,
                SupplierPayable.status.in_(["unpaid", "partially_paid"]),
                SupplierInvoice.invoice_date >= window_start,
                SupplierInvoice.invoice_date <= window_end,
            )
            .order_by(SupplierPayable.created_at.asc())
        )
    ).scalars().all()

    payable = None
    for cand in candidates:
        if money(cand.outstanding_amount) == money(txn.amount):
            payable = cand
            break
    if payable is None:
        return False

    # ── Build the same objects the manual flow builds ───────────────────
    idempotency_key = f"rule:{uuid.uuid4().hex[:16]}"
    payment = SupplierPayment(
        company_id=company_id,
        supplier_payable_id=payable.id,
        idempotency_key=f"bank-reconciliation:{idempotency_key}",
        amount=money(txn.amount),
        payment_date=txn.transaction_date,
        payment_method="bank_transfer",
        reference=txn.reference,
        notes="Auto-reconciled by rule",
        created_by=user_id,
    )
    db.add(payment)
    await db.flush()

    reconciliation = BankReconciliation(
        company_id=company_id,
        bank_transaction_id=txn.id,
        supplier_payable_id=payable.id,
        supplier_payment_id=payment.id,
        idempotency_key=idempotency_key,
        amount=payment.amount,
        reconciled_by=user_id,
    )
    db.add(reconciliation)
    payable.paid_amount = money(Decimal(payable.paid_amount) + payment.amount)
    payable.outstanding_amount = money(
        Decimal(payable.original_amount) - payable.paid_amount - Decimal(payable.credited_amount)
    )
    payable.status = "paid" if payable.outstanding_amount == 0 else "partially_paid"
    txn.matched_amount = money(Decimal(txn.matched_amount) + payment.amount)
    txn.status = "matched" if txn.matched_amount == txn.amount else "partially_matched"
    await db.flush()

    # Audit + GL
    from app.api.v1.endpoints.purchase_orders import add_audit

    add_audit(db, actor, "bank_transaction.reconciled",
              "bank_reconciliation", reconciliation.id, {
                  "bank_transaction_id": str(txn.id),
                  "supplier_payable_id": str(payable.id),
                  "supplier_payment_id": str(payment.id),
                  "amount": str(payment.amount),
                  "auto": True,
              })

    await post_supplier_bank_reconciliation_gl(
        db, company_id, actor,
        reconciliation_id=reconciliation.id,
        payment_id=payment.id,
        internal_invoice_number=payable.supplier_invoice.internal_invoice_number,
        reconciliation_date=txn.transaction_date,
        amount=payment.amount,
    )
    return True
