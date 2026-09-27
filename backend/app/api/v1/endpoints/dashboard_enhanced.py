"""Dashboard enhanced: quick actions, CRM pipeline, HR stats, export."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.order import Order, OrderStatus, OrderFulfillment
from app.models.client import Client
from app.models.product import Product
from app.models.warehouse import InventoryBalance
from app.core.time import utc_now
from app.models.task import Task
from app.models.crm import CRMLead, CRMOpportunity
from app.models.hr import Employee
from app.models.invoice import Invoice
from app.models.company import Company
from app.models.wms_ops import Shipment
from app.models.production import WorkOrder
from app.models.fleet import Vehicle
from app.models.maintenance import MaintenanceOrder
from app.models.approval import ApprovalRequest
from app.models.reporting import MetricDefinition
from app.models.receivable import (
    CustomerPayment,
    CustomerPaymentReversal,
    CustomerReceivable,
)
from app.models.purchase import (
    Supplier,
    SupplierInvoice,
    SupplierPayable,
    SupplierPayment,
    SupplierPaymentReversal,
)
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
    now = utc_now()

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

    # Low stock (canonical: sum of warehouse balances)
    stock_total = (
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.product_id == Product.id,
        )
        .correlate(Product)
        .scalar_subquery()
    )
    low_stock = (await db.execute(
        select(func.count(Product.id)).where(Product.company_id == company_id, stock_total <= Product.min_stock, Product.is_active == True)
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
    now = utc_now()

    overdue = (await db.execute(
        select(func.count(Task.id)).where(Task.company_id == company_id, Task.due_date < now, Task.status.notin_(["done", "cancelled"]))
    )).scalar() or 0

    stock_total_qa = (
        select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
        .where(
            InventoryBalance.company_id == company_id,
            InventoryBalance.product_id == Product.id,
        )
        .correlate(Product)
        .scalar_subquery()
    )
    low_stock = (await db.execute(
        select(func.count(Product.id)).where(Product.company_id == company_id, stock_total_qa <= Product.min_stock, Product.is_active == True)
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


# ── Dashboard 2.0: AR/AP aging, cash flow, drill-down ─────────────────────────

class AgingBucket(BaseModel):
    bucket: str            # current / 1_30 / 31_60 / 61_90 / 90_plus
    label: str
    amount: Decimal


class AgingSummary(BaseModel):
    currency: str
    ar_total: Decimal
    ap_total: Decimal
    ar_buckets: list[AgingBucket]
    ap_buckets: list[AgingBucket]


class CashFlowPoint(BaseModel):
    month: str             # YYYY-MM
    inflow: Decimal
    outflow: Decimal


class CashFlowSummary(BaseModel):
    currency: str
    series: list[CashFlowPoint]
    net_6m: Decimal


class DrillDownRow(BaseModel):
    id: str
    number: str
    counterparty: str
    due_date: str | None
    outstanding: Decimal
    days_overdue: int
    status: str
    currency: str


class DrillDownSummary(BaseModel):
    currency: str
    rows: list[DrillDownRow]


async def _report_currency(
    db: AsyncSession, company_id: UUID, requested: str | None
) -> str:
    if requested:
        return requested.upper()
    base_currency = await db.scalar(
        select(Company.currency).where(Company.id == company_id)
    )
    return (base_currency or "GEL").upper()


def _aging_buckets(rows: list[tuple[date, Decimal]]) -> list[AgingBucket]:
    today = date.today()
    buckets = {
        "current": Decimal("0"), "1_30": Decimal("0"), "31_60": Decimal("0"),
        "61_90": Decimal("0"), "90_plus": Decimal("0"),
    }
    for due_date, amount in rows:
        days = (today - due_date).days
        if days <= 0:
            buckets["current"] += amount
        elif days <= 30:
            buckets["1_30"] += amount
        elif days <= 60:
            buckets["31_60"] += amount
        elif days <= 90:
            buckets["61_90"] += amount
        else:
            buckets["90_plus"] += amount
    labels = {
        "current": "მიმდინარე", "1_30": "1–30 დღე", "31_60": "31–60 დღე",
        "61_90": "61–90 დღე", "90_plus": "90+ დღე",
    }
    return [
        AgingBucket(bucket=k, label=labels[k], amount=v)
        for k, v in buckets.items()
    ]


@router.get("/aging", response_model=ResponseBase[AgingSummary])
async def aging_summary(
    currency: str | None = Query(None, min_length=3, max_length=3),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    """AR/AP aging: outstanding receivables and payables by due-date bucket."""
    company_id = current_user.company_id
    report_currency = await _report_currency(db, company_id, currency)
    ar = (await db.execute(
        select(CustomerReceivable.due_date, CustomerReceivable.outstanding_amount)
        .where(
            CustomerReceivable.company_id == company_id,
            CustomerReceivable.currency == report_currency,
            CustomerReceivable.outstanding_amount > 0,
        )
    )).all()
    ap = (await db.execute(
        select(SupplierPayable.due_date, SupplierPayable.outstanding_amount)
        .where(
            SupplierPayable.company_id == company_id,
            SupplierPayable.currency_code == report_currency,
            SupplierPayable.outstanding_amount > 0,
        )
    )).all()

    ar_total = sum((Decimal(str(r.outstanding_amount)) for r in ar), Decimal("0"))
    ap_total = sum((Decimal(str(r.outstanding_amount)) for r in ap), Decimal("0"))

    return ResponseBase(data=AgingSummary(
        currency=report_currency,
        ar_total=ar_total,
        ap_total=ap_total,
        ar_buckets=_aging_buckets([(r.due_date, Decimal(str(r.outstanding_amount))) for r in ar]),
        ap_buckets=_aging_buckets([(r.due_date, Decimal(str(r.outstanding_amount))) for r in ap]),
    ))


def _month_offset(base: date, months_back: int) -> date:
    """First day of the month `months_back` months before `base`."""
    total = base.year * 12 + (base.month - 1) - months_back
    return date(total // 12, total % 12 + 1, 1)


@router.get("/cash-flow", response_model=ResponseBase[CashFlowSummary])
async def cash_flow(
    currency: str | None = Query(None, min_length=3, max_length=3),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    """Last 6 months of cash in/out: customer payments vs supplier payments."""
    company_id = current_user.company_id
    report_currency = await _report_currency(db, company_id, currency)
    today = date.today()
    six_months_ago = _month_offset(today, 5)

    customer_payments = (await db.execute(
        select(
            func.date_trunc("month", CustomerPayment.payment_date).label("month"),
            func.sum(CustomerPayment.amount),
        )
        .join(
            CustomerReceivable,
            CustomerReceivable.id == CustomerPayment.receivable_id,
        )
        .outerjoin(
            CustomerPaymentReversal,
            CustomerPaymentReversal.payment_id == CustomerPayment.id,
        )
        .where(
            CustomerPayment.company_id == company_id,
            CustomerPayment.status == "active",
            CustomerPaymentReversal.id.is_(None),
            CustomerReceivable.currency == report_currency,
            CustomerPayment.payment_date >= six_months_ago,
        )
        .group_by("month")
        .order_by("month")
    )).all()

    supplier_payments = (await db.execute(
        select(
            func.date_trunc("month", SupplierPayment.payment_date).label("month"),
            func.sum(SupplierPayment.amount),
        )
        .join(
            SupplierPayable,
            SupplierPayable.id == SupplierPayment.supplier_payable_id,
        )
        .outerjoin(
            SupplierPaymentReversal,
            SupplierPaymentReversal.supplier_payment_id == SupplierPayment.id,
        )
        .where(
            SupplierPayment.company_id == company_id,
            SupplierPaymentReversal.id.is_(None),
            SupplierPayable.currency_code == report_currency,
            SupplierPayment.payment_date >= six_months_ago,
        )
        .group_by("month")
        .order_by("month")
    )).all()

    inflow_map = {r.month.strftime("%Y-%m"): Decimal(str(r.sum or 0)) for r in customer_payments}
    outflow_map = {r.month.strftime("%Y-%m"): Decimal(str(r.sum or 0)) for r in supplier_payments}

    series = []
    for i in range(5, -1, -1):
        m = _month_offset(today, i)
        key = m.strftime("%Y-%m")
        series.append(CashFlowPoint(
            month=key,
            inflow=inflow_map.get(key, Decimal("0")),
            outflow=outflow_map.get(key, Decimal("0")),
        ))

    net = sum((p.inflow - p.outflow for p in series), Decimal("0"))
    return ResponseBase(data=CashFlowSummary(
        currency=report_currency,
        series=series,
        net_6m=net,
    ))


@router.get("/drill-down/{entity}", response_model=ResponseBase[DrillDownSummary])
async def drill_down(
    entity: Literal["ar", "ap"],
    bucket: Literal["all", "current", "1_30", "31_60", "61_90", "90_plus"] = "all",
    currency: str | None = Query(None, min_length=3, max_length=3),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    """Drill-down rows for AR or AP in one explicitly selected currency."""
    company_id = current_user.company_id
    report_currency = await _report_currency(db, company_id, currency)
    today = date.today()
    rows: list[DrillDownRow] = []

    if entity == "ar":
        result = await db.execute(
            select(CustomerReceivable)
            .where(
                CustomerReceivable.company_id == company_id,
                CustomerReceivable.currency == report_currency,
                CustomerReceivable.outstanding_amount > 0,
            )
            .order_by(CustomerReceivable.due_date)
        )
        for r in result.scalars().all():
            days = (today - r.due_date).days
            if bucket != "all":
                in_bucket = (
                    (bucket == "current" and days <= 0)
                    or (bucket == "1_30" and 0 < days <= 30)
                    or (bucket == "31_60" and 30 < days <= 60)
                    or (bucket == "61_90" and 60 < days <= 90)
                    or (bucket == "90_plus" and days > 90)
                )
                if not in_bucket:
                    continue
            rows.append(DrillDownRow(
                id=str(r.id), number=r.invoice_number, counterparty=r.client_name,
                due_date=r.due_date.isoformat(), outstanding=r.outstanding_amount,
                days_overdue=max(days, 0), status=r.status, currency=r.currency,
            ))
    else:
        result = await db.execute(
            select(
                SupplierPayable.id,
                SupplierPayable.due_date,
                SupplierPayable.outstanding_amount,
                SupplierPayable.status,
                SupplierPayable.currency_code,
                SupplierInvoice.supplier_invoice_number.label("invoice_number"),
                Supplier.name.label("supplier_name"),
            )
            .join(
                SupplierInvoice,
                SupplierInvoice.id == SupplierPayable.supplier_invoice_id,
            )
            .join(Supplier, Supplier.id == SupplierPayable.supplier_id)
            .where(
                SupplierPayable.company_id == company_id,
                SupplierPayable.currency_code == report_currency,
                SupplierPayable.outstanding_amount > 0,
            )
            .order_by(SupplierPayable.due_date)
        )
        for r in result.all():
            days = (today - r.due_date).days
            if bucket != "all":
                in_bucket = (
                    (bucket == "current" and days <= 0)
                    or (bucket == "1_30" and 0 < days <= 30)
                    or (bucket == "31_60" and 30 < days <= 60)
                    or (bucket == "61_90" and 60 < days <= 90)
                    or (bucket == "90_plus" and days > 90)
                )
                if not in_bucket:
                    continue
            rows.append(DrillDownRow(
                id=str(r.id), number=r.invoice_number, counterparty=r.supplier_name,
                due_date=r.due_date.isoformat(), outstanding=r.outstanding_amount,
                days_overdue=max(days, 0), status=r.status, currency=r.currency_code,
            ))

    return ResponseBase(data=DrillDownSummary(
        currency=report_currency,
        rows=rows,
    ))


# ── Dashboard customization: role views, KPI definitions, drill-down ──────────

class DashboardRoleView(BaseModel):
    key: str
    label: str
    kpis: list[str]
    modules: list[str]


class RoleViewsResponse(BaseModel):
    views: list[DashboardRoleView]
    default_view: str


@router.get("/role-views", response_model=ResponseBase[RoleViewsResponse])
async def role_views(
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    """Role-based dashboard layouts. Admin → director, accountant → finance,
    manager → sales, employee → default."""
    role = current_user.role
    admin_view = DashboardRoleView(
        key="director", label="დირექტორი",
        kpis=["revenue", "orders", "delayed_shipments", "production_backlog", "fleet_unavailable", "maintenance_critical", "approvals_pending", "otif_rate", "tms_dispatched", "tms_active", "tms_delayed"],
        modules=["sales", "finance", "crm", "tasks", "warehouse", "production", "fleet", "maintenance"],
    )
    acct_view = DashboardRoleView(
        key="accountant", label="ბუღალტერი",
        kpis=["revenue", "cashflow", "receivables", "payables", "unpaid_invoices", "approvals_pending"],
        modules=["finance", "accounting"],
    )
    sales_view = DashboardRoleView(
        key="sales", label="გაყიდვების მენეჯერი",
        kpis=["revenue", "orders", "clients", "pipeline", "leads", "delayed_shipments"],
        modules=["sales", "crm"],
    )
    wh_view = DashboardRoleView(
        key="warehouse", label="საწყობის მენეჯერი",
        kpis=["low_stock", "stock_value", "orders", "inventory", "delayed_shipments"],
        modules=["warehouse", "sales"],
    )
    operator_view = DashboardRoleView(
        key="operator", label="ოპერატორი",
        kpis=["tasks", "approvals_pending", "orders", "delayed_shipments", "maintenance_critical"],
        modules=["tasks", "sales", "maintenance"],
    )
    default_view = "director" if role == User.Role.ADMIN else (
        "accountant" if role == User.Role.ACCOUNTANT else (
            "sales" if role == User.Role.MANAGER else (
                "operator" if role == User.Role.EMPLOYEE else "director"
            )
        )
    )
    views = [admin_view, acct_view, sales_view, wh_view, operator_view]
    return ResponseBase(data=RoleViewsResponse(views=views, default_view=default_view))


KPI_DEFINITIONS: dict[str, dict] = {
    "revenue": {
        "label": "შემოსავალი",
        "formula": "Σ Invoice.total, სადაც status = 'issued' (გაცემული ინვოისები) — შეკვეთები შემოსავალში მხოლოდ ინვოისირების შემდეგ ხვდება",
        "source": "invoices ცხრილი, status = 'issued'",
    },
    "orders": {
        "label": "მიმდინარე შეკვეთები",
        "formula": "COUNT(orders) — სტატუსით გარდა completed/cancelled-ის",
        "source": "orders ცხრილი",
    },
    "clients": {
        "label": "აქტიური კლიენტები",
        "formula": "COUNT(clients) — deleted_at IS NULL",
        "source": "clients ცხრილი",
    },
    "tasks": {
        "label": "დაგვიანებული დავალებები",
        "formula": "COUNT(tasks) — due_date < now და status ∉ {done, cancelled}",
        "source": "tasks ცხრილი",
    },
    "cashflow": {
        "label": "ფულადი ნაკადი (6 თვე)",
        "formula": "Σ payments (შემოსავალი) − Σ expenses (ხარჯები) ბოლო 6 თვეში",
        "source": "customer_payments / supplier_payments",
    },
    "pipeline": {
        "label": "CRM Pipeline ღირებულება",
        "formula": "Σ opportunities.amount — stage ∉ {won, lost}",
        "source": "crm_opportunities ცხრილი",
    },
    "leads": {
        "label": "ღია ლიდები",
        "formula": "COUNT(crm_leads) — status ∉ {converted, unqualified}",
        "source": "crm_leads ცხრილი",
    },
    "receivables": {
        "label": "მოვალეები (AR)",
        "formula": "Σ customer_receivables ბალანსი — ასაკის ჯგუფების მიხედვით",
        "source": "customer_receivables / aging",
    },
    "payables": {
        "label": "ვალდებულებები (AP)",
        "formula": "Σ supplier_payables ბალანსი",
        "source": "supplier_payables / aging",
    },
    "unpaid_invoices": {
        "label": "გადაუხდელი ინვოისები",
        "formula": "Σ Invoice.total — სტატუსით ≠ paid",
        "source": "invoices ცხრილი",
    },
    "low_stock": {
        "label": "დეფიციტური ნაწილები",
        "formula": "COUNT(products) — Σ warehouse ბალანსი ≤ min_stock",
        "source": "products + inventory_balances",
    },
    "stock_value": {
        "label": "საწყობის ღირებულება",
        "formula": "Σ inventory_balances.quantity × product.unit_cost",
        "source": "inventory_balances + products",
    },
    "inventory": {
        "label": "მარაგის ერთეულები",
        "formula": "Σ inventory_balances.quantity (ყველა პროდუქტი/საწყობი)",
        "source": "inventory_balances",
    },
    "delayed_shipments": {
        "label": "დაგვიანებული მიწოდება",
        "formula": "COUNT(orders) — delivery_date < now და status ∉ {completed, cancelled}",
        "source": "orders ცხრილი (delivery_date)",
    },
    "production_backlog": {
        "label": "წარმოების ჩამორჩენა",
        "formula": "COUNT(work_orders) — end_date < today და status ∈ {confirmed, in_progress}",
        "source": "work_orders ცხრილი",
    },
    "fleet_unavailable": {
        "label": "ავტოპარკის მიუწვდომლობა",
        "formula": "COUNT(vehicles) — is_active=false ან დაზღვევის/ტექდათვალიერების ვადა გასული",
        "source": "vehicles ცხრილი",
    },
    "maintenance_critical": {
        "label": "კრიტიკული მოვლა",
        "formula": "COUNT(maintenance_orders) — status ∈ {scheduled, in_progress} და (priority='critical' ან type='emergency')",
        "source": "maintenance_orders ცხრილი",
    },
    "approvals_pending": {
        "label": "დასამტკიცებელი",
        "formula": "COUNT(approval_requests) — status='pending'",
        "source": "approval_requests ცხრილი",
    },
    "otif_rate": {
        "label": "OTIF",
        "formula": "completed (ვადაში) / ვადამოსული შეკვეთები × 100; ვადამოსულის არქონისას N/A (შედარება ვერ ითვლება)",
        "source": "orders ცხრილი (delivery_date)",
    },
    "tms_dispatched": {
        "label": "TMS — გაგზავნილი",
        "formula": "COUNT(tms_trips) — status='dispatched'",
        "source": "tms_trips ცხრილი",
    },
    "tms_active": {
        "label": "TMS — აქტიური",
        "formula": "COUNT(tms_trips) — status='in_progress'",
        "source": "tms_trips ცხრილი",
    },
    "tms_delayed": {
        "label": "TMS — დაგვიანებული",
        "formula": "COUNT(tms_trips) — status ∈ {dispatched,in_progress} და planned_end < now",
        "source": "tms_trips ცხრილი (planned_end)",
    },
}


class KPIInfo(BaseModel):
    key: str
    label: str
    formula: str
    source: str


@router.get("/kpi-definitions", response_model=ResponseBase[list[KPIInfo]])
async def kpi_definitions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    """KPI registry from the MetricDefinition table (REQ-RPT-01). Seeds the
    authoritative dict on first call if the table is empty for this company."""
    cid = current_user.company_id
    rows = (await db.execute(
        select(MetricDefinition).where(
            MetricDefinition.company_id == cid, MetricDefinition.is_active.is_(True)
        ).order_by(MetricDefinition.code)
    )).scalars().all()

    if not rows:
        # Lazy seed from the canonical KPI_DEFINITIONS dict (one source of truth)
        for code, v in KPI_DEFINITIONS.items():
            db.add(MetricDefinition(
                company_id=cid,
                code=code,
                name=v["label"],
                description=v.get("description"),
                formula=v["formula"],
                source=v["source"],
                formula_version=v.get("formula_version", 1),
                allowed_roles=v.get("allowed_roles"),
                refresh_interval=v.get("refresh_interval", 60),
                grain=v.get("grain"),
            ))
        await db.commit()
        rows = (await db.execute(
            select(MetricDefinition).where(
                MetricDefinition.company_id == cid, MetricDefinition.is_active.is_(True)
            ).order_by(MetricDefinition.code)
        )).scalars().all()
    else:
        # backfill any new canonical KPI codes that arrived after the initial seed
        existing = {m.code for m in rows}
        missing = [c for c in KPI_DEFINITIONS if c not in existing]
        if missing:
            for code in missing:
                v = KPI_DEFINITIONS[code]
                db.add(MetricDefinition(
                    company_id=cid,
                    code=code,
                    name=v["label"],
                    description=v.get("description"),
                    formula=v["formula"],
                    source=v["source"],
                    formula_version=v.get("formula_version", 1),
                    allowed_roles=v.get("allowed_roles"),
                    refresh_interval=v.get("refresh_interval", 60),
                    grain=v.get("grain"),
                ))
            await db.commit()
            rows = (await db.execute(
                select(MetricDefinition).where(
                    MetricDefinition.company_id == cid, MetricDefinition.is_active.is_(True)
                ).order_by(MetricDefinition.code)
            )).scalars().all()

    return ResponseBase(data=[
        KPIInfo(key=m.code, label=m.name, formula=m.formula, source=m.source or "")
        for m in rows
    ])


class KpiDrillDownRow(BaseModel):
    label: str
    value: str
    date: str | None = None
    status: str | None = None


class KpiDrillDownResponse(BaseModel):
    kpi: str
    title: str
    rows: list[KpiDrillDownRow]
    total: str


def _days_ago(db: AsyncSession, company_id: UUID, model, col, days: int):
    pass  # helper placeholder (specific queries inline below)


@router.get("/kpi-detail/{kpi_key}", response_model=ResponseBase[KpiDrillDownResponse])
async def kpi_drill_down(
    kpi_key: str,
    limit: int = Query(10, ge=1, le=50),
    period: str = "30d",
    warehouse_id: str | None = None,
    owner_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("dashboard", "can_access")),
):
    """Latest rows behind each KPI — click a card to see what makes up the number.
    Scoped to the same period / owner / warehouse as the dashboard card
    (REQ-DASH: widget click → same-scope filtered list)."""
    cid = current_user.company_id
    today = date.today()
    days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 30)
    period_start_ts = datetime.combine(today - timedelta(days=days), datetime.min.time())

    # Optional owner / warehouse scope (mirrors /summary)
    owner_uuid = None
    if owner_id:
        try:
            owner_uuid = UUID(owner_id)
        except ValueError:
            owner_uuid = None
    wh_uuid = None
    if warehouse_id:
        try:
            wh_uuid = UUID(warehouse_id)
        except ValueError:
            wh_uuid = None

    if kpi_key == "revenue":
        # Canonical revenue = issued invoices (same source as summary KPI)
        rows = (await db.execute(
            select(Invoice).where(
                Invoice.company_id == cid,
                Invoice.status == "issued",
                Invoice.invoice_date >= period_start_ts.date(),
            )
            .order_by(Invoice.created_at.desc())
            .limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=f"ინვოისი {inv.invoice_number}", value=str(inv.total), date=str(inv.created_at.date() if inv.created_at else ""), status=inv.status) for inv in rows]
        total = str((await db.execute(select(func.coalesce(func.sum(Invoice.total), 0)).where(Invoice.company_id == cid, Invoice.status == "issued"))).scalar())
        return ResponseBase(data=KpiDrillDownResponse(kpi="revenue", title="შემოსავალი — გაცემული ინვოისები", rows=data, total=total))

    if kpi_key == "orders":
        scope = [Order.company_id == cid, Order.status.notin_([OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]), Order.created_at >= period_start_ts]
        if owner_uuid:
            scope.append(Order.assigned_to == owner_uuid)
        if wh_uuid:
            scope.append(
                Order.id.in_(
                    select(OrderFulfillment.order_id).where(OrderFulfillment.warehouse_id == wh_uuid)
                )
            )
        rows = (await db.execute(
            select(Order).where(*scope)
            .order_by(Order.created_at.desc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=f"#{o.order_number}", value=o.status, date=str(o.created_at.date() if o.created_at else ""), status=o.status) for o in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="orders", title="მიმდინარე შეკვეთები", rows=data, total=total))

    if kpi_key == "clients":
        rows = (await db.execute(
            select(Client).where(Client.company_id == cid, Client.deleted_at.is_(None))
            .order_by(Client.created_at.desc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=c.name or c.company_name or "—", value="კლიენტი", date=str(c.created_at.date() if c.created_at else "")) for c in rows]
        total = str((await db.execute(select(func.count(Client.id)).where(Client.company_id == cid, Client.deleted_at.is_(None)))).scalar())
        return ResponseBase(data=KpiDrillDownResponse(kpi="clients", title="ბოლო დამატებული კლიენტები", rows=data, total=total))

    if kpi_key == "tasks":
        rows = (await db.execute(
            select(Task).where(Task.company_id == cid, Task.due_date < utc_now(), Task.status.notin_(["done", "cancelled"]))
            .order_by(Task.due_date.asc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=t.title or "—", value="დაგვიანებული", date=str(t.due_date.date()) if t.due_date else None, status=t.status) for t in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="tasks", title="დაგვიანებული დავალებები", rows=data, total=total))

    if kpi_key == "leads":
        rows = (await db.execute(
            select(CRMLead).where(CRMLead.company_id == cid, CRMLead.status.notin_(["converted", "unqualified"]))
            .order_by(CRMLead.created_at.desc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=l.name or "—", value=l.status or "—", date=str(l.created_at.date()) if l.created_at else None, status=l.status) for l in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="leads", title="ღია ლიდები", rows=data, total=total))

    if kpi_key == "low_stock":
        stock_total = (
            select(func.coalesce(func.sum(InventoryBalance.quantity), 0))
            .where(InventoryBalance.company_id == cid, InventoryBalance.product_id == Product.id)
            .correlate(Product).scalar_subquery()
        )
        rows = (await db.execute(
            select(Product).where(Product.company_id == cid, stock_total <= Product.min_stock, Product.is_active == True)
            .order_by(Product.name).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=p.name or p.sku or "—", value=f"მინიმუმი: {p.min_stock}", status="low_stock") for p in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="low_stock", title="დეფიციტური პროდუქტები", rows=data, total=total))

    if kpi_key == "delayed_shipments":
        rows = (await db.execute(
            select(Order).where(
                Order.company_id == cid,
                Order.delivery_date.isnot(None),
                Order.delivery_date < utc_now(),
                Order.status.notin_([OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]),
            ).order_by(Order.delivery_date.asc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=f"#{o.order_number}", value=f"ვადა: {o.delivery_date.date() if o.delivery_date else '—'}", date=str(o.delivery_date.date()) if o.delivery_date else None, status=o.status) for o in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="delayed_shipments", title="დაგვიანებული მიწოდება", rows=data, total=total))

    if kpi_key == "production_backlog":
        rows = (await db.execute(
            select(WorkOrder).where(
                WorkOrder.company_id == cid,
                WorkOrder.end_date.isnot(None),
                WorkOrder.end_date < today,
                WorkOrder.status.in_(["confirmed", "in_progress"]),
            ).order_by(WorkOrder.end_date.asc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=f"#{wo.order_number}", value=wo.status, date=str(wo.end_date) if wo.end_date else None, status=wo.status) for wo in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="production_backlog", title="წარმოების ჩამორჩენა", rows=data, total=total))

    if kpi_key == "fleet_unavailable":
        rows = (await db.execute(
            select(Vehicle).where(
                Vehicle.company_id == cid,
                (Vehicle.is_active.is_(False))
                | (Vehicle.insurance_valid_until.isnot(None) & (Vehicle.insurance_valid_until < today))
                | (Vehicle.tech_inspection_until.isnot(None) & (Vehicle.tech_inspection_until < today)),
            ).order_by(Vehicle.plate_number).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=f"{v.plate_number} {v.brand} {v.model}".strip(), value="unavailable", status="fleet_unavailable") for v in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="fleet_unavailable", title="ავტოპარკის მიუწვდომლობა", rows=data, total=total))

    if kpi_key == "maintenance_critical":
        rows = (await db.execute(
            select(MaintenanceOrder).where(
                MaintenanceOrder.company_id == cid,
                MaintenanceOrder.status.in_(["scheduled", "in_progress"]),
                (MaintenanceOrder.priority == "critical") | (MaintenanceOrder.maintenance_type == "emergency"),
            ).order_by(MaintenanceOrder.created_at.desc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=f"#{mo.order_number} {mo.asset_name or ''}".strip(), value=mo.priority + '/' + mo.maintenance_type, date=str(mo.created_at.date()) if mo.created_at else None, status=mo.status) for mo in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="maintenance_critical", title="კრიტიკული მოვლა", rows=data, total=total))

    if kpi_key == "approvals_pending":
        rows = (await db.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.company_id == cid,
                ApprovalRequest.status == ApprovalRequest.Status.PENDING,
            ).order_by(ApprovalRequest.created_at.desc()).limit(limit)
        )).scalars().all()
        data = [KpiDrillDownRow(label=a.title or "—", value=a.approval_type, date=str(a.created_at.date()) if a.created_at else None, status=a.status) for a in rows]
        total = str(len(rows))
        return ResponseBase(data=KpiDrillDownResponse(kpi="approvals_pending", title="დასამტკიცებელი რიგი", rows=data, total=total))

    if kpi_key == "otif_rate":
        due = int((await db.execute(select(func.count(Order.id)).where(
            Order.company_id == cid, Order.delivery_date.isnot(None),
            Order.delivery_date < utc_now(), Order.status.notin_([OrderStatus.CANCELLED.value, OrderStatus.DRAFT.value]),
        ))).scalar() or 0)
        done = int((await db.execute(select(func.count(Order.id)).where(
            Order.company_id == cid, Order.delivery_date.isnot(None),
            Order.delivery_date < utc_now(), Order.status == OrderStatus.COMPLETED.value,
        ))).scalar() or 0)
        total_str = f"{done}/{due} ({round(done / due * 100, 1)}%)" if due else "N/A"
        return ResponseBase(data=KpiDrillDownResponse(kpi="otif_rate", title="OTIF — დროული მიწოდება", rows=[], total=total_str))

    return ResponseBase(data=KpiDrillDownResponse(kpi=kpi_key, title=kpi_key, rows=[], total="0"))
