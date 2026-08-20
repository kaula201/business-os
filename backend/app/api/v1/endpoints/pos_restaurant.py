"""Restaurant POS API: tables, order types, self-ordering (QR)."""
import secrets
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.pos import POSOrder, POSOrderItem, POSSession
from app.models.pos_restaurant import RestaurantTable, POSOrderType, SelfOrderSession
from app.models.product import Product
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/pos", tags=["POS — რესტორანი"])


# ── Tables ───────────────────────────────────────────────────────────────────

@router.get("/tables", response_model=ResponseBase[list[dict]])
async def list_tables(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    rows = (await db.execute(
        select(RestaurantTable).where(RestaurantTable.company_id == current_user.company_id).order_by(RestaurantTable.name)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "name": t.name, "capacity": t.capacity,
        "status": t.status, "current_order_id": str(t.current_order_id) if t.current_order_id else None,
        "qr_code": t.qr_code, "is_active": t.is_active,
    } for t in rows])


@router.post("/tables", response_model=ResponseBase[dict], status_code=201)
async def create_table(
    name: str = Query(..., min_length=1),
    capacity: int = Query(2, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    table = RestaurantTable(
        company_id=current_user.company_id, name=name, capacity=capacity,
        qr_code=f"QR-{secrets.token_hex(6).upper()}",
    )
    db.add(table)
    await db.flush()
    return ResponseBase(data={
        "id": str(table.id), "name": table.name, "capacity": table.capacity,
        "status": table.status, "qr_code": table.qr_code,
    }, message="მაგიდა დაემატა")


@router.post("/tables/{table_id}/occupy", response_model=ResponseBase[dict])
async def occupy_table(
    table_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    table = (await db.execute(
        select(RestaurantTable).where(RestaurantTable.id == table_id, RestaurantTable.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="მაგიდა არ მოიძებნა")
    if table.status == "occupied":
        raise HTTPException(status_code=409, detail="მაგიდა უკვე დაკავებულია")
    table.status = "occupied"
    await db.flush()
    return ResponseBase(data={"id": str(table.id), "status": table.status}, message="მაგიდა დაკავებულია")


@router.post("/tables/{table_id}/free", response_model=ResponseBase[dict])
async def free_table(
    table_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    table = (await db.execute(
        select(RestaurantTable).where(RestaurantTable.id == table_id, RestaurantTable.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="მაგიდა არ მოიძებნა")
    table.status = "free"
    table.current_order_id = None
    await db.flush()
    return ResponseBase(data={"id": str(table.id), "status": table.status}, message="მაგიდა გათავისუფლდა")


@router.patch("/tables/{table_id}/position", response_model=ResponseBase[dict])
async def set_table_position(
    table_id: UUID,
    pos_x: int = Query(..., ge=0),
    pos_y: int = Query(..., ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_edit")),
):
    """Set table coordinates on the floor plan."""
    table = (await db.execute(
        select(RestaurantTable).where(RestaurantTable.id == table_id, RestaurantTable.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="მაგიდა არ მოიძებნა")
    table.pos_x = pos_x
    table.pos_y = pos_y
    await db.flush()
    return ResponseBase(data={"id": str(table.id), "pos_x": table.pos_x, "pos_y": table.pos_y}, message="მაგიდის პოზიცია განახლდა")


# ── Order types ─────────────────────────────────────────────────────────────

@router.get("/order-types", response_model=ResponseBase[list[dict]])
async def list_order_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_access")),
):
    rows = (await db.execute(
        select(POSOrderType).where(POSOrderType.company_id == current_user.company_id).order_by(POSOrderType.code)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "code": t.code, "name": t.name, "is_active": t.is_active,
    } for t in rows])


@router.post("/order-types", response_model=ResponseBase[dict], status_code=201)
async def create_order_type(
    code: str = Query(..., pattern="^(dine_in|takeaway|delivery|self_order)$"),
    name: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    existing = (await db.execute(
        select(POSOrderType).where(POSOrderType.company_id == current_user.company_id, POSOrderType.code == code)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="ტიპი უკვე არსებობს")
    ot = POSOrderType(company_id=current_user.company_id, code=code, name=name)
    db.add(ot)
    await db.flush()
    return ResponseBase(data={"id": str(ot.id), "code": ot.code, "name": ot.name}, message="შეკვეთის ტიპი დაემატა")


# ── Self-ordering (QR) ──────────────────────────────────────────────────────

@router.post("/self-order/start", response_model=ResponseBase[dict], status_code=201)
async def start_self_order(
    table_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    """Start a self-ordering session (customer scans QR)."""
    token = secrets.token_urlsafe(24)
    session = SelfOrderSession(
        company_id=current_user.company_id, table_id=table_id, token=token,
    )
    db.add(session)
    await db.flush()
    return ResponseBase(data={
        "id": str(session.id), "token": session.token, "table_id": str(table_id) if table_id else None,
    }, message="თვითმომსახურების სესია დაიწყო")


@router.post("/self-order/{token}/submit", response_model=ResponseBase[dict], status_code=201)
async def submit_self_order(
    token: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("pos", "can_create")),
):
    """Customer submits their order from the self-ordering session."""
    items = payload.get("items", [])
    session = (await db.execute(
        select(SelfOrderSession).where(SelfOrderSession.token == token, SelfOrderSession.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="სესია არ მოიძებნა")
    if session.status != "active":
        raise HTTPException(status_code=409, detail="სესია დახურულია")

    # find an open POS session to attach the order to
    pos_session = (await db.execute(
        select(POSSession).where(POSSession.company_id == current_user.company_id, POSSession.status == "open")
    )).scalars().first()
    if not pos_session:
        raise HTTPException(status_code=409, detail="ღია ცვლა არ არის")

    subtotal = Decimal("0")
    order_items = []
    for item in items:
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
        company_id=current_user.company_id, session_id=pos_session.id,
        order_number=f"SO-{utc_now():%y%m%d}-{count + 1:04d}",
        status="completed", subtotal=subtotal, vat_amount=vat, total=total,
        payment_method="cash", created_by=current_user.id,
    )
    db.add(order)
    await db.flush()
    for item in order_items:
        db.add(POSOrderItem(pos_order_id=order.id, **item))
    await db.flush()

    pos_session.total_orders += 1
    pos_session.total_sales += total
    session.order_id = order.id
    session.status = "closed"
    session.closed_at = utc_now()
    if session.table_id:
        table = (await db.execute(select(RestaurantTable).where(RestaurantTable.id == session.table_id))).scalar_one_or_none()
        if table:
            table.status = "occupied"
            table.current_order_id = order.id
    await db.flush()
    return ResponseBase(data={
        "order_id": str(order.id), "order_number": order.order_number, "total": float(total),
    }, message="შეკვეთა მიღებულია")
