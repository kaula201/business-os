"""Reports module schemas: metrics, definitions, charts, export scope settings."""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Metric definitions (explanations) ────────────────────────────────────────
class MetricDefinition(BaseModel):
    """A human-readable explanation for one report metric."""
    key: str
    label: str
    formula: str
    source: str
    description: str


# ── KPI summary ───────────────────────────────────────────────────────────────
class ReportsKPIs(BaseModel):
    total_revenue: float = 0.0
    total_invoices: int = 0
    avg_invoice_value: float = 0.0
    paid_revenue: float = 0.0
    outstanding_revenue: float = 0.0


# ── Charts ────────────────────────────────────────────────────────────────────
class RevenueByMonthPoint(BaseModel):
    month: str  # "2026-01"
    label: str  # "იან 2026"
    amount: float = 0.0
    invoice_count: int = 0


class TopProduct(BaseModel):
    product_id: Optional[str] = None
    name: str
    quantity: float = 0.0
    revenue: float = 0.0


class TopClient(BaseModel):
    client_id: Optional[str] = None
    name: str
    invoice_count: int = 0
    revenue: float = 0.0


class ReportsCharts(BaseModel):
    revenue_by_month: List[RevenueByMonthPoint] = []
    top_products: List[TopProduct] = []
    top_clients: List[TopClient] = []


# ── Export scope / preferences ────────────────────────────────────────────────
class ExportScope(BaseModel):
    default_date_range: str = Field("30d", description="7d, 30d, 90d, 12m, all")
    default_export_scope: str = Field("current", description="current | all")
    group_by_month: bool = Field(False)


class ExportScopeUpdate(BaseModel):
    default_date_range: Optional[str] = Field(None, pattern="^(7d|30d|90d|12m|all)$")
    default_export_scope: Optional[str] = Field(None, pattern="^(current|all)$")
    group_by_month: Optional[bool] = None


# ── Report response (single fetchable object) ────────────────────────────────
class ReportsSummary(BaseModel):
    period: str
    date_from: date
    date_to: date
    kpi: ReportsKPIs
    charts: ReportsCharts
    metric_definitions: List[MetricDefinition] = []
    export_scope: ExportScope


class ReportsRevenueRow(BaseModel):
    """One row for the revenue detail endpoint (per month or per day)."""
    period_label: str
    amount: float = 0.0
    invoice_count: int = 0
