"""Orders enhanced: analytics, bulk actions, export."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.order import Order, OrderItem, OrderStatus
from app.schemas.common import ResponseBase
from pydantic import BaseModel, Field
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/orders", tags=["შეკვეთები — გაძლიერებული"])


# ── Analytics ──────────────────────────────────────────────────────────────────

class OrderAnalytics(BaseModel):
    total_orders: int
    total_revenue: Decimal
    avg_order_value: Decimal
    orders_by_status: list[dict]
    top_products: list[dict]
    revenue_today: Decimal
    revenue_this_month: Decimal
    orders_today: int
    orders_this_month: int


@router.get("/analytics", response_model=ResponseBase[OrderAnalytics])
async def order_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("orders", "can_access")),
):
    company_id = current_user.company_id
    today = datetime.combine(date.today(), datetime.min.time())

    # Total stats
    total = (await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id)
    )).one()
    total_orders, total_revenue = total[0], Decimal(str(total[1] or 0))

    # By status
    status_rows = (await db.execute(
        select(Order.status, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id)
        .group_by(Order.status)
    )).all()
    orders_by_status = [{"status": s, "count": c, "total": float(t)} for s, c, t in status_rows]

    # Top products
    product_rows = (await db.execute(
        select(OrderItem.product_name, func.sum(OrderItem.quantity), func.sum(OrderItem.total))
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.company_id == company_id, Order.status != OrderStatus.CANCELLED.value)
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.total).desc())
        .limit(10)
    )).all()
    top_products = [{"name": n, "quantity": float(q), "total": float(t)} for n, q, t in product_rows]

    # Today / this month
    month_start = today.replace(day=1)
    today_stats = (await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id, Order.created_at >= today)
    )).one()
    month_stats = (await db.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id, Order.created_at >= month_start)
    )).one()

    avg = total_revenue / total_orders if total_orders > 0 else Decimal("0")

    return ResponseBase(data=OrderAnalytics(
        total_orders=total_orders, total_revenue=total_revenue, avg_order_value=avg,
        orders_by_status=orders_by_status, top_products=top_products,
        revenue_today=Decimal(str(today_stats[1] or 0)),
        revenue_this_month=Decimal(str(month_stats[1] or 0)),
        orders_today=today_stats[0], orders_this_month=month_stats[0],
    ))


# ── Bulk Actions ────────────────────────────────────────────────────────────────

class BulkOrderStatusUpdate(BaseModel):
    ids: list[UUID]
    status: str = Field(..., max_length=20)


@router.post("/bulk/status", response_model=ResponseBase[dict])
async def bulk_update_order_status(
    data: BulkOrderStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("orders", "can_edit")),
):
    result = await db.execute(
        update(Order)
        .where(Order.id.in_(data.ids), Order.company_id == current_user.company_id)
        .values(status=data.status)
    )
    await db.flush()
    return ResponseBase(data={"updated": result.rowcount, "status": data.status})


# ── Export ──────────────────────────────────────────────────────────────────────

@router.get("/export")
async def export_orders(
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("orders", "can_access")),
):
    filters = [Order.company_id == current_user.company_id]
    if status:
        filters.append(Order.status == status)
    if date_from:
        filters.append(Order.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        filters.append(Order.created_at <= datetime.fromisoformat(date_to))

    rows = (await db.execute(
        select(Order).where(*filters)
        .options(selectinload(Order.client), selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )).unique().scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "შეკვეთები"
    ws.append(["ნომერი", "კლიენტი", "სტატუსი", "ქვე-ჯამი", "დღგ", "სულ", "თარიღი", "მიწოდების თარიღი", "შენიშვნა"])
    for o in rows:
        ws.append([o.order_number, o.client.name if o.client else "", o.status,
                   float(o.subtotal), float(o.vat_amount), float(o.total),
                   str(o.created_at), str(o.delivery_date or ""), o.notes or ""])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=orders.xlsx"})
