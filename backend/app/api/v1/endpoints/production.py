"""Production / Manufacturing API: BOM, work orders, work centers, reservations, receipts."""
from decimal import Decimal
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.user import User
from app.models.production import (
    BillOfMaterial, BOMItem, WorkOrder, WorkCenter,
    ProductionReservation, FinishedGoodsReceipt,
    Routing, RoutingOperation, WorkOrderOperation, WorkOrderConsumption,
    WorkOrderWip, WorkOrderScrapItem, ProductionGenealogy,
    MrpSuggestion, MaintenanceDowntimeWindow,
)
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse
from app.models.product import Product
from app.schemas.common import ResponseBase, PaginatedResponse
from app.schemas.production import (
    BOMCreate, BOMResponse, BOMDetailResponse, BOMCostBreakdown,
    BOMItemCreate, BOMItemResponse,
    WorkCenterCreate, WorkCenterResponse,
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse,
    ProductionReservationCreate, ProductionReservationResponse,
    ComponentAvailabilityResponse, ComponentAvailabilityItem,
    FinishedGoodsReceiptCreate, FinishedGoodsReceiptResponse,
    RoutingCreate, RoutingResponse,
    RoutingOperationCreate, RoutingOperationResponse,
    WorkOrderOperationStart, WorkOrderOperationComplete, WorkOrderOperationResponse,
    WorkOrderConsumptionCreate, WorkOrderConsumptionResponse,
    WorkOrderWipResponse,
    WorkOrderScrapCreate, WorkOrderScrapResponse,
    GenealogyCreate, GenealogyResponse,
    MrpRunResponse,
    DowntimeWindowCreate, DowntimeWindowResponse,
    CapacityResponse,
)
from app.services.inventory import sync_product_current_stock

router = APIRouter(prefix="/production", tags=["წარმოება"])


# ── BOM ────────────────────────────────────────────────────────────────────────

@router.get("/boms", response_model=ResponseBase[PaginatedResponse[BOMResponse]])
async def list_boms(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    query = select(BillOfMaterial).where(BillOfMaterial.company_id == current_user.company_id)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(BillOfMaterial.code).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return ResponseBase(data=PaginatedResponse(
        items=[BOMResponse.model_validate(b) for b in result.scalars().all()],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/boms", response_model=ResponseBase[BOMResponse], status_code=201)
async def create_bom(
    data: BOMCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    bom = BillOfMaterial(company_id=current_user.company_id, **data.model_dump())
    db.add(bom)
    await db.flush()
    await db.refresh(bom)
    return ResponseBase(data=BOMResponse.model_validate(bom))


@router.get("/boms/{bom_id}", response_model=ResponseBase[BOMDetailResponse])
async def get_bom(
    bom_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    result = await db.execute(
        select(BillOfMaterial)
        .where(BillOfMaterial.id == bom_id, BillOfMaterial.company_id == current_user.company_id)
        .options(joinedload(BillOfMaterial.items))
    )
    bom = result.unique().scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM არ მოიძებნა")

    items = [BOMItemResponse.model_validate(i) for i in bom.items]
    total_material = sum(i.quantity * i.unit_cost for i in bom.items)
    total_labor = bom.labor_cost
    total_overhead = bom.overhead_cost
    total_cost = total_material + total_labor + total_overhead
    unit_cost = total_cost / bom.quantity if bom.quantity else Decimal("0")

    resp = BOMDetailResponse(
        **BOMResponse.model_validate(bom).model_dump(),
        items=items,
        total_material_cost=total_material,
        total_labor_cost=total_labor,
        total_overhead_cost=total_overhead,
        total_cost=total_cost,
        unit_cost=unit_cost,
    )
    return ResponseBase(data=resp)


@router.get("/boms/{bom_id}/cost", response_model=ResponseBase[BOMCostBreakdown])
async def calculate_bom_cost(
    bom_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    """Calculate full cost breakdown for a BOM (material + labor + overhead)."""
    result = await db.execute(
        select(BillOfMaterial)
        .where(BillOfMaterial.id == bom_id, BillOfMaterial.company_id == current_user.company_id)
        .options(joinedload(BillOfMaterial.items))
    )
    bom = result.unique().scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=404, detail="BOM არ მოიძებნა")

    items = [BOMItemResponse.model_validate(i) for i in bom.items]
    total_material = sum(i.quantity * i.unit_cost for i in bom.items)
    total_labor = bom.labor_cost
    total_overhead = bom.overhead_cost
    total_cost = total_material + total_labor + total_overhead
    unit_cost = total_cost / bom.quantity if bom.quantity else Decimal("0")

    return ResponseBase(data=BOMCostBreakdown(
        bom_id=bom.id,
        bom_code=bom.code,
        bom_name=bom.name,
        product_id=bom.product_id,
        bom_quantity=bom.quantity,
        items=items,
        total_material_cost=total_material,
        total_labor_cost=total_labor,
        total_overhead_cost=total_overhead,
        total_cost=total_cost,
        unit_cost=unit_cost,
    ))


# ── BOM Items ──────────────────────────────────────────────────────────────────

@router.get("/boms/{bom_id}/items", response_model=ResponseBase[list[BOMItemResponse]])
async def list_bom_items(
    bom_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    result = await db.execute(
        select(BOMItem)
        .join(BillOfMaterial)
        .where(
            BOMItem.bom_id == bom_id,
            BillOfMaterial.company_id == current_user.company_id,
        )
    )
    items = result.scalars().all()
    return ResponseBase(data=[BOMItemResponse.model_validate(i) for i in items])


@router.post("/boms/{bom_id}/items", response_model=ResponseBase[BOMItemResponse], status_code=201)
async def add_bom_item(
    bom_id: UUID,
    data: BOMItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    # Verify BOM belongs to company
    bom_result = await db.execute(
        select(BillOfMaterial).where(
            BillOfMaterial.id == bom_id,
            BillOfMaterial.company_id == current_user.company_id,
        )
    )
    if not bom_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="BOM არ მოიძებნა")

    item = BOMItem(bom_id=bom_id, **data.model_dump())
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return ResponseBase(data=BOMItemResponse.model_validate(item))


# ── Work Centers ───────────────────────────────────────────────────────────────

@router.get("/work-centers", response_model=ResponseBase[PaginatedResponse[WorkCenterResponse]])
async def list_work_centers(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    query = select(WorkCenter).where(WorkCenter.company_id == current_user.company_id)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(WorkCenter.code).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return ResponseBase(data=PaginatedResponse(
        items=[WorkCenterResponse.model_validate(wc) for wc in result.scalars().all()],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/work-centers", response_model=ResponseBase[WorkCenterResponse], status_code=201)
async def create_work_center(
    data: WorkCenterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    wc = WorkCenter(company_id=current_user.company_id, **data.model_dump())
    db.add(wc)
    await db.flush()
    await db.refresh(wc)
    return ResponseBase(data=WorkCenterResponse.model_validate(wc))


# ── Work Orders ──────────────────────────────────────────────────────────────────

@router.get("/work-orders", response_model=ResponseBase[PaginatedResponse[WorkOrderResponse]])
async def list_work_orders(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    query = select(WorkOrder).where(WorkOrder.company_id == current_user.company_id)
    if status:
        query = query.where(WorkOrder.status == status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(WorkOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return ResponseBase(data=PaginatedResponse(
        items=[WorkOrderResponse.model_validate(w) for w in result.scalars().all()],
        total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/work-orders", response_model=ResponseBase[WorkOrderResponse], status_code=201)
async def create_work_order(
    data: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    order_number = await allocate_document_number(db, current_user.company_id, "work_order", "WO")
    wo = WorkOrder(company_id=current_user.company_id, order_number=order_number, **data.model_dump())
    db.add(wo)
    await db.flush()
    await db.refresh(wo)
    return ResponseBase(data=WorkOrderResponse.model_validate(wo))


@router.get("/work-orders/{wo_id}", response_model=ResponseBase[WorkOrderResponse])
async def get_work_order(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == wo_id,
            WorkOrder.company_id == current_user.company_id,
        )
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")
    return ResponseBase(data=WorkOrderResponse.model_validate(wo))


@router.patch("/work-orders/{wo_id}", response_model=ResponseBase[WorkOrderResponse])
async def update_work_order(
    wo_id: UUID,
    data: WorkOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == wo_id,
            WorkOrder.company_id == current_user.company_id,
        )
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(wo, field, value)
    await db.flush()
    await db.refresh(wo)
    return ResponseBase(data=WorkOrderResponse.model_validate(wo))


# ── Component Availability Check ────────────────────────────────────────────────

@router.get("/work-orders/{wo_id}/availability", response_model=ResponseBase[ComponentAvailabilityResponse])
async def check_component_availability(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    """Check if all BOM components for a work order are available in warehouse."""
    result = await db.execute(
        select(WorkOrder)
        .where(WorkOrder.id == wo_id, WorkOrder.company_id == current_user.company_id)
        .options(joinedload(WorkOrder.bom).joinedload(BillOfMaterial.items))
    )
    wo = result.unique().scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")

    items = []
    all_available = True

    for bom_item in wo.bom.items:
        # Get total available across all warehouses for this company
        bal_result = await db.execute(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
            .where(
                InventoryBalance.company_id == current_user.company_id,
                InventoryBalance.product_id == bom_item.product_id,
            )
        )
        available_qty = bal_result.scalar() or 0

        # Account for scrap in required quantity
        scrap_mult = 1 + (bom_item.scrap_percent / 100)
        required_qty = bom_item.quantity * wo.planned_quantity * scrap_mult
        short_qty = max(0, required_qty - available_qty)
        is_avail = short_qty == 0
        if not is_avail:
            all_available = False

        # Get product name
        prod_result = await db.execute(
            select(Product).where(Product.id == bom_item.product_id)
        )
        prod = prod_result.scalar_one_or_none()

        items.append(ComponentAvailabilityItem(
            product_id=bom_item.product_id,
            product_name=prod.name if prod else "Unknown",
            product_sku=prod.sku if prod else "N/A",
            required_quantity=required_qty,
            available_quantity=available_qty,
            short_quantity=short_qty,
            is_available=is_avail,
        ))

    return ResponseBase(data=ComponentAvailabilityResponse(
        work_order_id=wo_id,
        items=items,
        all_available=all_available,
    ))


# ── Production Reservations ────────────────────────────────────────────────────

@router.get("/work-orders/{wo_id}/reservations", response_model=ResponseBase[list[ProductionReservationResponse]])
async def list_reservations(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    result = await db.execute(
        select(ProductionReservation).where(
            ProductionReservation.work_order_id == wo_id,
            ProductionReservation.company_id == current_user.company_id,
        )
    )
    reservations = result.scalars().all()
    return ResponseBase(data=[ProductionReservationResponse.model_validate(r) for r in reservations])


@router.post("/work-orders/{wo_id}/reservations", response_model=ResponseBase[ProductionReservationResponse], status_code=201)
async def create_reservation(
    wo_id: UUID,
    data: ProductionReservationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Reserve materials from warehouse for a work order."""
    # Verify work order
    wo_result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == wo_id,
            WorkOrder.company_id == current_user.company_id,
        )
    )
    if not wo_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")

    # Check warehouse balance
    bal_result = await db.execute(
        select(InventoryBalance).where(
            InventoryBalance.company_id == current_user.company_id,
            InventoryBalance.warehouse_id == data.warehouse_id,
            InventoryBalance.product_id == data.product_id,
        )
    )
    balance = bal_result.scalar_one_or_none()
    available = balance.quantity if balance else 0
    if available < data.quantity_reserved:
        raise HTTPException(
            status_code=400,
            detail=f"არასაკმარისი მარაგი. ხელმისაწვდომია: {available}, მოთხოვნილია: {data.quantity_reserved}",
        )

    reservation = ProductionReservation(
        company_id=current_user.company_id,
        work_order_id=wo_id,
        **data.model_dump(),
    )
    db.add(reservation)
    await db.flush()
    await db.refresh(reservation)
    return ResponseBase(data=ProductionReservationResponse.model_validate(reservation))


# ── Finished Goods Receipt ──────────────────────────────────────────────────────

@router.get("/work-orders/{wo_id}/receipts", response_model=ResponseBase[list[FinishedGoodsReceiptResponse]])
async def list_receipts(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    result = await db.execute(
        select(FinishedGoodsReceipt).where(
            FinishedGoodsReceipt.work_order_id == wo_id,
            FinishedGoodsReceipt.company_id == current_user.company_id,
        )
    )
    receipts = result.scalars().all()
    return ResponseBase(data=[FinishedGoodsReceiptResponse.model_validate(r) for r in receipts])


@router.post("/work-orders/{wo_id}/receipts", response_model=ResponseBase[FinishedGoodsReceiptResponse], status_code=201)
async def create_finished_goods_receipt(
    wo_id: UUID,
    data: FinishedGoodsReceiptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Receive finished goods from a work order into warehouse."""
    # Verify work order
    wo_result = await db.execute(
        select(WorkOrder).where(
            WorkOrder.id == wo_id,
            WorkOrder.company_id == current_user.company_id,
        )
    )
    wo = wo_result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")

    if wo.status not in (WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.COMPLETED):
        raise HTTPException(status_code=400, detail="მიღება შესაძლებელია მხოლოდ მიმდინარე ან დასრულებული ორდერისთვის")

    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="რაოდენობა დადებითი უნდა იყოს")
    if data.product_id != wo.product_id:
        raise HTTPException(
            status_code=400,
            detail="მიღებული პროდუქტი არ ემთხვევა სამუშაო ორდერის პროდუქტს",
        )
    warehouse = (
        await db.execute(
            select(Warehouse).where(
                Warehouse.id == data.warehouse_id,
                Warehouse.company_id == current_user.company_id,
                Warehouse.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if warehouse is None:
        raise HTTPException(status_code=404, detail="საწყობი არ მოიძებნა")

    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    receipt_number = await allocate_document_number(db, current_user.company_id, "fg_receipt", "FGR")

    payload = data.model_dump(exclude={"work_order_id"})
    receipt = FinishedGoodsReceipt(
        company_id=current_user.company_id,
        work_order_id=wo_id,
        receipt_number=receipt_number,
        created_by=current_user.id,
        **payload,
    )
    db.add(receipt)

    # Update inventory balance
    bal_result = await db.execute(
        select(InventoryBalance).where(
            InventoryBalance.company_id == current_user.company_id,
            InventoryBalance.warehouse_id == data.warehouse_id,
            InventoryBalance.product_id == data.product_id,
        )
        .with_for_update()
    )
    balance = bal_result.scalar_one_or_none()
    if balance:
        balance.quantity += data.quantity
    else:
        balance = InventoryBalance(
            company_id=current_user.company_id,
            warehouse_id=data.warehouse_id,
            product_id=data.product_id,
            quantity=data.quantity,
        )
        db.add(balance)

    # Record inventory movement
    movement = InventoryMovement(
        company_id=current_user.company_id,
        warehouse_id=data.warehouse_id,
        product_id=data.product_id,
        movement_type="in",
        quantity=data.quantity,
        balance_after=(balance.quantity if balance else data.quantity),
        reason="production_receipt",
        notes=f"Finished goods receipt {receipt_number} for WO {wo.order_number}",
        reference=f"FGR:{receipt_number}",
        created_by=current_user.id,
    )
    db.add(movement)
    await sync_product_current_stock(
        db,
        company_id=current_user.company_id,
        product_id=data.product_id,
    )

    # Update work order completed quantity
    wo.completed_quantity += data.quantity
    if wo.completed_quantity >= wo.planned_quantity and wo.status == WorkOrder.Status.IN_PROGRESS:
        wo.status = WorkOrder.Status.COMPLETED

    # ── Production 2.0: backflush component consumption + WIP + GL ──
    bom_result = await db.execute(
        select(BillOfMaterial)
        .options(joinedload(BillOfMaterial.items))
        .where(BillOfMaterial.id == wo.bom_id)
    )
    bom = bom_result.unique().scalar_one_or_none()
    consumed_material_cost = Decimal("0")
    if bom:
        for item in (bom.items or []):
            scrap_mult = Decimal("1") + (item.scrap_percent or Decimal("0")) / Decimal("100")
            need = item.quantity * data.quantity * scrap_mult
            # take from the receipt warehouse balance first (fallback: any warehouse)
            bal = (await db.execute(
                select(InventoryBalance)
                .where(
                    InventoryBalance.company_id == current_user.company_id,
                    InventoryBalance.product_id == item.product_id,
                    InventoryBalance.warehouse_id == data.warehouse_id,
                )
                .with_for_update()
            )).scalar_one_or_none()
            if bal is None or bal.quantity < need:
                bal = (await db.execute(
                    select(InventoryBalance)
                    .where(
                        InventoryBalance.company_id == current_user.company_id,
                        InventoryBalance.product_id == item.product_id,
                        InventoryBalance.quantity >= need,
                    )
                    .with_for_update()
                    .order_by(InventoryBalance.quantity.desc())
                    .limit(1)
                )).scalar_one_or_none()
            if bal is None or bal.quantity < need:
                raise HTTPException(
                    status_code=409,
                    detail=f"კომპონენტის საკმარისი ნაშთი არ არის: {item.product_id} (საჭიროა {need})",
                )
            bal.quantity = bal.quantity - need
            unit_cost = item.unit_cost or Decimal("0")
            total_cost = unit_cost * need
            consumed_material_cost += total_cost
            db.add(WorkOrderConsumption(
                company_id=current_user.company_id,
                work_order_id=wo_id,
                product_id=item.product_id,
                warehouse_id=bal.warehouse_id,
                quantity=need,
                unit_cost=unit_cost,
                total_cost=total_cost,
                is_backflush=True,
            ))
            db.add(InventoryMovement(
                company_id=current_user.company_id,
                warehouse_id=bal.warehouse_id,
                product_id=item.product_id,
                movement_type="out",
                quantity=-need,
                balance_after=bal.quantity,
                reason="production_consumption",
                notes=f"Backflush {receipt_number} WO {wo.order_number}",
                reference=f"FGR:{receipt_number}",
                created_by=current_user.id,
            ))
            # mark reservation consumed
            res = (await db.execute(
                select(ProductionReservation)
                .where(
                    ProductionReservation.work_order_id == wo_id,
                    ProductionReservation.product_id == item.product_id,
                    ProductionReservation.status != "consumed",
                )
                .limit(1)
            )).scalar_one_or_none()
            if res:
                res.quantity_consumed = res.quantity_consumed + need
                if res.quantity_consumed >= res.quantity_reserved:
                    res.status = "consumed"
                else:
                    res.status = "partially_consumed"
            await sync_product_current_stock(db, company_id=current_user.company_id, product_id=item.product_id)

    # WIP: material + labor + overhead vs estimate
    labor_cost = bom.labor_cost if bom else Decimal("0")
    overhead_cost = bom.overhead_cost if bom else Decimal("0")
    total_cost_value = consumed_material_cost + labor_cost + overhead_cost
    estimated = wo.planned_quantity * ((bom.labor_cost + bom.overhead_cost) if bom else 0)
    wip = (await db.execute(select(WorkOrderWip).where(WorkOrderWip.work_order_id == wo_id))).scalar_one_or_none()
    if wip is None:
        wip = WorkOrderWip(
            company_id=current_user.company_id,
            work_order_id=wo_id,
            material_cost=consumed_material_cost,
            labor_cost=labor_cost,
            overhead_cost=overhead_cost,
            total_cost=total_cost_value,
            estimated_cost=estimated,
            variance=total_cost_value - estimated,
        )
        db.add(wip)
    else:
        wip.material_cost = wip.material_cost + consumed_material_cost
        wip.labor_cost = labor_cost
        wip.overhead_cost = overhead_cost
        wip.total_cost = wip.material_cost + wip.labor_cost + wip.overhead_cost
        wip.variance = wip.total_cost - wip.estimated_cost

    # GL: finish production — Dr 1200 finished goods, Cr 1210 WIP (material+labor+overhead)
    if total_cost_value > 0:
        try:
            from app.services.gl_posting import post_journal_entry
            await post_journal_entry(
                db,
                current_user.company_id,
                current_user,
                entry_date=date.today(),
                description=f"წარმოების დასრულება — {wo.order_number} ({data.quantity} ერთ.)",
                reference_type="production_receipt",
                reference_id=receipt.id,
                lines=[
                    ("1200", total_cost_value, Decimal("0")),
                    ("1210", Decimal("0"), total_cost_value),
                ],
            )
        except Exception:
            # WIP ანგარიში ჯერ არ არსებობს ძველ კომპანიებში → GL-ის გარეშე ვაგრძელებთ, ჩამოწერა მაინც სწორია
            pass

    await db.flush()
    await db.refresh(receipt)
    return ResponseBase(data=FinishedGoodsReceiptResponse.model_validate(receipt))


# ═════════════════════════════════════════════════════════════════════════════
# Production 2.0 — routings, operations (actual labor), capacity, consumption,
# scrap/by-products, WIP, genealogy, MRP, downtime windows
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/routings", response_model=ResponseBase[list[RoutingResponse]])
async def list_routings(
    product_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    q = select(Routing).where(Routing.company_id == current_user.company_id)
    if product_id:
        q = q.where(Routing.product_id == product_id)
    rows = (await db.execute(q.options(joinedload(Routing.operations)).order_by(Routing.code))).unique().scalars().all()
    return ResponseBase(data=[RoutingResponse.model_validate(r) for r in rows])


@router.post("/routings", response_model=ResponseBase[RoutingResponse], status_code=201)
async def create_routing(
    data: RoutingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    r = Routing(company_id=current_user.company_id, **data.model_dump())
    db.add(r)
    await db.flush()
    await db.refresh(r)
    return ResponseBase(data=RoutingResponse.model_validate(r), message="მარშრუტი შეიქმნა")


@router.post("/routings/{routing_id}/operations", response_model=ResponseBase[RoutingOperationResponse], status_code=201)
async def add_routing_operation(
    routing_id: UUID,
    data: RoutingOperationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    r = (await db.execute(select(Routing).where(
        Routing.id == routing_id, Routing.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="მარშრუტი არ მოიძებნა")
    op = RoutingOperation(company_id=current_user.company_id, routing_id=routing_id, **data.model_dump())
    db.add(op)
    await db.flush()
    await db.refresh(op)
    return ResponseBase(data=RoutingOperationResponse.model_validate(op), message="ოპერაცია დაემატა")


@router.post("/work-orders/{wo_id}/routing", status_code=201, response_model=ResponseBase[list[WorkOrderOperationResponse]])
async def apply_routing_to_work_order(
    wo_id: UUID,
    routing_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Copy a routing's operations onto a work order (scheduling baseline)."""
    wo = (await db.execute(select(WorkOrder).where(
        WorkOrder.id == wo_id, WorkOrder.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")
    rops = (await db.execute(select(RoutingOperation).where(
        RoutingOperation.routing_id == routing_id, RoutingOperation.company_id == current_user.company_id,
    ).order_by(RoutingOperation.sequence))).scalars().all()
    created = []
    for op in rops:
        wo_op = WorkOrderOperation(
            company_id=current_user.company_id,
            work_order_id=wo_id,
            sequence=op.sequence,
            name=op.name,
            work_center_id=op.work_center_id,
            standard_minutes=op.standard_time_minutes,
            actual_minutes=Decimal("0"),
            actual_labor_cost=Decimal("0"),
            status="pending",
        )
        db.add(wo_op)
        created.append(wo_op)
    await db.flush()
    return ResponseBase(data=[WorkOrderOperationResponse.model_validate(o) for o in created], message="მარშრუტი გადაეცა ორდერს")


@router.get("/work-orders/{wo_id}/operations", response_model=ResponseBase[list[WorkOrderOperationResponse]])
async def list_work_order_operations(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    rows = (await db.execute(select(WorkOrderOperation).where(
        WorkOrderOperation.work_order_id == wo_id, WorkOrderOperation.company_id == current_user.company_id,
    ).order_by(WorkOrderOperation.sequence))).scalars().all()
    return ResponseBase(data=[WorkOrderOperationResponse.model_validate(r) for r in rows])


@router.post("/work-orders/{wo_id}/operations/{op_id}/start", response_model=ResponseBase[WorkOrderOperationResponse])
async def start_work_order_operation(
    wo_id: UUID,
    op_id: UUID,
    data: WorkOrderOperationStart,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    op = (await db.execute(select(WorkOrderOperation).where(
        WorkOrderOperation.id == op_id,
        WorkOrderOperation.work_order_id == wo_id,
        WorkOrderOperation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not op:
        raise HTTPException(status_code=404, detail="ოპერაცია არ მოიძებნა")
    if op.status != "pending":
        raise HTTPException(status_code=409, detail="ოპერაცია უკვე მიმდინარე/დასრულებულია")
    op.status = "in_progress"
    op.started_at = utc_now()
    if data.work_center_id:
        op.work_center_id = data.work_center_id
    if data.notes:
        op.notes = data.notes
    await db.flush()
    await db.refresh(op)
    return ResponseBase(data=WorkOrderOperationResponse.model_validate(op), message="ოპერაცია დაიწყო")


@router.post("/work-orders/{wo_id}/operations/{op_id}/complete", response_model=ResponseBase[WorkOrderOperationResponse])
async def complete_work_order_operation(
    wo_id: UUID,
    op_id: UUID,
    data: WorkOrderOperationComplete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Complete an operation, recording actual labor time and cost → WIP labor."""
    op = (await db.execute(select(WorkOrderOperation).where(
        WorkOrderOperation.id == op_id,
        WorkOrderOperation.work_order_id == wo_id,
        WorkOrderOperation.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not op:
        raise HTTPException(status_code=404, detail="ოპერაცია არ მოიძებნა")
    op.actual_minutes = data.actual_minutes
    op.status = "done"
    op.finished_at = utc_now()
    # actual labor cost = actual hours × work-center hourly rate
    rate = Decimal("0")
    if op.work_center_id:
        wc = (await db.execute(select(WorkCenter).where(WorkCenter.id == op.work_center_id))).scalar_one_or_none()
        rate = wc.hourly_rate if wc else Decimal("0")
    op.actual_labor_cost = (op.actual_minutes / Decimal("60")) * rate
    # accumulate into WIP
    wip = (await db.execute(select(WorkOrderWip).where(WorkOrderWip.work_order_id == wo_id))).scalar_one_or_none()
    if wip is None:
        wip = WorkOrderWip(company_id=current_user.company_id, work_order_id=wo_id)
        db.add(wip)
    wip.labor_cost = wip.labor_cost + op.actual_labor_cost
    wip.total_cost = wip.material_cost + wip.labor_cost + wip.overhead_cost
    wip.variance = wip.total_cost - wip.estimated_cost
    if data.notes:
        op.notes = data.notes
    await db.flush()
    await db.refresh(op)
    return ResponseBase(data=WorkOrderOperationResponse.model_validate(op), message="ოპერაცია დასრულდა")


@router.get("/work-orders/{wo_id}/consumptions", response_model=ResponseBase[list[WorkOrderConsumptionResponse]])
async def list_consumptions(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    rows = (await db.execute(select(WorkOrderConsumption).where(
        WorkOrderConsumption.work_order_id == wo_id, WorkOrderConsumption.company_id == current_user.company_id,
    ).order_by(WorkOrderConsumption.consumed_at.desc()))).scalars().all()
    return ResponseBase(data=[WorkOrderConsumptionResponse.model_validate(r) for r in rows])


@router.post("/work-orders/{wo_id}/consumptions", response_model=ResponseBase[WorkOrderConsumptionResponse], status_code=201)
async def add_manual_consumption(
    wo_id: UUID,
    data: WorkOrderConsumptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Manual component consumption (no backflush) — decrements warehouse + product stock."""
    wo = (await db.execute(select(WorkOrder).where(
        WorkOrder.id == wo_id, WorkOrder.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")
    bal = (await db.execute(select(InventoryBalance).where(
        InventoryBalance.company_id == current_user.company_id,
        InventoryBalance.warehouse_id == data.warehouse_id,
        InventoryBalance.product_id == data.product_id,
    ).with_for_update())).scalar_one_or_none()
    if bal is None or bal.quantity < data.quantity:
        raise HTTPException(status_code=409, detail="კომპონენტის საკმარისი ნაშთი არ არის")
    bal.quantity = bal.quantity - data.quantity
    total = data.unit_cost * data.quantity
    c = WorkOrderConsumption(
        company_id=current_user.company_id, work_order_id=wo_id,
        product_id=data.product_id, warehouse_id=data.warehouse_id,
        quantity=data.quantity, unit_cost=data.unit_cost, total_cost=total,
        is_backflush=False,
    )
    db.add(c)
    db.add(InventoryMovement(
        company_id=current_user.company_id, warehouse_id=data.warehouse_id,
        product_id=data.product_id, movement_type="out", quantity=-data.quantity,
        balance_after=bal.quantity, reason="production_consumption_manual",
        notes=f"Manual consumption WO {wo.order_number}", reference=f"WO:{wo_id}",
        created_by=current_user.id,
    ))
    await sync_product_current_stock(db, company_id=current_user.company_id, product_id=data.product_id)
    # WIP material accumulation
    wip_obj = (await db.execute(select(WorkOrderWip).where(WorkOrderWip.work_order_id == wo_id))).scalar_one_or_none()
    if wip_obj is None:
        wip_obj = WorkOrderWip(company_id=current_user.company_id, work_order_id=wo_id)
        db.add(wip_obj)
    wip_obj.material_cost = wip_obj.material_cost + total
    wip_obj.total_cost = wip_obj.material_cost + wip_obj.labor_cost + wip_obj.overhead_cost
    wip_obj.variance = wip_obj.total_cost - wip_obj.estimated_cost
    await db.flush()
    await db.refresh(c)
    return ResponseBase(data=WorkOrderConsumptionResponse.model_validate(c), message="მოხმარება დაფიქსირდა")


@router.get("/work-orders/{wo_id}/wip", response_model=ResponseBase[WorkOrderWipResponse])
async def get_work_order_wip(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    wip = (await db.execute(select(WorkOrderWip).where(
        WorkOrderWip.work_order_id == wo_id, WorkOrderWip.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not wip:
        raise HTTPException(status_code=404, detail="WIP არ მოიძებნა")
    return ResponseBase(data=WorkOrderWipResponse.model_validate(wip))


@router.post("/work-orders/{wo_id}/scrap", response_model=ResponseBase[WorkOrderScrapResponse], status_code=201)
async def add_scrap_or_byproduct(
    wo_id: UUID,
    data: WorkOrderScrapCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Record scrap (waste) or by-product — by-product receives stock into warehouse."""
    wo = (await db.execute(select(WorkOrder).where(
        WorkOrder.id == wo_id, WorkOrder.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")
    total = data.unit_cost * data.quantity
    item = WorkOrderScrapItem(
        company_id=current_user.company_id, work_order_id=wo_id,
        product_id=data.product_id, quantity=data.quantity,
        kind=data.kind, unit_cost=data.unit_cost, total_value=total,
        notes=data.notes,
    )
    db.add(item)
    wo.scrapped_quantity = wo.scrapped_quantity + data.quantity
    if data.kind == "by_product":
        # by-product has salvage value → receive into first warehouse
        wh = (await db.execute(select(Warehouse).where(
            Warehouse.company_id == current_user.company_id, Warehouse.is_active.is_(True),
        ).order_by(Warehouse.is_default.desc()).limit(1))).scalars().first()
        if wh:
            bal = (await db.execute(select(InventoryBalance).where(
                InventoryBalance.company_id == current_user.company_id,
                InventoryBalance.warehouse_id == wh.id,
                InventoryBalance.product_id == data.product_id,
            ).with_for_update())).scalar_one_or_none()
            if bal:
                bal.quantity = bal.quantity + data.quantity
            else:
                db.add(InventoryBalance(company_id=current_user.company_id, warehouse_id=wh.id,
                                        product_id=data.product_id, quantity=data.quantity))
            db.add(InventoryMovement(
                company_id=current_user.company_id, warehouse_id=wh.id,
                product_id=data.product_id, movement_type="in", quantity=data.quantity,
                balance_after=(bal.quantity if bal else data.quantity),
                reason="production_byproduct", notes=f"By-product WO {wo.order_number}",
                reference=f"WO:{wo_id}", created_by=current_user.id,
            ))
            await sync_product_current_stock(db, company_id=current_user.company_id, product_id=data.product_id)
    await db.flush()
    await db.refresh(item)
    return ResponseBase(data=WorkOrderScrapResponse.model_validate(item), message="ჩაიწერა")


@router.get("/work-orders/{wo_id}/genealogy", response_model=ResponseBase[list[GenealogyResponse]])
async def list_genealogy(
    wo_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    rows = (await db.execute(select(ProductionGenealogy).where(
        ProductionGenealogy.work_order_id == wo_id, ProductionGenealogy.company_id == current_user.company_id,
    ).order_by(ProductionGenealogy.created_at.desc()))).scalars().all()
    return ResponseBase(data=[GenealogyResponse.model_validate(r) for r in rows])


@router.post("/work-orders/{wo_id}/genealogy", response_model=ResponseBase[GenealogyResponse], status_code=201)
async def add_genealogy(
    wo_id: UUID,
    data: GenealogyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Traceability: which component lot/serial went into a finished lot/serial."""
    wo = (await db.execute(select(WorkOrder).where(
        WorkOrder.id == wo_id, WorkOrder.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="სამუშაო ორდერი არ მოიძებნა")
    g = ProductionGenealogy(
        company_id=current_user.company_id, work_order_id=wo_id,
        finished_product_id=wo.product_id, finished_lot=data.finished_lot,
        finished_serial=data.finished_serial,
        component_product_id=data.component_product_id,
        component_lot=data.component_lot, component_serial=data.component_serial,
        quantity=data.quantity,
    )
    db.add(g)
    await db.flush()
    await db.refresh(g)
    return ResponseBase(data=GenealogyResponse.model_validate(g), message="გენეალოგია დაფიქსირდა")


@router.post("/mrp/run", response_model=ResponseBase[MrpRunResponse])
async def run_mrp(
    horizon_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    """MRP: explode BOM demand for open work orders, compare with on-hand and
    reserved stock, generate make (in-house) / buy (purchase) suggestions."""
    from datetime import timedelta
    horizon = date.today() + timedelta(days=horizon_days)
    suggestions = []
    make_n = buy_n = 0
    # open work orders within the horizon (demand source)
    wos = (await db.execute(select(WorkOrder).where(
        WorkOrder.company_id == current_user.company_id,
        WorkOrder.status.in_(["draft", "confirmed", "in_progress"]),
    ))).scalars().all()
    seen_products: dict[UUID, Decimal] = {}
    for wo in wos:
        seen_products[wo.product_id] = seen_products.get(wo.product_id, Decimal("0")) + wo.planned_quantity
        # explode components
        bom = (await db.execute(select(BillOfMaterial).options(joinedload(BillOfMaterial.items)).where(
            BillOfMaterial.id == wo.bom_id,
        ))).unique().scalar_one_or_none()
        if bom:
            for item in (bom.items or []):
                scrap_mult = Decimal("1") + (item.scrap_percent or Decimal("0")) / Decimal("100")
                seen_products[item.product_id] = seen_products.get(item.product_id, Decimal("0")) + item.quantity * wo.planned_quantity * scrap_mult
    for pid, demand in seen_products.items():
        on_hand = (await db.execute(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0)).where(
                InventoryBalance.company_id == current_user.company_id, InventoryBalance.product_id == pid,
            )
        )).scalar() or Decimal("0")
        reserved = (await db.execute(
            select(func.coalesce(func.sum(ProductionReservation.quantity_reserved), 0)).where(
                ProductionReservation.company_id == current_user.company_id, ProductionReservation.product_id == pid,
                ProductionReservation.status != "consumed",
            )
        )).scalar() or Decimal("0")
        short = max(Decimal("0"), demand - on_hand - reserved)
        if short > 0:
            kind = "buy"
            # if a BOM produces the product → make; else buy
            has_bom = (await db.execute(select(BillOfMaterial.id).where(
                BillOfMaterial.company_id == current_user.company_id, BillOfMaterial.product_id == pid,
                BillOfMaterial.is_active.is_(True),
            ).limit(1))).scalar_one_or_none()
            if has_bom:
                kind = "make"
            sug = MrpSuggestion(
                company_id=current_user.company_id, product_id=pid, kind=kind,
                demand_qty=demand, on_hand_qty=on_hand, reserved_qty=reserved,
                suggested_qty=short, due_date=horizon, status="open",
            )
            db.add(sug)
            suggestions.append({"product_id": str(pid), "kind": kind, "suggested_qty": float(short)})
            if kind == "make":
                make_n += 1
            else:
                buy_n += 1
    await db.flush()
    return ResponseBase(data=MrpRunResponse(generated=len(suggestions), make_suggestions=make_n, buy_suggestions=buy_n, suggestions=suggestions), message="MRP გაანალიზდა")


@router.get("/mrp/suggestions", response_model=ResponseBase[list[dict]])
async def list_mrp_suggestions(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    q = select(MrpSuggestion).where(MrpSuggestion.company_id == current_user.company_id)
    if status:
        q = q.where(MrpSuggestion.status == status)
    rows = (await db.execute(q.order_by(MrpSuggestion.created_at.desc()).limit(100))).scalars().all()
    ids = {r.product_id for r in rows}
    names = {row[0]: row[1] for row in (await db.execute(select(Product.id, Product.name).where(Product.id.in_(ids)))).all()} if ids else {}
    return ResponseBase(data=[{
        "id": str(r.id), "product_id": str(r.product_id), "product_name": names.get(r.product_id),
        "kind": r.kind, "demand_qty": float(r.demand_qty), "on_hand_qty": float(r.on_hand_qty),
        "reserved_qty": float(r.reserved_qty), "suggested_qty": float(r.suggested_qty),
        "due_date": r.due_date.isoformat() if r.due_date else None, "status": r.status,
    } for r in rows])


@router.post("/maintenance-downtime", response_model=ResponseBase[DowntimeWindowResponse], status_code=201)
async def add_downtime_window(
    data: DowntimeWindowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Planned maintenance/break windows — reduce effective work-center capacity."""
    wc = (await db.execute(select(WorkCenter.id).where(
        WorkCenter.id == data.work_center_id, WorkCenter.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not wc:
        raise HTTPException(status_code=404, detail="სამუშაო ცენტრი არ მოიძებნა")
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="დასრულების დრო უნდა იყოს დაწყებაზე გვიან")
    w = MaintenanceDowntimeWindow(company_id=current_user.company_id, **data.model_dump())
    db.add(w)
    await db.flush()
    await db.refresh(w)
    return ResponseBase(data=DowntimeWindowResponse.model_validate(w), message="დაუნთაიმ ფანჯარა დაფიქსირდა")


@router.get("/maintenance-downtime", response_model=ResponseBase[list[DowntimeWindowResponse]])
async def list_downtime_windows(
    work_center_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    q = select(MaintenanceDowntimeWindow).where(MaintenanceDowntimeWindow.company_id == current_user.company_id)
    if work_center_id:
        q = q.where(MaintenanceDowntimeWindow.work_center_id == work_center_id)
    rows = (await db.execute(q.order_by(MaintenanceDowntimeWindow.start_time.desc()).limit(100))).scalars().all()
    return ResponseBase(data=[DowntimeWindowResponse.model_validate(r) for r in rows])


@router.get("/work-centers/{wc_id}/capacity", response_model=ResponseBase[CapacityResponse])
async def work_center_capacity(
    wc_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_access")),
):
    """Capacity utilization: scheduled operation minutes + downtime windows vs shift capacity."""
    from datetime import datetime as dt
    wc = (await db.execute(select(WorkCenter).where(
        WorkCenter.id == wc_id, WorkCenter.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not wc:
        raise HTTPException(status_code=404, detail="სამუშაო ცენტრი არ მოიძებნა")
    today = date.today()
    d_from = date_from or today
    d_to = date_to or today
    # scheduled minutes: standard minutes of pending/in_progress operations on this center
    sched_min = (await db.execute(
        select(func.coalesce(func.sum(WorkOrderOperation.standard_minutes), 0)).where(
            WorkOrderOperation.work_center_id == wc_id,
            WorkOrderOperation.status.in_(["pending", "in_progress"]),
        )
    )).scalar() or Decimal("0")
    # downtime minutes within window
    down_min = (await db.execute(
        select(func.coalesce(func.sum(func.extract("epoch", MaintenanceDowntimeWindow.end_time - MaintenanceDowntimeWindow.start_time) / 60), 0)).where(
            MaintenanceDowntimeWindow.work_center_id == wc_id,
            MaintenanceDowntimeWindow.company_id == current_user.company_id,
            MaintenanceDowntimeWindow.start_time >= dt.combine(d_from, dt.min.time()),
            MaintenanceDowntimeWindow.end_time <= dt.combine(d_to, dt.max.time()),
        )
    )).scalar() or Decimal("0")
    # capacity model: 1 shift = 480 min, capacity_per_shift units
    total_capacity_min = Decimal("480") * (wc.capacity_per_shift or Decimal("1"))
    available = max(Decimal("0"), total_capacity_min - sched_min - down_min)
    util = (sched_min / total_capacity_min * Decimal("100")) if total_capacity_min > 0 else Decimal("0")
    return ResponseBase(data=CapacityResponse(
        work_center_id=wc.id, work_center_code=wc.code, work_center_name=wc.name,
        capacity_per_shift=wc.capacity_per_shift, scheduled_operations_minutes=sched_min,
        available_minutes=available, utilization_percent=util, downtime_minutes=down_min,
    ))
