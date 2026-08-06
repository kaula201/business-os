"""WMS: batch/lot and serial-number tracking endpoints."""
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.dependencies import require_module
from app.core.time import utc_now
from app.models.product import Product
from app.models.warehouse import (
    InventoryBalance,
    InventoryMovement,
    ProductBatch,
    ProductSerial,
    Warehouse,
)
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.inventory import sync_product_current_stock

router = APIRouter(prefix="/wms", tags=["WMS — პარტიები და სერიული ნომრები"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class BatchCreate(BaseModel):
    warehouse_id: UUID
    product_id: UUID
    batch_number: str = Field(..., min_length=1, max_length=100)
    production_date: datetime | None = None
    expiry_date: datetime | None = None
    quantity: Decimal = Field(..., gt=0)
    unit_cost: Decimal | None = None
    notes: str | None = None


class BatchResponse(BaseModel):
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    batch_number: str
    production_date: datetime | None
    expiry_date: datetime | None
    quantity: Decimal
    unit_cost: Decimal | None
    notes: str | None
    created_at: datetime


class BatchAdjustment(BaseModel):
    quantity_delta: Decimal
    reason: str = Field(..., min_length=1, max_length=255)


class BatchTransfer(BaseModel):
    destination_warehouse_id: UUID
    reason: str = Field(default="batch_transfer", min_length=1, max_length=255)


class SerialRegister(BaseModel):
    product_id: UUID
    serial_number: str = Field(..., min_length=1, max_length=150)
    batch_id: UUID | None = None
    warehouse_id: UUID | None = None
    notes: str | None = None


class SerialResponse(BaseModel):
    id: UUID
    product_id: UUID
    batch_id: UUID | None
    serial_number: str
    status: str
    warehouse_id: UUID | None
    sold_at: datetime | None
    notes: str | None
    created_at: datetime


async def _require_product(db: AsyncSession, company_id: UUID, product_id: UUID) -> Product:
    product = (
        await db.execute(
            select(Product).where(Product.id == product_id, Product.company_id == company_id)
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
    return product


async def _require_warehouse(db: AsyncSession, company_id: UUID, warehouse_id: UUID) -> Warehouse:
    warehouse = (
        await db.execute(
            select(Warehouse).where(
                Warehouse.id == warehouse_id,
                Warehouse.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if not warehouse:
        raise HTTPException(status_code=404, detail="საწყობი არ მოიძებნა")
    return warehouse


async def _adjust_inventory(
    db: AsyncSession,
    *,
    company_id: UUID,
    warehouse_id: UUID,
    product_id: UUID,
    quantity_delta: Decimal,
    reference: str,
    reason: str,
    user_id: UUID,
) -> None:
    if quantity_delta == 0:
        return
    lock_key = f"{company_id}:{warehouse_id}:{product_id}"
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": lock_key},
    )
    balance = (
        await db.execute(
            select(InventoryBalance)
            .where(
                InventoryBalance.company_id == company_id,
                InventoryBalance.warehouse_id == warehouse_id,
                InventoryBalance.product_id == product_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if balance is None:
        if quantity_delta < 0:
            raise HTTPException(status_code=409, detail="საწყობში არასაკმარისი ნაშთია")
        balance = InventoryBalance(
            company_id=company_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=Decimal("0"),
            reserved_quantity=Decimal("0"),
        )
        db.add(balance)
        await db.flush()

    before = Decimal(balance.quantity)
    after = before + quantity_delta
    reserved = Decimal(balance.reserved_quantity)
    if after < 0:
        raise HTTPException(status_code=409, detail="საწყობში არასაკმარისი ნაშთია")
    if after < reserved:
        raise HTTPException(status_code=409, detail="ოპერაცია დარეზერვებულ მარაგს შეამცირებს")
    balance.quantity = after
    db.add(InventoryMovement(
        company_id=company_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        movement_type="in" if quantity_delta > 0 else "out",
        quantity=abs(quantity_delta),
        balance_before=before,
        balance_after=after,
        reserved_before=reserved,
        reserved_after=reserved,
        reason=reason,
        reason_category="wms",
        reference=reference,
        reference_type="batch",
        created_by=user_id,
    ))
    await db.flush()
    await sync_product_current_stock(
        db, company_id=company_id, product_id=product_id
    )


async def _increase_inventory(
    db: AsyncSession,
    *,
    company_id: UUID,
    warehouse_id: UUID,
    product_id: UUID,
    quantity: Decimal,
    batch_number: str,
    user_id: UUID,
) -> None:
    await _adjust_inventory(
        db,
        company_id=company_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity_delta=quantity,
        reference=batch_number,
        reason="batch_receipt",
        user_id=user_id,
    )


# ── Batches ──────────────────────────────────────────────────────────────────

@router.post("/batches", response_model=ResponseBase[BatchResponse], status_code=201)
async def create_batch(
    payload: BatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    company_id = current_user.company_id
    await _require_product(db, company_id, payload.product_id)
    await _require_warehouse(db, company_id, payload.warehouse_id)
    existing = await db.execute(
        select(ProductBatch).where(
            ProductBatch.company_id == company_id,
            ProductBatch.batch_number == payload.batch_number,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ასეთი პარტიის ნომერი უკვე არსებობს")

    batch = ProductBatch(
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        batch_number=payload.batch_number,
        production_date=payload.production_date,
        expiry_date=payload.expiry_date,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        notes=payload.notes,
    )
    db.add(batch)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="ასეთი პარტიის ნომერი უკვე არსებობს") from exc
    await _increase_inventory(
        db,
        company_id=company_id,
        warehouse_id=payload.warehouse_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        batch_number=payload.batch_number,
        user_id=current_user.id,
    )
    await db.refresh(batch)
    return ResponseBase(data=batch, message="პარტია შექმნილია")


@router.get("/batches", response_model=ResponseBase[list[BatchResponse]])
async def list_batches(
    product_id: UUID | None = None,
    expiring_soon: bool = False,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_access")),
):
    company_id = current_user.company_id
    query = select(ProductBatch).where(ProductBatch.company_id == company_id)
    if product_id:
        query = query.where(ProductBatch.product_id == product_id)
    if expiring_soon:
        today_start = datetime.combine(date.today(), datetime.min.time())
        query = query.where(
            ProductBatch.expiry_date.isnot(None),
            ProductBatch.expiry_date >= today_start,
            ProductBatch.expiry_date <= today_start + timedelta(days=30),
        )
    query = query.order_by(ProductBatch.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return ResponseBase(data=result.scalars().all())


@router.post("/batches/{batch_id}/receive", response_model=ResponseBase[BatchResponse])
async def receive_batch(
    batch_id: UUID,
    quantity: Decimal = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    """Increase batch quantity on goods receipt."""
    batch = (
        await db.execute(
            select(ProductBatch).where(
                ProductBatch.id == batch_id,
                ProductBatch.company_id == current_user.company_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="პარტია არ მოიძებნა")
    batch.quantity += quantity
    await _increase_inventory(
        db,
        company_id=current_user.company_id,
        warehouse_id=batch.warehouse_id,
        product_id=batch.product_id,
        quantity=quantity,
        batch_number=batch.batch_number,
        user_id=current_user.id,
    )
    await db.flush()
    await db.refresh(batch)
    return ResponseBase(data=batch, message="პარტიის რაოდენობა განახლებულია")


@router.post("/batches/{batch_id}/adjust", response_model=ResponseBase[BatchResponse])
async def adjust_batch(
    batch_id: UUID,
    payload: BatchAdjustment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    delta = Decimal(payload.quantity_delta)
    if delta == 0:
        raise HTTPException(status_code=422, detail="quantity_delta არ უნდა იყოს 0")
    batch = (
        await db.execute(
            select(ProductBatch).where(
                ProductBatch.id == batch_id,
                ProductBatch.company_id == current_user.company_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="პარტია არ მოიძებნა")
    new_quantity = Decimal(batch.quantity) + delta
    if new_quantity < 0:
        raise HTTPException(status_code=409, detail="პარტიაში არასაკმარისი ნაშთია")
    if delta < 0:
        serialized_available = await db.scalar(
            select(func.count(ProductSerial.id)).where(
                ProductSerial.company_id == current_user.company_id,
                ProductSerial.batch_id == batch.id,
                ProductSerial.status.in_(["in_stock", "returned"]),
            )
        )
        untracked_quantity = Decimal(batch.quantity) - Decimal(serialized_available or 0)
        if abs(delta) > untracked_quantity:
            raise HTTPException(
                status_code=409,
                detail="სერიული ერთეულები შეცვალეთ serial status ოპერაციით",
            )
    await _adjust_inventory(
        db,
        company_id=current_user.company_id,
        warehouse_id=batch.warehouse_id,
        product_id=batch.product_id,
        quantity_delta=delta,
        reference=batch.batch_number,
        reason=payload.reason,
        user_id=current_user.id,
    )
    batch.quantity = new_quantity
    await db.flush()
    await db.refresh(batch)
    return ResponseBase(data=batch, message="პარტიის ნაშთი განახლებულია")


@router.post("/batches/{batch_id}/transfer", response_model=ResponseBase[BatchResponse])
async def transfer_batch(
    batch_id: UUID,
    payload: BatchTransfer,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    batch = (
        await db.execute(
            select(ProductBatch).where(
                ProductBatch.id == batch_id,
                ProductBatch.company_id == current_user.company_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="პარტია არ მოიძებნა")
    await _require_warehouse(
        db, current_user.company_id, payload.destination_warehouse_id
    )
    if batch.warehouse_id == payload.destination_warehouse_id:
        raise HTTPException(status_code=409, detail="პარტია უკვე ამ საწყობშია")
    quantity = Decimal(batch.quantity)
    if quantity <= 0:
        raise HTTPException(status_code=409, detail="ცარიელი პარტიის გადატანა შეუძლებელია")
    source_warehouse_id = batch.warehouse_id
    await _adjust_inventory(
        db,
        company_id=current_user.company_id,
        warehouse_id=source_warehouse_id,
        product_id=batch.product_id,
        quantity_delta=-quantity,
        reference=batch.batch_number,
        reason=payload.reason,
        user_id=current_user.id,
    )
    await _adjust_inventory(
        db,
        company_id=current_user.company_id,
        warehouse_id=payload.destination_warehouse_id,
        product_id=batch.product_id,
        quantity_delta=quantity,
        reference=batch.batch_number,
        reason=payload.reason,
        user_id=current_user.id,
    )
    batch.warehouse_id = payload.destination_warehouse_id
    await db.execute(
        update(ProductSerial)
        .where(
            ProductSerial.company_id == current_user.company_id,
            ProductSerial.batch_id == batch.id,
            ProductSerial.status.in_(["in_stock", "returned"]),
        )
        .values(warehouse_id=payload.destination_warehouse_id)
    )
    await db.flush()
    await db.refresh(batch)
    return ResponseBase(data=batch, message="პარტია გადატანილია")


# ── Serials ──────────────────────────────────────────────────────────────────

@router.post("/serials", response_model=ResponseBase[SerialResponse], status_code=201)
async def register_serial(
    payload: SerialRegister,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    company_id = current_user.company_id
    await _require_product(db, company_id, payload.product_id)
    if payload.warehouse_id:
        await _require_warehouse(db, company_id, payload.warehouse_id)
    if payload.batch_id:
        batch = (
            await db.execute(
                select(ProductBatch).where(
                    ProductBatch.id == payload.batch_id,
                    ProductBatch.company_id == company_id,
                )
            )
        ).scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="პარტია არ მოიძებნა")
        if batch.product_id != payload.product_id:
            raise HTTPException(status_code=409, detail="პარტია სხვა პროდუქტს ეკუთვნის")
        if payload.warehouse_id and batch.warehouse_id != payload.warehouse_id:
            raise HTTPException(status_code=409, detail="პარტია სხვა საწყობს ეკუთვნის")
    existing = await db.execute(
        select(ProductSerial).where(
            ProductSerial.company_id == company_id,
            ProductSerial.serial_number == payload.serial_number,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ასეთი სერიული ნომერი უკვე არსებობს")

    serial = ProductSerial(
        company_id=company_id,
        product_id=payload.product_id,
        batch_id=payload.batch_id,
        serial_number=payload.serial_number,
        status="in_stock",
        warehouse_id=payload.warehouse_id,
        notes=payload.notes,
    )
    db.add(serial)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="ასეთი სერიული ნომერი უკვე არსებობს") from exc
    await db.refresh(serial)
    return ResponseBase(data=serial, message="სერიული ნომერი რეგისტრირებულია")


@router.get("/serials", response_model=ResponseBase[list[SerialResponse]])
async def list_serials(
    product_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_access")),
):
    company_id = current_user.company_id
    query = select(ProductSerial).where(ProductSerial.company_id == company_id)
    if product_id:
        query = query.where(ProductSerial.product_id == product_id)
    if status:
        query = query.where(ProductSerial.status == status)
    query = query.order_by(ProductSerial.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return ResponseBase(data=result.scalars().all())


@router.patch("/serials/{serial_id}/status", response_model=ResponseBase[SerialResponse])
async def update_serial_status(
    serial_id: UUID,
    status: str = Query(..., pattern="^(in_stock|sold|returned|scrapped)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    serial = (
        await db.execute(
            select(ProductSerial).where(
                ProductSerial.id == serial_id,
                ProductSerial.company_id == current_user.company_id,
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not serial:
        raise HTTPException(status_code=404, detail="სერიული ნომერი არ მოიძებნა")

    available_statuses = {"in_stock", "returned"}
    was_available = serial.status in available_statuses
    will_be_available = status in available_statuses
    quantity_delta = Decimal(int(will_be_available) - int(was_available))
    if quantity_delta:
        if not serial.warehouse_id:
            raise HTTPException(status_code=409, detail="სერიულ ნომერს საწყობი არ აქვს")
        batch = None
        if serial.batch_id:
            batch = (
                await db.execute(
                    select(ProductBatch).where(
                        ProductBatch.id == serial.batch_id,
                        ProductBatch.company_id == current_user.company_id,
                    ).with_for_update()
                )
            ).scalar_one_or_none()
            if not batch:
                raise HTTPException(status_code=404, detail="პარტია არ მოიძებნა")
            new_batch_quantity = Decimal(batch.quantity) + quantity_delta
            if new_batch_quantity < 0:
                raise HTTPException(status_code=409, detail="პარტიაში არასაკმარისი ნაშთია")
            batch.quantity = new_batch_quantity
        await _adjust_inventory(
            db,
            company_id=current_user.company_id,
            warehouse_id=serial.warehouse_id,
            product_id=serial.product_id,
            quantity_delta=quantity_delta,
            reference=batch.batch_number if batch else serial.serial_number,
            reason=f"serial_status:{serial.status}->{status}",
            user_id=current_user.id,
        )

    serial.status = status
    serial.sold_at = utc_now() if status == "sold" else None
    await db.flush()
    await db.refresh(serial)
    return ResponseBase(data=serial, message="სტატუსი განახლებულია")
