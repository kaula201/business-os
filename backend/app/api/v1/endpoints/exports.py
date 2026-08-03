"""Export API — download data as Excel files."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.client import Client
from app.models.product import Product
from app.models.task import Task
from app.utils.excel import (
    export_orders_to_excel,
    export_clients_to_excel,
    export_products_to_excel,
    export_tasks_to_excel,
)

router = APIRouter(prefix="/exports", tags=["ექსპორტი"])


@router.get("/orders")
async def export_orders(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Order).where(Order.company_id == current_user.company_id)
    if status:
        query = query.where(Order.status == status)
    result = await db.execute(query.order_by(Order.created_at.desc()))
    orders = result.scalars().all()

    data = [
        {
            "order_number": o.order_number,
            "client_name": o.client.name if o.client else None,
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "subtotal": float(o.subtotal),
            "vat_amount": float(o.vat_amount),
            "total": float(o.total),
            "created_at": o.created_at.isoformat() if o.created_at else "",
        }
        for o in orders
    ]
    excel_bytes = export_orders_to_excel(data)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=orders.xlsx"},
    )


@router.get("/clients")
async def export_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Client).where(Client.company_id == current_user.company_id)
        .order_by(Client.name)
    )
    clients = result.scalars().all()
    data = [
        {
            "name": c.name,
            "client_type": c.client_type.value if hasattr(c.client_type, "value") else str(c.client_type),
            "identification_code": c.identification_code,
            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
            "phone": c.contacts[0].phone if c.contacts else "",
            "email": c.contacts[0].email if c.contacts else "",
            "created_at": c.created_at.isoformat() if c.created_at else "",
        }
        for c in clients
    ]
    excel_bytes = export_clients_to_excel(data)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=clients.xlsx"},
    )


@router.get("/products")
async def export_products(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.company_id == current_user.company_id)
        .order_by(Product.name)
    )
    products = result.scalars().all()
    data = [
        {
            "sku": p.sku,
            "name": p.name,
            "category_name": p.category.name if hasattr(p, "category") and p.category else "",
            "unit": p.unit,
            "min_stock": float(p.min_stock),
            "current_stock": float(p.current_stock),
            "sale_price": float(p.sale_price),
            "purchase_price": float(p.purchase_price) if p.purchase_price else 0,
            "stock_status": "good",
        }
        for p in products
    ]
    excel_bytes = export_products_to_excel(data)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=products.xlsx"},
    )


@router.get("/tasks")
async def export_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Task).where(Task.company_id == current_user.company_id)
        .order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()
    data = [
        {
            "title": t.title,
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "priority": t.priority.value if hasattr(t.priority, "value") else str(t.priority),
            "assigned_to_name": t.assignee.full_name if hasattr(t, "assignee") and t.assignee else "",
            "due_date": t.due_date.isoformat() if t.due_date else "",
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        for t in tasks
    ]
    excel_bytes = export_tasks_to_excel(data)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=tasks.xlsx"},
    )