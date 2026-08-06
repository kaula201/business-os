import json
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.audit import AuditLog
from app.models.order import InventoryReservation, Order, OrderFulfillment
from app.models.product import Product
from app.models.purchase import GoodsReceipt, PurchaseOrder
from app.models.user import User
from app.models.warehouse import (
    InventoryBalance,
    InventoryCount,
    InventoryCountLine,
    InventoryMovement,
    ProductBatch,
    Warehouse,
    WarehouseZone,
    ZoneBalance,
)
from app.schemas.common import ResponseBase
from app.schemas.warehouse import (
    InventoryBalanceResponse,
    InventoryCountCreate,
    InventoryCountLineCreate,
    InventoryCountLineResponse,
    InventoryCountLineUpdate,
    InventoryCountPostResult,
    InventoryCountResponse,
    InventoryCountUpdate,
    InventoryMovementResponse,
    StockTransferCreate,
    StockTransferResponse,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseStockAdjustment,
    WarehouseUpdate,
    WarehouseZoneCreate,
    WarehouseZoneResponse,
    WarehouseZoneUpdate,
    ZoneBalanceResponse,
)
from app.services.inventory import sync_product_current_stock

router = APIRouter(prefix="/warehouses", tags=["საწყობები"])


async def get_active_reserved_quantity(
    db: AsyncSession, company_id: UUID, warehouse_id: UUID, product_id: UUID
) -> Decimal:
    reserved = (
        await db.execute(
            select(func.coalesce(func.sum(InventoryReservation.quantity), 0)).where(
                InventoryReservation.company_id == company_id,
                InventoryReservation.warehouse_id == warehouse_id,
                InventoryReservation.product_id == product_id,
                InventoryReservation.status == "active",
            )
        )
    ).scalar_one()
    return Decimal(reserved)


async def reject_batch_tracked_generic_write(
    db: AsyncSession, company_id: UUID, warehouse_id: UUID, product_id: UUID
) -> None:
    """Prevent canonical stock writes that bypass lot-level synchronization."""
    has_batch = await db.scalar(
        select(ProductBatch.id).where(
            ProductBatch.company_id == company_id,
            ProductBatch.warehouse_id == warehouse_id,
            ProductBatch.product_id == product_id,
        ).limit(1)
    )
    if has_batch:
        raise HTTPException(
            status_code=409,
            detail="პარტიებად აღრიცხული მარაგი შეცვალეთ WMS batch ოპერაციით",
        )


def add_warehouse_audit(
    db: AsyncSession,
    current_user: User,
    action: str,
    warehouse_id: UUID,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            action=action,
            entity_type="warehouse",
            entity_id=warehouse_id,
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


async def get_company_warehouse(
    db: AsyncSession, warehouse_id: UUID, company_id: UUID
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
        raise HTTPException(status_code=404, detail="საწყობი არ მოიძებნა")
    return warehouse


async def get_company_product(
    db: AsyncSession, product_id: UUID, company_id: UUID
) -> Product:
    product = (
        await db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.company_id == company_id,
                Product.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
    return product


async def get_locked_balance(
    db: AsyncSession,
    company_id: UUID,
    warehouse_id: UUID,
    product_id: UUID,
) -> InventoryBalance | None:
    result = await db.execute(
        select(InventoryBalance)
        .where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.warehouse_id == warehouse_id,
            InventoryBalance.product_id == product_id,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def get_locked_zone_balance(
    db: AsyncSession,
    company_id: UUID,
    zone_id: UUID,
    product_id: UUID,
) -> ZoneBalance | None:
    result = await db.execute(
        select(ZoneBalance)
        .where(
            ZoneBalance.company_id == company_id,
            ZoneBalance.zone_id == zone_id,
            ZoneBalance.product_id == product_id,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


# ── Warehouse CRUD ─────────────────────────────────────────────────────────────

@router.get("/", response_model=ResponseBase[list[WarehouseResponse]])
async def list_warehouses(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Warehouse).where(
        Warehouse.company_id == current_user.company_id,
    )
    if not include_inactive:
        query = query.where(Warehouse.is_active.is_(True))
    result = await db.execute(
        query.order_by(
            Warehouse.is_active.desc(), Warehouse.is_default.desc(), Warehouse.name
        )
    )
    return ResponseBase(
        data=[WarehouseResponse.model_validate(item) for item in result.scalars().all()]
    )


@router.post("/", response_model=ResponseBase[WarehouseResponse])
async def create_warehouse(
    data: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized_code = data.code.strip().upper()
    duplicate = (
        await db.execute(
            select(Warehouse.id).where(
                Warehouse.company_id == current_user.company_id,
                Warehouse.code == normalized_code,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="ამ კოდით საწყობი უკვე არსებობს")

    if data.is_default:
        await db.execute(
            update(Warehouse)
            .where(Warehouse.company_id == current_user.company_id)
            .values(is_default=False)
        )

    warehouse = Warehouse(
        company_id=current_user.company_id,
        code=normalized_code,
        name=data.name.strip(),
        address=data.address,
        is_default=data.is_default,
    )
    db.add(warehouse)
    await db.flush()
    await db.refresh(warehouse)
    add_warehouse_audit(
        db,
        current_user,
        "warehouse.created",
        warehouse.id,
        {"code": warehouse.code, "name": warehouse.name, "is_default": warehouse.is_default},
    )
    return ResponseBase(data=WarehouseResponse.model_validate(warehouse))


@router.patch("/{warehouse_id}", response_model=ResponseBase[WarehouseResponse])
async def update_warehouse(
    warehouse_id: UUID,
    data: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    warehouse = await get_company_warehouse(db, warehouse_id, current_user.company_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="ცვლილება არ არის მითითებული")

    if "code" in changes:
        normalized_code = changes["code"].strip().upper()
        duplicate = (
            await db.execute(
                select(Warehouse.id).where(
                    Warehouse.company_id == current_user.company_id,
                    Warehouse.code == normalized_code,
                    Warehouse.id != warehouse.id,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(status_code=409, detail="ამ კოდით საწყობი უკვე არსებობს")
        changes["code"] = normalized_code
    if "name" in changes:
        changes["name"] = changes["name"].strip()

    before = {field: getattr(warehouse, field) for field in changes}
    for field, value in changes.items():
        setattr(warehouse, field, value)
    await db.flush()
    await db.refresh(warehouse)
    add_warehouse_audit(
        db,
        current_user,
        "warehouse.updated",
        warehouse.id,
        {"before": before, "after": changes},
    )
    return ResponseBase(data=WarehouseResponse.model_validate(warehouse))


@router.post(
    "/{warehouse_id}/set-default", response_model=ResponseBase[WarehouseResponse]
)
async def set_default_warehouse(
    warehouse_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    warehouse = await get_company_warehouse(db, warehouse_id, current_user.company_id)
    previous_default = (
        await db.execute(
            select(Warehouse.id).where(
                Warehouse.company_id == current_user.company_id,
                Warehouse.is_default.is_(True),
            )
        )
    ).scalar_one_or_none()
    await db.execute(
        update(Warehouse)
        .where(
            Warehouse.company_id == current_user.company_id,
            Warehouse.id != warehouse.id,
        )
        .values(is_default=False)
    )
    warehouse.is_default = True
    await db.flush()
    await db.refresh(warehouse)
    add_warehouse_audit(
        db,
        current_user,
        "warehouse.default_changed",
        warehouse.id,
        {"previous_default_id": previous_default, "new_default_id": warehouse.id},
    )
    return ResponseBase(data=WarehouseResponse.model_validate(warehouse))


@router.post("/{warehouse_id}/archive", response_model=ResponseBase[WarehouseResponse])
async def archive_warehouse(
    warehouse_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    warehouse = await get_company_warehouse(db, warehouse_id, current_user.company_id)
    if warehouse.is_default:
        raise HTTPException(
            status_code=409,
            detail="მთავარი საწყობის დეაქტივაციამდე სხვა საწყობი მონიშნეთ მთავარ საწყობად",
        )
    non_zero_balances = (
        await db.execute(
            select(func.count(InventoryBalance.id)).where(
                InventoryBalance.company_id == current_user.company_id,
                InventoryBalance.warehouse_id == warehouse.id,
                InventoryBalance.quantity != Decimal("0"),
            )
        )
    ).scalar() or 0
    if non_zero_balances:
        raise HTTPException(
            status_code=409,
            detail="საწყობში ნაშთია. დეაქტივაციამდე ნაშთი სხვა საწყობში გადაიტანეთ",
        )
    active_order_count = (
        await db.execute(
            select(func.count(OrderFulfillment.id))
            .join(Order, Order.id == OrderFulfillment.order_id)
            .where(
                OrderFulfillment.company_id == current_user.company_id,
                OrderFulfillment.warehouse_id == warehouse.id,
                Order.status.in_(["draft", "confirmed", "preparing", "shipping"]),
            )
        )
    ).scalar() or 0
    if active_order_count:
        raise HTTPException(
            status_code=409,
            detail="საწყობი აქტიურ შეკვეთებში გამოიყენება და ვერ დეაქტივირდება",
        )
    active_purchase_order_count = (
        await db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.company_id == current_user.company_id,
                PurchaseOrder.warehouse_id == warehouse.id,
                PurchaseOrder.status.in_(["draft", "approved", "partially_received"]),
            )
        )
    ).scalar() or 0
    if active_purchase_order_count:
        raise HTTPException(
            status_code=409,
            detail="საწყობი აქტიურ Purchase Order-ში გამოიყენება და ვერ დეაქტივირდება",
        )

    warehouse.is_active = False
    await db.flush()
    await db.refresh(warehouse)
    add_warehouse_audit(
        db,
        current_user,
        "warehouse.archived",
        warehouse.id,
        {"code": warehouse.code, "name": warehouse.name},
    )
    return ResponseBase(data=WarehouseResponse.model_validate(warehouse))


@router.delete("/{warehouse_id}", response_model=ResponseBase[dict])
async def delete_warehouse(
    warehouse_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_delete")),
):
    warehouse = await get_company_warehouse(db, warehouse_id, current_user.company_id)
    if warehouse.is_default:
        raise HTTPException(
            status_code=409,
            detail="მთავარი საწყობის წაშლამდე სხვა საწყობი მონიშნეთ მთავარ საწყობად",
        )

    balance_count = (
        await db.execute(
            select(func.count(InventoryBalance.id)).where(
                InventoryBalance.company_id == current_user.company_id,
                InventoryBalance.warehouse_id == warehouse.id,
            )
        )
    ).scalar() or 0
    movement_count = (
        await db.execute(
            select(func.count(InventoryMovement.id)).where(
                InventoryMovement.company_id == current_user.company_id,
                or_(
                    InventoryMovement.warehouse_id == warehouse.id,
                    InventoryMovement.destination_warehouse_id == warehouse.id,
                ),
            )
        )
    ).scalar() or 0
    order_reference_count = (
        await db.execute(
            select(func.count(OrderFulfillment.id)).where(
                OrderFulfillment.company_id == current_user.company_id,
                OrderFulfillment.warehouse_id == warehouse.id,
            )
        )
    ).scalar() or 0
    reservation_count = (
        await db.execute(
            select(func.count(InventoryReservation.id)).where(
                InventoryReservation.company_id == current_user.company_id,
                InventoryReservation.warehouse_id == warehouse.id,
            )
        )
    ).scalar() or 0
    purchase_order_count = (
        await db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.company_id == current_user.company_id,
                PurchaseOrder.warehouse_id == warehouse.id,
            )
        )
    ).scalar() or 0
    goods_receipt_count = (
        await db.execute(
            select(func.count(GoodsReceipt.id)).where(
                GoodsReceipt.company_id == current_user.company_id,
                GoodsReceipt.warehouse_id == warehouse.id,
            )
        )
    ).scalar() or 0
    if purchase_order_count or goods_receipt_count:
        raise HTTPException(
            status_code=409,
            detail="საწყობი შესყიდვების ისტორიაში გამოიყენება. გამოიყენეთ დეაქტივაცია",
        )
    if order_reference_count or reservation_count:
        raise HTTPException(
            status_code=409,
            detail="საწყობი შეკვეთების ისტორიაში გამოიყენება. გამოიყენეთ დეაქტივაცია",
        )
    if balance_count or movement_count:
        raise HTTPException(
            status_code=409,
            detail="საწყობს ოპერაციების ისტორია აქვს. გამოიყენეთ დეაქტივაცია",
        )

    add_warehouse_audit(
        db,
        current_user,
        "warehouse.deleted",
        warehouse.id,
        {"code": warehouse.code, "name": warehouse.name},
    )
    await db.delete(warehouse)
    await db.flush()
    return ResponseBase(data={"message": "საწყობი წაიშალა"})


# ── Balances (with reserved/available/on-hand) ─────────────────────────────────

@router.get("/balances", response_model=ResponseBase[list[InventoryBalanceResponse]])
async def list_balances(
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(InventoryBalance, Warehouse, Product)
        .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
        .join(Product, Product.id == InventoryBalance.product_id)
        .where(InventoryBalance.company_id == current_user.company_id)
    )
    if product_id:
        query = query.where(InventoryBalance.product_id == product_id)
    if warehouse_id:
        query = query.where(InventoryBalance.warehouse_id == warehouse_id)

    rows = (await db.execute(query.order_by(Warehouse.name, Product.name))).all()
    return ResponseBase(
        data=[
            InventoryBalanceResponse(
                id=balance.id,
                product_id=balance.product_id,
                product_name=product.name,
                warehouse_id=balance.warehouse_id,
                warehouse_name=warehouse.name,
                warehouse_code=warehouse.code,
                quantity=float(balance.quantity),
                reserved_quantity=float(balance.reserved_quantity),
                available_quantity=float(balance.quantity - balance.reserved_quantity),
                updated_at=balance.updated_at,
            )
            for balance, warehouse, product in rows
        ]
    )


# ── Stock Adjustment ───────────────────────────────────────────────────────────

@router.post(
    "/adjust-stock", response_model=ResponseBase[InventoryMovementResponse]
)
async def adjust_warehouse_stock(
    data: WarehouseStockAdjustment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    await get_company_warehouse(
        db, data.warehouse_id, current_user.company_id
    )
    product = await get_company_product(db, data.product_id, current_user.company_id)
    await reject_batch_tracked_generic_write(
        db, current_user.company_id, data.warehouse_id, data.product_id
    )
    balance = await get_locked_balance(
        db, current_user.company_id, data.warehouse_id, data.product_id
    )
    if balance is None:
        balance = InventoryBalance(
            company_id=current_user.company_id,
            warehouse_id=data.warehouse_id,
            product_id=data.product_id,
            quantity=Decimal("0"),
            reserved_quantity=Decimal("0"),
        )
        db.add(balance)
        await db.flush()

    old_quantity = Decimal(balance.quantity)
    old_reserved = Decimal(balance.reserved_quantity)
    quantity = Decimal(str(data.quantity))
    if data.movement_type == "in":
        new_quantity = old_quantity + quantity
    elif data.movement_type == "out":
        if old_quantity < quantity:
            raise HTTPException(status_code=400, detail="საწყობში არასაკმარისი ნაშთია")
        new_quantity = old_quantity - quantity
    else:
        new_quantity = quantity

    active_reserved = await get_active_reserved_quantity(
        db, current_user.company_id, data.warehouse_id, data.product_id
    )
    if new_quantity < active_reserved:
        raise HTTPException(
            status_code=409,
            detail="ოპერაცია დარეზერვებული მარაგის რაოდენობას შეამცირებს",
        )

    balance.quantity = new_quantity
    await sync_product_current_stock(
        db,
        company_id=current_user.company_id,
        product_id=data.product_id,
    )

    # Update zone balance if zone_id provided
    if data.zone_id:
        zone_balance = await get_locked_zone_balance(
            db, current_user.company_id, data.zone_id, data.product_id
        )
        if zone_balance is None:
            zone_balance = ZoneBalance(
                company_id=current_user.company_id,
                zone_id=data.zone_id,
                product_id=data.product_id,
                quantity=Decimal("0"),
            )
            db.add(zone_balance)
            await db.flush()
        if data.movement_type == "in":
            zone_balance.quantity = Decimal(zone_balance.quantity) + quantity
        elif data.movement_type == "out":
            zone_balance.quantity = Decimal(zone_balance.quantity) - quantity
        else:
            zone_balance.quantity = new_quantity

    movement = InventoryMovement(
        company_id=current_user.company_id,
        warehouse_id=data.warehouse_id,
        zone_id=data.zone_id,
        product_id=data.product_id,
        movement_type=data.movement_type,
        quantity=quantity,
        balance_before=old_quantity,
        balance_after=new_quantity,
        reserved_before=old_reserved,
        reserved_after=Decimal(balance.reserved_quantity),
        reason=data.reason,
        reason_category=data.reason_category,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(movement)
    await db.flush()
    await db.refresh(movement)

    return ResponseBase(
        data=InventoryMovementResponse(
            id=movement.id,
            product_id=movement.product_id,
            product_name=product.name,
            warehouse_id=movement.warehouse_id,
            zone_id=movement.zone_id,
            movement_type=movement.movement_type,
            quantity=float(movement.quantity),
            balance_before=float(movement.balance_before) if movement.balance_before is not None else None,
            balance_after=float(movement.balance_after),
            reserved_before=float(movement.reserved_before) if movement.reserved_before is not None else None,
            reserved_after=float(movement.reserved_after) if movement.reserved_after is not None else None,
            reason=movement.reason,
            reason_category=movement.reason_category,
            notes=movement.notes,
            reference=movement.reference,
            reference_type=movement.reference_type,
            created_by=movement.created_by,
            created_at=movement.created_at,
        )
    )


# ── Stock Transfer ──────────────────────────────────────────────────────────────

@router.post("/transfers", response_model=ResponseBase[StockTransferResponse])
async def transfer_stock(
    data: StockTransferCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    await get_company_product(db, data.product_id, current_user.company_id)
    await get_company_warehouse(
        db, data.source_warehouse_id, current_user.company_id
    )
    await get_company_warehouse(
        db, data.destination_warehouse_id, current_user.company_id
    )
    await reject_batch_tracked_generic_write(
        db, current_user.company_id, data.source_warehouse_id, data.product_id
    )

    source = await get_locked_balance(
        db,
        current_user.company_id,
        data.source_warehouse_id,
        data.product_id,
    )
    quantity = Decimal(str(data.quantity))
    if source is None or Decimal(source.quantity) < quantity:
        raise HTTPException(status_code=400, detail="საწყობში არასაკმარისი ნაშთია")
    active_reserved = await get_active_reserved_quantity(
        db,
        current_user.company_id,
        data.source_warehouse_id,
        data.product_id,
    )
    if Decimal(source.quantity) - quantity < active_reserved:
        raise HTTPException(
            status_code=409,
            detail="გადატანა დარეზერვებულ მარაგს შეამცირებს",
        )

    destination = await get_locked_balance(
        db,
        current_user.company_id,
        data.destination_warehouse_id,
        data.product_id,
    )
    if destination is None:
        destination = InventoryBalance(
            company_id=current_user.company_id,
            warehouse_id=data.destination_warehouse_id,
            product_id=data.product_id,
            quantity=Decimal("0"),
            reserved_quantity=Decimal("0"),
        )
        db.add(destination)
        await db.flush()

    source_old_qty = Decimal(source.quantity)
    source_old_reserved = Decimal(source.reserved_quantity)
    dest_old_qty = Decimal(destination.quantity)
    dest_old_reserved = Decimal(destination.reserved_quantity)

    source.quantity = source_old_qty - quantity
    destination.quantity = dest_old_qty + quantity
    reference = f"TRF-{uuid4().hex[:12].upper()}"

    db.add_all(
        [
            InventoryMovement(
                company_id=current_user.company_id,
                warehouse_id=data.source_warehouse_id,
                destination_warehouse_id=data.destination_warehouse_id,
                product_id=data.product_id,
                movement_type="transfer_out",
                quantity=quantity,
                balance_before=source_old_qty,
                balance_after=source.quantity,
                reserved_before=source_old_reserved,
                reserved_after=Decimal(source.reserved_quantity),
                reason=data.reason,
                reason_category=data.reason_category,
                notes=data.notes,
                reference=reference,
                reference_type="transfer",
                created_by=current_user.id,
            ),
            InventoryMovement(
                company_id=current_user.company_id,
                warehouse_id=data.destination_warehouse_id,
                product_id=data.product_id,
                movement_type="transfer_in",
                quantity=quantity,
                balance_before=dest_old_qty,
                balance_after=destination.quantity,
                reserved_before=dest_old_reserved,
                reserved_after=Decimal(destination.reserved_quantity),
                reason=data.reason,
                reason_category=data.reason_category,
                notes=data.notes,
                reference=reference,
                reference_type="transfer",
                created_by=current_user.id,
            ),
        ]
    )
    await db.flush()

    return ResponseBase(
        data=StockTransferResponse(
            reference=reference,
            product_id=data.product_id,
            source_warehouse_id=data.source_warehouse_id,
            destination_warehouse_id=data.destination_warehouse_id,
            quantity=float(quantity),
            source_balance_after=float(source.quantity),
            destination_balance_after=float(destination.quantity),
        )
    )


# ── Movement History ───────────────────────────────────────────────────────────

@router.get("/movements", response_model=ResponseBase[list[InventoryMovementResponse]])
async def list_movements(
    product_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    movement_type: str | None = None,
    reason_category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(InventoryMovement, Product, Warehouse)
        .join(Product, Product.id == InventoryMovement.product_id)
        .join(Warehouse, Warehouse.id == InventoryMovement.warehouse_id)
        .where(InventoryMovement.company_id == current_user.company_id)
    )
    if product_id:
        query = query.where(InventoryMovement.product_id == product_id)
    if warehouse_id:
        query = query.where(InventoryMovement.warehouse_id == warehouse_id)
    if movement_type:
        query = query.where(InventoryMovement.movement_type == movement_type)
    if reason_category:
        query = query.where(InventoryMovement.reason_category == reason_category)
    if date_from:
        query = query.where(InventoryMovement.created_at >= date_from)
    if date_to:
        query = query.where(InventoryMovement.created_at <= date_to)

    rows = (
        await db.execute(
            query.order_by(InventoryMovement.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    return ResponseBase(
        data=[
            InventoryMovementResponse(
                id=mov.id,
                product_id=mov.product_id,
                product_name=product.name,
                warehouse_id=mov.warehouse_id,
                warehouse_name=warehouse.name,
                zone_id=mov.zone_id,
                movement_type=mov.movement_type,
                quantity=float(mov.quantity),
                balance_before=float(mov.balance_before) if mov.balance_before is not None else None,
                balance_after=float(mov.balance_after),
                reserved_before=float(mov.reserved_before) if mov.reserved_before is not None else None,
                reserved_after=float(mov.reserved_after) if mov.reserved_after is not None else None,
                reason=mov.reason,
                reason_category=mov.reason_category,
                notes=mov.notes,
                reference=mov.reference,
                reference_type=mov.reference_type,
                created_by=mov.created_by,
                created_at=mov.created_at,
            )
            for mov, product, warehouse in rows
        ]
    )


# ── Warehouse Zones ────────────────────────────────────────────────────────────

@router.get("/zones", response_model=ResponseBase[list[WarehouseZoneResponse]])
async def list_zones(
    warehouse_id: UUID | None = None,
    zone_type: str | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(WarehouseZone).where(
        WarehouseZone.company_id == current_user.company_id,
    )
    if warehouse_id:
        query = query.where(WarehouseZone.warehouse_id == warehouse_id)
    if zone_type:
        query = query.where(WarehouseZone.zone_type == zone_type)
    if not include_inactive:
        query = query.where(WarehouseZone.is_active.is_(True))

    result = await db.execute(
        query.order_by(WarehouseZone.sort_order, WarehouseZone.code)
    )
    return ResponseBase(
        data=[WarehouseZoneResponse.model_validate(item) for item in result.scalars().all()]
    )


@router.post("/zones", response_model=ResponseBase[WarehouseZoneResponse])
async def create_zone(
    data: WarehouseZoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    await get_company_warehouse(db, data.warehouse_id, current_user.company_id)

    normalized_code = data.code.strip().upper()
    duplicate = (
        await db.execute(
            select(WarehouseZone.id).where(
                WarehouseZone.company_id == current_user.company_id,
                WarehouseZone.warehouse_id == data.warehouse_id,
                WarehouseZone.code == normalized_code,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="ამ კოდით ზონა უკვე არსებობს")

    if data.parent_id:
        parent = (
            await db.execute(
                select(WarehouseZone).where(
                    WarehouseZone.id == data.parent_id,
                    WarehouseZone.company_id == current_user.company_id,
                )
            )
        ).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="მშობელი ზონა არ მოიძებნა")

    zone = WarehouseZone(
        company_id=current_user.company_id,
        warehouse_id=data.warehouse_id,
        parent_id=data.parent_id,
        code=normalized_code,
        name=data.name.strip(),
        zone_type=data.zone_type,
        is_pickable=data.is_pickable,
        sort_order=data.sort_order,
    )
    db.add(zone)
    await db.flush()
    await db.refresh(zone)
    return ResponseBase(data=WarehouseZoneResponse.model_validate(zone))


@router.patch("/zones/{zone_id}", response_model=ResponseBase[WarehouseZoneResponse])
async def update_zone(
    zone_id: UUID,
    data: WarehouseZoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    zone = (
        await db.execute(
            select(WarehouseZone).where(
                WarehouseZone.id == zone_id,
                WarehouseZone.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="ზონა არ მოიძებნა")

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="ცვლილება არ არის მითითებული")

    if "code" in changes:
        changes["code"] = changes["code"].strip().upper()
    if "name" in changes:
        changes["name"] = changes["name"].strip()

    for field, value in changes.items():
        setattr(zone, field, value)
    await db.flush()
    await db.refresh(zone)
    return ResponseBase(data=WarehouseZoneResponse.model_validate(zone))


@router.delete("/zones/{zone_id}", response_model=ResponseBase[dict])
async def delete_zone(
    zone_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_delete")),
):
    zone = (
        await db.execute(
            select(WarehouseZone).where(
                WarehouseZone.id == zone_id,
                WarehouseZone.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="ზონა არ მოიძებნა")

    child_count = (
        await db.execute(
            select(func.count(WarehouseZone.id)).where(
                WarehouseZone.parent_id == zone_id,
            )
        )
    ).scalar() or 0
    if child_count:
        raise HTTPException(
            status_code=409,
            detail="ზონას გააჩნია ქვეზონები. ჯერ წაშალეთ ქვეზონები",
        )

    await db.delete(zone)
    await db.flush()
    return ResponseBase(data={"message": "ზონა წაიშალა"})


# ── Zone Balances ──────────────────────────────────────────────────────────────

@router.get("/zone-balances", response_model=ResponseBase[list[ZoneBalanceResponse]])
async def list_zone_balances(
    zone_id: UUID | None = None,
    product_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(ZoneBalance, WarehouseZone, Product)
        .join(WarehouseZone, WarehouseZone.id == ZoneBalance.zone_id)
        .join(Product, Product.id == ZoneBalance.product_id)
        .where(ZoneBalance.company_id == current_user.company_id)
    )
    if zone_id:
        query = query.where(ZoneBalance.zone_id == zone_id)
    if product_id:
        query = query.where(ZoneBalance.product_id == product_id)

    rows = (await db.execute(query.order_by(WarehouseZone.code, Product.name))).all()
    return ResponseBase(
        data=[
            ZoneBalanceResponse(
                id=zb.id,
                zone_id=zb.zone_id,
                zone_code=zone.code,
                zone_name=zone.name,
                product_id=zb.product_id,
                product_name=product.name,
                quantity=float(zb.quantity),
                updated_at=zb.updated_at,
            )
            for zb, zone, product in rows
        ]
    )


# ── Inventory Counts ───────────────────────────────────────────────────────────

@router.get("/counts", response_model=ResponseBase[list[InventoryCountResponse]])
async def list_counts(
    warehouse_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(InventoryCount, Warehouse)
        .join(Warehouse, Warehouse.id == InventoryCount.warehouse_id)
        .where(InventoryCount.company_id == current_user.company_id)
    )
    if warehouse_id:
        query = query.where(InventoryCount.warehouse_id == warehouse_id)
    if status:
        query = query.where(InventoryCount.status == status)

    rows = (
        await db.execute(
            query.order_by(InventoryCount.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    result = []
    for count, warehouse in rows:
        line_count = (
            await db.execute(
                select(func.count(InventoryCountLine.id)).where(
                    InventoryCountLine.count_id == count.id
                )
            )
        ).scalar() or 0

        total_diff = (
            await db.execute(
                select(func.coalesce(func.sum(InventoryCountLine.difference), 0)).where(
                    InventoryCountLine.count_id == count.id
                )
            )
        ).scalar() or 0

        result.append(
            InventoryCountResponse(
                id=count.id,
                warehouse_id=count.warehouse_id,
                warehouse_name=warehouse.name,
                zone_id=count.zone_id,
                count_number=count.count_number,
                status=count.status,
                count_type=count.count_type,
                notes=count.notes,
                counted_by=count.counted_by,
                approved_by=count.approved_by,
                counted_at=count.counted_at,
                approved_at=count.approved_at,
                line_count=line_count,
                total_difference=float(total_diff),
                created_at=count.created_at,
                updated_at=count.updated_at,
            )
        )

    return ResponseBase(data=result)


@router.post("/counts", response_model=ResponseBase[InventoryCountResponse])
async def create_count(
    data: InventoryCountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    await get_company_warehouse(db, data.warehouse_id, current_user.company_id)

    # Generate count number
    count_seq = (
        await db.execute(
            select(func.count(InventoryCount.id)).where(
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar() or 0
    count_number = f"IC-{count_seq + 1:05d}"

    count = InventoryCount(
        company_id=current_user.company_id,
        warehouse_id=data.warehouse_id,
        zone_id=data.zone_id,
        count_number=count_number,
        status="draft",
        count_type=data.count_type,
        notes=data.notes,
    )
    db.add(count)
    await db.flush()
    await db.refresh(count)

    return ResponseBase(
        data=InventoryCountResponse(
            id=count.id,
            warehouse_id=count.warehouse_id,
            zone_id=count.zone_id,
            count_number=count.count_number,
            status=count.status,
            count_type=count.count_type,
            notes=count.notes,
            counted_by=count.counted_by,
            approved_by=count.approved_by,
            counted_at=count.counted_at,
            approved_at=count.approved_at,
            line_count=0,
            total_difference=0,
            created_at=count.created_at,
            updated_at=count.updated_at,
        )
    )


@router.patch("/counts/{count_id}", response_model=ResponseBase[InventoryCountResponse])
async def update_count(
    count_id: UUID,
    data: InventoryCountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        await db.execute(
            select(InventoryCount).where(
                InventoryCount.id == count_id,
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not count:
        raise HTTPException(status_code=404, detail="ინვენტარიზაცია არ მოიძებნა")

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="ცვლილება არ არის მითითებული")

    if "status" in changes:
        new_status = changes["status"]
        valid_transitions = {
            "draft": ["in_progress", "cancelled"],
            "in_progress": ["completed", "cancelled"],
            "completed": ["posted", "cancelled"],
            "cancelled": ["draft"],
            "posted": [],
        }
        allowed = valid_transitions.get(count.status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=409,
                detail=f"სტატუსის შეცვლა '{count.status}' → '{new_status}' დაუშვებელია",
            )

        if new_status == "completed":
            changes["counted_at"] = func.now()
            changes["counted_by"] = current_user.id
        elif new_status == "posted":
            changes["approved_at"] = func.now()
            changes["approved_by"] = current_user.id

    for field, value in changes.items():
        setattr(count, field, value)
    await db.flush()
    await db.refresh(count)

    # Recalculate totals
    line_count = (
        await db.execute(
            select(func.count(InventoryCountLine.id)).where(
                InventoryCountLine.count_id == count.id
            )
        )
    ).scalar() or 0
    total_diff = (
        await db.execute(
            select(func.coalesce(func.sum(InventoryCountLine.difference), 0)).where(
                InventoryCountLine.count_id == count.id
            )
        )
    ).scalar() or 0

    warehouse = (
        await db.execute(select(Warehouse).where(Warehouse.id == count.warehouse_id))
    ).scalar_one()

    return ResponseBase(
        data=InventoryCountResponse(
            id=count.id,
            warehouse_id=count.warehouse_id,
            warehouse_name=warehouse.name,
            zone_id=count.zone_id,
            count_number=count.count_number,
            status=count.status,
            count_type=count.count_type,
            notes=count.notes,
            counted_by=count.counted_by,
            approved_by=count.approved_by,
            counted_at=count.counted_at,
            approved_at=count.approved_at,
            line_count=line_count,
            total_difference=float(total_diff),
            created_at=count.created_at,
            updated_at=count.updated_at,
        )
    )


@router.get("/counts/{count_id}", response_model=ResponseBase[InventoryCountResponse])
async def get_count(
    count_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        await db.execute(
            select(InventoryCount).where(
                InventoryCount.id == count_id,
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not count:
        raise HTTPException(status_code=404, detail="ინვენტარიზაცია არ მოიძებნა")

    warehouse = (
        await db.execute(select(Warehouse).where(Warehouse.id == count.warehouse_id))
    ).scalar_one()

    line_count = (
        await db.execute(
            select(func.count(InventoryCountLine.id)).where(
                InventoryCountLine.count_id == count.id
            )
        )
    ).scalar() or 0
    total_diff = (
        await db.execute(
            select(func.coalesce(func.sum(InventoryCountLine.difference), 0)).where(
                InventoryCountLine.count_id == count.id
            )
        )
    ).scalar() or 0

    return ResponseBase(
        data=InventoryCountResponse(
            id=count.id,
            warehouse_id=count.warehouse_id,
            warehouse_name=warehouse.name,
            zone_id=count.zone_id,
            count_number=count.count_number,
            status=count.status,
            count_type=count.count_type,
            notes=count.notes,
            counted_by=count.counted_by,
            approved_by=count.approved_by,
            counted_at=count.counted_at,
            approved_at=count.approved_at,
            line_count=line_count,
            total_difference=float(total_diff),
            created_at=count.created_at,
            updated_at=count.updated_at,
        )
    )


# ── Count Lines ────────────────────────────────────────────────────────────────

@router.get(
    "/counts/{count_id}/lines",
    response_model=ResponseBase[list[InventoryCountLineResponse]],
)
async def list_count_lines(
    count_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        await db.execute(
            select(InventoryCount).where(
                InventoryCount.id == count_id,
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not count:
        raise HTTPException(status_code=404, detail="ინვენტარიზაცია არ მოიძებნა")

    query = (
        select(InventoryCountLine, Product)
        .join(Product, Product.id == InventoryCountLine.product_id)
        .where(InventoryCountLine.count_id == count_id)
        .order_by(Product.name)
    )
    rows = (await db.execute(query)).all()

    return ResponseBase(
        data=[
            InventoryCountLineResponse(
                id=line.id,
                count_id=line.count_id,
                product_id=line.product_id,
                product_name=product.name,
                zone_id=line.zone_id,
                expected_quantity=float(line.expected_quantity),
                counted_quantity=float(line.counted_quantity) if line.counted_quantity is not None else None,
                difference=float(line.difference) if line.difference is not None else None,
                notes=line.notes,
                created_at=line.created_at,
            )
            for line, product in rows
        ]
    )


@router.post(
    "/counts/{count_id}/lines",
    response_model=ResponseBase[InventoryCountLineResponse],
)
async def add_count_line(
    count_id: UUID,
    data: InventoryCountLineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    count = (
        await db.execute(
            select(InventoryCount).where(
                InventoryCount.id == count_id,
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not count:
        raise HTTPException(status_code=404, detail="ინვენტარიზაცია არ მოიძებნა")
    if count.status not in ("draft", "in_progress"):
        raise HTTPException(
            status_code=409,
            detail="ხაზის დამატება შესაძლებელია მხოლოდ draft ან in_progress სტატუსზე",
        )

    product = await get_company_product(db, data.product_id, current_user.company_id)

    # Get expected quantity from balance
    balance = (
        await db.execute(
            select(InventoryBalance).where(
                InventoryBalance.company_id == current_user.company_id,
                InventoryBalance.warehouse_id == count.warehouse_id,
                InventoryBalance.product_id == data.product_id,
            )
        )
    ).scalar_one_or_none()
    expected_qty = Decimal(balance.quantity) if balance else Decimal("0")

    counted_qty = Decimal(str(data.counted_quantity))
    difference = counted_qty - expected_qty

    line = InventoryCountLine(
        count_id=count_id,
        product_id=data.product_id,
        zone_id=data.zone_id or count.zone_id,
        expected_quantity=expected_qty,
        counted_quantity=counted_qty,
        difference=difference,
        notes=data.notes,
    )
    db.add(line)
    await db.flush()
    await db.refresh(line)

    return ResponseBase(
        data=InventoryCountLineResponse(
            id=line.id,
            count_id=line.count_id,
            product_id=line.product_id,
            product_name=product.name,
            zone_id=line.zone_id,
            expected_quantity=float(line.expected_quantity),
            counted_quantity=float(line.counted_quantity) if line.counted_quantity is not None else None,
            difference=float(line.difference) if line.difference is not None else None,
            notes=line.notes,
            created_at=line.created_at,
        )
    )


@router.patch(
    "/counts/{count_id}/lines/{line_id}",
    response_model=ResponseBase[InventoryCountLineResponse],
)
async def update_count_line(
    count_id: UUID,
    line_id: UUID,
    data: InventoryCountLineUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    line = (
        await db.execute(
            select(InventoryCountLine)
            .join(InventoryCount, InventoryCount.id == InventoryCountLine.count_id)
            .where(
                InventoryCountLine.id == line_id,
                InventoryCountLine.count_id == count_id,
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="ინვენტარიზაციის ხაზი არ მოიძებნა")

    changes = data.model_dump(exclude_unset=True)
    if "counted_quantity" in changes:
        counted_qty = Decimal(str(changes["counted_quantity"]))
        line.counted_quantity = counted_qty
        line.difference = counted_qty - line.expected_quantity
    if "notes" in changes:
        line.notes = changes["notes"]

    await db.flush()
    await db.refresh(line)

    product = (
        await db.execute(select(Product).where(Product.id == line.product_id))
    ).scalar_one()

    return ResponseBase(
        data=InventoryCountLineResponse(
            id=line.id,
            count_id=line.count_id,
            product_id=line.product_id,
            product_name=product.name,
            zone_id=line.zone_id,
            expected_quantity=float(line.expected_quantity),
            counted_quantity=float(line.counted_quantity) if line.counted_quantity is not None else None,
            difference=float(line.difference) if line.difference is not None else None,
            notes=line.notes,
            created_at=line.created_at,
        )
    )


@router.delete(
    "/counts/{count_id}/lines/{line_id}",
    response_model=ResponseBase[dict],
)
async def delete_count_line(
    count_id: UUID,
    line_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_delete")),
):
    line = (
        await db.execute(
            select(InventoryCountLine)
            .join(InventoryCount, InventoryCount.id == InventoryCountLine.count_id)
            .where(
                InventoryCountLine.id == line_id,
                InventoryCountLine.count_id == count_id,
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="ინვენტარიზაციის ხაზი არ მოიძებნა")

    await db.delete(line)
    await db.flush()
    return ResponseBase(data={"message": "ხაზი წაიშალა"})


# ── Post Count (apply differences as adjustments) ───────────────────────────────

@router.post(
    "/counts/{count_id}/post",
    response_model=ResponseBase[InventoryCountPostResult],
)
async def post_count(
    count_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    count = (
        await db.execute(
            select(InventoryCount).where(
                InventoryCount.id == count_id,
                InventoryCount.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not count:
        raise HTTPException(status_code=404, detail="ინვენტარიზაცია არ მოიძებნა")
    if count.status != "completed":
        raise HTTPException(
            status_code=409,
            detail="ინვენტარიზაციის განთავსება შესაძლებელია მხოლოდ completed სტატუსზე",
        )

    lines = (
        await db.execute(
            select(InventoryCountLine).where(
                InventoryCountLine.count_id == count_id,
                InventoryCountLine.difference != None,
                InventoryCountLine.difference != Decimal("0"),
            )
        )
    ).scalars().all()

    adjustments_created = 0
    total_difference = Decimal("0")

    for line in lines:
        diff = Decimal(line.difference)
        total_difference += diff

        await reject_batch_tracked_generic_write(
            db, current_user.company_id, count.warehouse_id, line.product_id
        )
        balance = await get_locked_balance(
            db, current_user.company_id, count.warehouse_id, line.product_id
        )
        if balance is None:
            balance = InventoryBalance(
                company_id=current_user.company_id,
                warehouse_id=count.warehouse_id,
                product_id=line.product_id,
                quantity=Decimal("0"),
                reserved_quantity=Decimal("0"),
            )
            db.add(balance)
            await db.flush()

        old_qty = Decimal(balance.quantity)
        new_qty = old_qty + diff
        balance.quantity = new_qty

        movement = InventoryMovement(
            company_id=current_user.company_id,
            warehouse_id=count.warehouse_id,
            zone_id=line.zone_id,
            product_id=line.product_id,
            movement_type="adjustment",
            quantity=abs(diff),
            balance_before=old_qty,
            balance_after=new_qty,
            reserved_before=Decimal(balance.reserved_quantity),
            reserved_after=Decimal(balance.reserved_quantity),
            reason="inventory_count",
            reason_category="count",
            notes=f"ინვენტარიზაცია {count.count_number}: მოსალოდნელი {float(line.expected_quantity)}, დათვლილი {float(line.counted_quantity)}",
            reference=count.count_number,
            reference_type="count",
            created_by=current_user.id,
        )
        db.add(movement)
        await sync_product_current_stock(
            db,
            company_id=current_user.company_id,
            product_id=line.product_id,
        )
        adjustments_created += 1

    count.status = "posted"
    count.approved_at = func.now()
    count.approved_by = current_user.id
    await db.flush()

    return ResponseBase(
        data=InventoryCountPostResult(
            count_id=count.id,
            count_number=count.count_number,
            lines_posted=len(lines),
            adjustments_created=adjustments_created,
            total_difference=float(total_difference),
        )
    )
