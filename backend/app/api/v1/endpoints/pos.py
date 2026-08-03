"""Point of Sale API: sessions, orders, payments."""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.pos import POSSession, POSOrder, POSOrderItem
from app.models.product import Product
from app.schemas.common import ResponseBase
from app.schemas.pos import (
    POSSessionCreate, POSSessionResponse,
    POSOrderCreate, POSOrderResponse, POSOrderItemResponse,
)
from datetime import datetime

router = APIRouter(prefix="/pos", tags=["POS — სალარო"])


# ── Sessions ────────────────────────────────────────────────────────────────

@router.get("/sessions", response_model=ResponseBase[list[POSSessionResponse]])
async def list_sessions(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    filters = [POSSession.company_id == current_user.company_id]
    if status:
        filters.append(POSSession.status == status)
    rows = (await db.execute(
        select(POSSession).where(*filters).order_by(POSSession.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[POSSessionResponse.model_validate(s) for s in rows])


@router.post("/sessions", response_model=ResponseBase[POSSessionResponse], status_code=201)
async def open_session(
    data: POSSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    session = POSSession(
        company_id=current_user.company_id,
        name=data.name.strip(),
        opened_by=current_user.id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return ResponseBase(data=POSSessionResponse.model_validate(session))


@router.post("/sessions/{session_id}/close", response_model=ResponseBase[POSSessionResponse])
async def close_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_edit")),
):
    session = (await db.execute(
        select(POSSession).where(POSSession.id == session_id, POSSession.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="სესია არ მოიძებნა")
    if session.status != "open":
        raise HTTPException(status_code=409, detail="სესია უკვე დახურულია")
    session.status = "closed"
    session.closed_at = datetime.utcnow()
    await db.flush()
    await db.refresh(session)
    return ResponseBase(data=POSSessionResponse.model_validate(session))


# ── Orders ────────────────────────────────────────────────────────────────────

@router.get("/orders", response_model=ResponseBase[list[POSOrderResponse]])
async def list_pos_orders(
    session_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    filters = [POSOrder.company_id == current_user.company_id]
    if session_id:
        filters.append(POSOrder.session_id == session_id)
    rows = (await db.execute(
        select(POSOrder).where(*filters)
        .options(selectinload(POSOrder.items))
        .order_by(POSOrder.created_at.desc())
    )).unique().scalars().all()
    return ResponseBase(data=[POSOrderResponse.model_validate(o) for o in rows])


@router.post("/orders", response_model=ResponseBase[POSOrderResponse], status_code=201)
async def create_pos_order(
    data: POSOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    # Verify session
    session = (await db.execute(
        select(POSSession).where(POSSession.id == data.session_id, POSSession.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="სესია არ მოიძებნა")
    if session.status != "open":
        raise HTTPException(status_code=409, detail="სესია დახურულია, გაყიდვა შეუძლებელია")

    # Allocate order number
    today = datetime.utcnow()
    count = (await db.execute(
        select(func.count(POSOrder.id)).where(POSOrder.company_id == current_user.company_id)
    )).scalar()
    order_number = f"POS-{today.strftime('%y%m%d')}-{count + 1:04d}"

    subtotal = Decimal("0")
    items = []
    for item_data in data.items:
        product = (await db.execute(
            select(Product).where(Product.id == item_data.product_id, Product.company_id == current_user.company_id)
        )).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"პროდუქტი {item_data.product_id} არ მოიძებნა")
        qty = Decimal(str(item_data.quantity))
        price = Decimal(str(item_data.unit_price))
        line_total = (qty * price).quantize(Decimal("0.01"))
        subtotal += line_total
        items.append({
            "product_id": item_data.product_id,
            "product_name": product.name,
            "quantity": qty,
            "unit_price": price,
            "line_total": line_total,
        })

    vat = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
    total = subtotal + vat

    order = POSOrder(
        company_id=current_user.company_id,
        session_id=data.session_id,
        client_id=data.client_id,
        order_number=order_number,
        subtotal=subtotal,
        vat_amount=vat,
        total=total,
        payment_method=data.payment_method,
        payment_reference=data.payment_reference,
        created_by=current_user.id,
    )
    db.add(order)
    await db.flush()

    for item in items:
        db.add(POSOrderItem(pos_order_id=order.id, **item))
    await db.flush()

    # Update session totals
    session.total_orders += 1
    session.total_sales += total
    await db.flush()

    # Reload with items
    result = (await db.execute(
        select(POSOrder).where(POSOrder.id == order.id).options(selectinload(POSOrder.items))
    )).unique().scalar_one()
    return ResponseBase(data=POSOrderResponse.model_validate(result))
