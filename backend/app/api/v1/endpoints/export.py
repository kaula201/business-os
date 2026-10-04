"""Export endpoints — Excel downloads for all modules."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.client import Client
from app.models.product import Product
from app.models.order import Order
from app.models.task import Task
from app.utils.excel import export_clients, export_products, export_orders, export_tasks
import io

router = APIRouter(prefix="/export", tags=["ექსპორტი"])

# Mass export downloads whole datasets (including personal identification codes).
# That is a bulk-read action, not a plain read: employees and accountants must not
# be able to pull the full client/product/order/task tables out of the system.
EXPORT_ALLOWED_ROLES = (User.Role.ADMIN, User.Role.MANAGER)


def require_export_role(current_user: User = Depends(get_current_user)) -> User:
    """Bulk dataset export is limited to administrator and manager roles."""
    if current_user.role not in EXPORT_ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail="მონაცემთა ექსპორტის უფლება არ გაქვთ")
    return current_user


def _stream_response(data: bytes, filename: str):
    import urllib.parse
    encoded_name = urllib.parse.quote(filename)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
        },
    )


@router.get("/clients")
async def download_clients(
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
    _export_role: User = Depends(require_export_role),
):
    """Export clients to Excel."""
    query = select(Client).where(Client.company_id == str(current_user.company_id), Client.deleted_at.is_(None))
    if status:
        query = query.where(Client.status == status)
    if search:
        query = query.where(Client.name.ilike(f"%{search}%"))
    query = query.order_by(Client.name)
    result = await db.execute(query)
    clients = result.scalars().all()

    output = []
    for c in clients:
        output.append({
            "name": c.name,
            "client_type": c.client_type if isinstance(c.client_type, str) else c.client_type.value,
            "identification_code": c.identification_code,
            "status": c.status if isinstance(c.status, str) else c.status.value,
            "phone": getattr(c, "phone", "") or "",
            "email": getattr(c, "email", "") or "",
            "created_at": str(c.created_at) if c.created_at else "",
        })
    data = export_clients(output)
    return _stream_response(data, f"კლიენტები_{len(clients)}.xlsx")


@router.get("/products")
async def download_products(
    category_id: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
    _export_role: User = Depends(require_export_role),
):
    """Export products to Excel."""
    query = select(Product).where(
        Product.company_id == str(current_user.company_id),
        Product.is_active == True
    ).options(selectinload(Product.category))
    if category_id:
        query = query.where(Product.category_id == category_id)
    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))
    query = query.order_by(Product.name)
    result = await db.execute(query)
    products = result.scalars().all()

    output = []
    for p in products:
        output.append({
            "sku": p.sku,
            "name": p.name,
            "category_name": p.category.name if p.category else "",
            "unit": p.unit,
            "current_stock": float(p.current_stock),
            "min_stock": float(p.min_stock),
            "sale_price": float(p.sale_price),
            "purchase_price": float(p.purchase_price) if p.purchase_price else None,
        })
    data = export_products(output)
    return _stream_response(data, f"საწყობი_{len(products)}.xlsx")


@router.get("/orders")
async def download_orders(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
    _export_role: User = Depends(require_export_role),
):
    """Export orders to Excel."""
    query = select(Order).where(Order.company_id == str(current_user.company_id)).options(
        selectinload(Order.client)
    )
    if status:
        query = query.where(Order.status == status)
    query = query.order_by(Order.created_at.desc())
    result = await db.execute(query)
    orders = result.scalars().all()

    output = []
    for o in orders:
        output.append({
            "order_number": o.order_number,
            "client_name": o.client.name if o.client else "",
            "status": o.status if isinstance(o.status, str) else o.status.value,
            "vat_amount": float(o.vat_amount),
            "total": float(o.total),
            "notes": o.notes or "",
            "created_at": str(o.created_at) if o.created_at else "",
        })
    data = export_orders(output)
    return _stream_response(data, f"შეკვეთები_{len(orders)}.xlsx")


@router.get("/tasks")
async def download_tasks(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
    _export_role: User = Depends(require_export_role),
):
    """Export tasks to Excel."""
    query = select(Task).where(Task.company_id == str(current_user.company_id)).options(
        selectinload(Task.assignee)
    )
    if status:
        query = query.where(Task.status == status)
    query = query.order_by(Task.created_at.desc())
    result = await db.execute(query)
    tasks = result.scalars().all()

    output = []
    for t in tasks:
        output.append({
            "title": t.title,
            "priority": t.priority if isinstance(t.priority, str) else t.priority.value,
            "status": t.status if isinstance(t.status, str) else t.status.value,
            "assigned_to_name": t.assignee.full_name if t.assignee else "",
            "due_date": str(t.due_date) if t.due_date else None,
            "created_at": str(t.created_at) if t.created_at else "",
        })
    data = export_tasks(output)
    return _stream_response(data, f"დავალებები_{len(tasks)}.xlsx")