"""Tenant-scoped immutable customer invoice endpoints."""

import io
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit, allocate_document_number
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.invoice import Invoice, InvoiceItem
from app.models.receivable import CustomerReceivable
from app.models.order import Order
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.invoice import (
    InvoiceGenerate,
    InvoiceDraftUpdate,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
)
from app.services.gl_hooks import post_invoice_gl
from app.utils.invoice_exports import generate_invoice_docx, generate_invoice_xlsx
from app.utils.pdf import generate_invoice_pdf

router = APIRouter(prefix="/invoices", tags=["ინვოისები"])

INVOICEABLE_ORDER_STATUSES = {"confirmed", "preparing", "shipping", "completed"}
# Cancelled orders cannot be invoiced
NON_INVOICEABLE_STATUSES = {"cancelled", "draft"}


def money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def quantity(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def require_issued_export(invoice: Invoice) -> None:
    if invoice.status != "issued":
        raise HTTPException(status_code=409, detail="ჩამოტვირთვამდე Draft Invoice უნდა დაადასტუროთ")


def item_response(item: InvoiceItem) -> InvoiceItemResponse:
    return InvoiceItemResponse(
        id=item.id,
        order_item_id=item.order_item_id,
        product_id=item.product_id,
        line_number=item.line_number,
        product_name=item.product_name,
        quantity=float(item.quantity),
        unit_price=float(item.unit_price),
        discount_percent=float(item.discount_percent),
        line_subtotal=float(item.line_subtotal),
        vat_rate=float(item.vat_rate),
        vat_amount=float(item.vat_amount),
        line_total=float(item.line_total),
    )


def invoice_response(invoice: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=invoice.id,
        company_id=invoice.company_id,
        client_id=invoice.client_id,
        order_id=invoice.order_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        currency=invoice.currency,
        subtotal=float(invoice.subtotal),
        vat_amount=float(invoice.vat_amount),
        total=float(invoice.total),
        order_number=invoice.order_number,
        seller_name=invoice.seller_name,
        seller_identification_code=invoice.seller_identification_code,
        seller_address=invoice.seller_address,
        seller_phone=invoice.seller_phone,
        seller_email=invoice.seller_email,
        client_name=invoice.client_name,
        client_identification_code=invoice.client_identification_code,
        client_address=invoice.client_address,
        notes=invoice.notes,
        download_url=f"/api/v1/invoices/{invoice.id}/download",
        items=[item_response(item) for item in invoice.items],
        created_at=invoice.created_at,
        updated_at=invoice.updated_at,
    )


def invoice_audit_snapshot(invoice: Invoice) -> dict:
    """Serializable editable document version stored in the immutable audit log."""
    return {
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "currency": invoice.currency,
        "seller": {
            "name": invoice.seller_name,
            "identification_code": invoice.seller_identification_code,
            "address": invoice.seller_address,
            "phone": invoice.seller_phone,
            "email": invoice.seller_email,
        },
        "client": {
            "name": invoice.client_name,
            "identification_code": invoice.client_identification_code,
            "address": invoice.client_address,
        },
        "notes": invoice.notes,
        "subtotal": invoice.subtotal,
        "vat_amount": invoice.vat_amount,
        "total": invoice.total,
        "items": [
            {
                "line_number": item.line_number,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_percent": item.discount_percent,
                "vat_rate": item.vat_rate,
                "line_subtotal": item.line_subtotal,
                "vat_amount": item.vat_amount,
                "line_total": item.line_total,
            }
            for item in invoice.items
        ],
    }


def invoice_list_response(invoice: Invoice) -> InvoiceListResponse:
    return InvoiceListResponse(
        id=invoice.id,
        order_id=invoice.order_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        currency=invoice.currency,
        total=float(invoice.total),
        order_number=invoice.order_number,
        client_name=invoice.client_name,
        client_identification_code=invoice.client_identification_code,
        download_url=f"/api/v1/invoices/{invoice.id}/download",
        created_at=invoice.created_at,
    )


def render_invoice_pdf(invoice: Invoice) -> bytes:
    """Render the persisted immutable invoice snapshot as the canonical PDF."""
    return generate_invoice_pdf(
        invoice_number=invoice.invoice_number,
        order_number=invoice.order_number,
        company_name=invoice.seller_name,
        company_id_code=invoice.seller_identification_code,
        company_address=invoice.seller_address,
        company_phone=invoice.seller_phone,
        client_name=invoice.client_name,
        client_id_code=invoice.client_identification_code,
        client_address=invoice.client_address,
        items=[{
            "product_name": item.product_name,
            "quantity": float(item.quantity),
            "unit_price": float(item.unit_price),
            "discount_percent": float(item.discount_percent),
            "vat_rate": float(item.vat_rate),
            "total": float(item.line_total),
        } for item in invoice.items],
        subtotal=float(invoice.subtotal),
        vat_amount=float(invoice.vat_amount),
        total=float(invoice.total),
        created_at=invoice.invoice_date,
        due_date=invoice.due_date,
    )


async def load_invoice(db: AsyncSession, invoice_id: UUID, company_id: UUID) -> Invoice:
    invoice = (
        await db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.company_id == company_id)
            .options(selectinload(Invoice.items))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="ინვოისი არ მოიძებნა")
    return invoice


async def create_invoice_snapshot(
    db: AsyncSession,
    current_user: User,
    order: Order,
    *,
    idempotency_key: str,
    invoice_date: date,
    due_date: date,
    notes: str | None = None,
    issue: bool = True,
) -> Invoice:
    """Create an order snapshot as an editable draft or immediately issue it."""
    line_snapshots: list[dict] = []
    subtotal = Decimal("0")
    vat_amount = Decimal("0")
    vat_rate = Decimal("18.0000") if money(order.vat_amount) > 0 else Decimal("0.0000")
    for line_number, order_item in enumerate(order.items, start=1):
        line_quantity = quantity(order_item.quantity)
        unit_price = money(order_item.unit_price)
        discount_percent = Decimal(str(order_item.discount_percent or 0)).quantize(Decimal("0.0001"))
        gross = line_quantity * unit_price
        line_subtotal = money(gross * (Decimal("1") - discount_percent / Decimal("100")))
        line_vat = money(line_subtotal * vat_rate / Decimal("100"))
        line_total = money(line_subtotal + line_vat)
        subtotal += line_subtotal
        vat_amount += line_vat
        line_snapshots.append({
            "order_item_id": order_item.id,
            "product_id": order_item.product_id,
            "line_number": line_number,
            "product_name": order_item.product_name,
            "quantity": line_quantity,
            "unit_price": unit_price,
            "discount_percent": discount_percent,
            "line_subtotal": line_subtotal,
            "vat_rate": vat_rate,
            "vat_amount": line_vat,
            "line_total": line_total,
        })
    subtotal = money(subtotal)
    vat_amount = money(vat_amount)
    total = money(subtotal + vat_amount)
    invoice = Invoice(
        company_id=current_user.company_id,
        client_id=order.client_id,
        order_id=order.id,
        invoice_number=await allocate_document_number(
            db, current_user.company_id, "customer_invoice", "INV"
        ),
        idempotency_key=idempotency_key,
        status="issued" if issue else "draft",
        invoice_date=invoice_date,
        due_date=due_date,
        currency=order.company.currency or "GEL",
        subtotal=subtotal,
        vat_amount=vat_amount,
        total=total,
        order_number=order.order_number,
        seller_name=order.company.name,
        seller_identification_code=order.company.identification_code,
        seller_address=order.company.address or "",
        seller_phone=order.company.phone or "",
        seller_email=order.company.email or "",
        client_name=order.client.name,
        client_identification_code=order.client.identification_code,
        client_address=order.client.address or "",
        notes=notes,
        created_by=current_user.id,
    )
    db.add(invoice)
    await db.flush()
    for snapshot in line_snapshots:
        db.add(InvoiceItem(invoice_id=invoice.id, **snapshot))
    await db.flush()
    if not issue:
        add_audit(db, current_user, "customer_invoice.draft_created", "invoice", invoice.id, {
            "invoice_number": invoice.invoice_number,
            "order_id": order.id,
        })
        return await load_invoice(db, invoice.id, current_user.company_id)

    return await issue_invoice_snapshot(db, current_user, invoice)


async def issue_invoice_snapshot(
    db: AsyncSession,
    current_user: User,
    invoice: Invoice,
) -> Invoice:
    """Finalize one draft atomically; exact replays return the issued snapshot."""
    if invoice.status == "issued":
        return await load_invoice(db, invoice.id, current_user.company_id)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail="Invoice-ის დადასტურება ამ სტატუსში არ შეიძლება")

    existing_receivable = (
        await db.execute(
            select(CustomerReceivable).where(
                CustomerReceivable.company_id == current_user.company_id,
                CustomerReceivable.invoice_id == invoice.id,
            )
        )
    ).scalar_one_or_none()
    if existing_receivable:
        raise HTTPException(status_code=409, detail="Invoice-ს უკვე აქვს ფინანსური ჩანაწერი")

    invoice.status = "issued"
    receivable = CustomerReceivable(
        company_id=current_user.company_id,
        invoice_id=invoice.id,
        client_id=invoice.client_id,
        invoice_number=invoice.invoice_number,
        client_name=invoice.client_name,
        currency=invoice.currency,
        original_amount=invoice.total,
        paid_amount=Decimal("0"),
        credited_amount=Decimal("0"),
        outstanding_amount=invoice.total,
        due_date=invoice.due_date,
        status="overdue" if invoice.due_date < date.today() else "unpaid",
    )
    db.add(receivable)
    await db.flush()
    await post_invoice_gl(
        db, current_user.company_id, current_user,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        total=invoice.total,
        vat_amount=invoice.vat_amount,
        subtotal=invoice.subtotal,
    )
    add_audit(db, current_user, "customer_receivable.created", "customer_receivable", receivable.id, {
        "invoice_id": invoice.id,
        "client_id": invoice.client_id,
        "original_amount": invoice.total,
        "due_date": invoice.due_date,
    })
    add_audit(db, current_user, "customer_invoice.issued", "invoice", invoice.id, {
        "invoice_number": invoice.invoice_number,
        "order_id": invoice.order_id,
        "client_id": invoice.client_id,
        "total": invoice.total,
        "currency": invoice.currency,
    })
    await db.flush()
    return await load_invoice(db, invoice.id, current_user.company_id)


async def ensure_order_invoice_draft(
    db: AsyncSession,
    current_user: User,
    order: Order,
) -> Invoice:
    """Idempotently create one editable Invoice draft from an Order snapshot."""
    existing = (
        await db.execute(
            select(Invoice)
            .where(Invoice.company_id == current_user.company_id, Invoice.order_id == order.id)
            .options(selectinload(Invoice.items))
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    today = date.today()
    return await create_invoice_snapshot(
        db,
        current_user,
        order,
        idempotency_key=f"auto-draft:{order.id}",
        invoice_date=today,
        due_date=today + timedelta(days=14),
        notes="ავტომატურად შექმნილია შეკვეთიდან",
        issue=False,
    )


async def ensure_completed_order_invoice(
    db: AsyncSession,
    current_user: User,
    order: Order,
) -> Invoice:
    """Keep completion idempotent without bypassing the editable Draft workflow."""
    return await ensure_order_invoice_draft(db, current_user, order)


@router.post("/generate", response_model=ResponseBase[InvoiceResponse])
async def generate_invoice(
    data: InvoiceGenerate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_create")),
):
    idempotency_key = data.idempotency_key.strip()
    existing_key = (
        await db.execute(
            select(Invoice)
            .where(
                Invoice.company_id == current_user.company_id,
                Invoice.idempotency_key == idempotency_key,
            )
            .options(selectinload(Invoice.items))
        )
    ).scalar_one_or_none()
    if existing_key:
        if existing_key.order_id != data.order_id:
            raise HTTPException(status_code=409, detail="idempotency key სხვა ინვოისზე უკვე გამოყენებულია")
        return ResponseBase(data=invoice_response(existing_key))

    order = (
        await db.execute(
            select(Order)
            .where(Order.id == data.order_id, Order.company_id == current_user.company_id)
            .options(
                selectinload(Order.company),
                selectinload(Order.client),
                selectinload(Order.items),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")
    if order.status not in INVOICEABLE_ORDER_STATUSES:
        raise HTTPException(status_code=409, detail="ინვოისი მხოლოდ დადასტურებული ან შესრულების პროცესში მყოფი შეკვეთიდან შეიძლება შეიქმნას")
    if not order.items:
        raise HTTPException(status_code=409, detail="შეკვეთას პროდუქტის ხაზები არ აქვს")

    existing_order = (
        await db.execute(
            select(Invoice)
            .where(Invoice.company_id == current_user.company_id, Invoice.order_id == order.id)
            .options(selectinload(Invoice.items))
        )
    ).scalar_one_or_none()
    if existing_order:
        if existing_order.status == "draft":
            existing_order.invoice_date = data.invoice_date
            existing_order.due_date = data.due_date
            existing_order.notes = data.notes
            existing_order.idempotency_key = idempotency_key
            issued = await issue_invoice_snapshot(db, current_user, existing_order)
            return ResponseBase(data=invoice_response(issued))
        raise HTTPException(status_code=409, detail="ამ შეკვეთაზე ინვოისი უკვე არსებობს")

    invoice = await create_invoice_snapshot(
        db,
        current_user,
        order,
        idempotency_key=idempotency_key,
        invoice_date=data.invoice_date,
        due_date=data.due_date,
        notes=data.notes,
    )
    return ResponseBase(data=invoice_response(invoice))


@router.post("/{invoice_id}/issue", response_model=ResponseBase[InvoiceResponse])
async def issue_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_approve")),
):
    invoice = (
        await db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.company_id == current_user.company_id)
            .options(selectinload(Invoice.items))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="ინვოისი არ მოიძებნა")
    issued = await issue_invoice_snapshot(db, current_user, invoice)
    # Notify the company owner/admin about the issued invoice
    try:
        from app.models.notification import Notification
        owner_result = await db.execute(
            select(User).where(User.company_id == current_user.company_id, User.role.in_(["admin", "owner"]))
        )
        for u in owner_result.scalars().all():
            db.add(Notification(
                company_id=current_user.company_id,
                user_id=u.id,
                type="invoice",
                title=f"ინვოისი {invoice.invoice_number} დადასტურდა",
                message=f"თანხა: {invoice.total} {invoice.currency}",
                link=f"/invoices/{invoice.id}",
            ))
        await db.flush()
    except Exception:
        pass  # non-blocking
    # Refresh materialized views in a SEPARATE transaction so a failure
    # (e.g. views missing in test DB) never aborts the invoice transaction.
    try:
        await db.commit()
        for view in ("mv_sales_daily", "mv_receivables_aging", "mv_stock_balances"):
            try:
                await db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            except Exception:
                pass
        await db.commit()
    except Exception:
        await db.rollback()
    return ResponseBase(data=invoice_response(issued), message="Invoice დადასტურებულია")


@router.patch("/{invoice_id}/draft", response_model=ResponseBase[InvoiceResponse])
async def update_invoice_draft(
    invoice_id: UUID,
    data: InvoiceDraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_edit")),
):
    invoice = (
        await db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.company_id == current_user.company_id)
            .options(selectinload(Invoice.items))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="ინვოისი არ მოიძებნა")
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail="მხოლოდ Draft Invoice-ის რედაქტირება შეიძლება")

    before_snapshot = invoice_audit_snapshot(invoice)
    invoice.invoice_date = data.invoice_date
    invoice.due_date = data.due_date
    invoice.currency = data.currency
    invoice.seller_name = data.seller_name
    invoice.seller_identification_code = data.seller_identification_code
    invoice.seller_address = data.seller_address
    invoice.seller_phone = data.seller_phone
    invoice.seller_email = data.seller_email
    invoice.client_name = data.client_name
    invoice.client_identification_code = data.client_identification_code
    invoice.client_address = data.client_address
    invoice.notes = data.notes

    await db.execute(delete(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id))
    subtotal = Decimal("0")
    vat_amount = Decimal("0")
    for line_number, item in enumerate(data.items, start=1):
        line_quantity = quantity(item.quantity)
        unit_price = money(item.unit_price)
        discount_percent = Decimal(item.discount_percent).quantize(Decimal("0.0001"))
        vat_rate = Decimal(item.vat_rate).quantize(Decimal("0.0001"))
        line_subtotal = money(line_quantity * unit_price * (Decimal("1") - discount_percent / Decimal("100")))
        line_vat = money(line_subtotal * vat_rate / Decimal("100"))
        line_total = money(line_subtotal + line_vat)
        subtotal += line_subtotal
        vat_amount += line_vat
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            line_number=line_number,
            product_name=item.product_name,
            quantity=line_quantity,
            unit_price=unit_price,
            discount_percent=discount_percent,
            line_subtotal=line_subtotal,
            vat_rate=vat_rate,
            vat_amount=line_vat,
            line_total=line_total,
        ))
    invoice.subtotal = money(subtotal)
    invoice.vat_amount = money(vat_amount)
    invoice.total = money(invoice.subtotal + invoice.vat_amount)
    await db.flush()
    updated_invoice = await load_invoice(db, invoice.id, current_user.company_id)
    add_audit(db, current_user, "customer_invoice.draft_updated", "invoice", invoice.id, {
        "invoice_number": invoice.invoice_number,
        "before": before_snapshot,
        "after": invoice_audit_snapshot(updated_invoice),
    })
    await db.flush()
    return ResponseBase(data=invoice_response(updated_invoice))


@router.get("/", response_model=ResponseBase[PaginatedResponse[InvoiceListResponse]])
async def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    client_id: UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    filters = [Invoice.company_id == current_user.company_id]
    if status:
        filters.append(Invoice.status == status)
    if client_id:
        filters.append(Invoice.client_id == client_id)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(
            Invoice.invoice_number.ilike(term),
            Invoice.order_number.ilike(term),
            Invoice.client_name.ilike(term),
            Invoice.client_identification_code.ilike(term),
        ))
    total = (await db.execute(select(func.count(Invoice.id)).where(*filters))).scalar_one()
    invoices = (
        await db.execute(
            select(Invoice)
            .where(*filters)
            .order_by(Invoice.invoice_date.desc(), Invoice.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[invoice_list_response(invoice) for invoice in invoices],
    ))


@router.get("/{invoice_id}", response_model=ResponseBase[InvoiceResponse])
async def get_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    return ResponseBase(data=invoice_response(await load_invoice(db, invoice_id, current_user.company_id)))


@router.get("/{invoice_id}/preview")
async def preview_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    invoice = await load_invoice(db, invoice_id, current_user.company_id)
    try:
        pdf_bytes = render_invoice_pdf(invoice)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF გენერაცია ვერ მოხერხდა: {exc}") from exc
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{invoice.invoice_number}.pdf"'},
    )


@router.get("/{invoice_id}/download")
async def download_invoice(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    invoice = await load_invoice(db, invoice_id, current_user.company_id)
    require_issued_export(invoice)
    try:
        pdf_bytes = render_invoice_pdf(invoice)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF გენერაცია ვერ მოხერხდა: {exc}") from exc
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.get("/{invoice_id}/download-word")
async def download_invoice_word(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    invoice = await load_invoice(db, invoice_id, current_user.company_id)
    require_issued_export(invoice)
    try:
        content = generate_invoice_docx(invoice)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Word გენერაცია ვერ მოხერხდა: {exc}") from exc
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.docx"'},
    )


@router.get("/{invoice_id}/download-excel")
async def download_invoice_excel(
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    invoice = await load_invoice(db, invoice_id, current_user.company_id)
    require_issued_export(invoice)
    try:
        content = generate_invoice_xlsx(invoice)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excel გენერაცია ვერ მოხერხდა: {exc}") from exc
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.xlsx"'},
    )
