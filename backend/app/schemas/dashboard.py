# backend/app/schemas/dashboard.py
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class KPICards(BaseModel):
    active_clients: int
    active_orders: int
    overdue_tasks: int
    low_stock_products: int
    total_revenue: float = 0.0
    pipeline_value: float = 0.0
    open_leads: int = 0
    receivables_outstanding: float = 0.0
    payables_outstanding: float = 0.0
    stock_value: float = 0.0
    inventory_units: float = 0.0
    cashflow_30d: float = 0.0
    unpaid_invoices: float = 0.0
    # Period comparison (vs previous period of same length) — null when undeterminable
    revenue_change: float | None = None
    orders_change: float | None = None
    clients_change: float | None = None
    tasks_change: float | None = None
    cashflow_change: float | None = None


class KPITooltip(BaseModel):
    """Formula and source explanation for each KPI."""
    key: str
    label: str
    formula: str
    source: str


class RevenueChart(BaseModel):
    period: str  # 7d, 30d, 90d
    data: List["RevenueDataPoint"]


class RevenueDataPoint(BaseModel):
    date: str
    amount: float
    order_count: int


class OrderStatusDistribution(BaseModel):
    status: str
    count: int
    color: str


class RecentActivity(BaseModel):
    id: str
    type: str  # order_created, order_status_changed, client_added, task_completed
    description: str
    timestamp: datetime
    entity_id: Optional[str] = None


class DashboardSummary(BaseModel):
    kpi: KPICards
    revenue_chart: RevenueChart
    order_status_distribution: List[OrderStatusDistribution]
    recent_activity: List[RecentActivity]
    ai_summary: Optional[str] = None
    critical_alerts: List["CriticalAlert"]
    total_revenue: float = 0.0
    invoiced_orders_count: int = 0
    total_orders_count: int = 0
    kpi_tooltips: List[KPITooltip] = []


class CriticalAlert(BaseModel):
    type: str  # low_stock, overdue_task, overdue_payment
    severity: str  # high, medium
    title: str
    description: str
    entity_id: Optional[str] = None
