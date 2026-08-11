"""Quotations API — CRUD, status workflow, convert-to-order."""
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation, QuotationItem
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.sales_tools import (
    QuotationCreate,
    QuotationItemResponse,
    QuotationResponse,
    QuotationStatusUpdate,
)

router = APIRouter(prefix="/quotations", tags=["კომერციული შემოთავაზებები"])


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_response(q: Quotation, client_name: str | None = None) -> QuotationResponse:
    return QuotationResponse(
        id=q.id, company_id=q.company_id, client_id=q.client_id, client_name=client_name,
        quotation_number=q.quotation_number, quotation_date=q.quotation_date,
        valid_until=q.valid_until, status=q.status, currency=q.currency,
        subtotal=float(q.subtotal), vat_amount=float(q.vat_amount), total=float(q.total),
        discount_percent=float(q.discount_percent), notes=q.notes, order_id=q.order_id,
        items=[QuotationItemResponse(
            id=i.id, product_id=i.product_id, line_number=i.line_number,
            description=i.description, quantity=float(i.quantity), unit_price=float(i.unit_price),
            discount_percent=float(i.discount_percent), line_total=float(i.line_total),
        ) for i in q.items],
        created_at=q.created_at, updated_at=q.updated_at,
    )


async def _load_quotation(db, company_id, quotation_id, for_update=False) -> Quotation:
    stmt = select(Quotation).options(selectinload(Quotation.items)).where(
        Quotation.id == quotation_id, Quotation.company_id == company_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    q = (await db.execute(stmt)).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="შემოთავაზება ვერ მოიძებნა")
    return q


@router.get("/", response_model=ResponseBase[PaginatedResponse[QuotationResponse]])
async def list_quotations(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [Quotation.company_id == current_user.company_id]
    if status:
        filters.append(Quotation.status == status)
    if client_id:
        filters.append(Quotation.client_id == client_id)
    total = (await db.execute(select(func.count(Quotation.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(Quotation).options(selectinload(Quotation.items), selectinload(Quotation.client))
            .where(*filters)
            .order_by(Quotation.quotation_date.desc(), Quotation.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_to_response(q, q.client.name if q.client else None) for q in rows],
    ))


@router.post("/", response_model=ResponseBase[QuotationResponse], status_code=201)
async def create_quotation(
    data: QuotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (
        await db.execute(select(Client).where(
            Client.id == data.client_id, Client.company_id == current_user.company_id,
        ))
    ).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="კლიენტი ვერ მოიძებნა")

    # Validate products belong to company when product_id given
    product_ids = [i.product_id for i in data.items if i.product_id]
    if product_ids:
        found = (await db.execute(select(Product.id).where(
            Product.company_id == current_user.company_id, Product.id.in_(product_ids),
        ))).scalars().all()
        if len(found) != len(set(product_ids)):
            raise HTTPException(status_code=400, detail="ერთი ან მეტი პროდუქტი ვერ მოიძებნა")

    prefix = f"QT-{data.quotation_date.strftime('%Y%m%d')}"
    same_day = (await db.execute(select(func.count(Quotation.id)).where(
        Quotation.company_id == current_user.company_id,
        Quotation.quotation_number.like(f"{prefix}-%"),
    ))).scalar_one()
    number = f"{prefix}-{same_day + 1:03d}"

    subtotal = sum(money(i.quantity * i.unit_price) for i in data.items)
    discount = money(subtotal * data.discount_percent / 100)
    vat = money((subtotal - discount) * Decimal("0.18"))
    total = money(subtotal - discount + vat)

    q = Quotation(
        company_id=current_user.company_id, client_id=data.client_id,
        quotation_number=number, quotation_date=data.quotation_date,
        valid_until=data.valid_until, status="draft", currency=data.currency,
        subtotal=subtotal, vat_amount=vat, total=total,
        discount_percent=data.discount_percent, notes=data.notes,
        created_by=current_user.id,
    )
    db.add(q)
    await db.flush()
    for idx, item in enumerate(data.items, start=1):
        line_total = money(money(item.quantity * item.unit_price) * (1 - item.discount_percent / 100))
        db.add(QuotationItem(
            quotation_id=q.id, product_id=item.product_id, line_number=idx,
            description=item.description, quantity=item.quantity, unit_price=item.unit_price,
            discount_percent=item.discount_percent, line_total=line_total,
        ))
    await db.commit()
    await db.refresh(q)

    add_audit(db, current_user, "quotation.created", "quotation", q.id, {"number": number})
    await db.commit()

    result = await _load_quotation(db, current_user.company_id, q.id)
    return ResponseBase(data=_to_response(result, client.name))


@router.get("/{quotation_id}", response_model=ResponseBase[QuotationResponse])
async def get_quotation(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _load_quotation(db, current_user.company_id, quotation_id)
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    return ResponseBase(data=_to_response(q, client.name if client else None))


@router.patch("/{quotation_id}/status", response_model=ResponseBase[QuotationResponse])
async def update_quotation_status(
    quotation_id: uuid.UUID,
    data: QuotationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    q.status = data.status
    add_audit(db, current_user, "quotation.status_changed", "quotation", q.id, {"status": data.status})
    await db.commit()
    await db.refresh(q)
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    return ResponseBase(data=_to_response(q, client.name if client else None))


@router.post("/{quotation_id}/convert", response_model=ResponseBase[dict])
async def convert_quotation_to_order(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert an accepted quotation into a sales order."""
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    if q.status != "accepted":
        raise HTTPException(status_code=400, detail="მხოლოდ accepted სტატუსის შემოთავაზების კონვერტაცია შეიძლება")
    if q.order_id:
        raise HTTPException(status_code=400, detail="შემოთავაზება უკვე კონვერტირებულია")

    from app.models.order import Order, OrderItem

    order = Order(
        company_id=current_user.company_id, client_id=q.client_id,
        order_number=f"ORD-{q.quotation_number}", status="confirmed",
        subtotal=float(q.subtotal - q.vat_amount), vat_amount=float(q.vat_amount),
        total=float(q.total), created_by=current_user.id,
    )
    db.add(order)
    await db.flush()
    for item in q.items:
        if item.product_id:
            db.add(OrderItem(
                order_id=order.id, product_id=item.product_id,
                product_name=item.description, quantity=float(item.quantity),
                unit_price=float(item.unit_price), discount_percent=float(item.discount_percent),
            ))
    q.order_id = order.id
    q.status = "converted"
    add_audit(db, current_user, "quotation.converted", "quotation", q.id, {"order_id": str(order.id)})
    await db.commit()
    return ResponseBase(data={"order_id": str(order.id), "order_number": order.order_number})


@router.delete("/{quotation_id}", response_model=ResponseBase)
async def delete_quotation(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _load_quotation(db, current_user.company_id, quotation_id)
    if q.status in ("accepted", "converted"):
        raise HTTPException(status_code=400, detail="accepted/converted შემოთავაზების წაშლა არ შეიძლება")
    await db.delete(q)
    add_audit(db, current_user, "quotation.deleted", "quotation", q.id, {})
    await db.commit()
    return ResponseBase(message="შემოთავაზება წაშლილია")
