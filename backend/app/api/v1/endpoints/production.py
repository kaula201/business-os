"""Production / Manufacturing API: BOM, work orders, work centers, reservations, receipts."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.production import (
    BillOfMaterial, BOMItem, WorkOrder, WorkCenter,
    ProductionReservation, FinishedGoodsReceipt,
)
from app.models.warehouse import InventoryBalance, InventoryMovement
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
)

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

    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    receipt_number = await allocate_document_number(db, current_user.company_id, "fg_receipt", "FGR")

    receipt = FinishedGoodsReceipt(
        company_id=current_user.company_id,
        work_order_id=wo_id,
        receipt_number=receipt_number,
        created_by=current_user.id,
        **data.model_dump(),
    )
    db.add(receipt)

    # Update inventory balance
    bal_result = await db.execute(
        select(InventoryBalance).where(
            InventoryBalance.company_id == current_user.company_id,
            InventoryBalance.warehouse_id == data.warehouse_id,
            InventoryBalance.product_id == data.product_id,
        )
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

    # Update work order completed quantity
    wo.completed_quantity += data.quantity
    if wo.completed_quantity >= wo.planned_quantity and wo.status == WorkOrder.Status.IN_PROGRESS:
        wo.status = WorkOrder.Status.COMPLETED

    await db.flush()
    await db.refresh(receipt)
    return ResponseBase(data=FinishedGoodsReceiptResponse.model_validate(receipt))


# ── Full Production Workflow Demo ──────────────────────────────────────────────

@router.post("/demo/workflow", response_model=ResponseBase[dict])
async def production_workflow_demo(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("production", "can_create")),
):
    """Run a full production workflow: create BOM → create WO → check availability → reserve → receive finished goods."""
    from app.api.v1.endpoints.purchase_orders import allocate_document_number

    company_id = current_user.company_id
    steps = []

    # 1. Find or create a product to use as the finished good
    prod_result = await db.execute(
        select(Product).where(Product.company_id == company_id).limit(1)
    )
    finished_product = prod_result.scalar_one_or_none()
    if not finished_product:
        finished_product = Product(
            company_id=company_id,
            sku="DEMO-FG-001",
            name="Demo Finished Product",
            sale_price=150.0,
            purchase_price=100.0,
            unit="ცალი",
        )
        db.add(finished_product)
        await db.flush()
        await db.refresh(finished_product)
    steps.append(f"✅ Finished product: {finished_product.name} ({finished_product.sku})")

    # 2. Find or create a component product
    comp_result = await db.execute(
        select(Product).where(Product.company_id == company_id).limit(1).offset(1)
    )
    component = comp_result.scalar_one_or_none()
    if not component:
        component = Product(
            company_id=company_id,
            sku="DEMO-COMP-001",
            name="Demo Component Material",
            sale_price=30.0,
            purchase_price=20.0,
            unit="ცალი",
        )
        db.add(component)
        await db.flush()
        await db.refresh(component)
    steps.append(f"✅ Component: {component.name} ({component.sku})")

    # 3. Create a warehouse if none exists
    wh_result = await db.execute(
        select(InventoryBalance.warehouse_id).where(
            InventoryBalance.company_id == company_id
        ).limit(1)
    )
    wh_id = wh_result.scalar_one_or_none()
    if not wh_id:
        from app.models.warehouse import Warehouse
        wh = Warehouse(
            company_id=company_id,
            code="DEMO-WH",
            name="Demo Warehouse",
            is_default=True,
        )
        db.add(wh)
        await db.flush()
        wh_id = wh.id
    steps.append(f"✅ Warehouse ready")

    # 4. Ensure component has stock
    bal_result = await db.execute(
        select(InventoryBalance).where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.warehouse_id == wh_id,
            InventoryBalance.product_id == component.id,
        )
    )
    comp_balance = bal_result.scalar_one_or_none()
    if not comp_balance or comp_balance.quantity < 50:
        if comp_balance:
            comp_balance.quantity = 100
        else:
            comp_balance = InventoryBalance(
                company_id=company_id,
                warehouse_id=wh_id,
                product_id=component.id,
                quantity=100,
            )
            db.add(comp_balance)
        steps.append(f"✅ Stocked component: 100 units")

    # 5. Create BOM
    bom = BillOfMaterial(
        company_id=company_id,
        product_id=finished_product.id,
        code="DEMO-BOM-001",
        name="Demo BOM",
        quantity=1,
        labor_cost=10.0,
        overhead_cost=5.0,
    )
    db.add(bom)
    await db.flush()
    steps.append(f"✅ BOM created: {bom.code}")

    # 6. Add BOM item
    bom_item = BOMItem(
        bom_id=bom.id,
        product_id=component.id,
        quantity=2,
        unit_cost=20.0,
        scrap_percent=5,
    )
    db.add(bom_item)
    await db.flush()
    steps.append(f"✅ BOM item added: {component.name} x2 @ 20.00 (5% scrap)")

    # 7. Create work center
    wc = WorkCenter(
        company_id=company_id,
        code="DEMO-WC-001",
        name="Demo Assembly Line",
        work_center_type="line",
        hourly_rate=25.0,
        capacity_per_shift=100,
    )
    db.add(wc)
    await db.flush()
    steps.append(f"✅ Work center created: {wc.name}")

    # 8. Create work order
    wo_number = await allocate_document_number(db, company_id, "work_order", "WO")
    wo = WorkOrder(
        company_id=company_id,
        bom_id=bom.id,
        work_center_id=wc.id,
        order_number=wo_number,
        product_id=finished_product.id,
        planned_quantity=10,
        yield_percent=95,
        status=WorkOrder.Status.DRAFT,
    )
    db.add(wo)
    await db.flush()
    steps.append(f"✅ Work order created: {wo.order_number} (qty: 10)")

    # 9. Confirm the work order
    wo.status = WorkOrder.Status.CONFIRMED
    steps.append(f"✅ Work order confirmed")

    # 10. Check component availability
    scrap_mult = 1 + (bom_item.scrap_percent / 100)
    required_qty = bom_item.quantity * wo.planned_quantity * scrap_mult
    steps.append(f"✅ Availability check: need {required_qty}, have 100 — {'OK' if 100 >= required_qty else 'SHORT'}")

    # 11. Reserve materials
    reservation = ProductionReservation(
        company_id=company_id,
        work_order_id=wo.id,
        product_id=component.id,
        warehouse_id=wh_id,
        quantity_reserved=required_qty,
    )
    db.add(reservation)
    await db.flush()
    steps.append(f"✅ Reserved {required_qty} units of {component.name}")

    # 12. Start production
    wo.status = WorkOrder.Status.IN_PROGRESS
    steps.append(f"✅ Production started")

    # 13. Receive finished goods
    fg_number = await allocate_document_number(db, company_id, "fg_receipt", "FGR")
    receipt = FinishedGoodsReceipt(
        company_id=company_id,
        work_order_id=wo.id,
        product_id=finished_product.id,
        warehouse_id=wh_id,
        quantity=9,  # 10 planned - 1 scrap (10% yield loss)
        unit_cost=45.0,  # (2*20 + 10 labor + 5 overhead) / 1 unit per BOM
        receipt_number=fg_number,
        created_by=current_user.id,
    )
    db.add(receipt)

    # Update inventory for finished goods
    fg_balance_result = await db.execute(
        select(InventoryBalance).where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.warehouse_id == wh_id,
            InventoryBalance.product_id == finished_product.id,
        )
    )
    fg_bal = fg_balance_result.scalar_one_or_none()
    if fg_bal:
        fg_bal.quantity += 9
    else:
        fg_bal = InventoryBalance(
            company_id=company_id,
            warehouse_id=wh_id,
            product_id=finished_product.id,
            quantity=9,
        )
        db.add(fg_bal)

    movement = InventoryMovement(
        company_id=company_id,
        warehouse_id=wh_id,
        product_id=finished_product.id,
        movement_type="in",
        quantity=9,
        balance_after=9,
        reason="production_receipt",
        notes=f"Demo: Finished goods receipt {fg_number} for WO {wo.order_number}",
        reference=f"FGR:{fg_number}",
        created_by=current_user.id,
    )
    db.add(movement)

    wo.completed_quantity = 9
    wo.status = WorkOrder.Status.COMPLETED
    steps.append(f"✅ Received 9 units of {finished_product.name} into warehouse")

    # 14. Cost calculation
    total_material = bom_item.quantity * bom_item.unit_cost
    total_labor = bom.labor_cost
    total_overhead = bom.overhead_cost
    total_cost = total_material + total_labor + total_overhead
    unit_cost = total_cost / bom.quantity
    steps.append(f"✅ Cost: material={total_material}, labor={total_labor}, overhead={total_overhead}, total={total_cost}, unit={unit_cost}")

    await db.flush()

    return ResponseBase(data={
        "workflow": "complete",
        "summary": "Full production workflow executed successfully",
        "steps": steps,
        "bom_id": str(bom.id),
        "work_order_id": str(wo.id),
        "receipt_id": str(receipt.id),
    })
