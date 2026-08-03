"""Dashboard enhanced: quick actions, CRM pipeline, HR stats, export."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.client import Client
from app.models.product import Product
from app.models.task import Task
from app.models.crm import CRMLead, CRMOpportunity
from app.models.hr import Employee
from app.models.invoice import Invoice
from app.schemas.common import ResponseBase
from pydantic import BaseModel
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard — გაძლიერებული"])


# ── Extended KPIs ────────────────────────────────────────────────────────────

class ExtendedKPIs(BaseModel):
    total_revenue: Decimal
    revenue_this_month: Decimal
    total_orders: int
    orders_this_month: int
    total_clients: int
    new_clients_this_month: int
    open_leads: int
    pipeline_value: Decimal
    active_employees: int
    overdue_tasks: int
    low_stock_products: int
    unpaid_invoices: Decimal


@router.get("/extended-kpis", response_model=ResponseBase[ExtendedKPIs])
async def extended_kpis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    company_id = current_user.company_id
    today = date.today()
    month_start = datetime.combine(today.replace(day=1), datetime.min.time())
    now = datetime.utcnow()

    # Revenue
    total_rev = (await db.execute(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id, Order.status == OrderStatus.COMPLETED.value)
    )).scalar()
    month_rev = (await db.execute(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id, Order.status == OrderStatus.COMPLETED.value, Order.created_at >= month_start)
    )).scalar()

    # Orders
    total_orders = (await db.execute(select(func.count(Order.id)).where(Order.company_id == company_id))).scalar()
    month_orders = (await db.execute(select(func.count(Order.id)).where(Order.company_id == company_id, Order.created_at >= month_start))).scalar()

    # Clients
    total_clients = (await db.execute(select(func.count(Client.id)).where(Client.company_id == company_id, Client.deleted_at.is_(None)))).scalar()
    new_clients = (await db.execute(select(func.count(Client.id)).where(Client.company_id == company_id, Client.created_at >= month_start, Client.deleted_at.is_(None)))).scalar()

    # CRM
    open_leads = (await db.execute(select(func.count(CRMLead.id)).where(CRMLead.company_id == company_id, CRMLead.status.notin_(["converted", "unqualified"])))).scalar()
    pipeline = (await db.execute(
        select(func.coalesce(func.sum(CRMOpportunity.amount), 0))
        .where(CRMOpportunity.company_id == company_id, CRMOpportunity.stage.notin_(["won", "lost"]))
    )).scalar()

    # HR
    active_emp = (await db.execute(select(func.count(Employee.id)).where(Employee.company_id == company_id, Employee.status == Employee.Status.ACTIVE))).scalar()

    # Tasks
    overdue = (await db.execute(
        select(func.count(Task.id)).where(Task.company_id == company_id, Task.due_date < now, Task.status.notin_(["done", "cancelled"]))
    )).scalar()

    # Low stock
    low_stock = (await db.execute(
        select(func.count(Product.id)).where(Product.company_id == company_id, Product.current_stock <= Product.min_stock, Product.is_active == True)
    )).scalar()

    # Unpaid invoices
    unpaid = (await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id, Invoice.status == "issued")
    )).scalar()

    return ResponseBase(data=ExtendedKPIs(
        total_revenue=Decimal(str(total_rev or 0)),
        revenue_this_month=Decimal(str(month_rev or 0)),
        total_orders=total_orders or 0, orders_this_month=month_orders or 0,
        total_clients=total_clients or 0, new_clients_this_month=new_clients or 0,
        open_leads=open_leads or 0, pipeline_value=Decimal(str(pipeline or 0)),
        active_employees=active_emp or 0, overdue_tasks=overdue or 0,
        low_stock_products=low_stock or 0, unpaid_invoices=Decimal(str(unpaid or 0)),
    ))


# ── Quick Actions ────────────────────────────────────────────────────────────

class QuickAction(BaseModel):
    id: str
    label: str
    description: str
    icon: str
    route: str
    count: int | None = None


@router.get("/quick-actions", response_model=ResponseBase[list[QuickAction]])
async def quick_actions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    company_id = current_user.company_id
    now = datetime.utcnow()

    overdue = (await db.execute(
        select(func.count(Task.id)).where(Task.company_id == company_id, Task.due_date < now, Task.status.notin_(["done", "cancelled"]))
    )).scalar() or 0

    low_stock = (await db.execute(
        select(func.count(Product.id)).where(Product.company_id == company_id, Product.current_stock <= Product.min_stock, Product.is_active == True)
    )).scalar() or 0

    new_leads = (await db.execute(select(func.count(CRMLead.id)).where(CRMLead.company_id == company_id, CRMLead.status == "new"))).scalar() or 0

    return ResponseBase(data=[
        QuickAction(id="new_order", label="ახალი შეკვეთა", description="გაყიდვის შეკვეთის შექმნა", icon="Plus", route="/orders"),
        QuickAction(id="new_lead", label="ახალი ლიდი", description="CRM-ში ლიდის დამატება", icon="UserPlus", route="/crm?view=leads"),
        QuickAction(id="new_invoice", label="ახალი ინვოისი", description="ინვოისის გენერაცია", icon="FileText", route="/invoices"),
        QuickAction(id="overdue_tasks", label="ვადაგადაცილებული დავალებები", description=f"{overdue} დავალება ვადაგადაცილებულია", icon="AlertCircle", route="/tasks?view=overdue", count=overdue),
        QuickAction(id="low_stock", label="დაბალი ნაშთი", description=f"{low_stock} პროდუქტი", icon="Package", route="/warehouses", count=low_stock),
        QuickAction(id="new_leads", label="ახალი ლიდები", description=f"{new_leads} ლიდი დამუშავებას ელოდება", icon="Users", route="/crm?view=leads", count=new_leads),
    ])


# ── Export ──────────────────────────────────────────────────────────────────

@router.get("/export/summary")
async def export_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    company_id = current_user.company_id
    today = date.today()
    month_start = datetime.combine(today.replace(day=1), datetime.min.time())

    # Orders this month
    orders = (await db.execute(
        select(Order).where(Order.company_id == company_id, Order.created_at >= month_start).order_by(Order.created_at.desc())
    )).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "დეშბორდი"
    ws.append(["ნომერი", "კლიენტი", "სტატუსი", "თანხა", "თარიღი"])
    for o in orders:
        ws.append([o.order_number, o.client.name if o.client else "", o.status, float(o.total), str(o.created_at)])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=dashboard_orders.xlsx"})
