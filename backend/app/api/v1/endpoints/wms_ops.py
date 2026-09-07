"""WMS operations: picking, packing, replenishment, landed cost, traceability."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.product import Product
from app.models.warehouse import (
    InventoryBalance,
    InventoryMovement,
    ProductBatch,
    ProductSerial,
    Warehouse,
    UoM,
    UoMConversion,
    WarehouseReorderRule,
    PutawayStrategy,
    CycleCountSchedule,
    ConsignmentStock,
)
from app.models.wms_ops import (
    BatchTraceEvent,
    LandedCost,
    LandedCostAllocation,
    PackingSlip,
    PickList,
    PickListItem,
    ReplenishmentRule,
    WavePick,
    CrossDockOrder,
    CrossDockItem,
    Shipment,
    ShipmentItem,
    LotZoneBalance,
)
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/wms-ops", tags=["WMS — ოპერაციები"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class PickListCreate(BaseModel):
    order_id: UUID | None = None
    warehouse_id: UUID
    notes: str | None = None


class PickListItemIn(BaseModel):
    product_id: UUID
    batch_id: UUID | None = None
    quantity: Decimal = Field(..., gt=0)


class PickListCreateFull(BaseModel):
    warehouse_id: UUID
    order_id: UUID | None = None
    notes: str | None = None
    items: list[PickListItemIn] = Field(default_factory=list)


class PickItemRequest(BaseModel):
    item_id: UUID
    quantity: Decimal = Field(..., gt=0)


class PackingSlipCreate(BaseModel):
    pick_list_id: UUID
    weight: Decimal | None = None
    packages: int = Field(default=1, ge=1)
    notes: str | None = None


class ReplenishmentRuleCreate(BaseModel):
    warehouse_id: UUID
    product_id: UUID
    supplier_id: UUID | None = None
    min_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    max_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_quantity: Decimal | None = None
    safety_stock: Decimal = Field(default=Decimal("0"), ge=0)
    lead_time_days: int = Field(default=0, ge=0)


class LandedCostCreate(BaseModel):
    purchase_order_id: UUID | None = None
    supplier_id: UUID | None = None
    description: str = Field(..., min_length=1, max_length=255)
    total_amount: Decimal = Field(..., gt=0)
    currency: str = "GEL"


class LandedCostAllocate(BaseModel):
    allocations: list[dict]


class TraceResponse(BaseModel):
    batch_id: UUID | None
    serial_id: UUID | None
    product_id: UUID
    event_type: str
    quantity: Decimal | None
    from_warehouse_id: UUID | None
    to_warehouse_id: UUID | None
    reference: str | None
    notes: str | None
    created_at: datetime


async def _require_warehouse(db: AsyncSession, company_id: UUID, warehouse_id: UUID) -> Warehouse:
    w = (await db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.company_id == company_id)
    )).scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="საწყობი არ მოიძებნა")
    return w


async def _require_product(db: AsyncSession, company_id: UUID, product_id: UUID) -> Product:
    p = (await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == company_id)
    )).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
    return p


async def _add_trace(
    db: AsyncSession,
    *,
    company_id: UUID,
    product_id: UUID,
    event_type: str,
    batch_id: UUID | None = None,
    serial_id: UUID | None = None,
    quantity: Decimal | None = None,
    from_warehouse_id: UUID | None = None,
    to_warehouse_id: UUID | None = None,
    reference: str | None = None,
    notes: str | None = None,
    user_id: UUID | None = None,
) -> None:
    db.add(BatchTraceEvent(
        company_id=company_id,
        batch_id=batch_id,
        serial_id=serial_id,
        product_id=product_id,
        event_type=event_type,
        quantity=quantity,
        from_warehouse_id=from_warehouse_id,
        to_warehouse_id=to_warehouse_id,
        reference=reference,
        notes=notes,
        created_by=user_id,
    ))
    await db.flush()


# ── Picking ──────────────────────────────────────────────────────────────────

@router.post("/pick-lists", response_model=ResponseBase[dict], status_code=201)
async def create_pick_list(
    payload: PickListCreateFull,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_create")),
):
    company_id = current_user.company_id
    await _require_warehouse(db, company_id, payload.warehouse_id)
    if not payload.items:
        raise HTTPException(status_code=422, detail="პიკინგის სია ცარიელია")

    count = await db.scalar(select(func.count(PickList.id)).where(PickList.company_id == company_id))
    pick_number = f"PL-{datetime.now():%Y%m%d}-{int(count or 0) + 1:04d}"

    pick_list = PickList(
        company_id=company_id,
        order_id=payload.order_id,
        warehouse_id=payload.warehouse_id,
        pick_number=pick_number,
        status="draft",
        notes=payload.notes,
    )
    db.add(pick_list)
    await db.flush()

    for item in payload.items:
        await _require_product(db, company_id, item.product_id)
        batch = None
        if item.batch_id:
            batch = (await db.execute(
                select(ProductBatch).where(
                    ProductBatch.id == item.batch_id,
                    ProductBatch.company_id == company_id,
                )
            )).scalar_one_or_none()
            if not batch:
                raise HTTPException(status_code=404, detail="პარტია არ მოიძებნა")
            if batch.product_id != item.product_id:
                raise HTTPException(status_code=409, detail="პარტია სხვა პროდუქტს ეკუთვნის")
        db.add(PickListItem(
            pick_list_id=pick_list.id,
            product_id=item.product_id,
            batch_id=item.batch_id,
            quantity=item.quantity,
            picked_quantity=Decimal("0"),
            status="pending",
        ))
        await _add_trace(
            db, company_id=company_id, product_id=item.product_id,
            batch_id=item.batch_id, event_type="picked",
            quantity=item.quantity, from_warehouse_id=payload.warehouse_id,
            reference=pick_number, user_id=current_user.id,
        )
    await db.flush()
    return ResponseBase(data={"id": str(pick_list.id), "pick_number": pick_number}, message="პიკინგის სია შექმნილია")


@router.get("/pick-lists", response_model=ResponseBase[list[dict]])
async def list_pick_lists(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    company_id = current_user.company_id
    query = select(PickList).where(PickList.company_id == company_id)
    if status:
        query = query.where(PickList.status == status)
    query = query.order_by(PickList.created_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    result = []
    for pl in rows:
        lines = (await db.execute(
            select(PickListItem).where(PickListItem.pick_list_id == pl.id)
        )).scalars().all()
        result.append({
            "id": str(pl.id), "pick_number": pl.pick_number, "order_id": str(pl.order_id) if pl.order_id else None,
            "warehouse_id": str(pl.warehouse_id), "status": pl.status, "notes": pl.notes,
            "created_at": pl.created_at.isoformat(),
            "items": [{
                "id": str(i.id), "product_id": str(i.product_id), "batch_id": str(i.batch_id) if i.batch_id else None,
                "quantity": float(i.quantity), "picked_quantity": float(i.picked_quantity), "status": i.status,
            } for i in lines],
        })
    return ResponseBase(data=result)


@router.post("/pick-lists/{pick_list_id}/pick", response_model=ResponseBase[dict])
async def pick_item(
    pick_list_id: UUID,
    payload: PickItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_create")),
):
    company_id = current_user.company_id
    item = (await db.execute(
        select(PickListItem).join(PickList).where(
            PickListItem.id == payload.item_id,
            PickList.id == pick_list_id,
            PickList.company_id == company_id,
        ).with_for_update().options(selectinload(PickListItem.pick_list))
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="პიკინგის ელემენტი არ მოიძებნა")
    new_picked = Decimal(item.picked_quantity) + payload.quantity
    if new_picked > Decimal(item.quantity):
        raise HTTPException(status_code=409, detail="მეტი ვიდრე საჭირო რაოდენობაა")
    item.picked_quantity = new_picked
    item.status = "picked" if new_picked >= Decimal(item.quantity) else "partial"

    # decrement inventory
    balance = (await db.execute(
        select(InventoryBalance).where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.warehouse_id == item.pick_list.warehouse_id,
            InventoryBalance.product_id == item.product_id,
        ).with_for_update()
    )).scalar_one_or_none()
    if not balance or Decimal(balance.quantity) < payload.quantity:
        raise HTTPException(status_code=409, detail="საწყობში არასაკმარისი ნაშთია")
    balance.quantity = Decimal(balance.quantity) - payload.quantity

    # keep Product.current_stock in sync (Odoo-style stock on hand)
    product = (await db.execute(
        select(Product).where(Product.id == item.product_id, Product.company_id == company_id).with_for_update()
    )).scalar_one_or_none()
    if product:
        product.current_stock = float(Decimal(str(product.current_stock or 0)) - payload.quantity)

    if item.batch_id:
        batch = (await db.execute(
            select(ProductBatch).where(ProductBatch.id == item.batch_id).with_for_update()
        )).scalar_one_or_none()
        if batch:
            batch.quantity = Decimal(batch.quantity) - payload.quantity

    await _add_trace(
        db, company_id=company_id, product_id=item.product_id,
        batch_id=item.batch_id, event_type="picked",
        quantity=payload.quantity, from_warehouse_id=item.pick_list.warehouse_id,
        reference=item.pick_list.pick_number, user_id=current_user.id,
    )
    await db.flush()
    return ResponseBase(data={"item_id": str(item.id), "picked_quantity": float(item.picked_quantity)}, message="პიკინგი შესრულდა")


@router.post("/pick-lists/{pick_list_id}/complete", response_model=ResponseBase[dict])
async def complete_pick_list(
    pick_list_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_create")),
):
    pl = (await db.execute(
        select(PickList).where(PickList.id == pick_list_id, PickList.company_id == current_user.company_id).with_for_update()
    )).scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="პიკინგის სია არ მოიძებნა")
    lines = (await db.execute(select(PickListItem).where(PickListItem.pick_list_id == pl.id))).scalars().all()
    if any(Decimal(i.picked_quantity) < Decimal(i.quantity) for i in lines):
        raise HTTPException(status_code=409, detail="ყველა ელემენტი არ არის დაპიკებული")
    pl.status = "picked"
    await db.flush()
    return ResponseBase(data={"id": str(pl.id), "status": pl.status}, message="პიკინგი დასრულებულია")


# ── Packing ──────────────────────────────────────────────────────────────────

@router.post("/packing-slips", response_model=ResponseBase[dict], status_code=201)
async def create_packing_slip(
    payload: PackingSlipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_create")),
):
    company_id = current_user.company_id
    pl = (await db.execute(
        select(PickList).where(PickList.id == payload.pick_list_id, PickList.company_id == company_id)
    )).scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="პიკინგის სია არ მოიძებნა")
    if pl.status not in ("picked", "packed"):
        raise HTTPException(status_code=409, detail="პიკინგი ჯერ არ დასრულებულა")

    count = await db.scalar(select(func.count(PackingSlip.id)).where(PackingSlip.company_id == company_id))
    pack_number = f"PK-{datetime.now():%Y%m%d}-{int(count or 0) + 1:04d}"
    slip = PackingSlip(
        company_id=company_id, pick_list_id=pl.id, pack_number=pack_number,
        status="packed", weight=payload.weight, packages=payload.packages, notes=payload.notes,
    )
    db.add(slip)
    pl.status = "packed"
    await db.flush()
    return ResponseBase(data={"id": str(slip.id), "pack_number": pack_number}, message="შეფუთვა შექმნილია")


@router.get("/packing-slips", response_model=ResponseBase[list[dict]])
async def list_packing_slips(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    query = select(PackingSlip).where(PackingSlip.company_id == current_user.company_id)
    if status:
        query = query.where(PackingSlip.status == status)
    query = query.order_by(PackingSlip.created_at.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return ResponseBase(data=[{
        "id": str(s.id), "pack_number": s.pack_number, "pick_list_id": str(s.pick_list_id),
        "status": s.status, "weight": float(s.weight) if s.weight else None,
        "packages": s.packages, "notes": s.notes, "created_at": s.created_at.isoformat(),
    } for s in rows])


# ── Replenishment ────────────────────────────────────────────────────────────

@router.post("/replenishment-rules", response_model=ResponseBase[dict], status_code=201)
async def create_replenishment_rule(
    payload: ReplenishmentRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_create")),
):
    company_id = current_user.company_id
    await _require_warehouse(db, company_id, payload.warehouse_id)
    await _require_product(db, company_id, payload.product_id)
    existing = (await db.execute(
        select(ReplenishmentRule).where(
            ReplenishmentRule.company_id == company_id,
            ReplenishmentRule.warehouse_id == payload.warehouse_id,
            ReplenishmentRule.product_id == payload.product_id,
        )
    )).scalar_one_or_none()
    if existing:
        existing.min_quantity = payload.min_quantity
        existing.max_quantity = payload.max_quantity
        existing.reorder_quantity = payload.reorder_quantity
        existing.safety_stock = payload.safety_stock
        existing.lead_time_days = payload.lead_time_days
        existing.supplier_id = payload.supplier_id
        await db.flush()
        return ResponseBase(data={"id": str(existing.id)}, message="წესი განახლებულია")
    rule = ReplenishmentRule(
        company_id=company_id, warehouse_id=payload.warehouse_id, product_id=payload.product_id,
        supplier_id=payload.supplier_id,
        min_quantity=payload.min_quantity, max_quantity=payload.max_quantity,
        reorder_quantity=payload.reorder_quantity,
        safety_stock=payload.safety_stock, lead_time_days=payload.lead_time_days,
    )
    db.add(rule)
    await db.flush()
    return ResponseBase(data={"id": str(rule.id)}, message="წესი შექმნილია")


@router.get("/replenishment-rules", response_model=ResponseBase[list[dict]])
async def list_replenishment_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    rows = (await db.execute(
        select(ReplenishmentRule).where(ReplenishmentRule.company_id == current_user.company_id)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "warehouse_id": str(r.warehouse_id), "product_id": str(r.product_id),
        "min_quantity": float(r.min_quantity), "max_quantity": float(r.max_quantity),
        "reorder_quantity": float(r.reorder_quantity) if r.reorder_quantity else None,
        "safety_stock": float(r.safety_stock), "lead_time_days": r.lead_time_days,
        "supplier_id": str(r.supplier_id) if r.supplier_id else None,
        "is_active": r.is_active,
    } for r in rows])


@router.get("/replenishment/suggestions", response_model=ResponseBase[list[dict]])
async def replenishment_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    """Products below min level → suggested reorder quantity."""
    company_id = current_user.company_id
    rules = (await db.execute(
        select(ReplenishmentRule).where(
            ReplenishmentRule.company_id == company_id,
            ReplenishmentRule.is_active.is_(True),
        )
    )).scalars().all()
    suggestions = []
    for rule in rules:
        balance = (await db.execute(
            select(InventoryBalance).where(
                InventoryBalance.company_id == company_id,
                InventoryBalance.warehouse_id == rule.warehouse_id,
                InventoryBalance.product_id == rule.product_id,
            )
        )).scalar_one_or_none()
        on_hand = Decimal(balance.quantity) if balance else Decimal("0")
        threshold = rule.safety_stock if rule.safety_stock and rule.safety_stock > 0 else rule.min_quantity
        if on_hand < threshold:
            reorder = rule.reorder_quantity or (rule.max_quantity - on_hand)
            suggestions.append({
                "warehouse_id": str(rule.warehouse_id), "product_id": str(rule.product_id),
                "on_hand": float(on_hand), "min_quantity": float(rule.min_quantity),
                "suggested_quantity": float(max(reorder, Decimal("0"))),
            })
    return ResponseBase(data=suggestions)


# ── Landed cost ───────────────────────────────────────────────────────────────

@router.post("/landed-costs", response_model=ResponseBase[dict], status_code=201)
async def create_landed_cost(
    payload: LandedCostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_create")),
):
    lc = LandedCost(
        company_id=current_user.company_id,
        purchase_order_id=payload.purchase_order_id,
        supplier_id=payload.supplier_id,
        description=payload.description,
        total_amount=payload.total_amount,
        currency=payload.currency,
    )
    db.add(lc)
    await db.flush()
    return ResponseBase(data={"id": str(lc.id)}, message="ლენდედ ქოსთი შექმნილია")


@router.get("/landed-costs", response_model=ResponseBase[list[dict]])
async def list_landed_costs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    rows = (await db.execute(
        select(LandedCost).where(LandedCost.company_id == current_user.company_id)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(l.id), "description": l.description, "total_amount": float(l.total_amount),
        "currency": l.currency, "allocated": l.allocated,
        "purchase_order_id": str(l.purchase_order_id) if l.purchase_order_id else None,
        "supplier_id": str(l.supplier_id) if l.supplier_id else None,
        "created_at": l.created_at.isoformat(),
    } for l in rows])


@router.post("/landed-costs/{landed_cost_id}/allocate", response_model=ResponseBase[dict])
async def allocate_landed_cost(
    landed_cost_id: UUID,
    payload: LandedCostAllocate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_create")),
):
    company_id = current_user.company_id
    lc = (await db.execute(
        select(LandedCost).where(LandedCost.id == landed_cost_id, LandedCost.company_id == company_id).with_for_update()
    )).scalar_one_or_none()
    if not lc:
        raise HTTPException(status_code=404, detail="ლენდედ ქოსთი არ მოიძებნა")
    if lc.allocated:
        raise HTTPException(status_code=409, detail="უკვე განაწილებულია")

    total_allocated = Decimal("0")
    for alloc in payload.allocations:
        batch_id = UUID(alloc["batch_id"])
        amount = Decimal(str(alloc["amount"]))
        batch = (await db.execute(
            select(ProductBatch).where(ProductBatch.id == batch_id, ProductBatch.company_id == company_id)
        )).scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="პარტია არ მოიძებნა")
        db.add(LandedCostAllocation(
            landed_cost_id=lc.id, batch_id=batch.id, product_id=batch.product_id, amount=amount,
        ))
        if batch.unit_cost is not None and batch.quantity > 0:
            batch.unit_cost = Decimal(batch.unit_cost) + amount / Decimal(batch.quantity)
        total_allocated += amount
        await _add_trace(
            db, company_id=company_id, product_id=batch.product_id, batch_id=batch.id,
            event_type="cost_allocated", quantity=batch.quantity,
            reference=lc.description, notes=f"Landed cost {amount} {lc.currency}",
            user_id=current_user.id,
        )
    if total_allocated > Decimal(lc.total_amount):
        raise HTTPException(status_code=409, detail="განაწილებული თანხა აღემატება ჯამს")
    lc.allocated = True
    await db.flush()
    return ResponseBase(data={"allocated": float(total_allocated)}, message="ლენდედ ქოსთი განაწილდა")


# ── Traceability ──────────────────────────────────────────────────────────────

@router.get("/trace/{batch_id}", response_model=ResponseBase[list[TraceResponse]])
async def batch_trace(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    events = (await db.execute(
        select(BatchTraceEvent).where(
            BatchTraceEvent.company_id == current_user.company_id,
            BatchTraceEvent.batch_id == batch_id,
        ).order_by(BatchTraceEvent.created_at.asc())
    )).scalars().all()
    return ResponseBase(data=events)


@router.get("/trace/serial/{serial_id}", response_model=ResponseBase[list[TraceResponse]])
async def serial_trace(
    serial_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    events = (await db.execute(
        select(BatchTraceEvent).where(
            BatchTraceEvent.company_id == current_user.company_id,
            BatchTraceEvent.serial_id == serial_id,
        ).order_by(BatchTraceEvent.created_at.asc())
    )).scalars().all()
    return ResponseBase(data=events)


# ── FIFO / FEFO ───────────────────────────────────────────────────────────────

@router.get("/allocation/{product_id}", response_model=ResponseBase[list[dict]])
async def allocation_suggestion(
    product_id: UUID,
    strategy: str = Query("fefo", pattern="^(fifo|fefo)$"),
    quantity: Decimal = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("wms", "can_access")),
):
    """Suggest which batches to consume first for a product.

    FIFO — oldest production date first (first in, first out).
    FEFO — earliest expiry date first (first expiry, first out).
    """
    company_id = current_user.company_id
    await _require_product(db, company_id, product_id)
    query = select(ProductBatch).where(
        ProductBatch.company_id == company_id,
        ProductBatch.product_id == product_id,
        ProductBatch.quantity > 0,
    )
    if strategy == "fefo":
        query = query.order_by(ProductBatch.expiry_date.asc().nulls_last(), ProductBatch.created_at.asc())
    else:
        query = query.order_by(ProductBatch.production_date.asc().nulls_last(), ProductBatch.created_at.asc())
    batches = (await db.execute(query)).scalars().all()

    remaining = Decimal(quantity)
    allocation = []
    for b in batches:
        if remaining <= 0:
            break
        take = min(Decimal(b.quantity), remaining)
        allocation.append({
            "batch_id": str(b.id),
            "batch_number": b.batch_number,
            "quantity": float(take),
            "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
            "production_date": b.production_date.isoformat() if b.production_date else None,
            "unit_cost": float(b.unit_cost) if b.unit_cost else None,
        })
        remaining -= take

    if remaining > 0:
        return ResponseBase(
            data=allocation,
            message=f"საკმარისი მარაგი არ არის — დეფიციტი: {float(remaining)}",
        )
    return ResponseBase(data=allocation, message=f"{strategy.upper()} განაწილება")


# ── Warehouse 2.0 ────────────────────────────────────────────────────────────

@router.get("/uoms", response_model=ResponseBase)
async def list_uoms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(UoM).where(UoM.company_id == current_user.company_id).order_by(UoM.code)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(u.id), "code": u.code, "name": u.name, "category": u.category,
         "is_base": u.is_base, "is_active": u.is_active} for u in rows
    ], message="UoM სია")


@router.post("/uoms", response_model=ResponseBase, status_code=201)
async def create_uom(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    uom = UoM(
        id=_uuid.uuid4(), company_id=current_user.company_id,
        code=payload["code"].strip().upper(), name=payload["name"].strip(),
        category=payload.get("category", "unit"), is_base=payload.get("is_base", False),
    )
    db.add(uom)
    await db.commit()
    return ResponseBase(data={"id": str(uom.id), "code": uom.code}, message="UoM შექმნილია")


@router.post("/uom-conversions", response_model=ResponseBase, status_code=201)
async def create_uom_conversion(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    conv = UoMConversion(
        id=_uuid.uuid4(), company_id=current_user.company_id,
        from_uom_id=UUID(payload["from_uom_id"]), to_uom_id=UUID(payload["to_uom_id"]),
        factor=Decimal(str(payload["factor"])),
    )
    db.add(conv)
    await db.commit()
    return ResponseBase(data={"id": str(conv.id), "factor": float(conv.factor)}, message="კონვერტაცია შენახულია")


@router.get("/uom-conversions", response_model=ResponseBase)
async def list_uom_conversions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(UoMConversion).where(UoMConversion.company_id == current_user.company_id)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(c.id), "from_uom_id": str(c.from_uom_id), "to_uom_id": str(c.to_uom_id),
         "factor": float(c.factor)} for c in rows
    ], message="UoM კონვერტაციები")


@router.post("/uom/convert", response_model=ResponseBase)
async def convert_uom(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """Convert quantity between UoMs using stored conversion factors."""
    from_uom_id = UUID(payload["from_uom_id"])
    to_uom_id = UUID(payload["to_uom_id"])
    qty = Decimal(str(payload["quantity"]))
    if from_uom_id == to_uom_id:
        return ResponseBase(data={"quantity": float(qty)}, message="იგივე UoM")
    conv = (
        await db.execute(
            select(UoMConversion).where(
                UoMConversion.company_id == current_user.company_id,
                UoMConversion.from_uom_id == from_uom_id,
                UoMConversion.to_uom_id == to_uom_id,
            )
        )
    ).scalars().first()
    if not conv:
        raise HTTPException(status_code=404, detail="კონვერტაცია არ არსებობს")
    result = qty * conv.factor
    return ResponseBase(data={"quantity": float(result), "factor": float(conv.factor)}, message="კონვერტირებული")


@router.get("/reorder-rules", response_model=ResponseBase)
async def list_reorder_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(WarehouseReorderRule).where(WarehouseReorderRule.company_id == current_user.company_id)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(r.id), "warehouse_id": str(r.warehouse_id), "product_id": str(r.product_id),
         "min_quantity": float(r.min_quantity), "max_quantity": float(r.max_quantity),
         "reorder_quantity": float(r.reorder_quantity), "lead_time_days": r.lead_time_days,
         "is_active": r.is_active} for r in rows
    ], message="Reorder rules")


@router.post("/reorder-rules", response_model=ResponseBase, status_code=201)
async def upsert_reorder_rule(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    rule = (
        await db.execute(
            select(WarehouseReorderRule).where(
                WarehouseReorderRule.company_id == current_user.company_id,
                WarehouseReorderRule.warehouse_id == UUID(payload["warehouse_id"]),
                WarehouseReorderRule.product_id == UUID(payload["product_id"]),
            )
        )
    ).scalars().first()
    if rule is None:
        rule = WarehouseReorderRule(
            id=_uuid.uuid4(), company_id=current_user.company_id,
            warehouse_id=UUID(payload["warehouse_id"]), product_id=UUID(payload["product_id"]),
        )
        db.add(rule)
    rule.min_quantity = Decimal(str(payload.get("min_quantity", rule.min_quantity)))
    rule.max_quantity = Decimal(str(payload.get("max_quantity", rule.max_quantity)))
    rule.reorder_quantity = Decimal(str(payload.get("reorder_quantity", rule.reorder_quantity)))
    rule.lead_time_days = int(payload.get("lead_time_days", rule.lead_time_days))
    rule.is_active = payload.get("is_active", rule.is_active)
    await db.commit()
    return ResponseBase(data={"id": str(rule.id)}, message="Reorder rule შენახულია")


@router.get("/reorder/suggestions", response_model=ResponseBase)
async def reorder_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """Warehouse-specific reorder suggestions: balance < min → suggest reorder qty."""
    rules = (
        await db.execute(
            select(WarehouseReorderRule).where(
                WarehouseReorderRule.company_id == current_user.company_id,
                WarehouseReorderRule.is_active.is_(True),
            )
        )
    ).scalars().all()
    suggestions = []
    for r in rules:
        bal = (
            await db.execute(
                select(InventoryBalance).where(
                    InventoryBalance.company_id == current_user.company_id,
                    InventoryBalance.warehouse_id == r.warehouse_id,
                    InventoryBalance.product_id == r.product_id,
                )
            )
        ).scalars().first()
        on_hand = bal.quantity if bal else Decimal("0")
        if on_hand < r.min_quantity:
            suggestions.append({
                "warehouse_id": str(r.warehouse_id),
                "product_id": str(r.product_id),
                "on_hand": float(on_hand),
                "min_quantity": float(r.min_quantity),
                "suggested_order": float(r.reorder_quantity),
                "lead_time_days": r.lead_time_days,
            })
    return ResponseBase(data=suggestions, message="Reorder suggestions")


@router.get("/putaway-strategies", response_model=ResponseBase)
async def list_putaway_strategies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(PutawayStrategy).where(PutawayStrategy.company_id == current_user.company_id)
            .order_by(PutawayStrategy.priority)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(p.id), "name": p.name, "priority": p.priority,
         "product_id": str(p.product_id) if p.product_id else None,
         "category_id": str(p.category_id) if p.category_id else None,
         "zone_id": str(p.zone_id), "is_active": p.is_active} for p in rows
    ], message="Putaway strategies")


@router.post("/putaway-strategies", response_model=ResponseBase, status_code=201)
async def create_putaway_strategy(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    strat = PutawayStrategy(
        id=_uuid.uuid4(), company_id=current_user.company_id,
        name=payload["name"], priority=int(payload.get("priority", 100)),
        product_id=UUID(payload["product_id"]) if payload.get("product_id") else None,
        category_id=UUID(payload["category_id"]) if payload.get("category_id") else None,
        zone_id=UUID(payload["zone_id"]),
        is_active=payload.get("is_active", True),
    )
    db.add(strat)
    await db.commit()
    return ResponseBase(data={"id": str(strat.id)}, message="Putaway strategy შენახულია")


@router.post("/putaway/suggest", response_model=ResponseBase)
async def suggest_putaway(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """Directed putaway: find best zone for a product on receipt."""
    product_id = UUID(payload["product_id"])
    strategies = (
        await db.execute(
            select(PutawayStrategy).where(
                PutawayStrategy.company_id == current_user.company_id,
                PutawayStrategy.is_active.is_(True),
            ).order_by(PutawayStrategy.priority)
        )
    ).scalars().all()
    for s in strategies:
        if s.product_id == product_id or s.category_id is not None:
            return ResponseBase(
                data={"zone_id": str(s.zone_id), "strategy": s.name, "priority": s.priority},
                message="Putaway ზონა",
            )
    raise HTTPException(status_code=404, detail="Putaway strategy არ მოიძებნა")


@router.get("/cycle-count-schedules", response_model=ResponseBase)
async def list_cycle_count_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(CycleCountSchedule).where(CycleCountSchedule.company_id == current_user.company_id)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(c.id), "warehouse_id": str(c.warehouse_id),
         "zone_id": str(c.zone_id) if c.zone_id else None, "abc_class": c.abc_class,
         "frequency_days": c.frequency_days,
         "next_run_date": c.next_run_date.isoformat() if c.next_run_date else None,
         "last_run_date": c.last_run_date.isoformat() if c.last_run_date else None,
         "is_active": c.is_active} for c in rows
    ], message="Cycle count schedules")


@router.post("/cycle-count-schedules", response_model=ResponseBase, status_code=201)
async def create_cycle_count_schedule(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    from datetime import timedelta
    freq = int(payload.get("frequency_days", 30))
    sched = CycleCountSchedule(
        id=_uuid.uuid4(), company_id=current_user.company_id,
        warehouse_id=UUID(payload["warehouse_id"]),
        zone_id=UUID(payload["zone_id"]) if payload.get("zone_id") else None,
        abc_class=payload.get("abc_class"), frequency_days=freq,
        next_run_date=datetime.utcnow() + timedelta(days=freq),
        is_active=payload.get("is_active", True),
    )
    db.add(sched)
    await db.commit()
    return ResponseBase(data={"id": str(sched.id)}, message="Cycle count schedule შენახულია")


@router.get("/consignment-stock", response_model=ResponseBase)
async def list_consignment_stock(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(ConsignmentStock).where(ConsignmentStock.company_id == current_user.company_id)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(c.id), "warehouse_id": str(c.warehouse_id), "product_id": str(c.product_id),
         "owner_id": str(c.owner_id), "quantity": float(c.quantity),
         "reserved_quantity": float(c.reserved_quantity),
         "unit_cost": float(c.unit_cost) if c.unit_cost else None} for c in rows
    ], message="Consignment stock")


@router.post("/consignment-stock", response_model=ResponseBase, status_code=201)
async def upsert_consignment_stock(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    stock = (
        await db.execute(
            select(ConsignmentStock).where(
                ConsignmentStock.company_id == current_user.company_id,
                ConsignmentStock.warehouse_id == UUID(payload["warehouse_id"]),
                ConsignmentStock.product_id == UUID(payload["product_id"]),
                ConsignmentStock.owner_id == UUID(payload["owner_id"]),
            )
        )
    ).scalars().first()
    if stock is None:
        stock = ConsignmentStock(
            id=_uuid.uuid4(), company_id=current_user.company_id,
            warehouse_id=UUID(payload["warehouse_id"]), product_id=UUID(payload["product_id"]),
            owner_id=UUID(payload["owner_id"]),
        )
        db.add(stock)
    stock.quantity = Decimal(str(payload.get("quantity", stock.quantity)))
    if payload.get("unit_cost") is not None:
        stock.unit_cost = Decimal(str(payload["unit_cost"]))
    await db.commit()
    return ResponseBase(data={"id": str(stock.id), "quantity": float(stock.quantity)}, message="Consignment stock შენახულია")


@router.get("/stock-aging", response_model=ResponseBase)
async def stock_aging(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """Stock aging: days since last movement per product+warehouse."""
    from datetime import date
    balances = (
        await db.execute(
            select(InventoryBalance).where(InventoryBalance.company_id == current_user.company_id)
        )
    ).scalars().all()
    rows = []
    for b in balances:
        last_mv = (
            await db.execute(
                select(func.max(InventoryMovement.created_at)).where(
                    InventoryMovement.company_id == current_user.company_id,
                    InventoryMovement.warehouse_id == b.warehouse_id,
                    InventoryMovement.product_id == b.product_id,
                )
            )
        ).scalar_one_or_none()
        days = (date.today() - last_mv.date()).days if last_mv else None
        rows.append({
            "warehouse_id": str(b.warehouse_id), "product_id": str(b.product_id),
            "quantity": float(b.quantity), "last_movement_days": days,
        })
    return ResponseBase(data=rows, message="Stock aging")


@router.get("/expiry-alerts", response_model=ResponseBase)
async def expiry_alerts(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """Expiry alerts: batches expiring within N days (default 30)."""
    from datetime import timedelta
    horizon = datetime.utcnow() + timedelta(days=days)
    batches = (
        await db.execute(
            select(ProductBatch).where(
                ProductBatch.company_id == current_user.company_id,
                ProductBatch.expiry_date.is_not(None),
                ProductBatch.expiry_date <= horizon,
                ProductBatch.quantity > 0,
            ).order_by(ProductBatch.expiry_date)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"batch_id": str(b.id), "batch_number": b.batch_number, "product_id": str(b.product_id),
         "quantity": float(b.quantity),
         "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None} for b in batches
    ], message="Expiry alerts")


@router.get("/abc-xyz", response_model=ResponseBase)
async def abc_xyz_classification(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """ABC/XYZ classification: list products with their classes."""
    products = (
        await db.execute(
            select(Product).where(Product.company_id == current_user.company_id)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"product_id": str(p.id), "sku": p.sku, "name": p.name,
         "abc_class": p.abc_class, "xyz_class": p.xyz_class,
         "is_quarantine": p.is_quarantine, "quarantine_reason": p.quarantine_reason} for p in products
    ], message="ABC/XYZ classification")


@router.post("/abc-xyz", response_model=ResponseBase)
async def set_abc_xyz(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """Set ABC/XYZ class + quarantine for a product."""
    product = (
        await db.execute(
            select(Product).where(
                Product.company_id == current_user.company_id,
                Product.id == UUID(payload["product_id"]),
            )
        )
    ).scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
    if payload.get("abc_class") is not None:
        product.abc_class = payload["abc_class"]
    if payload.get("xyz_class") is not None:
        product.xyz_class = payload["xyz_class"]
    if payload.get("is_quarantine") is not None:
        product.is_quarantine = payload["is_quarantine"]
        product.quarantine_reason = payload.get("quarantine_reason")
    await db.commit()
    return ResponseBase(data={"product_id": str(product.id), "abc_class": product.abc_class,
                              "xyz_class": product.xyz_class, "is_quarantine": product.is_quarantine},
                        message="კლასიფიკაცია შენახულია")


# ── WMS 2.0 ───────────────────────────────────────────────────────────────────

@router.post("/waves", response_model=ResponseBase, status_code=201)
async def create_wave(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """Wave/batch picking: create wave, optionally attach pick lists."""
    import uuid as _uuid
    from app.models.order import DocumentSequence
    seq = (
        await db.execute(
            select(DocumentSequence).where(
                DocumentSequence.company_id == current_user.company_id,
                DocumentSequence.document_type == "wave_pick",
            )
        )
    ).scalars().first()
    if seq is None:
        seq = DocumentSequence(company_id=current_user.company_id, document_type="wave_pick", next_value=2)
        db.add(seq)
        current = 1
    else:
        current = seq.next_value
        seq.next_value += 1
    wave = WavePick(
        id=_uuid.uuid4(), company_id=current_user.company_id,
        wave_number=f"WAVE-{current:05d}", status="planned",
        warehouse_id=UUID(payload["warehouse_id"]),
        picker_id=UUID(payload["picker_id"]) if payload.get("picker_id") else None,
        notes=payload.get("notes"), created_by=current_user.id,
    )
    db.add(wave)
    await db.flush()
    for pl_id in payload.get("pick_list_ids", []):
        pl = (
            await db.execute(
                select(PickList).where(
                    PickList.id == UUID(pl_id),
                    PickList.company_id == current_user.company_id,
                )
            )
        ).scalars().first()
        if pl:
            pl.wave_id = wave.id
    await db.commit()
    return ResponseBase(data={"id": str(wave.id), "wave_number": wave.wave_number}, message="Wave შექმნილია")


@router.get("/waves", response_model=ResponseBase)
async def list_waves(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(WavePick).where(WavePick.company_id == current_user.company_id)
            .order_by(WavePick.created_at.desc())
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(w.id), "wave_number": w.wave_number, "status": w.status,
         "warehouse_id": str(w.warehouse_id),
         "started_at": w.started_at.isoformat() if w.started_at else None,
         "completed_at": w.completed_at.isoformat() if w.completed_at else None} for w in rows
    ], message="Waves")


@router.post("/waves/{wave_id}/complete", response_model=ResponseBase)
async def complete_wave(
    wave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    from app.core.time import utc_now
    wave = (
        await db.execute(
            select(WavePick).where(
                WavePick.id == wave_id, WavePick.company_id == current_user.company_id
            )
        )
    ).scalars().first()
    if not wave:
        raise HTTPException(status_code=404, detail="Wave არ მოიძებნა")
    wave.status = "completed"
    wave.completed_at = utc_now()
    await db.commit()
    return ResponseBase(data={"id": str(wave.id), "status": "completed"}, message="Wave დასრულდა")


@router.post("/cross-dock-orders", response_model=ResponseBase, status_code=201)
async def create_cross_dock_order(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    from app.models.order import DocumentSequence
    seq = (
        await db.execute(
            select(DocumentSequence).where(
                DocumentSequence.company_id == current_user.company_id,
                DocumentSequence.document_type == "cross_dock",
            )
        )
    ).scalars().first()
    if seq is None:
        seq = DocumentSequence(company_id=current_user.company_id, document_type="cross_dock", next_value=2)
        db.add(seq)
        current = 1
    else:
        current = seq.next_value
        seq.next_value += 1
    order = CrossDockOrder(
        id=_uuid.uuid4(), company_id=current_user.company_id,
        cross_dock_number=f"XD-{current:05d}", status="planned",
        source_warehouse_id=UUID(payload["source_warehouse_id"]),
        destination_warehouse_id=UUID(payload["destination_warehouse_id"]),
        notes=payload.get("notes"), created_by=current_user.id,
    )
    db.add(order)
    await db.flush()
    for it in payload.get("items", []):
        db.add(CrossDockItem(
            id=_uuid.uuid4(), cross_dock_order_id=order.id,
            product_id=UUID(it["product_id"]), quantity=Decimal(str(it["quantity"])),
        ))
    await db.commit()
    return ResponseBase(data={"id": str(order.id), "cross_dock_number": order.cross_dock_number}, message="Cross-dock შექმნილია")


@router.get("/cross-dock-orders", response_model=ResponseBase)
async def list_cross_dock_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(CrossDockOrder).where(CrossDockOrder.company_id == current_user.company_id)
            .order_by(CrossDockOrder.created_at.desc())
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(o.id), "cross_dock_number": o.cross_dock_number, "status": o.status,
         "source_warehouse_id": str(o.source_warehouse_id),
         "destination_warehouse_id": str(o.destination_warehouse_id),
         "scheduled_date": o.scheduled_date.isoformat() if o.scheduled_date else None} for o in rows
    ], message="Cross-dock orders")


@router.post("/shipments", response_model=ResponseBase, status_code=201)
async def create_shipment(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    from app.models.order import DocumentSequence
    seq = (
        await db.execute(
            select(DocumentSequence).where(
                DocumentSequence.company_id == current_user.company_id,
                DocumentSequence.document_type == "shipment",
            )
        )
    ).scalars().first()
    if seq is None:
        seq = DocumentSequence(company_id=current_user.company_id, document_type="shipment", next_value=2)
        db.add(seq)
        current = 1
    else:
        current = seq.next_value
        seq.next_value += 1
    ship = Shipment(
        id=_uuid.uuid4(), company_id=current_user.company_id,
        shipment_number=f"SHP-{current:05d}", status="draft",
        carrier=payload.get("carrier"), tracking_number=payload.get("tracking_number"),
        warehouse_id=UUID(payload["warehouse_id"]), notes=payload.get("notes"),
        created_by=current_user.id,
    )
    db.add(ship)
    await db.flush()
    for it in payload.get("items", []):
        db.add(ShipmentItem(
            id=_uuid.uuid4(), shipment_id=ship.id,
            product_id=UUID(it["product_id"]), quantity=Decimal(str(it["quantity"])),
        ))
    await db.commit()
    return ResponseBase(data={"id": str(ship.id), "shipment_number": ship.shipment_number}, message="Shipment შექმნილია")


@router.get("/shipments", response_model=ResponseBase)
async def list_shipments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(Shipment).where(Shipment.company_id == current_user.company_id)
            .order_by(Shipment.created_at.desc())
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(s.id), "shipment_number": s.shipment_number, "status": s.status,
         "carrier": s.carrier, "tracking_number": s.tracking_number,
         "warehouse_id": str(s.warehouse_id),
         "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
         "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None} for s in rows
    ], message="Shipments")


@router.post("/shipments/{shipment_id}/ship", response_model=ResponseBase)
async def ship_shipment(
    shipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    from app.core.time import utc_now
    ship = (
        await db.execute(
            select(Shipment).where(
                Shipment.id == shipment_id, Shipment.company_id == current_user.company_id
            )
        )
    ).scalars().first()
    if not ship:
        raise HTTPException(status_code=404, detail="Shipment არ მოიძებნა")
    ship.status = "shipped"
    ship.shipped_at = utc_now()
    await db.commit()
    return ResponseBase(data={"id": str(ship.id), "status": "shipped"}, message="Shipment გაგზავნილია")


@router.get("/lot-zone-balances", response_model=ResponseBase)
async def list_lot_zone_balances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    rows = (
        await db.execute(
            select(LotZoneBalance).where(LotZoneBalance.company_id == current_user.company_id)
        )
    ).scalars().all()
    return ResponseBase(data=[
        {"id": str(l.id), "batch_id": str(l.batch_id), "zone_id": str(l.zone_id),
         "quantity": float(l.quantity)} for l in rows
    ], message="Lot zone balances")


@router.post("/lot-zone-balances", response_model=ResponseBase, status_code=201)
async def upsert_lot_zone_balance(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    import uuid as _uuid
    bal = (
        await db.execute(
            select(LotZoneBalance).where(
                LotZoneBalance.company_id == current_user.company_id,
                LotZoneBalance.batch_id == UUID(payload["batch_id"]),
                LotZoneBalance.zone_id == UUID(payload["zone_id"]),
            )
        )
    ).scalars().first()
    if bal is None:
        bal = LotZoneBalance(
            id=_uuid.uuid4(), company_id=current_user.company_id,
            batch_id=UUID(payload["batch_id"]), zone_id=UUID(payload["zone_id"]),
        )
        db.add(bal)
    bal.quantity = Decimal(str(payload.get("quantity", bal.quantity)))
    await db.commit()
    return ResponseBase(data={"id": str(bal.id), "quantity": float(bal.quantity)}, message="Lot zone balance შენახულია")


@router.post("/gs1/parse", response_model=ResponseBase)
async def parse_gs1_barcode(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("warehouse", "can_access")),
):
    """GS1 barcode parsing: (01)GTIN(10)batch(17)expiry(21)serial — FNC1-separated."""
    import re
    code = payload.get("barcode", "")
    result = {}
    # Split on FNC1 (GS, \x1d) — the standard GS1 separator for variable-length AIs
    segments = code.split("\x1d")
    for seg in segments:
        if not seg:
            continue
        if seg.startswith("01") and len(seg) >= 16:
            result["01"] = seg[2:16]
        elif seg.startswith("10"):
            result["10"] = seg[2:]
        elif seg.startswith("17") and len(seg) >= 8:
            result["17"] = seg[2:8]
        elif seg.startswith("11") and len(seg) >= 8:
            result["11"] = seg[2:8]
        elif seg.startswith("21"):
            result["21"] = seg[2:]
        elif seg.startswith("30"):
            result["30"] = seg[2:]
    if not result:
        raise HTTPException(status_code=400, detail="GS1 ფორმატი ვერ ამოიცნო")
    return ResponseBase(data=result, message="GS1 barcode გაშიფრულია")
