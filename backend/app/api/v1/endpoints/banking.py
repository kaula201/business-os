import csv
import hashlib
import io
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.supplier_finance import (
    add_audit,
    build_payable_response,
    load_payable,
    refresh_payable_graph,
)
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.banking import (
    BankAccount,
    BankReconciliation,
    BankStatementImport,
    BankTransaction,
)
from app.models.bank_connection import BankConnection
from app.models.purchase import SupplierPayable, SupplierPayment, SupplierPaymentReversal
from app.models.receivable import CustomerReceivable
from app.models.user import User
from app.schemas.banking import (
    BankAccountCreate,
    BankAccountResponse,
    BankReconciliationCreate,
    BankReconciliationListResponse,
    BankReconciliationResponse,
    BankReconciliationResult,
    BankReconciliationReversalCreate,
    BankStatementImportCreate,
    BankStatementImportResponse,
    BankTransactionResponse,
)
from app.services.gl_hooks import (
    post_supplier_bank_reconciliation_gl,
    post_supplier_bank_reconciliation_reversal_gl,
)
from app.schemas.common import PaginatedResponse, ResponseBase
from app.services.accounting_periods import ensure_period_open

router = APIRouter(tags=["საბანკო ოპერაციები"])


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def require_finance_role(user: User) -> None:
    if user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="საბანკო ოპერაციის შესრულების უფლება არ გაქვთ")


def account_response(account: BankAccount) -> BankAccountResponse:
    return BankAccountResponse(
        id=account.id,
        bank_name=account.bank_name,
        account_name=account.account_name,
        iban=account.iban,
        currency=account.currency,
        status=account.status,
        created_at=account.created_at,
    )


def import_response(statement: BankStatementImport) -> BankStatementImportResponse:
    return BankStatementImportResponse(
        id=statement.id,
        bank_account_id=statement.bank_account_id,
        filename=statement.filename,
        transaction_count=statement.transaction_count,
        debit_total=float(statement.debit_total),
        credit_total=float(statement.credit_total),
        created_at=statement.created_at,
    )


def transaction_response(transaction: BankTransaction) -> BankTransactionResponse:
    unmatched = money(Decimal(transaction.amount) - Decimal(transaction.matched_amount))
    return BankTransactionResponse(
        id=transaction.id,
        bank_account_id=transaction.bank_account_id,
        bank_account_name=transaction.bank_account.account_name,
        transaction_date=transaction.transaction_date,
        reference=transaction.reference,
        description=transaction.description,
        counterparty=transaction.counterparty,
        amount=float(transaction.amount),
        matched_amount=float(transaction.matched_amount),
        unmatched_amount=float(unmatched),
        direction=transaction.direction,
        currency=transaction.currency,
        status=transaction.status,
        created_at=transaction.created_at,
    )


def reconciliation_response(row: BankReconciliation) -> BankReconciliationResponse:
    return BankReconciliationResponse(
        id=row.id,
        bank_transaction_id=row.bank_transaction_id,
        supplier_payable_id=row.supplier_payable_id,
        supplier_payment_id=row.supplier_payment_id,
        amount=float(row.amount),
        status=row.status,
        notes=row.notes,
        reversal_reason=row.reversal_reason,
        reversed_at=row.reversed_at,
        created_at=row.created_at,
    )


async def load_transaction(
    db: AsyncSession, transaction_id: UUID, company_id: UUID, *, for_update: bool = False
) -> BankTransaction:
    query = select(BankTransaction).where(
        BankTransaction.id == transaction_id,
        BankTransaction.company_id == company_id,
    )
    if for_update:
        query = query.with_for_update()
    transaction = (
        await db.execute(query.options(selectinload(BankTransaction.bank_account)).execution_options(populate_existing=True))
    ).scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="საბანკო transaction არ მოიძებნა")
    return transaction


async def result_response(
    db: AsyncSession, transaction: BankTransaction, payable, reconciliation: BankReconciliation
) -> BankReconciliationResult:
    transaction = await load_transaction(db, transaction.id, transaction.company_id)
    payable = await refresh_payable_graph(db, payable)
    await db.refresh(reconciliation)
    return BankReconciliationResult(
        transaction=transaction_response(transaction),
        payable=build_payable_response(payable),
        reconciliation=reconciliation_response(reconciliation),
    )


@router.get("/bank-accounts/", response_model=ResponseBase[list[BankAccountResponse]])
async def list_bank_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = (
        await db.execute(
            select(BankAccount)
            .where(BankAccount.company_id == current_user.company_id)
            .order_by(BankAccount.account_name)
        )
    ).scalars().all()
    return ResponseBase(data=[account_response(account) for account in accounts])


@router.get("/bank-accounts/{account_id}/balance", response_model=ResponseBase[dict])
async def bank_account_balance(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return bank account balance: total debits, total credits, net balance."""
    account = (
        await db.execute(select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.company_id == current_user.company_id,
        ))
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="საბანკო ანგარიში არ მოიძებნა")

    debit_total = await db.scalar(
        select(func.coalesce(func.sum(BankTransaction.amount), 0))
        .where(
            BankTransaction.bank_account_id == account_id,
            BankTransaction.company_id == current_user.company_id,
            BankTransaction.direction == "debit",
        )
    )
    credit_total = await db.scalar(
        select(func.coalesce(func.sum(BankTransaction.amount), 0))
        .where(
            BankTransaction.bank_account_id == account_id,
            BankTransaction.company_id == current_user.company_id,
            BankTransaction.direction == "credit",
        )
    )
    return ResponseBase(data={
        "account_name": account.account_name,
        "iban": account.iban,
        "currency": account.currency,
        "total_debits": float(debit_total or 0),
        "total_credits": float(credit_total or 0),
        "net_balance": float((debit_total or 0) - (credit_total or 0)),
    })


@router.post("/bank-accounts/", response_model=ResponseBase[BankAccountResponse])
async def create_bank_account(
    data: BankAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    iban = data.iban.replace(" ", "").upper()
    existing = (
        await db.execute(select(BankAccount.id).where(
            BankAccount.company_id == current_user.company_id,
            BankAccount.iban == iban,
        ).limit(1))
    ).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="ეს საბანკო ანგარიში უკვე არსებობს")
    account = BankAccount(
        company_id=current_user.company_id,
        bank_name=data.bank_name.strip(),
        account_name=data.account_name.strip(),
        iban=iban,
        currency=data.currency.upper(),
        created_by=current_user.id,
    )
    db.add(account)
    await db.flush()
    add_audit(db, current_user, "bank_account.created", "bank_account", account.id, {
        "bank_name": account.bank_name, "iban": account.iban, "currency": account.currency,
    })
    await db.refresh(account)
    return ResponseBase(data=account_response(account))


@router.post(
    "/bank-accounts/{account_id}/statement-imports",
    response_model=ResponseBase[BankStatementImportResponse],
)
async def import_bank_statement(
    account_id: UUID,
    data: BankStatementImportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    account = (
        await db.execute(select(BankAccount).where(
            BankAccount.id == account_id,
            BankAccount.company_id == current_user.company_id,
        ).with_for_update())
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="საბანკო ანგარიში არ მოიძებნა")

    idempotency_key = data.idempotency_key.strip()
    content_hash = hashlib.sha256(data.csv_content.encode("utf-8-sig")).hexdigest()
    existing = (
        await db.execute(select(BankStatementImport).where(
            BankStatementImport.company_id == current_user.company_id,
            (BankStatementImport.idempotency_key == idempotency_key)
            | ((BankStatementImport.bank_account_id == account.id) & (BankStatementImport.content_hash == content_hash)),
        ).order_by(BankStatementImport.created_at).limit(1))
    ).scalars().first()
    if existing:
        if existing.bank_account_id != account.id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა ანგარიშზე უკვე გამოყენებულია")
        return ResponseBase(data=import_response(existing))

    reader = csv.DictReader(io.StringIO(data.csv_content.lstrip("\ufeff")))
    required = {"transaction_date", "reference", "description", "counterparty", "amount", "direction", "currency"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise HTTPException(status_code=422, detail="CSV სვეტები არასწორია")

    parsed: list[dict] = []
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for index, row in enumerate(reader, start=2):
        try:
            transaction_date = date.fromisoformat((row["transaction_date"] or "").strip())
            amount = money(Decimal((row["amount"] or "").strip()))
        except (ValueError, InvalidOperation):
            raise HTTPException(status_code=422, detail=f"CSV-ის {index}-ე ხაზზე თარიღი ან თანხა არასწორია")
        direction = (row["direction"] or "").strip().lower()
        currency = (row["currency"] or account.currency).strip().upper()
        if amount <= 0 or direction not in {"debit", "credit"}:
            raise HTTPException(status_code=422, detail=f"CSV-ის {index}-ე ხაზზე amount/direction არასწორია")
        if currency != account.currency:
            raise HTTPException(status_code=422, detail=f"CSV-ის {index}-ე ხაზის ვალუტა ანგარიშს არ ემთხვევა")
        reference = (row["reference"] or "").strip() or f"ROW-{index}"
        description = (row["description"] or "").strip()
        counterparty = (row["counterparty"] or "").strip()
        fingerprint_source = "|".join([
            str(account.id), transaction_date.isoformat(), reference, description,
            counterparty, str(amount), direction, currency,
        ])
        fingerprint = hashlib.sha256(fingerprint_source.encode()).hexdigest()
        parsed.append({
            "transaction_date": transaction_date,
            "reference": reference,
            "description": description,
            "counterparty": counterparty,
            "amount": amount,
            "direction": direction,
            "currency": currency,
            "fingerprint": fingerprint,
        })
        if direction == "debit":
            debit_total += amount
        else:
            credit_total += amount
    if not parsed:
        raise HTTPException(status_code=422, detail="CSV transaction-ებს არ შეიცავს")

    for transaction_date in sorted({row["transaction_date"] for row in parsed}):
        await ensure_period_open(db, current_user.company_id, transaction_date)

    statement = BankStatementImport(
        company_id=current_user.company_id,
        bank_account_id=account.id,
        idempotency_key=idempotency_key,
        filename=data.filename.strip(),
        content_hash=content_hash,
        transaction_count=len(parsed),
        debit_total=money(debit_total),
        credit_total=money(credit_total),
        imported_by=current_user.id,
    )
    db.add(statement)
    await db.flush()
    fingerprints = [row["fingerprint"] for row in parsed]
    existing_fingerprints = set((
        await db.execute(select(BankTransaction.fingerprint).where(
            BankTransaction.company_id == current_user.company_id,
            BankTransaction.bank_account_id == account.id,
            BankTransaction.fingerprint.in_(fingerprints),
        ))
    ).scalars().all())
    for row in parsed:
        if row["fingerprint"] in existing_fingerprints:
            continue
        db.add(BankTransaction(
            company_id=current_user.company_id,
            bank_account_id=account.id,
            statement_import_id=statement.id,
            matched_amount=Decimal("0"),
            status="unmatched",
            **row,
        ))
    await db.flush()
    add_audit(db, current_user, "bank_statement.imported", "bank_statement_import", statement.id, {
        "bank_account_id": account.id,
        "filename": statement.filename,
        "transaction_count": statement.transaction_count,
        "debit_total": statement.debit_total,
        "credit_total": statement.credit_total,
    })
    await db.refresh(statement)
    return ResponseBase(data=import_response(statement))


@router.get(
    "/bank-transactions/",
    response_model=ResponseBase[PaginatedResponse[BankTransactionResponse]],
)
async def list_bank_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    bank_account_id: UUID | None = None,
    direction: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [BankTransaction.company_id == current_user.company_id]
    if bank_account_id:
        filters.append(BankTransaction.bank_account_id == bank_account_id)
    if direction:
        filters.append(BankTransaction.direction == direction)
    if status:
        filters.append(BankTransaction.status == status)
    total = (await db.execute(select(func.count(BankTransaction.id)).where(*filters))).scalar_one()
    transactions = (
        await db.execute(
            select(BankTransaction)
            .where(*filters)
            .options(selectinload(BankTransaction.bank_account))
            .order_by(BankTransaction.transaction_date.desc(), BankTransaction.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[transaction_response(row) for row in transactions],
    ))


@router.get("/reconciliation-suggestions", response_model=ResponseBase[list[dict]])
async def reconciliation_suggestions(
    bank_account_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return unmatched bank transactions with candidate payable/receivable matches
    and a confidence score (0-100) so the user can review and approve in batch."""
    require_finance_role(current_user)
    filters = [BankTransaction.company_id == current_user.company_id, BankTransaction.status == "unmatched"]
    if bank_account_id:
        filters.append(BankTransaction.bank_account_id == bank_account_id)
    txns = (await db.execute(
        select(BankTransaction).where(*filters)
        .order_by(BankTransaction.transaction_date.desc())
        .limit(limit)
    )).scalars().all()

    payables = (await db.execute(select(SupplierPayable).where(
        SupplierPayable.company_id == current_user.company_id,
        SupplierPayable.status == "unpaid",
        SupplierPayable.outstanding_amount > 0,
    ).options(selectinload(SupplierPayable.supplier), selectinload(SupplierPayable.supplier_invoice)))).scalars().all()
    receivables = (await db.execute(select(CustomerReceivable).where(
        CustomerReceivable.company_id == current_user.company_id,
        CustomerReceivable.status == "unpaid",
        CustomerReceivable.outstanding_amount > 0,
    ))).scalars().all()

    suggestions = []
    for txn in txns:
        candidates = []
        if txn.direction == "debit":
            for p in payables:
                if p.currency_code != txn.currency:
                    continue
                diff = abs(float(p.outstanding_amount) - float(txn.amount))
                score = 100 if diff == 0 else max(0, 100 - int(diff / max(float(txn.amount), 1) * 100))
                if score >= 60:
                    candidates.append({"kind": "payable", "id": str(p.id), "label": f"{p.supplier_invoice.internal_invoice_number} — {p.supplier.name}",
                                       "amount": float(p.outstanding_amount), "confidence": score,
                                       "reason": "თანხა ემთხვევა" if score == 100 else "თანხა ახლოსაა"})
        else:
            for r in receivables:
                if r.currency != txn.currency:
                    continue
                diff = abs(float(r.outstanding_amount) - float(txn.amount))
                score = 100 if diff == 0 else max(0, 100 - int(diff / max(float(txn.amount), 1) * 100))
                if score >= 60:
                    candidates.append({"kind": "receivable", "id": str(r.id), "label": f"{r.invoice_number} — {r.client_name}",
                                       "amount": float(r.outstanding_amount), "confidence": score,
                                       "reason": "თანხა ემთხვევა" if score == 100 else "თანხა ახლოსაა"})
        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        suggestions.append({
            "transaction_id": str(txn.id), "reference": txn.reference, "description": txn.description,
            "counterparty": txn.counterparty, "amount": float(txn.amount), "direction": txn.direction,
            "transaction_date": str(txn.transaction_date), "candidates": candidates[:3],
        })
    return ResponseBase(data=suggestions)


@router.post(
    "/bank-transactions/{transaction_id}/reconciliations",
    response_model=ResponseBase[BankReconciliationResult],
)
async def reconcile_bank_transaction(
    transaction_id: UUID,
    data: BankReconciliationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    idempotency_key = data.idempotency_key.strip()
    existing = (
        await db.execute(select(BankReconciliation).where(
            BankReconciliation.company_id == current_user.company_id,
            BankReconciliation.idempotency_key == idempotency_key,
        ))
    ).scalar_one_or_none()
    if existing:
        if existing.bank_transaction_id != transaction_id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა reconciliation-ზე გამოყენებულია")
        transaction = await load_transaction(db, existing.bank_transaction_id, current_user.company_id)
        payable = await load_payable(db, existing.supplier_payable_id, current_user.company_id)
        return ResponseBase(data=await result_response(db, transaction, payable, existing))

    transaction = await load_transaction(db, transaction_id, current_user.company_id, for_update=True)
    if transaction.direction != "debit":
        raise HTTPException(status_code=409, detail="Supplier Payable-ს მხოლოდ debit transaction შეიძლება დაუკავშირდეს")
    payable = await load_payable(db, data.supplier_payable_id, current_user.company_id, for_update=True)
    unmatched = money(Decimal(transaction.amount) - Decimal(transaction.matched_amount))
    if data.amount > unmatched:
        raise HTTPException(status_code=409, detail="შეჯერების თანხა transaction-ის დარჩენილ თანხას აჭარბებს")
    if data.amount > payable.outstanding_amount:
        raise HTTPException(status_code=409, detail="შეჯერების თანხა payable-ის დარჩენილ თანხას აჭარბებს")

    payment = SupplierPayment(
        company_id=current_user.company_id,
        supplier_payable_id=payable.id,
        idempotency_key=f"bank-reconciliation:{idempotency_key}",
        amount=money(data.amount),
        payment_date=transaction.transaction_date,
        payment_method="bank_transfer",
        reference=transaction.reference,
        notes=data.notes or "Bank statement reconciliation",
        created_by=current_user.id,
    )
    db.add(payment)
    await db.flush()
    reconciliation = BankReconciliation(
        company_id=current_user.company_id,
        bank_transaction_id=transaction.id,
        supplier_payable_id=payable.id,
        supplier_payment_id=payment.id,
        idempotency_key=idempotency_key,
        amount=payment.amount,
        notes=data.notes,
        reconciled_by=current_user.id,
    )
    db.add(reconciliation)
    payable.paid_amount = money(Decimal(payable.paid_amount) + payment.amount)
    payable.outstanding_amount = money(
        Decimal(payable.original_amount) - payable.paid_amount - Decimal(payable.credited_amount)
    )
    payable.status = "paid" if payable.outstanding_amount == 0 else "partially_paid"
    transaction.matched_amount = money(Decimal(transaction.matched_amount) + payment.amount)
    transaction.status = "matched" if transaction.matched_amount == transaction.amount else "partially_matched"
    await db.flush()
    add_audit(db, current_user, "bank_transaction.reconciled", "bank_reconciliation", reconciliation.id, {
        "bank_transaction_id": transaction.id,
        "supplier_payable_id": payable.id,
        "supplier_payment_id": payment.id,
        "amount": payment.amount,
    })
    await post_supplier_bank_reconciliation_gl(
        db, current_user.company_id, current_user,
        reconciliation_id=reconciliation.id,
        payment_id=payment.id,
        internal_invoice_number=payable.supplier_invoice.internal_invoice_number,
        reconciliation_date=transaction.transaction_date,
        amount=payment.amount,
    )
    return ResponseBase(data=await result_response(db, transaction, payable, reconciliation))


@router.get(
    "/bank-reconciliations/",
    response_model=ResponseBase[PaginatedResponse[BankReconciliationListResponse]],
)
async def list_bank_reconciliations(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    bank_transaction_id: UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [BankReconciliation.company_id == current_user.company_id]
    if bank_transaction_id:
        filters.append(BankReconciliation.bank_transaction_id == bank_transaction_id)
    if status:
        filters.append(BankReconciliation.status == status)
    total = (await db.execute(select(func.count(BankReconciliation.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(BankReconciliation)
            .where(*filters)
            .options(
                selectinload(BankReconciliation.bank_transaction),
                selectinload(BankReconciliation.supplier_payable).selectinload(SupplierPayable.supplier),
                selectinload(BankReconciliation.supplier_payable).selectinload(SupplierPayable.supplier_invoice),
            )
            .order_by(BankReconciliation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    items = [
        BankReconciliationListResponse(
            **reconciliation_response(row).model_dump(),
            transaction_reference=row.bank_transaction.reference,
            supplier_name=row.supplier_payable.supplier.name,
            supplier_invoice_number=row.supplier_payable.supplier_invoice.supplier_invoice_number,
        )
        for row in rows
    ]
    return ResponseBase(data=PaginatedResponse(total=total, page=page, page_size=page_size, items=items))


@router.post(
    "/bank-reconciliations/{reconciliation_id}/reversal",
    response_model=ResponseBase[BankReconciliationResult],
)
async def reverse_bank_reconciliation(
    reconciliation_id: UUID,
    data: BankReconciliationReversalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_finance_role(current_user)
    reconciliation = (
        await db.execute(select(BankReconciliation).where(
            BankReconciliation.id == reconciliation_id,
            BankReconciliation.company_id == current_user.company_id,
        ).with_for_update())
    ).scalar_one_or_none()
    if not reconciliation:
        raise HTTPException(status_code=404, detail="Bank reconciliation არ მოიძებნა")
    idempotency_key = data.idempotency_key.strip()
    if reconciliation.status == "reversed":
        if reconciliation.reversal_idempotency_key != idempotency_key:
            raise HTTPException(status_code=409, detail="ეს reconciliation უკვე გაუქმებულია")
        transaction = await load_transaction(db, reconciliation.bank_transaction_id, current_user.company_id)
        payable = await load_payable(db, reconciliation.supplier_payable_id, current_user.company_id)
        return ResponseBase(data=await result_response(db, transaction, payable, reconciliation))

    duplicate_key = (
        await db.execute(select(BankReconciliation.id).where(
            BankReconciliation.company_id == current_user.company_id,
            BankReconciliation.reversal_idempotency_key == idempotency_key,
        ).limit(1))
    ).scalars().first()
    if duplicate_key:
        raise HTTPException(status_code=409, detail="reversal idempotency key უკვე გამოყენებულია")
    transaction = await load_transaction(db, reconciliation.bank_transaction_id, current_user.company_id, for_update=True)
    payable = await load_payable(db, reconciliation.supplier_payable_id, current_user.company_id, for_update=True)
    payment = (
        await db.execute(select(SupplierPayment).where(
            SupplierPayment.id == reconciliation.supplier_payment_id,
            SupplierPayment.company_id == current_user.company_id,
        ).with_for_update())
    ).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=409, detail="reconciliation payment არ მოიძებნა")
    payment_reversal = (
        await db.execute(select(SupplierPaymentReversal).where(
            SupplierPaymentReversal.supplier_payment_id == payment.id
        ))
    ).scalar_one_or_none()
    if payment_reversal:
        raise HTTPException(status_code=409, detail="ამ reconciliation-ის payment უკვე გაუქმებულია")

    db.add(SupplierPaymentReversal(
        company_id=current_user.company_id,
        supplier_payment_id=payment.id,
        supplier_payable_id=payable.id,
        idempotency_key=f"bank-reconciliation-reversal:{idempotency_key}",
        amount=payment.amount,
        reason=data.reason.strip(),
        created_by=current_user.id,
    ))
    payable.paid_amount = money(Decimal(payable.paid_amount) - Decimal(payment.amount))
    payable.outstanding_amount = money(
        Decimal(payable.original_amount) - payable.paid_amount - Decimal(payable.credited_amount)
    )
    payable.status = "paid" if payable.outstanding_amount == 0 else (
        "partially_paid" if payable.paid_amount > 0 else "unpaid"
    )
    transaction.matched_amount = money(Decimal(transaction.matched_amount) - Decimal(reconciliation.amount))
    transaction.status = "unmatched" if transaction.matched_amount == 0 else "partially_matched"
    reconciliation.status = "reversed"
    reconciliation.reversal_idempotency_key = idempotency_key
    reconciliation.reversal_reason = data.reason.strip()
    reconciliation.reversed_by = current_user.id
    reconciliation.reversed_at = utc_now()
    await db.flush()
    add_audit(db, current_user, "bank_reconciliation.reversed", "bank_reconciliation", reconciliation.id, {
        "bank_transaction_id": transaction.id,
        "supplier_payable_id": payable.id,
        "amount": reconciliation.amount,
        "reason": reconciliation.reversal_reason,
    })
    await post_supplier_bank_reconciliation_reversal_gl(
        db, current_user.company_id, current_user,
        reversal_id=reconciliation.id,
        reconciliation_id=reconciliation.id,
        internal_invoice_number=payable.supplier_invoice.internal_invoice_number,
        reversal_date=date.today(),
        amount=reconciliation.amount,
    )
    return ResponseBase(data=await result_response(db, transaction, payable, reconciliation))


# ── Bank connections (TBC/BOG sync) ───────────────────────────────────────────

@router.get("/connections", response_model=ResponseBase[list[dict]])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BankConnection).where(BankConnection.company_id == current_user.company_id).order_by(BankConnection.bank)
    )
    return ResponseBase(data=[{
        "id": str(c.id), "bank": c.bank, "name": c.name, "account_number": c.account_number,
        "is_active": c.is_active, "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
    } for c in result.scalars().all()])


@router.post("/connections", response_model=ResponseBase[dict], status_code=201)
async def create_connection(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = BankConnection(
        company_id=current_user.company_id,
        bank=data.get("bank", "tbc"),
        name=data.get("name", ""),
        account_number=data.get("account_number", ""),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return ResponseBase(data={"id": str(c.id), "bank": c.bank, "name": c.name}, message="ბანკის კავშირი შეიქმნა")


@router.delete("/connections/{connection_id}", response_model=ResponseBase[dict])
async def delete_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BankConnection).where(BankConnection.id == connection_id, BankConnection.company_id == current_user.company_id)
    )
    c = result.scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="კავშირი არ მოიძებნა")
    await db.delete(c)
    await db.commit()
    return ResponseBase(data={"id": str(connection_id)}, message="კავშირი წაიშალა")


@router.post("/connections/{connection_id}/sync", response_model=ResponseBase[dict])
async def sync_connection(
    connection_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sync bank transactions from TBC/BOG. Accepts a list of transactions
    (date, reference, description, counterparty, amount, direction, currency)
    and imports them with fingerprint deduplication."""
    result = await db.execute(
        select(BankConnection).where(BankConnection.id == connection_id, BankConnection.company_id == current_user.company_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="კავშირი არ მოიძებნა")

    account_result = await db.execute(
        select(BankAccount).where(
            BankAccount.company_id == current_user.company_id,
            BankAccount.iban == conn.account_number,
        )
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=400, detail="ანგარიში ვერ მოიძებნა — ჯერ შექმენით Bank Account")

    transactions = data.get("transactions", [])
    if not transactions:
        raise HTTPException(status_code=422, detail="transactions სია ცარიელია")

    statement = BankStatementImport(
        company_id=current_user.company_id,
        bank_account_id=account.id,
        idempotency_key=f"sync-{conn.id}-{utc_now().isoformat()}",
        filename=f"{conn.bank}-sync",
        content_hash=hashlib.sha256(str(transactions).encode()).hexdigest(),
        transaction_count=len(transactions),
        debit_total=Decimal("0"),
        credit_total=Decimal("0"),
        imported_by=current_user.id,
    )
    db.add(statement)
    await db.flush()

    created = 0
    skipped = 0
    for t in transactions:
        try:
            txn_date = date.fromisoformat((t.get("date") or "").strip()[:10])
            amount = Decimal(str(t.get("amount", "0")))
        except (ValueError, InvalidOperation):
            continue
        direction = (t.get("direction") or "credit").lower()
        currency = (t.get("currency") or account.currency).upper()
        reference = (t.get("reference") or "").strip() or f"SYNC-{created + 1}"
        description = (t.get("description") or "").strip()
        counterparty = (t.get("counterparty") or "").strip()
        fingerprint_source = "|".join([
            str(account.id), txn_date.isoformat(), reference, description,
            counterparty, str(amount), direction, currency,
        ])
        fingerprint = hashlib.sha256(fingerprint_source.encode()).hexdigest()

        existing = (await db.execute(
            select(BankTransaction.id).where(
                BankTransaction.company_id == current_user.company_id,
                BankTransaction.fingerprint == fingerprint,
            )
        )).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        db.add(BankTransaction(
            company_id=current_user.company_id,
            bank_account_id=account.id,
            statement_import_id=statement.id,
            transaction_date=txn_date,
            reference=reference,
            description=description,
            counterparty=counterparty,
            amount=amount,
            matched_amount=Decimal("0"),
            direction=direction,
            currency=currency,
            fingerprint=fingerprint,
            status="unmatched",
        ))
        created += 1

    conn.last_sync_at = utc_now()
    await db.commit()
    return ResponseBase(data={"created": created, "skipped": skipped}, message="სინქრონიზაცია დასრულდა")
