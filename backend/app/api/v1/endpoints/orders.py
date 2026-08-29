import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.invoices import ensure_completed_order_invoice, ensure_order_invoice_draft
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.client import Client
from app.models.order import (
    DocumentSequence,
    InventoryReservation,
    Order,
    OrderFulfillment,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentStatus,
)
from app.models.product import Product
from app.models.user import User
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.order import (
    InventoryReservationResponse,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderStatusChange,
    OrderStatusHistoryResponse,
    OrderLifecycleResponse,
    OrderLifecycleTransition,
    StockCheckResponse,
    StockCheckItem,
    PaymentUpdate,
    OrderTimelineEntry,
)

router = APIRouter(prefix="/orders", tags=["შეკვეთები"])

ALLOWED_TRANSITIONS = {
    OrderStatus.DRAFT.value: {OrderStatus.CONFIRMED.value, OrderStatus.CANCELLED.value},
    OrderStatus.CONFIRMED.value: {OrderStatus.PREPARING.value, OrderStatus.SHIPPING.value, OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value},
    OrderStatus.PREPARING.value: {OrderStatus.SHIPPING.value, OrderStatus.CANCELLED.value},
    OrderStatus.SHIPPING.value: {OrderStatus.COMPLETED.value},
    OrderStatus.COMPLETED.value: {OrderStatus.RETURNED.value},
    OrderStatus.CANCELLED.value: set(),
    OrderStatus.RETURNED.value: set(),
}

LIFECYCLE_ORDER = [
    OrderStatus.DRAFT.value,
    OrderStatus.CONFIRMED.value,
    OrderStatus.PREPARING.value,
    OrderStatus.SHIPPING.value,
    OrderStatus.COMPLETED.value,
    OrderStatus.CANCELLED.value,
]


def _order_options():
    return (
        selectinload(Order.company),
        selectinload(Order.client),
        selectinload(Order.assignee),
        selectinload(Order.items),
        selectinload(Order.fulfillment).selectinload(OrderFulfillment.warehouse),
        selectinload(Order.reservations),
    )


def _build_order_response(order: Order) -> OrderResponse:
    response = OrderResponse.model_validate(order)
    response.client_name = order.client.name if order.client else None
    if order.fulfillment:
        response.warehouse_id = order.fulfillment.warehouse_id
        response.warehouse_name = (
            order.fulfillment.warehouse.name if order.fulfillment.warehouse else None
        )
    statuses = {reservation.status for reservation in order.reservations}
    for status in ("active", "consumed", "returned", "released"):
        if status in statuses:
            response.reservation_status = status
            break
    return response


async def _load_order(
    db: AsyncSession,
    order_id: UUID,
    company_id: UUID,
    *,
    for_update: bool = False,
) -> Order | None:
    statement = select(Order).where(
        Order.id == order_id,
        Order.company_id == company_id,
    )
    if for_update:
        statement = statement.with_for_update()
    statement = statement.options(*_order_options())
    result = await db.execute(statement)
    return result.unique().scalar_one_or_none()


async def _get_active_warehouse(
    db: AsyncSession,
    warehouse_id: UUID,
    company_id: UUID,
) -> Warehouse:
    warehouse = (
        await db.execute(
            select(Warehouse).where(
                Warehouse.id == warehouse_id,
                Warehouse.company_id == company_id,
                Warehouse.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="აქტიური საწყობი არ მოიძებნა")
    return warehouse


async def _allocate_order_number(db: AsyncSession, company_id: UUID) -> str:
    lock_key = f"order-sequence:{company_id}"
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key})
    sequence = (
        await db.execute(
            select(DocumentSequence)
            .where(
                DocumentSequence.company_id == company_id,
                DocumentSequence.document_type == "order",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if sequence is None:
        existing_numbers = (
            await db.execute(select(Order.order_number).where(Order.company_id == company_id))
        ).scalars().all()
        allocated = 1
        for number in existing_numbers:
            try:
                allocated = max(allocated, int(number.rsplit("-", 1)[1]) + 1)
            except (IndexError, ValueError):
                continue
        sequence = DocumentSequence(
            company_id=company_id,
            document_type="order",
            next_value=allocated + 1,
        )
        db.add(sequence)
    else:
        allocated = sequence.next_value
        sequence.next_value += 1

    return f"ORD-{str(company_id)[:4].upper()}-{allocated:05d}"


def _write_order_audit(
    db: AsyncSession,
    current_user: User,
    order: Order,
    action: str,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            action=action,
            entity_type="warehouse_order",
            entity_id=order.id,
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


# ── Stock Availability Check ──────────────────────────────────────────────────


@router.get("/stock-check", response_model=ResponseBase[StockCheckResponse])
async def check_order_stock_availability(
    product_ids: str = Query(..., description="Comma-separated product UUIDs"),
    quantities: str = Query(..., description="Comma-separated quantities matching product_ids"),
    warehouse_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check stock availability for a set of products before creating an order."""
    pids = [UUID(p.strip()) for p in product_ids.split(",")]
    qtys = [float(q.strip()) for q in quantities.split(",")]
    if len(pids) != len(qtys):
        raise HTTPException(status_code=400, detail="product_ids and quantities must have same length")

    products = (
        await db.execute(
            select(Product).where(
                Product.id.in_(pids),
                Product.company_id == current_user.company_id,
            )
        )
    ).scalars().all()
    products_by_id = {p.id: p for p in products}

    # If no warehouse specified, use default
    wid = warehouse_id
    if wid is None:
        wid = (
            await db.execute(
                select(Warehouse.id).where(
                    Warehouse.company_id == current_user.company_id,
                    Warehouse.is_active.is_(True),
                    Warehouse.is_default.is_(True),
                )
            )
        ).scalar_one_or_none()

    items = []
    all_sufficient = True
    for pid, qty in zip(pids, qtys):
        product = products_by_id.get(pid)
        product_name = product.name if product else "Unknown"

        if wid:
            balance = (
                await db.execute(
                    select(InventoryBalance.quantity).where(
                        InventoryBalance.company_id == current_user.company_id,
                        InventoryBalance.warehouse_id == wid,
                        InventoryBalance.product_id == pid,
                    )
                )
            ).scalar_one_or_none() or Decimal("0")

            active_reserved = (
                await db.execute(
                    select(func.coalesce(func.sum(InventoryReservation.quantity), 0)).where(
                        InventoryReservation.company_id == current_user.company_id,
                        InventoryReservation.warehouse_id == wid,
                        InventoryReservation.product_id == pid,
                        InventoryReservation.status == "active",
                    )
                )
            ).scalar_one() or Decimal("0")

            available = float(balance - active_reserved)
        else:
            available = float(product.current_stock) if product else 0

        sufficient = available >= qty
        if not sufficient:
            all_sufficient = False
        items.append(StockCheckItem(
            product_id=pid,
            product_name=product_name,
            requested=qty,
            available=available,
            reserved=float(active_reserved) if wid else 0,
            sufficient=sufficient,
        ))

    return ResponseBase(data=StockCheckResponse(all_sufficient=all_sufficient, items=items))


# ── Order Lifecycle Visualization ─────────────────────────────────────────────


@router.get("/lifecycle", response_model=ResponseBase[OrderLifecycleResponse])
async def get_order_lifecycle(
    current_status: str = Query("draft"),
):
    """Get the order lifecycle visualization: all statuses, current position, available transitions."""
    current = current_status if current_status in LIFECYCLE_ORDER else OrderStatus.DRAFT.value
    transitions = []
    for status in LIFECYCLE_ORDER:
        allowed_next = ALLOWED_TRANSITIONS.get(status, set())
        for next_status in allowed_next:
            transitions.append(OrderLifecycleTransition(
                from_status=status,
                to_status=next_status,
                label=f"{status} → {next_status}",
                allowed=(status == current),
            ))
    return ResponseBase(data=OrderLifecycleResponse(
        current_status=current,
        available_transitions=transitions,
        all_statuses=LIFECYCLE_ORDER,
    ))


@router.get(
    "/{order_id}/lifecycle",
    response_model=ResponseBase[OrderLifecycleResponse],
)
async def get_order_lifecycle_for_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get lifecycle visualization for a specific order."""
    order = await _load_order(db, order_id, current_user.company_id)
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")

    current = order.status
    transitions = []
    allowed_next = ALLOWED_TRANSITIONS.get(current, set())
    for next_status in allowed_next:
        transitions.append(OrderLifecycleTransition(
            from_status=current,
            to_status=next_status,
            label=f"{current} → {next_status}",
            allowed=True,
        ))
    return ResponseBase(data=OrderLifecycleResponse(
        current_status=current,
        available_transitions=transitions,
        all_statuses=LIFECYCLE_ORDER,
    ))


# ── Payment Status Tracking ────────────────────────────────────────────────────


@router.patch(
    "/{order_id}/payment",
    response_model=ResponseBase[OrderResponse],
)
async def update_order_payment(
    order_id: UUID,
    data: PaymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("orders", "can_edit")),
):
    """Update payment status for an order."""
    order = await _load_order(db, order_id, current_user.company_id, for_update=True)
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")

    old_payment_status = order.payment_status
    order.payment_status = data.payment_status.value
    if data.paid_amount is not None:
        order.paid_amount = data.paid_amount
    if data.paid_at is not None:
        order.paid_at = data.paid_at
    elif data.payment_status == PaymentStatus.PAID and order.paid_at is None:
        order.paid_at = utc_now()

    _write_order_audit(
        db,
        current_user,
        order,
        "order.payment_updated",
        {
            "from": old_payment_status,
            "to": data.payment_status.value,
            "paid_amount": data.paid_amount,
            "notes": data.notes,
        },
    )
    await db.flush()
    updated = await _load_order(db, order.id, current_user.company_id)
    return ResponseBase(data=_build_order_response(updated))


# ── Order History Timeline ─────────────────────────────────────────────────────


@router.get(
    "/{order_id}/timeline",
    response_model=ResponseBase[list[OrderTimelineEntry]],
)
async def get_order_timeline(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full order history timeline combining status changes, payment updates, and audit events."""
    order = await _load_order(db, order_id, current_user.company_id)
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")

    # Get status history
    status_history = (
        await db.execute(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at, OrderStatusHistory.id)
        )
    ).scalars().all()

    # Get audit logs for this order
    audit_logs = (
        await db.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_type == "warehouse_order",
                AuditLog.entity_id == order_id,
                AuditLog.company_id == current_user.company_id,
            )
            .order_by(AuditLog.created_at, AuditLog.id)
        )
    ).scalars().all()

    # Merge into a single timeline
    entries: list[OrderTimelineEntry] = []

    for sh in status_history:
        entries.append(OrderTimelineEntry(
            id=sh.id,
            event_type="status_change",
            status=sh.status,
            description=f"სტატუსი შეიცვალა → {sh.status}",
            notes=sh.notes,
            changed_by=sh.changed_by,
            created_at=sh.created_at,
        ))

    for al in audit_logs:
        if al.action == "order.payment_updated":
            details = json.loads(al.details) if al.details else {}
            entries.append(OrderTimelineEntry(
                id=al.id,
                event_type="payment_update",
                payment_status=details.get("to"),
                description=f"გადახდის სტატუსი: {details.get('from', '?')} → {details.get('to', '?')}",
                notes=details.get("notes"),
                changed_by=al.user_id,
                created_at=al.created_at,
            ))

    # Sort by created_at
    entries.sort(key=lambda e: (e.created_at, str(e.id)))

    return ResponseBase(data=entries)


# ── Existing Endpoints (updated) ──────────────────────────────────────────────


@router.get("/", response_model=ResponseBase[PaginatedResponse[OrderListResponse]])
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    client_id: Optional[UUID] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    payment_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Order).where(Order.company_id == current_user.company_id).options(
        selectinload(Order.client), selectinload(Order.assignee)
    )
    if status:
        query = query.where(Order.status == status)
    if search:
        query = query.where(Order.order_number.ilike(f"%{search}%"))
    if client_id:
        query = query.where(Order.client_id == client_id)
    if date_from:
        query = query.where(Order.created_at >= date_from)
    if date_to:
        query = query.where(Order.created_at <= date_to)
    if payment_status:
        query = query.where(Order.payment_status == payment_status)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    orders = (
        await db.execute(
            query.order_by(Order.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    items = [
        OrderListResponse(
            id=order.id,
            order_number=order.order_number,
            client_name=order.client.name if order.client else None,
            status=order.status,
            total=float(order.total),
            payment_status=order.payment_status,
            created_at=order.created_at,
            assigned_to_name=order.assignee.full_name if order.assignee else None,
        )
        for order in orders
    ]
    return ResponseBase(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )
    )


@router.get("/{order_id}", response_model=ResponseBase[OrderResponse])
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await _load_order(db, order_id, current_user.company_id)
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")
    return ResponseBase(data=_build_order_response(order))


@router.post("/", response_model=ResponseBase[OrderResponse])
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (
        await db.execute(
            select(Client).where(
                Client.id == data.client_id,
                Client.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="კლიენტი არ მოიძებნა")

    warehouse = None
    if data.warehouse_id:
        warehouse = await _get_active_warehouse(
            db, data.warehouse_id, current_user.company_id
        )

    product_ids = {item.product_id for item in data.items if item.product_id}
    products_by_id: dict[UUID, Product] = {}
    if product_ids:
        products = (
            await db.execute(
                select(Product).where(
                    Product.id.in_(product_ids),
                    Product.company_id == current_user.company_id,
                )
            )
        ).scalars().all()
        products_by_id = {product.id: product for product in products}
        if len(products_by_id) != len(product_ids):
            raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    # Stock availability check before creating order
    if warehouse and product_ids:
        for item_data in data.items:
            if item_data.product_id:
                balance = (
                    await db.execute(
                        select(InventoryBalance.quantity).where(
                            InventoryBalance.company_id == current_user.company_id,
                            InventoryBalance.warehouse_id == warehouse.id,
                            InventoryBalance.product_id == item_data.product_id,
                        )
                    )
                ).scalar_one_or_none() or Decimal("0")
                active_reserved = (
                    await db.execute(
                        select(func.coalesce(func.sum(InventoryReservation.quantity), 0)).where(
                            InventoryReservation.company_id == current_user.company_id,
                            InventoryReservation.warehouse_id == warehouse.id,
                            InventoryReservation.product_id == item_data.product_id,
                            InventoryReservation.status == "active",
                        )
                    )
                ).scalar_one() or Decimal("0")
                available = balance - Decimal(active_reserved)
                if available < Decimal(str(item_data.quantity)):
                    product = products_by_id.get(item_data.product_id)
                    product_name = product.name if product else item_data.product_name
                    raise HTTPException(
                        status_code=409,
                        detail=f"პროდუქტის '{product_name}' საკმარისი ნაშთი არ არის საწყობში. "
                               f"მოთხოვნილი: {item_data.quantity}, ხელმისაწვდომი: {float(available)}",
                    )

    order = Order(
        company_id=current_user.company_id,
        client_id=data.client_id,
        order_number=await _allocate_order_number(db, current_user.company_id),
        status=OrderStatus.DRAFT.value,
        delivery_date=data.delivery_date,
        delivery_address=data.delivery_address,
        notes=data.notes,
        assigned_to=data.assigned_to,
        created_by=current_user.id,
        payment_due_date=data.payment_due_date,
    )
    db.add(order)
    await db.flush()

    subtotal = Decimal("0")
    for item_data in data.items:
        quantity = Decimal(str(item_data.quantity))
        unit_price = Decimal(str(item_data.unit_price))
        discount = Decimal(str(item_data.discount_percent))
        item_total = quantity * unit_price * (Decimal("1") - discount / Decimal("100"))
        subtotal += item_total
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=item_data.product_id,
                product_name=item_data.product_name,
                quantity=float(quantity),
                unit_price=float(unit_price),
                discount_percent=float(discount),
                total=float(item_total),
            )
        )

    if warehouse:
        db.add(
            OrderFulfillment(
                company_id=current_user.company_id,
                order_id=order.id,
                warehouse_id=warehouse.id,
            )
        )

    vat_rate = Decimal("0.18") if data.is_vat_payer else Decimal("0")
    vat_amount = subtotal * vat_rate
    order.subtotal = float(subtotal)
    order.vat_amount = float(vat_amount)
    order.vat_rate = float(vat_rate)
    order.total = float(subtotal + vat_amount)
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            status=OrderStatus.DRAFT.value,
            changed_by=current_user.id,
        )
    )
    _write_order_audit(
        db,
        current_user,
        order,
        "order.created",
        {"status": OrderStatus.DRAFT.value, "warehouse_id": data.warehouse_id},
    )
    await db.flush()
    created = await _load_order(db, order.id, current_user.company_id)
    await ensure_order_invoice_draft(db, current_user, created)
    return ResponseBase(data=_build_order_response(created))


async def _ensure_fulfillment(
    db: AsyncSession,
    order: Order,
    warehouse_id: UUID | None,
    company_id: UUID,
) -> OrderFulfillment:
    if order.fulfillment:
        return order.fulfillment
    selected_id = warehouse_id
    if selected_id is None:
        selected_id = (
            await db.execute(
                select(Warehouse.id).where(
                    Warehouse.company_id == company_id,
                    Warehouse.is_active.is_(True),
                    Warehouse.is_default.is_(True),
                )
            )
        ).scalar_one_or_none()
    if selected_id is None:
        raise HTTPException(status_code=409, detail="შეკვეთას აქტიური საწყობი არ აქვს არჩეული")
    warehouse = await _get_active_warehouse(db, selected_id, company_id)
    fulfillment = OrderFulfillment(
        company_id=company_id,
        order_id=order.id,
        warehouse_id=warehouse.id,
    )
    db.add(fulfillment)
    await db.flush()
    order.fulfillment = fulfillment
    fulfillment.warehouse = warehouse
    return fulfillment


async def _reserve_order_stock(
    db: AsyncSession,
    order: Order,
    warehouse_id: UUID | None,
    company_id: UUID,
) -> None:
    fulfillment = await _ensure_fulfillment(db, order, warehouse_id, company_id)
    quantities_by_product: dict[UUID, Decimal] = {}
    for item in order.items:
        if item.product_id:
            quantities_by_product[item.product_id] = quantities_by_product.get(
                item.product_id, Decimal("0")
            ) + Decimal(str(item.quantity))

    for product_id in sorted(quantities_by_product, key=str):
        balance = (
            await db.execute(
                select(InventoryBalance)
                .where(
                    InventoryBalance.company_id == company_id,
                    InventoryBalance.warehouse_id == fulfillment.warehouse_id,
                    InventoryBalance.product_id == product_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        on_hand = balance.quantity if balance else Decimal("0")
        active_reserved = (
            await db.execute(
                select(func.coalesce(func.sum(InventoryReservation.quantity), 0)).where(
                    InventoryReservation.company_id == company_id,
                    InventoryReservation.warehouse_id == fulfillment.warehouse_id,
                    InventoryReservation.product_id == product_id,
                    InventoryReservation.status == "active",
                )
            )
        ).scalar_one()
        requested = quantities_by_product[product_id]
        if on_hand - Decimal(active_reserved) < requested:
            raise HTTPException(
                status_code=409,
                detail="საწყობში ხელმისაწვდომი ნაშთი არასაკმარისია",
            )

    for item in order.items:
        if item.product_id:
            db.add(
                InventoryReservation(
                    company_id=company_id,
                    order_id=order.id,
                    order_item_id=item.id,
                    warehouse_id=fulfillment.warehouse_id,
                    product_id=item.product_id,
                    quantity=Decimal(str(item.quantity)),
                    status="active",
                )
            )


async def _release_reservations(order: Order) -> None:
    for reservation in order.reservations:
        if reservation.status == "active":
            reservation.status = "released"


async def _issue_reserved_stock(
    db: AsyncSession,
    order: Order,
    current_user: User,
) -> None:
    active = [reservation for reservation in order.reservations if reservation.status == "active"]
    for reservation in sorted(active, key=lambda item: (str(item.product_id), str(item.id))):
        balance = (
            await db.execute(
                select(InventoryBalance)
                .where(
                    InventoryBalance.company_id == current_user.company_id,
                    InventoryBalance.warehouse_id == reservation.warehouse_id,
                    InventoryBalance.product_id == reservation.product_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not balance or balance.quantity < reservation.quantity:
            raise HTTPException(status_code=409, detail="გასაცემად ნაშთი არასაკმარისია")
        product = (
            await db.execute(
                select(Product)
                .where(
                    Product.id == reservation.product_id,
                    Product.company_id == current_user.company_id,
                )
                .with_for_update()
            )
        ).scalar_one()
        balance.quantity -= reservation.quantity
        product.current_stock -= float(reservation.quantity)
        reservation.status = "consumed"
        db.add(
            InventoryMovement(
                company_id=current_user.company_id,
                warehouse_id=reservation.warehouse_id,
                product_id=reservation.product_id,
                movement_type="issue",
                quantity=-reservation.quantity,
                balance_after=balance.quantity,
                reason="order_shipping",
                notes=f"შეკვეთა {order.order_number}",
                reference=f"order:{order.id}",
                created_by=current_user.id,
            )
        )
        # COGS: Dr 5100 / Cr 1200 at weighted average cost (Odoo-style)
        from app.services.gl_hooks import post_sale_cogs_gl
        unit_cost = Decimal(str(product.purchase_price or 0))
        cogs_amount = (unit_cost * Decimal(str(reservation.quantity))).quantize(Decimal("0.01"))
        if cogs_amount > 0:
            await post_sale_cogs_gl(
                db, current_user.company_id, current_user,
                order_id=order.id,
                order_number=order.order_number,
                entry_date=date.today(),
                cogs_amount=cogs_amount,
            )


async def _return_order_stock(
    db: AsyncSession,
    order: Order,
    current_user: User,
) -> None:
    consumed = [reservation for reservation in order.reservations if reservation.status == "consumed"]
    for reservation in sorted(consumed, key=lambda item: (str(item.product_id), str(item.id))):
        balance = (
            await db.execute(
                select(InventoryBalance)
                .where(
                    InventoryBalance.company_id == current_user.company_id,
                    InventoryBalance.warehouse_id == reservation.warehouse_id,
                    InventoryBalance.product_id == reservation.product_id,
                )
                .with_for_update()
            )
        ).scalar_one()
        product = (
            await db.execute(
                select(Product)
                .where(
                    Product.id == reservation.product_id,
                    Product.company_id == current_user.company_id,
                )
                .with_for_update()
            )
        ).scalar_one()
        balance.quantity += reservation.quantity
        product.current_stock += float(reservation.quantity)
        reservation.status = "returned"
        db.add(
            InventoryMovement(
                company_id=current_user.company_id,
                warehouse_id=reservation.warehouse_id,
                product_id=reservation.product_id,
                movement_type="return",
                quantity=reservation.quantity,
                balance_after=balance.quantity,
                reason="order_return",
                notes=f"შეკვეთა {order.order_number}",
                reference=f"order:{order.id}",
                created_by=current_user.id,
            )
        )


@router.patch("/{order_id}/status", response_model=ResponseBase[OrderResponse])
async def change_order_status(
    order_id: UUID,
    data: OrderStatusChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("orders", "can_create")),
):
    order = await _load_order(
        db, order_id, current_user.company_id, for_update=True
    )
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")

    old_status = order.status.value if isinstance(order.status, OrderStatus) else order.status
    new_status = data.status.value
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"სტატუსის ცვლილება {old_status}-დან {new_status}-ზე დაუშვებელია",
        )

    if new_status == OrderStatus.CONFIRMED.value:
        await _reserve_order_stock(
            db, order, data.warehouse_id, current_user.company_id
        )
    elif new_status == OrderStatus.CANCELLED.value:
        await _release_reservations(order)
    elif new_status == OrderStatus.SHIPPING.value:
        await _issue_reserved_stock(db, order, current_user)
    elif new_status == OrderStatus.RETURNED.value:
        await _return_order_stock(db, order, current_user)

    order.status = new_status
    if new_status == OrderStatus.COMPLETED.value:
        await ensure_completed_order_invoice(db, current_user, order)
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            status=new_status,
            notes=data.notes,
            changed_by=current_user.id,
        )
    )
    _write_order_audit(
        db,
        current_user,
        order,
        "order.status_changed",
        {"from": old_status, "to": new_status, "notes": data.notes},
    )
    await db.flush()
    # Auto-submit waybill to RS.ge (Georgia) when order goes to shipping —
    # non-blocking: a failure here never aborts the status change.
    if new_status == OrderStatus.SHIPPING.value:
        try:
            from app.core.config import settings as _settings
            if _settings.RS_SERVICE_USER and _settings.RS_SERVICE_PASSWORD:
                from app.services.rs_ge import RSGeClient
                _rs = RSGeClient(_settings.RS_WAYBILL_URL, _settings.RS_SERVICE_USER, _settings.RS_SERVICE_PASSWORD)
                await _rs.submit_waybill(
                    waybill_number=order.order_number,
                    sender_id=str(current_user.company_id),
                    receiver_id=str(order.client_id) if order.client_id else "",
                    issue_date=order.created_at.strftime("%Y-%m-%d") if order.created_at else "",
                    total=str(order.total),
                )
        except Exception:
            pass  # RS.ge submission is best-effort; status stays changed
    updated = await _load_order(db, order.id, current_user.company_id)
    return ResponseBase(data=_build_order_response(updated))


@router.get(
    "/{order_id}/reservations",
    response_model=ResponseBase[list[InventoryReservationResponse]],
)
async def list_order_reservations(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order_exists = (
        await db.execute(
            select(Order.id).where(
                Order.id == order_id,
                Order.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not order_exists:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")

    reservations = (
        await db.execute(
            select(InventoryReservation)
            .where(
                InventoryReservation.order_id == order_id,
                InventoryReservation.company_id == current_user.company_id,
            )
            .options(
                selectinload(InventoryReservation.product),
                selectinload(InventoryReservation.warehouse),
            )
            .order_by(InventoryReservation.created_at, InventoryReservation.id)
        )
    ).scalars().all()
    response = []
    for reservation in reservations:
        balance_quantity = (
            await db.execute(
                select(InventoryBalance.quantity).where(
                    InventoryBalance.company_id == current_user.company_id,
                    InventoryBalance.warehouse_id == reservation.warehouse_id,
                    InventoryBalance.product_id == reservation.product_id,
                )
            )
        ).scalar_one_or_none() or Decimal("0")
        active_reserved = (
            await db.execute(
                select(func.coalesce(func.sum(InventoryReservation.quantity), 0)).where(
                    InventoryReservation.company_id == current_user.company_id,
                    InventoryReservation.warehouse_id == reservation.warehouse_id,
                    InventoryReservation.product_id == reservation.product_id,
                    InventoryReservation.status == "active",
                )
            )
        ).scalar_one()
        response.append(
            InventoryReservationResponse(
                id=reservation.id,
                product_id=reservation.product_id,
                product_name=reservation.product.name,
                warehouse_id=reservation.warehouse_id,
                warehouse_name=reservation.warehouse.name,
                quantity=reservation.quantity,
                status=reservation.status,
                available_after_reservation=(
                    Decimal(balance_quantity) - Decimal(active_reserved)
                ),
            )
        )
    return ResponseBase(data=response)


@router.get(
    "/{order_id}/history",
    response_model=ResponseBase[list[OrderStatusHistoryResponse]],
)
async def list_order_history(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order_exists = (
        await db.execute(
            select(Order.id).where(
                Order.id == order_id,
                Order.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not order_exists:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")
    history = (
        await db.execute(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.created_at, OrderStatusHistory.id)
        )
    ).scalars().all()
    return ResponseBase(
        data=[OrderStatusHistoryResponse.model_validate(entry) for entry in history]
    )
