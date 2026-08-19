"""Point of Sale API: sessions, orders, payments."""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.pos import POSSession, POSOrder, POSOrderItem
from app.models.pos import POSRefund, POSLoyaltyAccount, POSLoyaltyTransaction, POSOfflineQueue, POSFiscalDevice
from app.models.pos_extended import GiftCard, GiftCardTransaction, POSCashMovement, POSZReport
from app.models.product import Product
from app.schemas.common import ResponseBase
from app.core.time import utc_now
from app.schemas.pos import (
    POSSessionCreate, POSSessionResponse,
    POSOrderCreate, POSOrderResponse, POSOrderItemResponse,
)
from app.services.gl_posting import post_pos_sale, post_pos_refund
from datetime import date, datetime

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
    session.closed_at = utc_now()
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
    today = utc_now()
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

    # GL posting — every POS sale posts to the ledger (Odoo-style)
    await post_pos_sale(
        db, current_user.company_id, current_user,
        entry_date=utc_now().date(), reference_id=order.id,
        subtotal=subtotal, vat_amount=vat, total=total,
        payment_method=data.payment_method,
    )

    # Loyalty automation: earn 1 point per 1 GEL when a client is attached
    if data.client_id:
        account = (await db.execute(
            select(POSLoyaltyAccount).where(
                POSLoyaltyAccount.company_id == current_user.company_id,
                POSLoyaltyAccount.client_id == data.client_id,
            ).with_for_update()
        )).scalar_one_or_none()
        if not account:
            account = POSLoyaltyAccount(company_id=current_user.company_id, client_id=data.client_id)
            db.add(account)
            await db.flush()
        points = total.quantize(Decimal("0.01"))
        account.points += points
        account.total_earned += points
        db.add(POSLoyaltyTransaction(
            company_id=current_user.company_id, account_id=account.id, order_id=order.id,
            points=points, transaction_type="earn",
        ))
        await db.flush()

    # Reload with items
    result = (await db.execute(
        select(POSOrder).where(POSOrder.id == order.id).options(selectinload(POSOrder.items))
    )).unique().scalar_one()
    return ResponseBase(data=POSOrderResponse.model_validate(result))


# ── Refunds ───────────────────────────────────────────────────────────────────

@router.post("/orders/{order_id}/refund", response_model=ResponseBase[dict], status_code=201)
async def refund_pos_order(
    order_id: UUID,
    amount: Decimal = Query(..., gt=0),
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    company_id = current_user.company_id
    order = (await db.execute(
        select(POSOrder).where(POSOrder.id == order_id, POSOrder.company_id == company_id)
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")
    if order.status == "refunded":
        raise HTTPException(status_code=409, detail="შეკვეთა უკვე დაბრუნებულია")
    if amount > Decimal(order.total):
        raise HTTPException(status_code=409, detail="დაბრუნების თანხა აღემატება შეკვეთის ჯამს")

    count = (await db.execute(
        select(func.count(POSRefund.id)).where(POSRefund.company_id == company_id)
    )).scalar() or 0
    refund = POSRefund(
        company_id=company_id, order_id=order.id, session_id=order.session_id,
        refund_number=f"REF-{utc_now():%y%m%d}-{count + 1:04d}",
        amount=amount, reason=reason, created_by=current_user.id,
    )
    db.add(refund)
    order.status = "refunded" if amount >= Decimal(order.total) else "completed"
    await db.flush()

    # GL posting — refund reverses the sale (Odoo-style)
    refund_ratio = amount / Decimal(order.total) if order.total else Decimal("0")
    await post_pos_refund(
        db, current_user.company_id, current_user,
        entry_date=utc_now().date(), reference_id=refund.id,
        subtotal=(Decimal(order.subtotal) * refund_ratio).quantize(Decimal("0.01")),
        vat_amount=(Decimal(order.vat_amount) * refund_ratio).quantize(Decimal("0.01")),
        total=amount,
    )
    await db.flush()
    return ResponseBase(data={"id": str(refund.id), "refund_number": refund.refund_number}, message="დაბრუნება შესრულდა")


@router.get("/refunds", response_model=ResponseBase[list[dict]])
async def list_refunds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    rows = (await db.execute(
        select(POSRefund).where(POSRefund.company_id == current_user.company_id).order_by(POSRefund.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "refund_number": r.refund_number, "order_id": str(r.order_id),
        "amount": float(r.amount), "reason": r.reason, "created_at": r.created_at.isoformat(),
    } for r in rows])


# ── Loyalty ───────────────────────────────────────────────────────────────────

@router.get("/loyalty/{client_id}", response_model=ResponseBase[dict])
async def loyalty_balance(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    account = (await db.execute(
        select(POSLoyaltyAccount).where(
            POSLoyaltyAccount.company_id == current_user.company_id,
            POSLoyaltyAccount.client_id == client_id,
        )
    )).scalar_one_or_none()
    if not account:
        return ResponseBase(data={"client_id": str(client_id), "points": 0, "total_earned": 0, "total_redeemed": 0})
    return ResponseBase(data={
        "client_id": str(client_id), "points": float(account.points),
        "total_earned": float(account.total_earned), "total_redeemed": float(account.total_redeemed),
    })


@router.post("/loyalty/earn", response_model=ResponseBase[dict])
async def earn_loyalty_points(
    client_id: UUID,
    order_id: UUID,
    points: Decimal = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    company_id = current_user.company_id
    account = (await db.execute(
        select(POSLoyaltyAccount).where(
            POSLoyaltyAccount.company_id == company_id,
            POSLoyaltyAccount.client_id == client_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not account:
        account = POSLoyaltyAccount(company_id=company_id, client_id=client_id)
        db.add(account)
        await db.flush()
    account.points += points
    account.total_earned += points
    db.add(POSLoyaltyTransaction(
        company_id=company_id, account_id=account.id, order_id=order_id,
        points=points, transaction_type="earn",
    ))
    await db.flush()
    return ResponseBase(data={"points": float(account.points)}, message="ქულები დაერიცხა")


@router.post("/loyalty/redeem", response_model=ResponseBase[dict])
async def redeem_loyalty_points(
    client_id: UUID,
    points: Decimal = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    company_id = current_user.company_id
    account = (await db.execute(
        select(POSLoyaltyAccount).where(
            POSLoyaltyAccount.company_id == company_id,
            POSLoyaltyAccount.client_id == client_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not account or Decimal(account.points) < points:
        raise HTTPException(status_code=409, detail="არასაკმარისი ქულები")
    account.points -= points
    account.total_redeemed += points
    db.add(POSLoyaltyTransaction(
        company_id=company_id, account_id=account.id,
        points=-points, transaction_type="redeem",
    ))
    await db.flush()
    return ResponseBase(data={"points": float(account.points)}, message="ქულები ჩამოიჭრა")


# ── Offline queue ─────────────────────────────────────────────────────────────

@router.post("/offline/queue", response_model=ResponseBase[dict], status_code=201)
async def queue_offline_order(
    device_id: str = Query(..., min_length=1),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    entry = POSOfflineQueue(
        company_id=current_user.company_id, device_id=device_id, payload=payload,
    )
    db.add(entry)
    await db.flush()
    return ResponseBase(data={"id": str(entry.id)}, message="შეკვეთა რიგში დადგა")


@router.get("/offline/queue", response_model=ResponseBase[list[dict]])
async def list_offline_queue(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    filters = [POSOfflineQueue.company_id == current_user.company_id]
    if status:
        filters.append(POSOfflineQueue.status == status)
    rows = (await db.execute(
        select(POSOfflineQueue).where(*filters).order_by(POSOfflineQueue.created_at.asc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(q.id), "device_id": q.device_id, "payload": q.payload,
        "status": q.status, "created_at": q.created_at.isoformat(),
    } for q in rows])


@router.post("/offline/queue/{queue_id}/sync", response_model=ResponseBase[dict])
async def sync_offline_order(
    queue_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    """Sync a queued offline order — actually creates the POS order from the payload."""
    entry = (await db.execute(
        select(POSOfflineQueue).where(
            POSOfflineQueue.id == queue_id,
            POSOfflineQueue.company_id == current_user.company_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="რიგის ჩანაწერი არ მოიძებნა")
    if entry.status == "synced":
        raise HTTPException(status_code=409, detail="უკვე სინქრონიზებულია")

    payload = entry.payload or {}
    session_id = payload.get("session_id")
    session = (await db.execute(
        select(POSSession).where(POSSession.id == session_id, POSSession.company_id == current_user.company_id)
    )).scalar_one_or_none() if session_id else None
    if not session:
        session = (await db.execute(
            select(POSSession).where(POSSession.company_id == current_user.company_id, POSSession.status == "open")
        )).scalars().first()
    if not session:
        raise HTTPException(status_code=409, detail="ღია ცვლა არ არის — შეკვეთის სინქრონიზაცია შეუძლებელია")

    # rebuild the order from the payload
    subtotal = Decimal("0")
    order_items = []
    for item in payload.get("items", []):
        product = (await db.execute(
            select(Product).where(Product.id == item["product_id"], Product.company_id == current_user.company_id)
        )).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"პროდუქტი {item['product_id']} არ მოიძებნა")
        qty = Decimal(str(item["quantity"]))
        price = Decimal(str(item.get("unit_price", product.sale_price)))
        line_total = (qty * price).quantize(Decimal("0.01"))
        subtotal += line_total
        order_items.append({
            "product_id": product.id, "product_name": product.name,
            "quantity": qty, "unit_price": price, "line_total": line_total,
        })

    vat = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
    total = subtotal + vat
    count = (await db.execute(
        select(func.count(POSOrder.id)).where(POSOrder.company_id == current_user.company_id)
    )).scalar() or 0
    order = POSOrder(
        company_id=current_user.company_id, session_id=session.id,
        client_id=payload.get("client_id"),
        order_number=f"POS-{utc_now():%y%m%d}-{count + 1:04d}",
        status="completed", subtotal=subtotal, vat_amount=vat, total=total,
        payment_method=payload.get("payment_method", "cash"),
        payment_reference=payload.get("payment_reference"),
        created_by=current_user.id,
    )
    db.add(order)
    await db.flush()
    for item in order_items:
        db.add(POSOrderItem(pos_order_id=order.id, **item))
    await db.flush()

    session.total_orders += 1
    session.total_sales += total
    entry.status = "synced"
    entry.synced_at = utc_now()
    await db.flush()
    return ResponseBase(data={
        "id": str(entry.id), "order_id": str(order.id), "order_number": order.order_number,
        "total": float(total),
    }, message="შეკვეთა სინქრონიზებულია — POS შეკვეთა შეიქმნა")


# ── Fiscal devices ────────────────────────────────────────────────────────────

@router.get("/fiscal-devices", response_model=ResponseBase[list[dict]])
async def list_fiscal_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    rows = (await db.execute(
        select(POSFiscalDevice).where(POSFiscalDevice.company_id == current_user.company_id)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(d.id), "name": d.name, "device_type": d.device_type,
        "serial_number": d.serial_number, "is_active": d.is_active,
    } for d in rows])


@router.post("/fiscal-devices", response_model=ResponseBase[dict], status_code=201)
async def register_fiscal_device(
    name: str = Query(..., min_length=1),
    device_type: str = Query("fiscal_printer", pattern="^(fiscal_printer|terminal|barcode_scanner|cash_drawer|receipt_printer)$"),
    serial_number: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    device = POSFiscalDevice(
        company_id=current_user.company_id, name=name,
        device_type=device_type, serial_number=serial_number,
    )
    db.add(device)
    await db.flush()
    return ResponseBase(data={"id": str(device.id)}, message="მოწყობილობა დარეგისტრირდა")


@router.patch("/fiscal-devices/{device_id}", response_model=ResponseBase[dict])
async def update_fiscal_device(
    device_id: UUID,
    is_active: bool | None = None,
    name: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_edit")),
):
    """Toggle a device active/inactive or rename it."""
    device = (await db.execute(
        select(POSFiscalDevice).where(POSFiscalDevice.id == device_id, POSFiscalDevice.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="მოწყობილობა არ მოიძებნა")
    if is_active is not None:
        device.is_active = is_active
    if name:
        device.name = name
    await db.flush()
    return ResponseBase(data={
        "id": str(device.id), "name": device.name,
        "device_type": device.device_type, "is_active": device.is_active,
    }, message="მოწყობილობა განახლდა")


@router.get("/hardware/status", response_model=ResponseBase[dict])
async def hardware_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    """POS hardware overview: registered devices by type + online/offline state."""
    rows = (await db.execute(
        select(POSFiscalDevice).where(POSFiscalDevice.company_id == current_user.company_id)
    )).scalars().all()
    by_type: dict[str, int] = {}
    for d in rows:
        by_type[d.device_type] = by_type.get(d.device_type, 0) + 1
    return ResponseBase(data={
        "total_devices": len(rows),
        "active_devices": sum(1 for d in rows if d.is_active),
        "by_type": by_type,
        "devices": [{
            "id": str(d.id), "name": d.name, "device_type": d.device_type,
            "serial_number": d.serial_number, "is_active": d.is_active,
        } for d in rows],
    })


# ── Gift cards ────────────────────────────────────────────────────────────────

@router.get("/gift-cards", response_model=ResponseBase[list[dict]])
async def list_gift_cards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    rows = (await db.execute(
        select(GiftCard).where(GiftCard.company_id == current_user.company_id).order_by(GiftCard.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(g.id), "card_number": g.card_number, "pin": g.pin,
        "initial_balance": float(g.initial_balance), "balance": float(g.balance),
        "status": g.status, "expires_at": g.expires_at.isoformat() if g.expires_at else None,
        "created_at": g.created_at.isoformat(),
    } for g in rows])


@router.post("/gift-cards", response_model=ResponseBase[dict], status_code=201)
async def issue_gift_card(
    amount: Decimal = Query(..., gt=0),
    expires_at: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    """Issue a gift card with a unique number and optional PIN."""
    import random
    card_number = f"GC-{utc_now():%y%m%d}-{random.randint(100000, 999999)}"
    pin = f"{random.randint(1000, 9999)}"
    card = GiftCard(
        company_id=current_user.company_id, card_number=card_number, pin=pin,
        initial_balance=amount, balance=amount, expires_at=expires_at,
        issued_by=current_user.id,
    )
    db.add(card)
    await db.flush()
    db.add(GiftCardTransaction(
        company_id=current_user.company_id, card_id=card.id,
        amount=amount, transaction_type="issue", created_by=current_user.id,
    ))
    await db.flush()
    return ResponseBase(data={
        "id": str(card.id), "card_number": card.card_number, "pin": card.pin,
        "balance": float(card.balance),
    }, message="სასაჩუქრე ბარათი გაიცა")


@router.post("/gift-cards/{card_id}/top-up", response_model=ResponseBase[dict])
async def top_up_gift_card(
    card_id: UUID,
    amount: Decimal = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    card = (await db.execute(
        select(GiftCard).where(GiftCard.id == card_id, GiftCard.company_id == current_user.company_id).with_for_update()
    )).scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="ბარათი არ მოიძებნა")
    if card.status != "active":
        raise HTTPException(status_code=409, detail="ბარათი არაა აქტიური")
    card.balance += amount
    db.add(GiftCardTransaction(
        company_id=current_user.company_id, card_id=card.id,
        amount=amount, transaction_type="top_up", created_by=current_user.id,
    ))
    await db.flush()
    return ResponseBase(data={"balance": float(card.balance)}, message="ბარათი შეივსო")


@router.post("/gift-cards/{card_id}/redeem", response_model=ResponseBase[dict])
async def redeem_gift_card(
    card_id: UUID,
    amount: Decimal = Query(..., gt=0),
    order_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    card = (await db.execute(
        select(GiftCard).where(GiftCard.id == card_id, GiftCard.company_id == current_user.company_id).with_for_update()
    )).scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="ბარათი არ მოიძებნა")
    if card.status != "active":
        raise HTTPException(status_code=409, detail="ბარათი არაა აქტიური")
    if amount > Decimal(card.balance):
        raise HTTPException(status_code=409, detail="ბარათზე საკმარისი თანხა არ არის")
    card.balance -= amount
    if card.balance <= 0:
        card.status = "redeemed"
    db.add(GiftCardTransaction(
        company_id=current_user.company_id, card_id=card.id, order_id=order_id,
        amount=-amount, transaction_type="redeem", created_by=current_user.id,
    ))
    await db.flush()
    return ResponseBase(data={"balance": float(card.balance)}, message="ბარათით გადახდა შესრულდა")


# ── Cash register (X/Z reports, cash in/out) ─────────────────────────────────

@router.post("/sessions/{session_id}/cash-in", response_model=ResponseBase[dict])
async def cash_in(
    session_id: UUID,
    amount: Decimal = Query(..., gt=0),
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    session = (await db.execute(
        select(POSSession).where(POSSession.id == session_id, POSSession.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not session or session.status != "open":
        raise HTTPException(status_code=409, detail="ღია სესია არ მოიძებნა")
    db.add(POSCashMovement(
        company_id=current_user.company_id, session_id=session.id,
        movement_type="cash_in", amount=amount, reason=reason, created_by=current_user.id,
    ))
    await db.flush()
    return ResponseBase(data={"amount": float(amount)}, message="ნაღდი ფული შეიტანეს სალაროში")


@router.post("/sessions/{session_id}/cash-out", response_model=ResponseBase[dict])
async def cash_out(
    session_id: UUID,
    amount: Decimal = Query(..., gt=0),
    reason: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    session = (await db.execute(
        select(POSSession).where(POSSession.id == session_id, POSSession.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not session or session.status != "open":
        raise HTTPException(status_code=409, detail="ღია სესია არ მოიძებნა")
    db.add(POSCashMovement(
        company_id=current_user.company_id, session_id=session.id,
        movement_type="cash_out", amount=amount, reason=reason, created_by=current_user.id,
    ))
    await db.flush()
    return ResponseBase(data={"amount": float(amount)}, message="ნაღდი ფული ამოიღეს სალაროდან")


@router.get("/sessions/{session_id}/x-report", response_model=ResponseBase[dict])
async def x_report(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    """X-report — live session totals without closing."""
    session = (await db.execute(
        select(POSSession).where(POSSession.id == session_id, POSSession.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="სესია არ მოიძებნა")
    orders = (await db.execute(
        select(POSOrder).where(POSOrder.session_id == session.id)
    )).scalars().all()
    refunds = (await db.execute(
        select(POSRefund).where(POSRefund.session_id == session.id)
    )).scalars().all()
    movements = (await db.execute(
        select(POSCashMovement).where(POSCashMovement.session_id == session.id)
    )).scalars().all()
    cash_sales = sum((o.total for o in orders if o.payment_method == "cash"), Decimal("0"))
    card_sales = sum((o.total for o in orders if o.payment_method != "cash"), Decimal("0"))
    total_refunds = sum((r.amount for r in refunds), Decimal("0"))
    cash_in = sum((m.amount for m in movements if m.movement_type == "cash_in"), Decimal("0"))
    cash_out = sum((m.amount for m in movements if m.movement_type == "cash_out"), Decimal("0"))
    expected_cash = cash_sales + cash_in - cash_out - total_refunds
    return ResponseBase(data={
        "session_id": str(session.id), "session_name": session.name,
        "total_orders": len(orders), "total_sales": float(session.total_sales),
        "cash_sales": float(cash_sales), "card_sales": float(card_sales),
        "total_refunds": float(total_refunds),
        "cash_in": float(cash_in), "cash_out": float(cash_out),
        "expected_cash": float(expected_cash),
    })


@router.post("/sessions/{session_id}/z-report", response_model=ResponseBase[dict])
async def z_report(
    session_id: UUID,
    declared_cash: Decimal | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    """Z-report — close the session with a full cash register report."""
    session = (await db.execute(
        select(POSSession).where(POSSession.id == session_id, POSSession.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="სესია არ მოიძებნა")
    if session.status != "open":
        raise HTTPException(status_code=409, detail="სესია უკვე დახურულია")

    orders = (await db.execute(
        select(POSOrder).where(POSOrder.session_id == session.id)
    )).scalars().all()
    refunds = (await db.execute(
        select(POSRefund).where(POSRefund.session_id == session.id)
    )).scalars().all()
    movements = (await db.execute(
        select(POSCashMovement).where(POSCashMovement.session_id == session.id)
    )).scalars().all()
    cash_sales = sum((o.total for o in orders if o.payment_method == "cash"), Decimal("0"))
    total_refunds = sum((r.amount for r in refunds), Decimal("0"))
    cash_in = sum((m.amount for m in movements if m.movement_type == "cash_in"), Decimal("0"))
    cash_out = sum((m.amount for m in movements if m.movement_type == "cash_out"), Decimal("0"))
    expected_cash = cash_sales + cash_in - cash_out - total_refunds
    difference = (declared_cash or expected_cash) - expected_cash

    count = (await db.execute(
        select(func.count(POSZReport.id)).where(POSZReport.company_id == current_user.company_id)
    )).scalar() or 0
    report = POSZReport(
        company_id=current_user.company_id, session_id=session.id,
        report_number=f"Z-{utc_now():%y%m%d}-{count + 1:04d}",
        opened_at=session.opened_at, closed_at=utc_now(),
        total_sales=session.total_sales, total_orders=session.total_orders,
        total_refunds=total_refunds, cash_in=cash_in, cash_out=cash_out,
        expected_cash=expected_cash, declared_cash=declared_cash, difference=difference,
        created_by=current_user.id,
    )
    db.add(report)
    session.status = "closed"
    session.closed_at = utc_now()
    await db.flush()
    return ResponseBase(data={
        "report_number": report.report_number, "total_sales": float(report.total_sales),
        "total_orders": report.total_orders, "total_refunds": float(report.total_refunds),
        "expected_cash": float(expected_cash), "declared_cash": float(declared_cash or 0),
        "difference": float(difference),
    }, message="Z-ანგარიში შექმნილია, სესია დახურულია")


@router.get("/z-reports", response_model=ResponseBase[list[dict]])
async def list_z_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    rows = (await db.execute(
        select(POSZReport).where(POSZReport.company_id == current_user.company_id).order_by(POSZReport.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "report_number": r.report_number, "session_id": str(r.session_id),
        "total_sales": float(r.total_sales), "total_orders": r.total_orders,
        "total_refunds": float(r.total_refunds), "expected_cash": float(r.expected_cash),
        "declared_cash": float(r.declared_cash) if r.declared_cash else None,
        "difference": float(r.difference), "closed_at": r.closed_at.isoformat(),
    } for r in rows])
