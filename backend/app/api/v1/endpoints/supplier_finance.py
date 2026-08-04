import json
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import allocate_document_number
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.purchase import (
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierCreditNote,
    SupplierCreditNoteCurrencyDiff,
    SupplierInvoice,
    SupplierInvoiceItem,
    SupplierInvoiceTolerance,
    SupplierOverpayment,
    SupplierPayable,
    SupplierPayment,
    SupplierPaymentReversal,
)
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.supplier_finance import (
    DuplicateInvoiceCheck,
    DuplicateInvoiceResult,
    OverpaymentApplyCreate,
    SupplierCreditNoteCreate,
    SupplierCreditNoteCurrencyDiffResponse,
    SupplierCreditNoteResponse,
    SupplierInvoiceCreate,
    SupplierInvoiceItemResponse,
    SupplierInvoiceResponse,
    SupplierInvoiceStatusChange,
    SupplierInvoiceToleranceCreate,
    SupplierInvoiceToleranceResponse,
    SupplierOverpaymentResponse,
    SupplierPayableResponse,
    SupplierPaymentCreate,
    SupplierPaymentResponse,
    SupplierPaymentReversalCreate,
    SupplierPaymentReversalResponse,
)
from app.services.gl_hooks import (
    post_supplier_credit_note_gl,
    post_supplier_invoice_gl,
    post_supplier_payment_gl,
    post_supplier_payment_reversal_gl,
)

router = APIRouter(tags=["მომწოდებლის ფინანსები"])

INVOICE_OPTIONS = (
    selectinload(SupplierInvoice.supplier),
    selectinload(SupplierInvoice.purchase_order),
    selectinload(SupplierInvoice.items),
    selectinload(SupplierInvoice.payable).selectinload(SupplierPayable.payments).selectinload(SupplierPayment.reversal),
    selectinload(SupplierInvoice.payable).selectinload(SupplierPayable.credit_notes),
    selectinload(SupplierInvoice.payable).selectinload(SupplierPayable.overpayments),
    selectinload(SupplierInvoice.payable).selectinload(SupplierPayable.supplier),
    selectinload(SupplierInvoice.payable).selectinload(SupplierPayable.supplier_invoice),
)

PAYABLE_OPTIONS = (
    selectinload(SupplierPayable.supplier),
    selectinload(SupplierPayable.supplier_invoice),
    selectinload(SupplierPayable.payments).selectinload(SupplierPayment.reversal),
    selectinload(SupplierPayable.credit_notes),
    selectinload(SupplierPayable.overpayments),
)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def add_audit(
    db: AsyncSession,
    current_user: User,
    action: str,
    entity_type: str,
    entity_id: UUID,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


def effective_payable_status(payable: SupplierPayable) -> tuple[str, int]:
    if payable.status == "paid" or payable.outstanding_amount <= 0:
        if payable.overpaid_amount > 0:
            return "overpaid", 0
        return "paid", 0
    if payable.due_date < date.today():
        return "overdue", (date.today() - payable.due_date).days
    return payable.status, 0


def build_payable_response(payable: SupplierPayable) -> SupplierPayableResponse:
    status, days_overdue = effective_payable_status(payable)
    return SupplierPayableResponse(
        id=payable.id,
        supplier_id=payable.supplier_id,
        supplier_name=payable.supplier.name,
        supplier_invoice_id=payable.supplier_invoice_id,
        internal_invoice_number=payable.supplier_invoice.internal_invoice_number,
        supplier_invoice_number=payable.supplier_invoice.supplier_invoice_number,
        due_date=payable.due_date,
        original_amount=float(payable.original_amount),
        paid_amount=float(payable.paid_amount),
        credited_amount=float(payable.credited_amount),
        overpaid_amount=float(payable.overpaid_amount),
        outstanding_amount=float(payable.outstanding_amount),
        currency_code=payable.currency_code,
        exchange_rate=float(payable.exchange_rate),
        status=status,
        days_overdue=days_overdue,
        payments=[
            SupplierPaymentResponse(
                id=payment.id,
                amount=float(payment.amount),
                payment_date=payment.payment_date,
                payment_method=payment.payment_method,
                reference=payment.reference,
                notes=payment.notes,
                is_reversed=payment.reversal is not None,
                reversal=(
                    SupplierPaymentReversalResponse(
                        id=payment.reversal.id,
                        amount=float(payment.reversal.amount),
                        reason=payment.reversal.reason,
                        created_at=payment.reversal.created_at,
                    )
                    if payment.reversal else None
                ),
                created_at=payment.created_at,
            )
            for payment in sorted(payable.payments, key=lambda row: (row.payment_date, row.created_at))
        ],
        credit_notes=[
            SupplierCreditNoteResponse(
                id=credit.id,
                supplier_credit_note_number=credit.supplier_credit_note_number,
                amount=float(credit.amount),
                credit_date=credit.credit_date,
                reason=credit.reason,
                currency_code=getattr(credit, "currency_code", None) or payable.currency_code,
                exchange_rate=float(getattr(credit, "exchange_rate", Decimal("1"))),
                created_at=credit.created_at,
            )
            for credit in sorted(payable.credit_notes, key=lambda row: (row.credit_date, row.created_at))
        ],
        overpayments=[
            SupplierOverpaymentResponse(
                id=op.id,
                amount=float(op.amount),
                remaining_amount=float(op.remaining_amount),
                currency_code=op.currency_code,
                exchange_rate=float(op.exchange_rate),
                notes=op.notes,
                created_at=op.created_at,
            )
            for op in sorted(payable.overpayments, key=lambda row: row.created_at)
        ],
        created_at=payable.created_at,
        updated_at=payable.updated_at,
    )


def build_invoice_response(invoice: SupplierInvoice) -> SupplierInvoiceResponse:
    try:
        issues = json.loads(invoice.match_issues or "[]")
    except json.JSONDecodeError:
        issues = [invoice.match_issues]
    return SupplierInvoiceResponse(
        id=invoice.id,
        supplier_id=invoice.supplier_id,
        supplier_name=invoice.supplier.name,
        purchase_order_id=invoice.purchase_order_id,
        purchase_order_number=invoice.purchase_order.purchase_order_number,
        internal_invoice_number=invoice.internal_invoice_number,
        supplier_invoice_number=invoice.supplier_invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        status=invoice.status,
        matching_status=invoice.matching_status,
        match_issues=issues,
        subtotal=float(invoice.subtotal),
        vat_amount=float(invoice.vat_amount),
        total=float(invoice.total),
        notes=invoice.notes,
        approved_at=invoice.approved_at,
        items=[
            SupplierInvoiceItemResponse(
                id=item.id,
                purchase_order_item_id=item.purchase_order_item_id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=float(item.quantity),
                unit_price=float(item.unit_price),
                discount_percent=float(item.discount_percent),
                vat_rate=float(item.vat_rate),
                line_subtotal=float(item.line_subtotal),
                vat_amount=float(item.vat_amount),
                line_total=float(item.line_total),
                matching_status=item.matching_status,
                match_issue=item.match_issue,
            )
            for item in invoice.items
        ],
        payable=build_payable_response(invoice.payable) if invoice.payable else None,
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


async def load_invoice(
    db: AsyncSession, invoice_id: UUID, company_id: UUID, *, for_update: bool = False
) -> SupplierInvoice:
    query = select(SupplierInvoice).where(
        SupplierInvoice.id == invoice_id,
        SupplierInvoice.company_id == company_id,
    )
    if for_update:
        query = query.with_for_update()
    invoice = (
        await db.execute(query.options(*INVOICE_OPTIONS).execution_options(populate_existing=True))
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Supplier Invoice არ მოიძებნა")
    return invoice


async def load_payable(
    db: AsyncSession, payable_id: UUID, company_id: UUID, *, for_update: bool = False
) -> SupplierPayable:
    query = select(SupplierPayable).where(
        SupplierPayable.id == payable_id,
        SupplierPayable.company_id == company_id,
    )
    if for_update:
        query = query.with_for_update()
    payable = (
        await db.execute(query.options(*PAYABLE_OPTIONS).execution_options(populate_existing=True))
    ).unique().scalar_one_or_none()
    if not payable:
        raise HTTPException(status_code=404, detail="მომწოდებლის დავალიანება არ მოიძებნა")
    return payable


async def refresh_invoice_graph(
    db: AsyncSession, invoice: SupplierInvoice
) -> SupplierInvoice:
    await db.refresh(
        invoice,
        attribute_names=["supplier", "purchase_order", "items", "payable"],
    )
    if invoice.payable:
        await db.refresh(
            invoice.payable,
            attribute_names=["supplier", "supplier_invoice", "payments", "credit_notes", "overpayments"],
        )
    return invoice


async def refresh_payable_graph(
    db: AsyncSession, payable: SupplierPayable
) -> SupplierPayable:
    await db.refresh(payable)
    return await load_payable(db, payable.id, payable.company_id)


async def get_tolerance(
    db: AsyncSession, company_id: UUID
) -> SupplierInvoiceTolerance:
    """Get or create default tolerance settings for a company."""
    tolerance = (
        await db.execute(
            select(SupplierInvoiceTolerance).where(
                SupplierInvoiceTolerance.company_id == company_id
            )
        )
    ).scalar_one_or_none()
    if not tolerance:
        tolerance = SupplierInvoiceTolerance(company_id=company_id)
        db.add(tolerance)
        await db.flush()
    return tolerance


async def check_duplicate_invoice(
    db: AsyncSession,
    company_id: UUID,
    supplier_id: UUID,
    supplier_invoice_number: str,
    invoice_date: date,
    total: Decimal,
) -> dict:
    """Check for potential duplicate invoices with confidence levels."""
    tolerance = await get_tolerance(db, company_id)
    if not tolerance.enable_duplicate_detection:
        return {"is_duplicate": False, "confidence": "none", "matched_invoices": [], "reason": "Duplicate detection disabled"}

    lookback_date = invoice_date - timedelta(days=tolerance.duplicate_lookback_days)

    # High confidence: exact same number + same supplier
    exact_match = (
        await db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.company_id == company_id,
                SupplierInvoice.supplier_id == supplier_id,
                SupplierInvoice.supplier_invoice_number == supplier_invoice_number.strip(),
                SupplierInvoice.status != "cancelled",
            ).options(selectinload(SupplierInvoice.supplier))
        )
    ).scalars().all()

    if exact_match:
        return {
            "is_duplicate": True,
            "confidence": "high",
            "matched_invoices": [
                {
                    "id": str(inv.id),
                    "supplier_invoice_number": inv.supplier_invoice_number,
                    "internal_invoice_number": inv.internal_invoice_number,
                    "invoice_date": inv.invoice_date.isoformat(),
                    "total": float(inv.total),
                    "status": inv.status,
                }
                for inv in exact_match
            ],
            "reason": f"ზუსტი დუბლიკატი: იგივე ნომერი ({supplier_invoice_number}) იგივე მომწოდებლისთვის",
        }

    # Medium confidence: same number, different supplier (possible re-use)
    same_number_other_supplier = (
        await db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.company_id == company_id,
                SupplierInvoice.supplier_invoice_number == supplier_invoice_number.strip(),
                SupplierInvoice.supplier_id != supplier_id,
                SupplierInvoice.status != "cancelled",
                SupplierInvoice.invoice_date >= lookback_date,
            ).options(selectinload(SupplierInvoice.supplier))
        )
    ).scalars().all()

    if same_number_other_supplier:
        return {
            "is_duplicate": True,
            "confidence": "medium",
            "matched_invoices": [
                {
                    "id": str(inv.id),
                    "supplier_invoice_number": inv.supplier_invoice_number,
                    "internal_invoice_number": inv.internal_invoice_number,
                    "supplier_name": inv.supplier.name,
                    "invoice_date": inv.invoice_date.isoformat(),
                    "total": float(inv.total),
                    "status": inv.status,
                }
                for inv in same_number_other_supplier
            ],
            "reason": f"იგივე ნომერი ({supplier_invoice_number}) სხვა მომწოდებელთან — შესაძლო დუბლიკატი",
        }

    # Low confidence: similar amount + same supplier + close date
    amount_tolerance = float(tolerance.amount_tolerance)
    similar_amount = (
        await db.execute(
            select(SupplierInvoice).where(
                SupplierInvoice.company_id == company_id,
                SupplierInvoice.supplier_id == supplier_id,
                SupplierInvoice.status != "cancelled",
                SupplierInvoice.invoice_date >= lookback_date,
                func.abs(SupplierInvoice.total - total) <= amount_tolerance,
            ).options(selectinload(SupplierInvoice.supplier))
        )
    ).scalars().all()

    if similar_amount:
        return {
            "is_duplicate": True,
            "confidence": "low",
            "matched_invoices": [
                {
                    "id": str(inv.id),
                    "supplier_invoice_number": inv.supplier_invoice_number,
                    "internal_invoice_number": inv.internal_invoice_number,
                    "invoice_date": inv.invoice_date.isoformat(),
                    "total": float(inv.total),
                    "status": inv.status,
                }
                for inv in similar_amount
            ],
            "reason": f"მსგავსი თანხა (±{amount_tolerance}) იმავე მომწოდებლისთვის — შესაძლო დუბლიკატი",
        }

    return {"is_duplicate": False, "confidence": "none", "matched_invoices": [], "reason": None}


# ── Invoice endpoints ──────────────────────────────────────────────────────

@router.get(
    "/supplier-invoices/",
    response_model=ResponseBase[PaginatedResponse[SupplierInvoiceResponse]],
)
async def list_supplier_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    supplier_id: UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [SupplierInvoice.company_id == current_user.company_id]
    if status:
        filters.append(SupplierInvoice.status == status)
    if supplier_id:
        filters.append(SupplierInvoice.supplier_id == supplier_id)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(
            SupplierInvoice.internal_invoice_number.ilike(term),
            SupplierInvoice.supplier_invoice_number.ilike(term),
            SupplierInvoice.supplier.has(Supplier.name.ilike(term)),
            SupplierInvoice.purchase_order.has(PurchaseOrder.purchase_order_number.ilike(term)),
        ))
    total = (await db.execute(select(func.count(SupplierInvoice.id)).where(*filters))).scalar_one()
    invoices = (
        await db.execute(
            select(SupplierInvoice)
            .where(*filters)
            .options(*INVOICE_OPTIONS)
            .order_by(SupplierInvoice.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).unique().scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[build_invoice_response(invoice) for invoice in invoices],
    ))


@router.post("/supplier-invoices/", response_model=ResponseBase[SupplierInvoiceResponse])
async def create_supplier_invoice(
    data: SupplierInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    supplier = (
        await db.execute(select(Supplier).where(
            Supplier.id == data.supplier_id,
            Supplier.company_id == current_user.company_id,
            Supplier.is_active.is_(True),
        ))
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="აქტიური მომწოდებელი არ მოიძებნა")

    purchase_order = (
        await db.execute(
            select(PurchaseOrder)
            .where(
                PurchaseOrder.id == data.purchase_order_id,
                PurchaseOrder.company_id == current_user.company_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase Order არ მოიძებნა")
    if purchase_order.supplier_id != supplier.id:
        raise HTTPException(status_code=409, detail="Purchase Order სხვა მომწოდებელს ეკუთვნის")
    if purchase_order.status not in {"partially_received", "received"}:
        raise HTTPException(status_code=409, detail="Supplier Invoice მხოლოდ მიღებულ საქონელზე შეიძლება შეიქმნას")

    # ── Duplicate detection ──────────────────────────────────────────────
    duplicate_check = await check_duplicate_invoice(
        db, current_user.company_id, supplier.id,
        data.supplier_invoice_number, data.invoice_date, Decimal("0"),
    )
    if duplicate_check["is_duplicate"] and duplicate_check["confidence"] == "high":
        raise HTTPException(
            status_code=409,
            detail=f"დუბლიკატი ინვოისი: {duplicate_check['reason']}",
        )

    # ── Basic duplicate check (same number + same supplier) ──────────────
    duplicate = (
        await db.execute(select(SupplierInvoice.id).where(
            SupplierInvoice.company_id == current_user.company_id,
            SupplierInvoice.supplier_id == supplier.id,
            SupplierInvoice.supplier_invoice_number == data.supplier_invoice_number.strip(),
        ).limit(1))
    ).scalars().first()
    if duplicate:
        raise HTTPException(status_code=409, detail="მომწოდებლის ამ ნომრით invoice უკვე არსებობს")

    requested_ids = [item.purchase_order_item_id for item in data.items]
    po_items = (
        await db.execute(
            select(PurchaseOrderItem)
            .where(
                PurchaseOrderItem.id.in_(requested_ids),
                PurchaseOrderItem.purchase_order_id == purchase_order.id,
            )
            .with_for_update()
        )
    ).scalars().all()
    if len(po_items) != len(requested_ids):
        raise HTTPException(status_code=404, detail="ერთი ან მეტი Purchase Order item არ მოიძებნა")
    po_item_map = {item.id: item for item in po_items}

    billed_rows = (
        await db.execute(
            select(
                SupplierInvoiceItem.purchase_order_item_id,
                func.coalesce(func.sum(SupplierInvoiceItem.quantity), 0),
            )
            .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceItem.supplier_invoice_id)
            .where(
                SupplierInvoice.purchase_order_id == purchase_order.id,
                SupplierInvoice.status != "cancelled",
                SupplierInvoiceItem.purchase_order_item_id.in_(requested_ids),
            )
            .group_by(SupplierInvoiceItem.purchase_order_item_id)
        )
    ).all()
    billed = {row[0]: Decimal(row[1]) for row in billed_rows}

    # ── Load tolerance settings ────────────────────────────────────────
    tolerance = await get_tolerance(db, current_user.company_id)
    qty_tol = tolerance.quantity_tolerance_percent / Decimal("100")
    price_tol = tolerance.price_tolerance_percent / Decimal("100")

    internal_number = await allocate_document_number(
        db, current_user.company_id, "supplier_invoice", "SIN"
    )
    invoice = SupplierInvoice(
        company_id=current_user.company_id,
        supplier_id=supplier.id,
        purchase_order_id=purchase_order.id,
        internal_invoice_number=internal_number,
        supplier_invoice_number=data.supplier_invoice_number.strip(),
        invoice_date=data.invoice_date,
        due_date=data.due_date,
        status="draft",
        matching_status="matched",
        match_issues="[]",
        subtotal=Decimal("0"),
        vat_amount=Decimal("0"),
        total=Decimal("0"),
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(invoice)
    await db.flush()

    subtotal = Decimal("0")
    vat_total = Decimal("0")
    total = Decimal("0")
    invoice_issues: list[str] = []
    has_quantity_mismatch = False
    has_amount_mismatch = False
    for item_data in data.items:
        po_item = po_item_map[item_data.purchase_order_item_id]
        item_issues: list[str] = []
        available_to_invoice = Decimal(po_item.received_quantity) - billed.get(po_item.id, Decimal("0"))

        # ── Quantity tolerance check ────────────────────────────────────
        qty_diff = item_data.quantity - available_to_invoice
        max_allowed_qty = available_to_invoice * (Decimal("1") + qty_tol)
        if item_data.quantity > max_allowed_qty:
            has_quantity_mismatch = True
            item_issues.append(
                f"{po_item.product_name}: invoice quantity {item_data.quantity} მიღებულ და დაუფაქტურებელ {available_to_invoice}-ს აჭარბებს (tolerance: {tolerance.quantity_tolerance_percent}%)"
            )

        # ── Price/discount/VAT tolerance check ──────────────────────────
        price_diff = abs(item_data.unit_price - Decimal(po_item.unit_price))
        max_price_diff = Decimal(po_item.unit_price) * price_tol
        discount_diff = abs(item_data.discount_percent - Decimal(po_item.discount_percent))
        vat_diff = abs(item_data.vat_rate - Decimal(po_item.vat_rate))

        if price_diff > max_price_diff or discount_diff > 0 or vat_diff > 0:
            has_amount_mismatch = True
            issues_parts = []
            if price_diff > max_price_diff:
                issues_parts.append(f"ფასი {item_data.unit_price} (PO: {po_item.unit_price}, tolerance: {tolerance.price_tolerance_percent}%)")
            if discount_diff > 0:
                issues_parts.append(f"ფასდაკლება {item_data.discount_percent}% (PO: {po_item.discount_percent}%)")
            if vat_diff > 0:
                issues_parts.append(f"დღგ {item_data.vat_rate}% (PO: {po_item.vat_rate}%)")
            item_issues.append(f"{po_item.product_name}: {', '.join(issues_parts)} Purchase Order-ს არ ემთხვევა")

        gross = item_data.quantity * item_data.unit_price
        discount = gross * item_data.discount_percent / Decimal("100")
        line_subtotal = money(gross - discount)
        line_vat = money(line_subtotal * item_data.vat_rate / Decimal("100"))
        line_total = money(line_subtotal + line_vat)
        item_status = "matched" if not item_issues else (
            "quantity_mismatch" if has_quantity_mismatch else "amount_mismatch"
        )
        db.add(SupplierInvoiceItem(
            supplier_invoice_id=invoice.id,
            purchase_order_item_id=po_item.id,
            product_id=po_item.product_id,
            product_name=po_item.product_name,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            discount_percent=item_data.discount_percent,
            vat_rate=item_data.vat_rate,
            line_subtotal=line_subtotal,
            vat_amount=line_vat,
            line_total=line_total,
            matching_status=item_status,
            match_issue="; ".join(item_issues) or None,
        ))
        invoice_issues.extend(item_issues)
        subtotal += line_subtotal
        vat_total += line_vat
        total += line_total

    invoice.subtotal = money(subtotal)
    invoice.vat_amount = money(vat_total)
    invoice.total = money(total)
    invoice.matching_status = (
        "quantity_mismatch" if has_quantity_mismatch
        else "amount_mismatch" if has_amount_mismatch
        else "matched"
    )
    invoice.match_issues = json.dumps(invoice_issues, ensure_ascii=False)
    await db.flush()
    add_audit(db, current_user, "supplier_invoice.created", "supplier_invoice", invoice.id, {
        "internal_invoice_number": internal_number,
        "matching_status": invoice.matching_status,
        "total": invoice.total,
        "duplicate_check": duplicate_check["confidence"] if duplicate_check["is_duplicate"] else "clean",
    })
    invoice = await load_invoice(db, invoice.id, current_user.company_id)
    return ResponseBase(data=build_invoice_response(invoice))


@router.get("/supplier-invoices/{invoice_id}", response_model=ResponseBase[SupplierInvoiceResponse])
async def get_supplier_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = await load_invoice(db, invoice_id, current_user.company_id)
    return ResponseBase(data=build_invoice_response(invoice))


@router.patch("/supplier-invoices/{invoice_id}/status", response_model=ResponseBase[SupplierInvoiceResponse])
async def change_supplier_invoice_status(
    invoice_id: UUID,
    data: SupplierInvoiceStatusChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("supplier-finance", "can_edit")),
):
    invoice = await load_invoice(db, invoice_id, current_user.company_id, for_update=True)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail="მხოლოდ draft Supplier Invoice-ის სტატუსი შეიძლება შეიცვალოს")
    if data.status == "approved" and invoice.matching_status != "matched":
        raise HTTPException(status_code=409, detail="Mismatch-ის მქონე Supplier Invoice ვერ დამტკიცდება")

    invoice.status = data.status
    if data.status == "approved":
        invoice.approved_by = current_user.id
        invoice.approved_at = utc_now()
        db.add(SupplierPayable(
            company_id=current_user.company_id,
            supplier_id=invoice.supplier_id,
            supplier_invoice_id=invoice.id,
            due_date=invoice.due_date,
            original_amount=invoice.total,
            paid_amount=Decimal("0"),
            credited_amount=Decimal("0"),
            overpaid_amount=Decimal("0"),
            outstanding_amount=invoice.total,
            currency_code="GEL",
            exchange_rate=Decimal("1"),
            status="unpaid",
        ))
    await db.flush()
    add_audit(db, current_user, f"supplier_invoice.{data.status}", "supplier_invoice", invoice.id, {
        "status": data.status, "notes": data.notes,
    })
    if data.status == "approved":
        await post_supplier_invoice_gl(
            db, current_user.company_id, current_user,
            invoice_id=invoice.id,
            internal_invoice_number=invoice.internal_invoice_number,
            invoice_date=invoice.invoice_date,
            total=invoice.total,
            vat_amount=invoice.vat_amount,
            subtotal=invoice.subtotal,
        )
    invoice = await refresh_invoice_graph(db, invoice)
    return ResponseBase(data=build_invoice_response(invoice))


# ── Payable endpoints ──────────────────────────────────────────────────────

@router.get("/supplier-payables/", response_model=ResponseBase[PaginatedResponse[SupplierPayableResponse]])
async def list_supplier_payables(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    supplier_id: UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [SupplierPayable.company_id == current_user.company_id]
    if supplier_id:
        filters.append(SupplierPayable.supplier_id == supplier_id)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(
            SupplierPayable.supplier.has(Supplier.name.ilike(term)),
            SupplierPayable.supplier_invoice.has(or_(
                SupplierInvoice.internal_invoice_number.ilike(term),
                SupplierInvoice.supplier_invoice_number.ilike(term),
            )),
        ))
    payables = (
        await db.execute(
            select(SupplierPayable)
            .where(*filters)
            .options(*PAYABLE_OPTIONS)
            .order_by(SupplierPayable.due_date, SupplierPayable.created_at)
        )
    ).unique().scalars().all()
    responses = [build_payable_response(payable) for payable in payables]
    if status:
        responses = [payable for payable in responses if payable.status == status]
    total = len(responses)
    start = (page - 1) * page_size
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size, items=responses[start:start + page_size]
    ))


@router.get("/supplier-payables/{payable_id}", response_model=ResponseBase[SupplierPayableResponse])
async def get_supplier_payable(
    payable_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payable = await load_payable(db, payable_id, current_user.company_id)
    return ResponseBase(data=build_payable_response(payable))


# ── Payment endpoints (with partial payment + overpayment support) ─────────

@router.post("/supplier-payables/{payable_id}/payments", response_model=ResponseBase[SupplierPayableResponse])
async def post_supplier_payment(
    payable_id: UUID,
    data: SupplierPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {User.Role.ADMIN, User.Role.ACCOUNTANT}:
        raise HTTPException(status_code=403, detail="მომწოდებლის გადახდის უფლება არ გაქვთ")

    idempotency_key = data.idempotency_key.strip()
    existing = (
        await db.execute(select(SupplierPayment).where(
            SupplierPayment.company_id == current_user.company_id,
            SupplierPayment.idempotency_key == idempotency_key,
        ))
    ).scalar_one_or_none()
    if existing:
        if existing.supplier_payable_id != payable_id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა გადახდაზე უკვე გამოყენებულია")
        payable = await load_payable(db, payable_id, current_user.company_id)
        return ResponseBase(data=build_payable_response(payable))

    payable = await load_payable(db, payable_id, current_user.company_id, for_update=True)
    existing = (
        await db.execute(select(SupplierPayment).where(
            SupplierPayment.company_id == current_user.company_id,
            SupplierPayment.idempotency_key == idempotency_key,
        ))
    ).scalar_one_or_none()
    if existing:
        if existing.supplier_payable_id != payable_id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა გადახდაზე უკვე გამოყენებულია")
        payable = await load_payable(db, payable_id, current_user.company_id)
        return ResponseBase(data=build_payable_response(payable))

    # ── Partial payment: allow payment less than outstanding ────────────
    # ── Overpayment: allow payment exceeding outstanding if flag set ────
    if payable.status == "paid" and payable.outstanding_amount <= 0 and payable.overpaid_amount <= 0:
        raise HTTPException(status_code=409, detail="დავალიანება უკვე სრულად გადახდილია")

    if data.amount > payable.outstanding_amount and not data.allow_overpayment:
        raise HTTPException(status_code=409, detail="გადახდა დარჩენილ დავალიანებას აჭარბებს. გამოიყენეთ allow_overpayment=true თუ გსურთ ზედმეტად გადახდა")

    payment_amount = money(data.amount)
    payment = SupplierPayment(
        company_id=current_user.company_id,
        supplier_payable_id=payable.id,
        idempotency_key=idempotency_key,
        amount=payment_amount,
        payment_date=data.payment_date,
        payment_method=data.payment_method,
        reference=data.reference,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(payment)

    # Calculate how much goes to outstanding vs overpayment
    if payment_amount <= payable.outstanding_amount:
        # Normal or partial payment
        payable.paid_amount = money(Decimal(payable.paid_amount) + payment_amount)
        payable.outstanding_amount = money(
            Decimal(payable.original_amount) - payable.paid_amount - Decimal(payable.credited_amount)
        )
    else:
        # Overpayment: pay off outstanding, remainder goes to overpayment
        overpayment_amount = payment_amount - payable.outstanding_amount
        payable.paid_amount = money(Decimal(payable.paid_amount) + Decimal(payable.outstanding_amount))
        payable.outstanding_amount = Decimal("0")
        payable.overpaid_amount = money(Decimal(payable.overpaid_amount) + overpayment_amount)

        # Create overpayment record
        db.add(SupplierOverpayment(
            company_id=current_user.company_id,
            supplier_id=payable.supplier_id,
            supplier_payable_id=payable.id,
            idempotency_key=f"overpayment_{idempotency_key}",
            amount=overpayment_amount,
            remaining_amount=overpayment_amount,
            currency_code=data.currency_code or payable.currency_code,
            exchange_rate=Decimal("1"),
            notes=f"Overpayment from payment {data.reference or idempotency_key}",
            created_by=current_user.id,
        ))

    payable.status = "paid" if payable.outstanding_amount == 0 else "partially_paid"
    if payable.overpaid_amount > 0:
        payable.status = "overpaid"

    await db.flush()
    add_audit(db, current_user, "supplier_payment.posted", "supplier_payment", payment.id, {
        "supplier_payable_id": payable.id,
        "amount": payment.amount,
        "outstanding_amount": payable.outstanding_amount,
        "overpaid_amount": payable.overpaid_amount,
        "is_partial": payment_amount < Decimal(payable.original_amount),
        "is_overpayment": payment_amount > Decimal(payable.original_amount) - Decimal(payable.paid_amount) + payment_amount,
    })
    await post_supplier_payment_gl(
        db, current_user.company_id, current_user,
        payment_id=payment.id,
        payable_id=payable.id,
        internal_invoice_number=payable.supplier_invoice.internal_invoice_number,
        payment_date=payment.payment_date,
        amount=payment.amount,
    )
    payable = await refresh_payable_graph(db, payable)
    return ResponseBase(data=build_payable_response(payable))


# ── Credit note endpoints (with currency difference support) ────────────────

@router.post(
    "/supplier-payables/{payable_id}/credit-notes",
    response_model=ResponseBase[SupplierPayableResponse],
)
async def post_supplier_credit_note(
    payable_id: UUID,
    data: SupplierCreditNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "accountant"}:
        raise HTTPException(status_code=403, detail="Credit Note-ის შექმნის უფლება არ გაქვთ")

    idempotency_key = data.idempotency_key.strip()
    existing = (
        await db.execute(select(SupplierCreditNote).where(
            SupplierCreditNote.company_id == current_user.company_id,
            SupplierCreditNote.idempotency_key == idempotency_key,
        ))
    ).scalar_one_or_none()
    if existing:
        if existing.supplier_payable_id != payable_id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა Credit Note-ზე უკვე გამოყენებულია")
        payable = await load_payable(db, payable_id, current_user.company_id)
        return ResponseBase(data=build_payable_response(payable))

    payable = await load_payable(db, payable_id, current_user.company_id, for_update=True)
    existing = (
        await db.execute(select(SupplierCreditNote).where(
            SupplierCreditNote.company_id == current_user.company_id,
            SupplierCreditNote.idempotency_key == idempotency_key,
        ))
    ).scalar_one_or_none()
    if existing:
        if existing.supplier_payable_id != payable_id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა Credit Note-ზე უკვე გამოყენებულია")
        payable = await refresh_payable_graph(db, payable)
        return ResponseBase(data=build_payable_response(payable))

    duplicate_number = (
        await db.execute(select(SupplierCreditNote.id).where(
            SupplierCreditNote.company_id == current_user.company_id,
            SupplierCreditNote.supplier_id == payable.supplier_id,
            SupplierCreditNote.supplier_credit_note_number == data.supplier_credit_note_number.strip(),
        ).limit(1))
    ).scalars().first()
    if duplicate_number:
        raise HTTPException(status_code=409, detail="მომწოდებლის ამ ნომრით Credit Note უკვე არსებობს")

    # ── Currency difference handling ─────────────────────────────────────
    credit_note_currency = (data.currency_code or payable.currency_code).upper()
    exchange_rate = data.exchange_rate or Decimal("1")
    amount_in_credit_currency = money(data.amount)

    if credit_note_currency != payable.currency_code:
        # Convert credit note amount to payable currency
        amount_in_payable_currency = money(amount_in_credit_currency * exchange_rate)
        currency_difference = amount_in_payable_currency - amount_in_credit_currency

        if amount_in_payable_currency > payable.outstanding_amount:
            raise HTTPException(
                status_code=409,
                detail=f"Credit Note ({amount_in_payable_currency} {payable.currency_code}) დარჩენილ დავალიანებას ({payable.outstanding_amount} {payable.currency_code}) აჭარბებს",
            )

        credit = SupplierCreditNote(
            company_id=current_user.company_id,
            supplier_id=payable.supplier_id,
            supplier_payable_id=payable.id,
            supplier_invoice_id=payable.supplier_invoice_id,
            idempotency_key=idempotency_key,
            supplier_credit_note_number=data.supplier_credit_note_number.strip(),
            amount=amount_in_payable_currency,
            credit_date=data.credit_date,
            reason=data.reason.strip(),
            created_by=current_user.id,
        )
        db.add(credit)
        await db.flush()

        # Record currency difference
        db.add(SupplierCreditNoteCurrencyDiff(
            company_id=current_user.company_id,
            credit_note_id=credit.id,
            payable_currency=payable.currency_code,
            credit_note_currency=credit_note_currency,
            exchange_rate=exchange_rate,
            amount_in_payable_currency=amount_in_payable_currency,
            amount_in_credit_note_currency=amount_in_credit_currency,
            currency_difference=currency_difference,
        ))

        payable.credited_amount = money(Decimal(payable.credited_amount) + amount_in_payable_currency)
    else:
        if data.amount > payable.outstanding_amount:
            raise HTTPException(status_code=409, detail="Credit Note დარჩენილ დავალიანებას აჭარბებს")

        credit = SupplierCreditNote(
            company_id=current_user.company_id,
            supplier_id=payable.supplier_id,
            supplier_payable_id=payable.id,
            supplier_invoice_id=payable.supplier_invoice_id,
            idempotency_key=idempotency_key,
            supplier_credit_note_number=data.supplier_credit_note_number.strip(),
            amount=money(data.amount),
            credit_date=data.credit_date,
            reason=data.reason.strip(),
            created_by=current_user.id,
        )
        db.add(credit)
        await db.flush()
        payable.credited_amount = money(Decimal(payable.credited_amount) + data.amount)

    payable.outstanding_amount = money(
        Decimal(payable.original_amount) - Decimal(payable.paid_amount) - payable.credited_amount
    )
    payable.status = "paid" if payable.outstanding_amount == 0 else (
        "overpaid" if payable.overpaid_amount > 0 else (
            "partially_paid" if payable.paid_amount > 0 else "unpaid"
        )
    )
    await db.flush()
    add_audit(db, current_user, "supplier_credit_note.posted", "supplier_credit_note", credit.id, {
        "supplier_payable_id": payable.id,
        "amount": credit.amount,
        "outstanding_amount": payable.outstanding_amount,
        "currency_diff": credit_note_currency != payable.currency_code,
    })
    await post_supplier_credit_note_gl(
        db, current_user.company_id, current_user,
        credit_note_id=credit.id,
        payable_id=payable.id,
        internal_invoice_number=payable.supplier_invoice.internal_invoice_number,
        credit_date=credit.credit_date,
        amount=credit.amount,
    )
    payable = await refresh_payable_graph(db, payable)
    return ResponseBase(data=build_payable_response(payable))


# ── Payment reversal ────────────────────────────────────────────────────────

@router.post(
    "/supplier-payments/{payment_id}/reversal",
    response_model=ResponseBase[SupplierPayableResponse],
)
async def reverse_supplier_payment(
    payment_id: UUID,
    data: SupplierPaymentReversalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {"admin", "accountant"}:
        raise HTTPException(status_code=403, detail="გადახდის გაუქმების უფლება არ გაქვთ")

    idempotency_key = data.idempotency_key.strip()
    existing = (
        await db.execute(select(SupplierPaymentReversal).where(
            SupplierPaymentReversal.company_id == current_user.company_id,
            SupplierPaymentReversal.idempotency_key == idempotency_key,
        ))
    ).scalar_one_or_none()
    if existing:
        if existing.supplier_payment_id != payment_id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა reversal-ზე უკვე გამოყენებულია")
        payable = await load_payable(db, existing.supplier_payable_id, current_user.company_id)
        return ResponseBase(data=build_payable_response(payable))

    payment = (
        await db.execute(
            select(SupplierPayment).where(
                SupplierPayment.id == payment_id,
                SupplierPayment.company_id == current_user.company_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="მომწოდებლის გადახდა არ მოიძებნა")

    payable = await load_payable(
        db, payment.supplier_payable_id, current_user.company_id, for_update=True
    )
    existing_for_payment = (
        await db.execute(select(SupplierPaymentReversal).where(
            SupplierPaymentReversal.supplier_payment_id == payment.id
        ))
    ).scalar_one_or_none()
    if existing_for_payment:
        if existing_for_payment.idempotency_key == idempotency_key:
            payable = await refresh_payable_graph(db, payable)
            return ResponseBase(data=build_payable_response(payable))
        raise HTTPException(status_code=409, detail="ეს გადახდა უკვე გაუქმებულია")

    reversal = SupplierPaymentReversal(
        company_id=current_user.company_id,
        supplier_payment_id=payment.id,
        supplier_payable_id=payable.id,
        idempotency_key=idempotency_key,
        amount=payment.amount,
        reason=data.reason.strip(),
        created_by=current_user.id,
    )
    db.add(reversal)

    # Handle reversal of overpayment
    if payable.overpaid_amount > 0 and payment.amount > payable.paid_amount:
        # This payment was an overpayment — reduce overpaid amount
        overpayment_reduction = payment.amount - Decimal(payable.paid_amount)
        payable.overpaid_amount = money(Decimal(payable.overpaid_amount) - overpayment_reduction)
        payable.paid_amount = Decimal("0")
    else:
        payable.paid_amount = money(Decimal(payable.paid_amount) - Decimal(payment.amount))

    payable.outstanding_amount = money(
        Decimal(payable.original_amount) - payable.paid_amount - Decimal(payable.credited_amount)
    )
    payable.status = "paid" if payable.outstanding_amount == 0 else (
        "overpaid" if payable.overpaid_amount > 0 else (
            "partially_paid" if payable.paid_amount > 0 else "unpaid"
        )
    )
    await db.flush()
    add_audit(db, current_user, "supplier_payment.reversed", "supplier_payment", payment.id, {
        "supplier_payable_id": payable.id,
        "reversal_id": reversal.id,
        "amount": reversal.amount,
        "reason": reversal.reason,
        "outstanding_amount": payable.outstanding_amount,
    })
    await post_supplier_payment_reversal_gl(
        db, current_user.company_id, current_user,
        reversal_id=reversal.id,
        payment_id=payment.id,
        internal_invoice_number=payable.supplier_invoice.internal_invoice_number,
        reversal_date=date.today(),
        amount=reversal.amount,
    )
    payable = await refresh_payable_graph(db, payable)
    return ResponseBase(data=build_payable_response(payable))


# ── Duplicate invoice check endpoint ────────────────────────────────────────

@router.post("/supplier-invoices/check-duplicate", response_model=ResponseBase[DuplicateInvoiceResult])
async def check_duplicate_invoice_endpoint(
    data: DuplicateInvoiceCheck,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await check_duplicate_invoice(
        db, current_user.company_id, data.supplier_id,
        data.supplier_invoice_number, data.invoice_date, data.total,
    )
    return ResponseBase(data=DuplicateInvoiceResult(**result))


# ── Tolerance settings endpoints ───────────────────────────────────────────

@router.get("/supplier-invoice-tolerances/", response_model=ResponseBase[SupplierInvoiceToleranceResponse])
async def get_supplier_invoice_tolerances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tolerance = await get_tolerance(db, current_user.company_id)
    return ResponseBase(data=SupplierInvoiceToleranceResponse(
        id=tolerance.id,
        quantity_tolerance_percent=float(tolerance.quantity_tolerance_percent),
        price_tolerance_percent=float(tolerance.price_tolerance_percent),
        amount_tolerance=float(tolerance.amount_tolerance),
        enable_duplicate_detection=tolerance.enable_duplicate_detection,
        duplicate_lookback_days=tolerance.duplicate_lookback_days,
        created_at=tolerance.created_at,
        updated_at=tolerance.updated_at,
    ))


@router.put("/supplier-invoice-tolerances/", response_model=ResponseBase[SupplierInvoiceToleranceResponse])
async def update_supplier_invoice_tolerances(
    data: SupplierInvoiceToleranceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("supplier-finance", "can_edit")),
):
    tolerance = await get_tolerance(db, current_user.company_id)
    tolerance.quantity_tolerance_percent = data.quantity_tolerance_percent
    tolerance.price_tolerance_percent = data.price_tolerance_percent
    tolerance.amount_tolerance = data.amount_tolerance
    tolerance.enable_duplicate_detection = data.enable_duplicate_detection
    tolerance.duplicate_lookback_days = data.duplicate_lookback_days
    tolerance.updated_by = current_user.id
    await db.flush()
    await db.refresh(tolerance)
    add_audit(db, current_user, "supplier_invoice_tolerance.updated", "supplier_invoice_tolerance", tolerance.id, {
        "quantity_tolerance_percent": float(tolerance.quantity_tolerance_percent),
        "price_tolerance_percent": float(tolerance.price_tolerance_percent),
        "amount_tolerance": float(tolerance.amount_tolerance),
        "enable_duplicate_detection": tolerance.enable_duplicate_detection,
        "duplicate_lookback_days": tolerance.duplicate_lookback_days,
    })
    return ResponseBase(data=SupplierInvoiceToleranceResponse(
        id=tolerance.id,
        quantity_tolerance_percent=float(tolerance.quantity_tolerance_percent),
        price_tolerance_percent=float(tolerance.price_tolerance_percent),
        amount_tolerance=float(tolerance.amount_tolerance),
        enable_duplicate_detection=tolerance.enable_duplicate_detection,
        duplicate_lookback_days=tolerance.duplicate_lookback_days,
        created_at=tolerance.created_at,
        updated_at=tolerance.updated_at,
    ))


# ── Overpayment application endpoint ────────────────────────────────────────

@router.post("/supplier-overpayments/apply", response_model=ResponseBase[SupplierPayableResponse])
async def apply_overpayment(
    data: OverpaymentApplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply an overpayment from one payable to another payable."""
    overpayment = (
        await db.execute(
            select(SupplierOverpayment).where(
                SupplierOverpayment.id == data.overpayment_id,
                SupplierOverpayment.company_id == current_user.company_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not overpayment:
        raise HTTPException(status_code=404, detail="Overpayment არ მოიძებნა")
    if overpayment.remaining_amount <= 0:
        raise HTTPException(status_code=409, detail="Overpayment უკვე სრულად გამოყენებულია")

    target_payable = await load_payable(
        db, data.payable_id, current_user.company_id, for_update=True
    )
    if target_payable.supplier_id != overpayment.supplier_id:
        raise HTTPException(status_code=409, detail="Overpayment-ის გამოყენება შესაძლებელია მხოლოდ იმავე მომწოდებლის დავალიანებაზე")

    apply_amount = min(data.amount, overpayment.remaining_amount, target_payable.outstanding_amount)
    if apply_amount <= 0:
        raise HTTPException(status_code=409, detail="გამოსაყენებელი თანხა უნდა იყოს 0-ზე მეტი")

    # Apply to target payable
    target_payable.paid_amount = money(Decimal(target_payable.paid_amount) + apply_amount)
    target_payable.outstanding_amount = money(
        Decimal(target_payable.original_amount) - target_payable.paid_amount - Decimal(target_payable.credited_amount)
    )
    target_payable.status = "paid" if target_payable.outstanding_amount == 0 else "partially_paid"

    # Reduce overpayment remaining
    overpayment.remaining_amount = money(Decimal(overpayment.remaining_amount) - apply_amount)

    await db.flush()
    add_audit(db, current_user, "overpayment.applied", "supplier_overpayment", overpayment.id, {
        "from_overpayment_id": overpayment.id,
        "to_payable_id": target_payable.id,
        "amount": apply_amount,
        "remaining": overpayment.remaining_amount,
        "notes": data.notes,
    })
    target_payable = await refresh_payable_graph(db, target_payable)
    return ResponseBase(data=build_payable_response(target_payable))


# ── Overpayment list endpoint ────────────────────────────────────────────────

@router.get("/supplier-overpayments/", response_model=ResponseBase[list[SupplierOverpaymentResponse]])
async def list_supplier_overpayments(
    supplier_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [SupplierOverpayment.company_id == current_user.company_id]
    if supplier_id:
        filters.append(SupplierOverpayment.supplier_id == supplier_id)
    overpayments = (
        await db.execute(
            select(SupplierOverpayment)
            .where(*filters)
            .where(SupplierOverpayment.remaining_amount > 0)
            .order_by(SupplierOverpayment.created_at.desc())
        )
    ).scalars().all()
    return ResponseBase(data=[
        SupplierOverpaymentResponse(
            id=op.id,
            amount=float(op.amount),
            remaining_amount=float(op.remaining_amount),
            currency_code=op.currency_code,
            exchange_rate=float(op.exchange_rate),
            notes=op.notes,
            created_at=op.created_at,
        )
        for op in overpayments
    ])
