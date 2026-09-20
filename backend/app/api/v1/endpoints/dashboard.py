# backend/app/api/v1/endpoints/dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text
from datetime import date, datetime, timedelta
from uuid import UUID
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.user import User
from app.models.client import Client, ClientStatus
from app.models.order import Order, OrderStatus, OrderFulfillment
from app.models.product import Product
from app.models.warehouse import InventoryBalance
from app.models.task import Task, TaskStatus
from app.models.invoice import Invoice
from app.models.crm import CRMLead, CRMOpportunity
from app.models.receivable import CustomerReceivable
from app.models.purchase import SupplierPayable
from app.models.wms_ops import Shipment
from app.models.production import WorkOrder
from app.models.fleet import Vehicle
from app.models.maintenance import MaintenanceOrder
from app.models.approval import ApprovalRequest
from app.models.dashboard_layout import DashboardLayout
from app.schemas.dashboard import (
    DashboardSummary, KPICards, RevenueChart, RevenueDataPoint,
    OrderStatusDistribution, RecentActivity, CriticalAlert, KPITooltip,
    DashboardLayoutOut, DashboardLayoutIn, DashboardMetricsResponse,
)
from app.schemas.common import ResponseBase
from app.services.revenue import get_revenue_for_period, get_total_revenue

router = APIRouter(prefix="/dashboard", tags=["დეშბორდი"])


def _pct_change(cur: float, prev: float) -> float | None:
    """Percentage change vs previous period; None when previous is 0/undeterminable."""
    if prev is None or prev == 0:
        return None
    return round((float(cur) - float(prev)) / float(prev) * 100, 1)


@router.get("/summary", response_model=ResponseBase[DashboardSummary])
async def get_dashboard_summary(
    period: str = "30d",
    owner_id: str | None = None,
    warehouse_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = current_user.company_id
    now = utc_now()

    # Optional owner filter: narrows orders + tasks to one assignee
    owner_uuid = None
    if owner_id:
        owner_uuid = UUID(owner_id)
        owner_exists = (await db.execute(
            select(User.id).where(User.id == owner_uuid, User.company_id == company_id)
        )).scalar_one_or_none()
        if not owner_exists:
            raise HTTPException(status_code=404, detail="თანამშრომელი არ მოიძებნა")

    wh_uuid = None
    if warehouse_id:
        try:
            wh_uuid = UUID(warehouse_id)
        except ValueError:
            wh_uuid = None

    # Period mapping
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
    date_from = now - timedelta(days=days)

    # Previous period window (same length) — for KPI % comparison
    prev_from = date_from - timedelta(days=days)

    cur_cashflow = float((await db.execute(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id, Order.status == OrderStatus.COMPLETED.value, Order.created_at >= date_from)
    )).scalar() or 0)
    prev_cashflow = float((await db.execute(
        select(func.coalesce(func.sum(Order.total), 0))
        .where(Order.company_id == company_id, Order.status == OrderStatus.COMPLETED.value, Order.created_at >= prev_from, Order.created_at < date_from)
    )).scalar() or 0)

    cur_rev_issued = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id, Invoice.status == "issued", Invoice.created_at >= date_from)
    )).scalar() or 0)
    prev_rev_issued = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id, Invoice.status == "issued", Invoice.created_at >= prev_from, Invoice.created_at < date_from)
    )).scalar() or 0)

    prev_active_orders = int((await db.execute(
        select(func.count()).where(
            Order.company_id == company_id,
            Order.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
            Order.created_at >= prev_from, Order.created_at < date_from
        )
    )).scalar() or 0)
    prev_active_clients = int((await db.execute(
        select(func.count()).where(
            Client.company_id == company_id, Client.status == ClientStatus.ACTIVE,
            Client.deleted_at.is_(None),
            Client.created_at >= prev_from, Client.created_at < date_from
        )
    )).scalar() or 0)
    prev_overdue_tasks = int((await db.execute(
        select(func.count()).where(
            Task.company_id == company_id,
            Task.due_date < now, Task.status.notin_([TaskStatus.DONE, TaskStatus.CANCELLED]),
            Task.created_at >= prev_from, Task.created_at < date_from
        )
    )).scalar() or 0)

    # KPI Cards
    active_clients_count = (await db.execute(
        select(func.count()).where(
            Client.company_id == company_id,
            Client.status == ClientStatus.ACTIVE,
            Client.deleted_at.is_(None)
        )
    )).scalar() or 0

    order_scope = [Order.company_id == company_id]
    if owner_uuid:
        order_scope.append(Order.assigned_to == owner_uuid)
    if wh_uuid:
        # Order has no warehouse_id → scope active orders via OrderFulfillment
        order_scope.append(
            Order.id.in_(
                select(OrderFulfillment.order_id).where(
                    OrderFulfillment.warehouse_id == wh_uuid
                )
            )
        )
    active_orders_count = (await db.execute(
        select(func.count()).where(
            *order_scope,
            Order.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED])
        )
    )).scalar() or 0

    task_scope = [Task.company_id == company_id]
    if owner_uuid:
        task_scope.append(Task.assigned_to == owner_uuid)
    overdue_tasks_count = (await db.execute(
        select(func.count()).where(
            *task_scope,
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
        pipeline_value=float((await db.execute(
            select(func.coalesce(func.sum(CRMOpportunity.amount), 0))
            .where(CRMOpportunity.company_id == company_id, CRMOpportunity.stage.notin_(["won", "lost"]))
        )).scalar() or 0),
        open_leads=int((await db.execute(
            select(func.count(CRMLead.id)).where(CRMLead.company_id == company_id, CRMLead.status.notin_(["converted", "unqualified"]))
        )).scalar() or 0),
        receivables_outstanding=float((await db.execute(
            select(func.coalesce(func.sum(CustomerReceivable.outstanding_amount), 0))
            .where(CustomerReceivable.company_id == company_id, CustomerReceivable.status != "paid")
        )).scalar() or 0),
        payables_outstanding=float((await db.execute(
            select(func.coalesce(func.sum(SupplierPayable.outstanding_amount), 0))
            .where(SupplierPayable.company_id == company_id, SupplierPayable.status != "paid")
        )).scalar() or 0),
        stock_value=float((await db.execute(
            select(func.coalesce(func.sum(InventoryBalance.quantity * Product.purchase_price), 0))
            .where(InventoryBalance.company_id == company_id, InventoryBalance.product_id == Product.id)
        )).scalar() or 0),
        inventory_units=float((await db.execute(
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
            .where(InventoryBalance.company_id == company_id)
        )).scalar() or 0),
        cashflow_30d=float((await db.execute(
            select(func.coalesce(func.sum(Order.total), 0))
            .where(Order.company_id == company_id, Order.status == OrderStatus.COMPLETED.value, Order.created_at >= date_from)
        )).scalar() or 0),
        unpaid_invoices=float((await db.execute(
            select(func.coalesce(func.sum(Invoice.total), 0))
            .where(Invoice.company_id == company_id, Invoice.status == "issued")
        )).scalar() or 0),
        revenue_change=_pct_change(cur_rev_issued, prev_rev_issued),
        orders_change=_pct_change(active_orders_count, prev_active_orders),
        clients_change=_pct_change(active_clients_count, prev_active_clients),
        tasks_change=_pct_change(overdue_tasks_count, prev_overdue_tasks),
        cashflow_change=_pct_change(cur_cashflow, prev_cashflow),
        # ── Operational KPIs (REQ-DASH-01) ──────────────────────────────
        # Delayed deliveries: order promised before now, still not completed/cancelled
        delayed_shipments=int((await db.execute(
            select(func.count(Order.id)).where(
                Order.company_id == company_id,
                Order.delivery_date.isnot(None),
                Order.delivery_date < now,
                Order.status.notin_([OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]),
            )
        )).scalar() or 0),
        # Production backlog: confirmed/in-progress orders past their end date
        production_backlog=int((await db.execute(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.company_id == company_id,
                WorkOrder.end_date.isnot(None),
                WorkOrder.end_date < date.today(),
                WorkOrder.status.in_(["confirmed", "in_progress"]),
            )
        )).scalar() or 0),
        # Fleet unavailable: inactive vehicles or expired insurance/inspection
        fleet_unavailable=int((await db.execute(
            select(func.count(Vehicle.id)).where(
                Vehicle.company_id == company_id,
                (Vehicle.is_active.is_(False))
                | (Vehicle.insurance_valid_until.isnot(None) & (Vehicle.insurance_valid_until < date.today()))
                | (Vehicle.tech_inspection_until.isnot(None) & (Vehicle.tech_inspection_until < date.today())),
            )
        )).scalar() or 0),
        # Critical maintenance: emergency/critical open work orders
        maintenance_critical=int((await db.execute(
            select(func.count(MaintenanceOrder.id)).where(
                MaintenanceOrder.company_id == company_id,
                MaintenanceOrder.status.in_(["scheduled", "in_progress"]),
                (MaintenanceOrder.priority == "critical") | (MaintenanceOrder.maintenance_type == "emergency"),
            )
        )).scalar() or 0),
        # Pending approvals queue
        approvals_pending=int((await db.execute(
            select(func.count(ApprovalRequest.id)).where(
                ApprovalRequest.company_id == company_id,
                ApprovalRequest.status == ApprovalRequest.Status.PENDING,
            )
        )).scalar() or 0),
        # OTIF: completed among due (promised before now); None when nothing due yet
        otif_rate=(lambda due, done: round(done / due * 100, 1) if due else None)(
            int((await db.execute(
                select(func.count(Order.id)).where(
                    Order.company_id == company_id,
                    Order.delivery_date.isnot(None),
                    Order.delivery_date < now,
                    Order.status.notin_([OrderStatus.CANCELLED.value, OrderStatus.DRAFT.value]),
                )
            )).scalar() or 0),
            int((await db.execute(
                select(func.count(Order.id)).where(
                    Order.company_id == company_id,
                    Order.delivery_date.isnot(None),
                    Order.delivery_date < now,
                    Order.status == OrderStatus.COMPLETED.value,
                )
            )).scalar() or 0),
        ),
        last_updated_at=now,
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
            *order_scope
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
        select(Order).where(*order_scope)
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
            KPITooltip(key="delayed_shipments", label="დაგვიანებული მიწოდება",
                       formula="შეკვეთები, სადაც delivery_date გავიდა და შეკვეთა ღიაა (არა completed/cancelled)",
                       source="გაყიდვის შეკვეთები"),
            KPITooltip(key="production_backlog", label="წარმოების ჩამორჩენა",
                       formula="სამუშაო დავალებები (WorkOrder) სტატუსით confirmed/in_progress, რომელთა დასრულების ვადა გავიდა",
                       source="წარმოება"),
            KPITooltip(key="fleet_unavailable", label="ავტოპარკის მიუწვდომლობა",
                       formula="მანქანები არააქტიური ან ვადაგასული დაზღვევა/ტექდათვალიერება",
                       source="ავტოპარკი"),
            KPITooltip(key="maintenance_critical", label="კრიტიკული მოვლა",
                       formula="ღია სამუშაო დავალებები პრიორიტეტით critical ან ტიპით emergency",
                       source="Maintenance"),
            KPITooltip(key="approvals_pending", label="დასამტკიცებელი",
                       formula="მოლოდინში მყოფი (pending) დამტკიცების მოთხოვნები",
                       source="დამტკიცებები"),
            KPITooltip(key="otif_rate", label="OTIF",
                       formula="დროულად შესრულებული / ვადამოსული შეკვეთები × 100 (შედარება ვერ ითვლება, თუ ვადამოსულები არ არის)",
                       source="გაყიდვის შეკვეთები"),
        ],
    ))


@router.post("/refresh-views", response_model=ResponseBase[dict])
async def refresh_views(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually refresh materialized views (mv_sales_daily, mv_receivables_aging, mv_stock_balances)."""
    for view in ("mv_sales_daily", "mv_receivables_aging", "mv_stock_balances"):
        try:
            await db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
        except Exception:
            pass
    await db.commit()
    return ResponseBase(data={"refreshed": True}, message="Materialized views განახლდა")


# ── REQ-DASH: server-side layout + filtered metrics (10/10 gap closure) ──────


@router.get("/layout", response_model=ResponseBase[DashboardLayoutOut])
async def get_dashboard_layout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-user, per-company widget layout (JSON {view_key: [kpi_key, ...]})."""
    layout = (
        await db.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == current_user.id,
                DashboardLayout.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if layout is None:
        return ResponseBase(data=DashboardLayoutOut(layouts={}))
    return ResponseBase(
        data=DashboardLayoutOut(layouts=layout.widgets or {}, updated_at=layout.updated_at)
    )


@router.put("/layout", response_model=ResponseBase[DashboardLayoutOut])
async def put_dashboard_layout(
    payload: DashboardLayoutIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist per-view widget layout on the server (authoritative, not only localStorage)."""
    layout = (
        await db.execute(
            select(DashboardLayout).where(
                DashboardLayout.user_id == current_user.id,
                DashboardLayout.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if layout is None:
        layout = DashboardLayout(
            user_id=current_user.id,
            company_id=current_user.company_id,
            widgets=payload.layouts,
        )
        db.add(layout)
    else:
        layout.widgets = payload.layouts
    await db.commit()
    await db.refresh(layout)
    return ResponseBase(
        data=DashboardLayoutOut(layouts=layout.widgets or {}, updated_at=layout.updated_at)
    )


@router.get("/metrics", response_model=ResponseBase[DashboardMetricsResponse])
async def dashboard_metrics(
    from_date: str | None = None,
    to_date: str | None = None,
    branch_id: str | None = None,
    warehouse_id: str | None = None,
    team_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Filtered KPI snapshot (REQ-DASH-04). Warehouse filter narrows open orders
    via OrderFulfillment; branch/team are echoed (no branch/team table yet) so the
    contract is stable. No margin KPI is exposed — margin stays behind view_cost
    (AC-DASH-02).
    """
    cid = current_user.company_id
    period = "30d"
    if from_date and to_date:
        try:
            f = date.fromisoformat(from_date)
            t = date.fromisoformat(to_date)
            if f <= t:
                period = "custom"
        except ValueError:
            period = "30d"

    # Reuse the same computation as /summary for consistency (single source of truth)
    summary_data = await get_dashboard_summary(period=period, owner_id=None, db=db, current_user=current_user)
    kpi = (summary_data.data.kpi if summary_data and summary_data.data else None) or KPICards(
        active_clients=0, active_orders=0, overdue_tasks=0, low_stock_products=0,
    )

    # Warehouse filter: narrow active orders to those fulfilled in that warehouse
    if warehouse_id:
        try:
            wid = UUID(warehouse_id)
        except ValueError:
            wid = None
        if wid and kpi is not None:
            active_w = int((await db.execute(
                select(func.count(func.distinct(Order.id)))
                .select_from(Order)
                .join(OrderFulfillment, OrderFulfillment.order_id == Order.id)
                .where(
                    Order.company_id == cid,
                    Order.status.notin_([OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]),
                    OrderFulfillment.warehouse_id == wid,
                )
            )).scalar() or 0)
            kpi.active_orders = active_w

    # AC-DASH-02: margin widgets require view_cost — not exposed here at all
    # (no margin KPI exists in KPICards; the field set is permission-neutral).

    computed_at = utc_now()
    status = "fresh"
    return ResponseBase(data=DashboardMetricsResponse(
        kpi=kpi,
        from_date=from_date or (date.today() - timedelta(days=30)).isoformat(),
        to_date=to_date or date.today().isoformat(),
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        team_id=team_id,
        computed_at=computed_at,
        refresh_interval_seconds=60,
        status=status,
    ))
