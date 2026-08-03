"""Inventory enhanced: valuation, analytics, low stock alerts, export."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse
from app.models.product import Product
from app.schemas.common import ResponseBase
from pydantic import BaseModel
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/warehouses", tags=["საწყობები — გაძლიერებული"])


# ── Stock Valuation ────────────────────────────────────────────────────────────

class WarehouseValuation(BaseModel):
    warehouse_id: UUID
    warehouse_name: str
    product_count: int
    total_quantity: Decimal
    total_value: Decimal


@router.get("/valuation", response_model=ResponseBase[list[WarehouseValuation]])
async def stock_valuation(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_access")),
):
    company_id = current_user.company_id
    rows = (await db.execute(
        select(
            Warehouse.id, Warehouse.name,
            func.count(InventoryBalance.id),
            func.coalesce(func.sum(InventoryBalance.quantity), 0),
        )
        .outerjoin(InventoryBalance, InventoryBalance.warehouse_id == Warehouse.id)
        .where(Warehouse.company_id == company_id, Warehouse.is_active == True)
        .group_by(Warehouse.id, Warehouse.name)
        .order_by(Warehouse.name)
    )).all()

    # Get product cost prices for valuation
    products = (await db.execute(
        select(Product.id, Product.cost_price).where(Product.company_id == company_id)
    )).all()
    cost_map = {str(p[0]): Decimal(str(p[1] or 0)) for p in products}

    result = []
    for wh_id, wh_name, count, total_qty in rows:
        # Get balances for this warehouse to calculate value
        balances = (await db.execute(
            select(InventoryBalance.product_id, InventoryBalance.quantity)
            .where(InventoryBalance.company_id == company_id, InventoryBalance.warehouse_id == wh_id)
        )).all()
        total_value = Decimal("0")
        for pid, qty in balances:
            total_value += Decimal(str(qty)) * cost_map.get(str(pid), Decimal("0"))

        result.append(WarehouseValuation(
            warehouse_id=wh_id, warehouse_name=wh_name,
            product_count=count, total_quantity=Decimal(str(total_qty)),
            total_value=total_value,
        ))

    return ResponseBase(data=result)


# ── Movement Analytics ─────────────────────────────────────────────────────────

class MovementAnalytics(BaseModel):
    total_movements: int
    movements_today: int
    movements_this_month: int
    top_moved_products: list[dict]
    movement_by_type: list[dict]


@router.get("/movement-analytics", response_model=ResponseBase[MovementAnalytics])
async def movement_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_access")),
):
    company_id = current_user.company_id
    today = datetime.combine(date.today(), datetime.min.time())
    month_start = today.replace(day=1)

    total = (await db.execute(
        select(func.count(InventoryMovement.id))
        .where(InventoryMovement.company_id == company_id)
    )).scalar()

    today_count = (await db.execute(
        select(func.count(InventoryMovement.id))
        .where(InventoryMovement.company_id == company_id, InventoryMovement.created_at >= today)
    )).scalar()

    month_count = (await db.execute(
        select(func.count(InventoryMovement.id))
        .where(InventoryMovement.company_id == company_id, InventoryMovement.created_at >= month_start)
    )).scalar()

    # By type
    type_rows = (await db.execute(
        select(InventoryMovement.movement_type, func.count(InventoryMovement.id))
        .where(InventoryMovement.company_id == company_id)
        .group_by(InventoryMovement.movement_type)
        .order_by(func.count(InventoryMovement.id).desc())
    )).all()
    movement_by_type = [{"type": t, "count": c} for t, c in type_rows]

    # Top moved products
    product_rows = (await db.execute(
        select(Product.name, func.sum(func.abs(InventoryMovement.quantity)))
        .join(Product, Product.id == InventoryMovement.product_id)
        .where(InventoryMovement.company_id == company_id)
        .group_by(Product.name)
        .order_by(func.sum(func.abs(InventoryMovement.quantity)).desc())
        .limit(10)
    )).all()
    top_moved_products = [{"name": n, "total_quantity": float(q)} for n, q in product_rows]

    return ResponseBase(data=MovementAnalytics(
        total_movements=total or 0, movements_today=today_count or 0,
        movements_this_month=month_count or 0,
        top_moved_products=top_moved_products, movement_by_type=movement_by_type,
    ))


# ── Low Stock Alerts ────────────────────────────────────────────────────────────

class LowStockAlert(BaseModel):
    product_id: UUID
    product_name: str
    product_sku: str
    warehouse_id: UUID
    warehouse_name: str
    current_quantity: Decimal
    min_stock_level: Decimal


@router.get("/low-stock", response_model=ResponseBase[list[LowStockAlert]])
async def low_stock_alerts(
    threshold: float = Query(10, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_access")),
):
    company_id = current_user.company_id
    rows = (await db.execute(
        select(
            Product.id, Product.name, Product.sku, Product.min_stock_level,
            Warehouse.id, Warehouse.name,
            InventoryBalance.quantity,
        )
        .join(Product, Product.id == InventoryBalance.product_id)
        .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
        .where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.quantity < threshold,
            Warehouse.is_active == True,
            Product.is_active == True,
        )
        .order_by(InventoryBalance.quantity)
    )).all()

    alerts = []
    for pid, pname, sku, min_stock, wid, wname, qty in rows:
        alerts.append(LowStockAlert(
            product_id=pid, product_name=pname, product_sku=sku or "",
            warehouse_id=wid, warehouse_name=wname,
            current_quantity=Decimal(str(qty)),
            min_stock_level=Decimal(str(min_stock or 0)),
        ))

    return ResponseBase(data=alerts)


# ── Export ──────────────────────────────────────────────────────────────────────

@router.get("/export/balances")
async def export_balances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_access")),
):
    rows = (await db.execute(
        select(InventoryBalance, Warehouse, Product)
        .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
        .join(Product, Product.id == InventoryBalance.product_id)
        .where(InventoryBalance.company_id == current_user.company_id)
        .order_by(Warehouse.name, Product.name)
    )).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ნაშთები"
    ws.append(["საწყობი", "პროდუქტი", "SKU", "რაოდენობა", "ბოლო განახლება"])
    for bal, wh, prod in rows:
        ws.append([wh.name, prod.name, prod.sku or "", float(bal.quantity), str(bal.updated_at)])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=inventory_balances.xlsx"})


@router.get("/export/movements")
async def export_movements(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_access")),
):
    since = datetime.combine(date.today() - timedelta(days=days), datetime.min.time())
    rows = (await db.execute(
        select(InventoryMovement, Warehouse, Product)
        .join(Warehouse, Warehouse.id == InventoryMovement.warehouse_id)
        .join(Product, Product.id == InventoryMovement.product_id)
        .where(InventoryMovement.company_id == current_user.company_id, InventoryMovement.created_at >= since)
        .order_by(InventoryMovement.created_at.desc())
    )).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "მოძრაობები"
    ws.append(["თარიღი", "საწყობი", "პროდუქტი", "ტიპი", "რაოდენობა", "მიზეზი", "შენიშვნა"])
    for mov, wh, prod in rows:
        ws.append([str(mov.created_at), wh.name, prod.name, mov.movement_type,
                   float(mov.quantity), mov.reason, mov.notes or ""])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=inventory_movements.xlsx"})
