"""WMS operations: picking, packing, replenishment, landed cost, traceability."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.product import Product
from app.models.warehouse import (
    InventoryBalance,
    ProductBatch,
    ProductSerial,
    Warehouse,
)
from app.models.wms_ops import (
    BatchTraceEvent,
    LandedCost,
    LandedCostAllocation,
    PackingSlip,
    PickList,
    PickListItem,
    ReplenishmentRule,
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
    min_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    max_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_quantity: Decimal | None = None


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
        ).with_for_update()
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
        await db.flush()
        return ResponseBase(data={"id": str(existing.id)}, message="წესი განახლებულია")
    rule = ReplenishmentRule(
        company_id=company_id, warehouse_id=payload.warehouse_id, product_id=payload.product_id,
        min_quantity=payload.min_quantity, max_quantity=payload.max_quantity,
        reorder_quantity=payload.reorder_quantity,
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
        if on_hand < rule.min_quantity:
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
