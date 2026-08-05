# backend/app/api/v1/endpoints/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.user import User
from app.models.client import Client, ClientStatus
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.warehouse import InventoryBalance
from app.models.task import Task, TaskStatus
from app.models.invoice import Invoice
from app.schemas.dashboard import (
    DashboardSummary, KPICards, RevenueChart, RevenueDataPoint,
    OrderStatusDistribution, RecentActivity, CriticalAlert, KPITooltip
)
from app.schemas.common import ResponseBase
from app.services.revenue import get_revenue_for_period, get_total_revenue

router = APIRouter(prefix="/dashboard", tags=["დეშბორდი"])


@router.get("/summary", response_model=ResponseBase[DashboardSummary])
async def get_dashboard_summary(
    period: str = "30d",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = current_user.company_id
    now = utc_now()

    # Period mapping
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
    date_from = now - timedelta(days=days)

    # KPI Cards
    active_clients_count = (await db.execute(
        select(func.count()).where(
            Client.company_id == company_id,
            Client.status == ClientStatus.ACTIVE,
            Client.deleted_at.is_(None)
        )
    )).scalar() or 0

    active_orders_count = (await db.execute(
        select(func.count()).where(
            Order.company_id == company_id,
            Order.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED])
        )
    )).scalar() or 0

    overdue_tasks_count = (await db.execute(
        select(func.count()).where(
            Task.company_id == company_id,
            Task.due_date < now,
            Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
        )
    )).scalar() or 0

    stock_total = (
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.product_id == Product.id,
        )
        .correlate(Product)
        .scalar_subquery()
    )
    low_stock_count = (await db.execute(
        select(func.count(Product.id)).where(
            Product.company_id == company_id,
            stock_total <= Product.min_stock,
            Product.is_active == True
        )
    )).scalar() or 0

    # Canonical revenue from issued invoices
    total_revenue = await get_total_revenue(db, company_id)

    # Invoiced vs total order counts — Dashboard revenue context:
    # revenue is counted ONLY from issued invoices, so show how many of the
    # company's orders have actually been invoiced.
    total_orders_count = (await db.execute(
        select(func.count()).where(
            Order.company_id == company_id,
            Order.status.notin_([OrderStatus.CANCELLED]),
        )
    )).scalar() or 0

    invoiced_orders_count = (await db.execute(
        select(func.count()).where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
        )
    )).scalar() or 0

    kpi = KPICards(
        active_clients=active_clients_count,
        active_orders=active_orders_count,
        overdue_tasks=overdue_tasks_count,
        low_stock_products=low_stock_count,
        total_revenue=float(total_revenue),
    )

    # Revenue chart (daily aggregation from issued invoices)
    revenue_data = []
    for i in range(days):
        day_start = date_from + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        day_rev = await get_revenue_for_period(db, company_id, day_start, day_end)
        revenue_data.append(RevenueDataPoint(
            date=day_start.strftime("%Y-%m-%d"),
            amount=float(day_rev),
            order_count=0,
        ))

    revenue_chart = RevenueChart(period=period, data=revenue_data)

    # Order status distribution
    status_colors = {
        "draft": "#9CA3AF", "confirmed": "#3B82F6", "preparing": "#EAB308",
        "shipping": "#F97316", "completed": "#22C55E", "cancelled": "#EF4444"
    }
    status_result = await db.execute(
        select(Order.status, func.count()).where(
            Order.company_id == company_id
        ).group_by(Order.status)
    )
    order_status_dist = [
        OrderStatusDistribution(
            status=row[0], count=row[1],
            color=status_colors.get(row[0], "#9CA3AF")
        )
        for row in status_result.all()
    ]

    # Recent activity (last 10)
    recent_orders = (await db.execute(
        select(Order).where(Order.company_id == company_id)
        .order_by(Order.created_at.desc()).limit(10)
    )).scalars().all()

    recent_activity = []
    for o in recent_orders:
        recent_activity.append(RecentActivity(
            id=str(o.id),
            type="order_created",
            description=f"ახალი შეკვეთა: {o.order_number}",
            timestamp=o.created_at,
            entity_id=str(o.id)
        ))

    # Critical alerts
    alerts = []
    if low_stock_count > 0:
        low_stock_products = (await db.execute(
            select(Product, stock_total.label("stock_total")).where(
                Product.company_id == company_id,
                stock_total <= Product.min_stock,
                Product.is_active == True
            ).limit(5)
        )).all()
        for p, current_stock in low_stock_products:
            current_stock_value = float(current_stock)
            alerts.append(CriticalAlert(
                type="low_stock",
                severity="high" if current_stock_value <= 0 else "medium",
                title=f"დაბალი ნაშთი: {p.name}",
                description=f"მიმდინარე ნაშთი: {current_stock_value} {p.unit}",
                entity_id=str(p.id)
            ))

    if overdue_tasks_count > 0:
        overdue_tasks = (await db.execute(
            select(Task).where(
                Task.company_id == company_id,
                Task.due_date < now,
                Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED])
            ).order_by(Task.due_date).limit(5)
        )).scalars().all()
        for t in overdue_tasks:
            days_overdue = (now - t.due_date).days
            alerts.append(CriticalAlert(
                type="overdue_task",
                severity="high" if days_overdue > 7 else "medium",
                title=f"დაგვიანებული დავალება: {t.title}",
                description=f"ვადაგადაცილება: {days_overdue} დღე",
                entity_id=str(t.id)
            ))

    return ResponseBase(data=DashboardSummary(
        kpi=kpi,
        revenue_chart=revenue_chart,
        order_status_distribution=order_status_dist,
        recent_activity=recent_activity[:10],
        critical_alerts=alerts,
        ai_summary=None,
        total_revenue=float(total_revenue),
        invoiced_orders_count=invoiced_orders_count,
        total_orders_count=total_orders_count,
        kpi_tooltips=[
            KPITooltip(key="active_clients", label="აქტიური კლიენტები",
                       formula="კლიენტების რაოდენობა სტატუსით 'active'",
                       source="კლიენტების რეესტრი"),
            KPITooltip(key="active_orders", label="აქტიური შეკვეთები",
                       formula="შეკვეთების რაოდენობა, გარდა 'completed' და 'cancelled'",
                       source="გაყიდვის შეკვეთები"),
            KPITooltip(key="overdue_tasks", label="ვადაგადაცილებული დავალებები",
                       formula="დავალებები, რომელთა ვადა გავიდა და სტატუსი არ არის 'done' ან 'cancelled'",
                       source="დავალებები"),
            KPITooltip(key="low_stock_products", label="დაბალი ნაშთი",
                       formula="პროდუქტები, სადაც საწყობების ჯამური ნაშთი <= მინიმალურ ნაშთს",
                       source="საწყობის ნაშთები"),
            KPITooltip(key="total_revenue", label="ჯამური შემოსავალი",
                       formula="მხოლოდ გაცემული (issued) ინვოისების ჯამი",
                       source="გაყიდვის ინვოისები"),
        ],
    ))
