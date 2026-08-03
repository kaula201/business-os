from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.banking import load_transaction, transaction_response
from app.api.v1.endpoints.supplier_finance import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.receivable import (
    CustomerBankReconciliation,
    CustomerBankReconciliationReversal,
    CustomerCreditNote,
    CustomerPayment,
    CustomerPaymentReversal,
    CustomerReceivable,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.receivable import (
    CustomerBankReconciliationCreate,
    CustomerBankReconciliationResponse,
    CustomerBankReconciliationResult,
    CustomerBankReconciliationReversalCreate,
    CustomerCreditNoteCreate,
    CustomerCreditNoteResponse,
    CustomerCreditNoteResult,
    CustomerPaymentCreate,
    CustomerPaymentResponse,
    CustomerPaymentResult,
    CustomerPaymentReversalCreate,
    CustomerReceivableResponse,
)
from app.services.gl_hooks import (
    post_customer_bank_reconciliation_gl,
    post_customer_bank_reconciliation_reversal_gl,
    post_customer_credit_note_gl,
    post_customer_payment_gl,
    post_customer_payment_reversal_gl,
)

router = APIRouter(tags=["კლიენტის ფინანსები"])


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def require_finance_role(user: User) -> None:
    if user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="კლიენტის ფინანსური ოპერაციის შესრულების უფლება არ გაქვთ")


def refresh_status(receivable: CustomerReceivable) -> None:
    outstanding = money(receivable.original_amount - receivable.paid_amount - receivable.credited_amount)
    receivable.outstanding_amount = outstanding
    if outstanding <= 0:
        receivable.status = "paid" if money(receivable.paid_amount) > 0 else "credited"
    elif money(receivable.paid_amount) > 0:
        receivable.status = "partially_paid"
    elif receivable.due_date < date.today():
        receivable.status = "overdue"
    else:
        receivable.status = "unpaid"


def payment_response(payment: CustomerPayment) -> CustomerPaymentResponse:
    return CustomerPaymentResponse(
        id=payment.id,
        receivable_id=payment.receivable_id,
        amount=float(payment.amount),
        payment_date=payment.payment_date,
        payment_method=payment.payment_method,
        reference=payment.reference,
        notes=payment.notes,
        status=payment.status,
        reversal_reason=payment.reversal.reason if payment.reversal else None,
        created_at=payment.created_at,
    )


def credit_response(credit: CustomerCreditNote) -> CustomerCreditNoteResponse:
    return CustomerCreditNoteResponse(
        id=credit.id,
        receivable_id=credit.receivable_id,
        credit_note_number=credit.credit_note_number,
        amount=float(credit.amount),
        credit_date=credit.credit_date,
        reason=credit.reason,
        created_at=credit.created_at,
    )


def receivable_response(receivable: CustomerReceivable) -> CustomerReceivableResponse:
    outstanding = money(receivable.original_amount - receivable.paid_amount - receivable.credited_amount)
    overdue_days = max((date.today() - receivable.due_date).days, 0) if outstanding > 0 else 0
    return CustomerReceivableResponse(
        id=receivable.id,
        invoice_id=receivable.invoice_id,
        invoice_number=receivable.invoice_number,
        client_id=receivable.client_id,
        client_name=receivable.client_name,
        currency=receivable.currency,
        original_amount=float(receivable.original_amount),
        paid_amount=float(receivable.paid_amount),
        credited_amount=float(receivable.credited_amount),
        outstanding_amount=float(outstanding),
        due_date=receivable.due_date,
        overdue_days=overdue_days,
        status=receivable.status,
        payments=[payment_response(row) for row in receivable.payments],
        credit_notes=[credit_response(row) for row in receivable.credit_notes],
        created_at=receivable.created_at,
    )


def reconciliation_response(row: CustomerBankReconciliation) -> CustomerBankReconciliationResponse:
    reversal = row.reversal
    return CustomerBankReconciliationResponse(
        id=row.id,
        bank_transaction_id=row.bank_transaction_id,
        customer_receivable_id=row.customer_receivable_id,
        customer_payment_id=row.customer_payment_id,
        amount=float(row.amount),
        status="reversed" if reversal else row.status,
        notes=row.notes,
        reversal_reason=reversal.reason if reversal else row.reversal_reason,
        reversed_at=reversal.created_at if reversal else row.reversed_at,
        created_at=row.created_at,
    )


def receivable_options():
    return (
        selectinload(CustomerReceivable.payments).selectinload(CustomerPayment.reversal),
        selectinload(CustomerReceivable.credit_notes),
    )


async def load_receivable(db: AsyncSession, receivable_id: UUID, company_id: UUID, *, for_update: bool = False):
    query = select(CustomerReceivable).where(
        CustomerReceivable.id == receivable_id,
        CustomerReceivable.company_id == company_id,
    )
    if for_update:
        query = query.with_for_update()
    row = (await db.execute(query.options(*receivable_options()).execution_options(populate_existing=True))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="კლიენტის დავალიანება არ მოიძებნა")
    refresh_status(row)
    return row


async def result_for_payment(db, receivable, payment):
    receivable = await load_receivable(db, receivable.id, receivable.company_id)
    payment = (
        await db.execute(
            select(CustomerPayment)
            .where(CustomerPayment.id == payment.id)
            .options(selectinload(CustomerPayment.reversal))
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return CustomerPaymentResult(receivable=receivable_response(receivable), payment=payment_response(payment))


@router.get("/customer-receivables/", response_model=ResponseBase[PaginatedResponse[CustomerReceivableResponse]])
async def list_receivables(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    invoice_id: UUID | None = None,
    client_id: UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CustomerReceivable.company_id == current_user.company_id]
    if invoice_id:
        filters.append(CustomerReceivable.invoice_id == invoice_id)
    if client_id:
        filters.append(CustomerReceivable.client_id == client_id)
    if status:
        filters.append(CustomerReceivable.status == status)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(CustomerReceivable.invoice_number.ilike(term), CustomerReceivable.client_name.ilike(term)))
    total = (await db.execute(select(func.count(CustomerReceivable.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(CustomerReceivable)
            .where(*filters)
            .options(*receivable_options())
            .order_by(CustomerReceivable.due_date, CustomerReceivable.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    for row in rows:
        refresh_status(row)
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[receivable_response(row) for row in rows],
    ))


@router.get("/customer-receivables/{receivable_id}", response_model=ResponseBase[CustomerReceivableResponse])
async def get_receivable(
    receivable_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    receivable = await load_receivable(db, receivable_id, current_user.company_id)
    return ResponseBase(data=receivable_response(receivable))


@router.post("/customer-receivables/{receivable_id}/payments", response_model=ResponseBase[CustomerPaymentResult])
async def create_payment(
    receivable_id: UUID,
    data: CustomerPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    key = data.idempotency_key.strip()
    existing = (
        await db.execute(
            select(CustomerPayment)
            .where(CustomerPayment.company_id == current_user.company_id, CustomerPayment.idempotency_key == key)
            .options(selectinload(CustomerPayment.reversal))
        )
    ).scalar_one_or_none()
    if existing:
        if (
            existing.receivable_id != receivable_id
            or money(existing.amount) != money(data.amount)
            or existing.payment_date != data.payment_date
            or existing.payment_method != data.payment_method.strip()
            or existing.reference != data.reference.strip()
        ):
            raise HTTPException(status_code=409, detail="idempotency key განსხვავებული გადახდისთვის უკვე გამოყენებულია")
        receivable = await load_receivable(db, existing.receivable_id, current_user.company_id)
        return ResponseBase(data=CustomerPaymentResult(receivable=receivable_response(receivable), payment=payment_response(existing)))

    receivable = await load_receivable(db, receivable_id, current_user.company_id, for_update=True)
    existing = (
        await db.execute(
            select(CustomerPayment)
            .where(CustomerPayment.company_id == current_user.company_id, CustomerPayment.idempotency_key == key)
            .options(selectinload(CustomerPayment.reversal))
        )
    ).scalar_one_or_none()
    if existing:
        if (
            existing.receivable_id != receivable_id
            or money(existing.amount) != money(data.amount)
            or existing.payment_date != data.payment_date
            or existing.payment_method != data.payment_method.strip()
            or existing.reference != data.reference.strip()
        ):
            raise HTTPException(status_code=409, detail="idempotency key განსხვავებული გადახდისთვის უკვე გამოყენებულია")
        return ResponseBase(data=await result_for_payment(db, receivable, existing))
    amount = money(data.amount)
    if amount > money(receivable.outstanding_amount):
        raise HTTPException(status_code=409, detail="გადახდა დარჩენილ დავალიანებას აღემატება")
    payment = CustomerPayment(
        company_id=current_user.company_id,
        receivable_id=receivable.id,
        idempotency_key=key,
        amount=amount,
        payment_date=data.payment_date,
        payment_method=data.payment_method.strip(),
        reference=data.reference.strip(),
        notes=data.notes,
        status="active",
        created_by=current_user.id,
    )
    db.add(payment)
    receivable.paid_amount = money(receivable.paid_amount + amount)
    refresh_status(receivable)
    await db.flush()
    add_audit(db, current_user, "customer_payment.created", "customer_payment", payment.id, {
        "receivable_id": receivable.id, "amount": amount, "reference": payment.reference,
    })
    await post_customer_payment_gl(
        db, current_user.company_id, current_user,
        payment_id=payment.id,
        receivable_id=receivable.id,
        invoice_number=receivable.invoice_number,
        payment_date=payment.payment_date,
        amount=amount,
    )
    await db.flush()
    return ResponseBase(data=await result_for_payment(db, receivable, payment))


@router.post("/customer-payments/{payment_id}/reversal", response_model=ResponseBase[CustomerPaymentResult])
async def reverse_payment(
    payment_id: UUID,
    data: CustomerPaymentReversalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    payment = (
        await db.execute(
            select(CustomerPayment)
            .where(CustomerPayment.id == payment_id, CustomerPayment.company_id == current_user.company_id)
            .options(selectinload(CustomerPayment.reversal))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="კლიენტის გადახდა არ მოიძებნა")
    if payment.reversal:
        if payment.reversal.idempotency_key == data.idempotency_key.strip():
            receivable = await load_receivable(db, payment.receivable_id, current_user.company_id)
            return ResponseBase(data=await result_for_payment(db, receivable, payment))
        raise HTTPException(status_code=409, detail="ეს გადახდა უკვე გაუქმებულია")
    receivable = await load_receivable(db, payment.receivable_id, current_user.company_id, for_update=True)
    reversal = CustomerPaymentReversal(
        company_id=current_user.company_id,
        payment_id=payment.id,
        idempotency_key=data.idempotency_key.strip(),
        reason=data.reason.strip(),
        reversed_by=current_user.id,
    )
    db.add(reversal)
    payment.status = "reversed"
    receivable.paid_amount = money(receivable.paid_amount - payment.amount)
    refresh_status(receivable)
    await db.flush()
    add_audit(db, current_user, "customer_payment.reversed", "customer_payment", payment.id, {
        "receivable_id": receivable.id, "amount": payment.amount, "reason": reversal.reason,
    })
    await post_customer_payment_reversal_gl(
        db, current_user.company_id, current_user,
        reversal_id=reversal.id,
        payment_id=payment.id,
        invoice_number=receivable.invoice_number,
        reversal_date=date.today(),
        amount=payment.amount,
    )
    await db.flush()
    return ResponseBase(data=await result_for_payment(db, receivable, payment))


@router.post("/customer-receivables/{receivable_id}/credit-notes", response_model=ResponseBase[CustomerCreditNoteResult])
async def create_credit_note(
    receivable_id: UUID,
    data: CustomerCreditNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    key = data.idempotency_key.strip()
    existing = (
        await db.execute(select(CustomerCreditNote).where(
            CustomerCreditNote.company_id == current_user.company_id,
            CustomerCreditNote.idempotency_key == key,
        ))
    ).scalar_one_or_none()
    if existing:
        if (
            existing.receivable_id != receivable_id
            or money(existing.amount) != money(data.amount)
            or existing.credit_note_number != data.credit_note_number.strip()
            or existing.credit_date != data.credit_date
            or existing.reason != data.reason.strip()
        ):
            raise HTTPException(status_code=409, detail="idempotency key განსხვავებული Credit Note-ისთვის უკვე გამოყენებულია")
        receivable = await load_receivable(db, existing.receivable_id, current_user.company_id)
        return ResponseBase(data=CustomerCreditNoteResult(
            receivable=receivable_response(receivable), credit_note=credit_response(existing)
        ))
    receivable = await load_receivable(db, receivable_id, current_user.company_id, for_update=True)
    existing = (
        await db.execute(select(CustomerCreditNote).where(
            CustomerCreditNote.company_id == current_user.company_id,
            CustomerCreditNote.idempotency_key == key,
        ))
    ).scalar_one_or_none()
    if existing:
        if (
            existing.receivable_id != receivable_id
            or money(existing.amount) != money(data.amount)
            or existing.credit_note_number != data.credit_note_number.strip()
            or existing.credit_date != data.credit_date
            or existing.reason != data.reason.strip()
        ):
            raise HTTPException(status_code=409, detail="idempotency key განსხვავებული Credit Note-ისთვის უკვე გამოყენებულია")
        return ResponseBase(data=CustomerCreditNoteResult(
            receivable=receivable_response(receivable), credit_note=credit_response(existing)
        ))
    amount = money(data.amount)
    if amount > money(receivable.outstanding_amount):
        raise HTTPException(status_code=409, detail="credit თანხა დარჩენილ დავალიანებას აღემატება")
    duplicate_number = (
        await db.execute(select(CustomerCreditNote.id).where(
            CustomerCreditNote.company_id == current_user.company_id,
            CustomerCreditNote.credit_note_number == data.credit_note_number.strip(),
        ).limit(1))
    ).scalars().first()
    if duplicate_number:
        raise HTTPException(status_code=409, detail="Credit Note-ის ნომერი უკვე არსებობს")
    credit = CustomerCreditNote(
        company_id=current_user.company_id,
        receivable_id=receivable.id,
        idempotency_key=key,
        credit_note_number=data.credit_note_number.strip(),
        amount=amount,
        credit_date=data.credit_date,
        reason=data.reason.strip(),
        created_by=current_user.id,
    )
    db.add(credit)
    receivable.credited_amount = money(receivable.credited_amount + amount)
    refresh_status(receivable)
    await db.flush()
    add_audit(db, current_user, "customer_credit_note.created", "customer_credit_note", credit.id, {
        "receivable_id": receivable.id, "amount": amount, "credit_note_number": credit.credit_note_number,
    })
    await post_customer_credit_note_gl(
        db, current_user.company_id, current_user,
        credit_note_id=credit.id,
        receivable_id=receivable.id,
        invoice_number=receivable.invoice_number,
        credit_date=credit.credit_date,
        amount=amount,
    )
    await db.refresh(credit)
    receivable = await load_receivable(db, receivable.id, current_user.company_id)
    return ResponseBase(data=CustomerCreditNoteResult(
        receivable=receivable_response(receivable), credit_note=credit_response(credit)
    ))


async def bank_result(db, transaction, receivable, reconciliation):
    transaction = await load_transaction(db, transaction.id, transaction.company_id)
    receivable = await load_receivable(db, receivable.id, receivable.company_id)
    reconciliation = (
        await db.execute(
            select(CustomerBankReconciliation)
            .where(CustomerBankReconciliation.id == reconciliation.id)
            .options(selectinload(CustomerBankReconciliation.reversal))
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    return CustomerBankReconciliationResult(
        transaction=transaction_response(transaction).model_dump(),
        receivable=receivable_response(receivable),
        reconciliation=reconciliation_response(reconciliation),
    )


@router.post("/bank-transactions/{transaction_id}/customer-reconciliations", response_model=ResponseBase[CustomerBankReconciliationResult])
async def reconcile_customer_receivable(
    transaction_id: UUID,
    data: CustomerBankReconciliationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    key = data.idempotency_key.strip()
    existing = (
        await db.execute(select(CustomerBankReconciliation).where(
            CustomerBankReconciliation.company_id == current_user.company_id,
            CustomerBankReconciliation.idempotency_key == key,
        ))
    ).scalar_one_or_none()
    if existing:
        if (
            existing.bank_transaction_id != transaction_id
            or existing.customer_receivable_id != data.customer_receivable_id
            or money(existing.amount) != money(data.amount)
            or (existing.notes or "") != (data.notes or "")
        ):
            raise HTTPException(status_code=409, detail="idempotency key განსხვავებული საბანკო შეჯერებისთვის უკვე გამოყენებულია")
        transaction = await load_transaction(db, existing.bank_transaction_id, current_user.company_id)
        receivable = await load_receivable(db, existing.customer_receivable_id, current_user.company_id)
        return ResponseBase(data=await bank_result(db, transaction, receivable, existing))
    transaction = await load_transaction(db, transaction_id, current_user.company_id, for_update=True)
    if transaction.direction != "credit":
        raise HTTPException(status_code=409, detail="კლიენტის დავალიანებას მხოლოდ credit transaction შეიძლება შეჯერდეს")
    receivable = await load_receivable(db, data.customer_receivable_id, current_user.company_id, for_update=True)
    existing = (
        await db.execute(select(CustomerBankReconciliation).where(
            CustomerBankReconciliation.company_id == current_user.company_id,
            CustomerBankReconciliation.idempotency_key == key,
        ))
    ).scalar_one_or_none()
    if existing:
        if (
            existing.bank_transaction_id != transaction_id
            or existing.customer_receivable_id != data.customer_receivable_id
            or money(existing.amount) != money(data.amount)
            or (existing.notes or "") != (data.notes or "")
        ):
            raise HTTPException(status_code=409, detail="idempotency key განსხვავებული საბანკო შეჯერებისთვის უკვე გამოყენებულია")
        return ResponseBase(data=await bank_result(db, transaction, receivable, existing))
    amount = money(data.amount)
    unmatched = money(transaction.amount - transaction.matched_amount)
    if amount > unmatched or amount > money(receivable.outstanding_amount):
        raise HTTPException(status_code=409, detail="შეჯერების თანხა ხელმისაწვდომ ნაშთს აღემატება")
    payment = CustomerPayment(
        company_id=current_user.company_id,
        receivable_id=receivable.id,
        idempotency_key=f"bank:{key}",
        amount=amount,
        payment_date=transaction.transaction_date,
        payment_method="bank_transfer",
        reference=transaction.reference,
        notes=data.notes,
        status="active",
        created_by=current_user.id,
    )
    db.add(payment)
    await db.flush()
    reconciliation = CustomerBankReconciliation(
        company_id=current_user.company_id,
        bank_transaction_id=transaction.id,
        customer_receivable_id=receivable.id,
        customer_payment_id=payment.id,
        idempotency_key=key,
        amount=amount,
        notes=data.notes,
        reconciled_by=current_user.id,
    )
    db.add(reconciliation)
    transaction.matched_amount = money(transaction.matched_amount + amount)
    transaction.status = "matched" if transaction.matched_amount == transaction.amount else "partially_matched"
    receivable.paid_amount = money(receivable.paid_amount + amount)
    refresh_status(receivable)
    await db.flush()
    add_audit(db, current_user, "customer_bank_reconciliation.created", "customer_bank_reconciliation", reconciliation.id, {
        "bank_transaction_id": transaction.id, "receivable_id": receivable.id, "amount": amount,
    })
    await post_customer_bank_reconciliation_gl(
        db, current_user.company_id, current_user,
        reconciliation_id=reconciliation.id,
        payment_id=payment.id,
        invoice_number=receivable.invoice_number,
        reconciliation_date=transaction.transaction_date,
        amount=amount,
    )
    return ResponseBase(data=await bank_result(db, transaction, receivable, reconciliation))


# ── Customer Statement ────────────────────────────────────────────────────────

@router.get("/customer-receivables/{receivable_id}/statement", response_model=ResponseBase[dict])
async def customer_statement(
    receivable_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full customer statement: invoice, payments, credit notes, balance history."""
    receivable = await load_receivable(db, receivable_id, current_user.company_id)

    events = []
    events.append({
        "date": str(receivable.created_at.date()),
        "type": "invoice_issued",
        "description": f"ინვოისი {receivable.invoice_number}",
        "amount": float(receivable.original_amount),
        "balance": float(receivable.original_amount),
    })

    running_balance = float(receivable.original_amount)
    for payment in receivable.payments:
        if payment.status == "active":
            running_balance -= float(payment.amount)
            events.append({
                "date": str(payment.payment_date),
                "type": "payment",
                "description": f"გადახდა ({payment.payment_method}) — {payment.reference or ''}",
                "amount": -float(payment.amount),
                "balance": round(running_balance, 2),
            })

    for credit in receivable.credit_notes:
        running_balance -= float(credit.amount)
        events.append({
            "date": str(credit.credit_date),
            "type": "credit_note",
            "description": f"Credit Note {credit.credit_note_number} — {credit.reason}",
            "amount": -float(credit.amount),
            "balance": round(running_balance, 2),
        })

    return ResponseBase(data={
        "client_name": receivable.client_name,
        "invoice_number": receivable.invoice_number,
        "original_amount": float(receivable.original_amount),
        "paid_amount": float(receivable.paid_amount),
        "credited_amount": float(receivable.credited_amount),
        "outstanding_amount": float(receivable.outstanding_amount),
        "due_date": str(receivable.due_date),
        "status": receivable.status,
        "events": sorted(events, key=lambda e: e["date"]),
    })


@router.get("/bank-customer-reconciliations/", response_model=ResponseBase[PaginatedResponse[CustomerBankReconciliationResponse]])
async def list_customer_reconciliations(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    customer_receivable_id: UUID | None = None,
    bank_transaction_id: UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [CustomerBankReconciliation.company_id == current_user.company_id]
    if customer_receivable_id:
        filters.append(CustomerBankReconciliation.customer_receivable_id == customer_receivable_id)
    if bank_transaction_id:
        filters.append(CustomerBankReconciliation.bank_transaction_id == bank_transaction_id)
    if status == "reversed":
        filters.append(CustomerBankReconciliation.reversal.has())
    elif status == "active":
        filters.append(~CustomerBankReconciliation.reversal.has())
    elif status:
        filters.append(CustomerBankReconciliation.status == status)
    total = (await db.execute(select(func.count(CustomerBankReconciliation.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(CustomerBankReconciliation)
            .where(*filters)
            .options(selectinload(CustomerBankReconciliation.reversal))
            .order_by(CustomerBankReconciliation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[reconciliation_response(row) for row in rows],
    ))


@router.post("/bank-customer-reconciliations/{reconciliation_id}/reversal", response_model=ResponseBase[CustomerBankReconciliationResult])
async def reverse_customer_reconciliation(
    reconciliation_id: UUID,
    data: CustomerBankReconciliationReversalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    reconciliation = (
        await db.execute(
            select(CustomerBankReconciliation)
            .where(
                CustomerBankReconciliation.id == reconciliation_id,
                CustomerBankReconciliation.company_id == current_user.company_id,
            )
            .options(selectinload(CustomerBankReconciliation.reversal))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not reconciliation:
        raise HTTPException(status_code=404, detail="კლიენტის საბანკო შეჯერება არ მოიძებნა")
    key = data.idempotency_key.strip()
    if reconciliation.reversal:
        if (
            reconciliation.reversal.idempotency_key != key
            or reconciliation.reversal.reason != data.reason.strip()
        ):
            raise HTTPException(status_code=409, detail="ეს შეჯერება უკვე გაუქმებულია")
        transaction = await load_transaction(db, reconciliation.bank_transaction_id, current_user.company_id)
        receivable = await load_receivable(db, reconciliation.customer_receivable_id, current_user.company_id)
        return ResponseBase(data=await bank_result(db, transaction, receivable, reconciliation))
    transaction = await load_transaction(db, reconciliation.bank_transaction_id, current_user.company_id, for_update=True)
    receivable = await load_receivable(db, reconciliation.customer_receivable_id, current_user.company_id, for_update=True)
    payment = (
        await db.execute(select(CustomerPayment).where(
            CustomerPayment.id == reconciliation.customer_payment_id,
            CustomerPayment.company_id == current_user.company_id,
        ).with_for_update())
    ).scalar_one()
    db.add(CustomerPaymentReversal(
        company_id=current_user.company_id,
        payment_id=payment.id,
        idempotency_key=f"bank-reversal:{key}",
        reason=data.reason.strip(),
        reversed_by=current_user.id,
    ))
    reversal = CustomerBankReconciliationReversal(
        company_id=current_user.company_id,
        reconciliation_id=reconciliation.id,
        bank_transaction_id=reconciliation.bank_transaction_id,
        customer_receivable_id=reconciliation.customer_receivable_id,
        amount=reconciliation.amount,
        idempotency_key=key,
        reason=data.reason.strip(),
        reversed_by=current_user.id,
    )
    db.add(reversal)
    reconciliation.reversal = reversal
    payment.status = "reversed"
    transaction.matched_amount = money(transaction.matched_amount - reconciliation.amount)
    transaction.status = "unmatched" if transaction.matched_amount == 0 else "partially_matched"
    receivable.paid_amount = money(receivable.paid_amount - reconciliation.amount)
    refresh_status(receivable)
    await db.flush()
    add_audit(db, current_user, "customer_bank_reconciliation.reversed", "customer_bank_reconciliation", reconciliation.id, {
        "bank_transaction_id": transaction.id, "receivable_id": receivable.id,
        "amount": reconciliation.amount, "reason": data.reason.strip(),
    })
    await post_customer_bank_reconciliation_reversal_gl(
        db, current_user.company_id, current_user,
        reversal_id=reversal.id,
        reconciliation_id=reconciliation.id,
        invoice_number=receivable.invoice_number,
        reversal_date=date.today(),
        amount=reconciliation.amount,
    )
    return ResponseBase(data=await bank_result(db, transaction, receivable, reconciliation))
