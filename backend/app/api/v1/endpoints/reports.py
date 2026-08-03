"""Reports module — revenue analytics, metric definitions, charts, export scope settings.

Revenue is computed from the canonical issued-invoices semantic layer
(`Invoice.status == "issued"`, `Invoice.total`, `Invoice.invoice_date`), the same
single source of truth used by Dashboard, AI, GL and customer finance.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceItem
from app.models.module import AppModule
from app.models.product import Product
from app.models.report import ReportPreference
from app.models.receivable import CustomerReceivable
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.report import (
    ExportScope,
    ExportScopeUpdate,
    MetricDefinition,
    ReportsCharts,
    ReportsKPIs,
    ReportsRevenueRow,
    ReportsSummary,
    RevenueByMonthPoint,
    TopClient,
    TopProduct,
)

router = APIRouter(prefix="/reports", tags=["რეპორტები"])

VALID_RANGES = {"7d", "30d", "90d", "12m", "all"}

# ── Metric definitions (explanations surfaced to the UI) ─────────────────────
METRIC_DEFINITIONS = [
    MetricDefinition(
        key="total_revenue",
        label="ჯამური შემოსავალი",
        formula="SUM(invoices.total) WHERE status='issued'",
        source="გაყიდვის ინვოისები (issued)",
        description=(
            "შემოსავალი გამოითვლება მხოლოდ დადასტურებული (issued) ინვოისებიდან — "
            "ინვოისის ჯამური თანხის ჯამი არჩეულ პერიოდში."
        ),
    ),
    MetricDefinition(
        key="total_invoices",
        label="ინვოისების რაოდენობა",
        formula="COUNT(invoices) WHERE status='issued'",
        source="გაყიდვის ინვოისები (issued)",
        description="არჩეულ პერიოდში გაცემული (issued) ინვოისების რაოდენობა.",
    ),
    MetricDefinition(
        key="avg_invoice_value",
        label="საშუალო ინვოისის ღირებულება",
        formula="total_revenue / total_invoices",
        source="გაყიდვის ინვოისები (issued)",
        description="საშუალო თანხა ერთ ინვოისზე — ჯამური შემოსავალი გაყოფილი ინვოისების რაოდენობაზე.",
    ),
    MetricDefinition(
        key="paid_revenue",
        label="მიღებული შემოსავალი",
        formula="SUM(customer_receivables.paid_amount)",
        source="მომხმარებელთა დავალიანება (შეგროვებული)",
        description="არჩეულ პერიოდში რეალურად მიღებული გადახდების ჯამი.",
    ),
    MetricDefinition(
        key="outstanding_revenue",
        label="გადასახდელი შემოსავალი",
        formula="SUM(customer_receivables.outstanding_amount)",
        source="მომხმარებელთა დავალიანება",
        description="ჯერ მიუღებელი (outstanding) დავალიანების ჯამი issued ინვოისების მიხედვით.",
    ),
]

# Georgian month labels for chart x-axis.
_MONTH_LABELS = [
    "იან", "თებ", "მარ", "აპრ", "მაი", "ივნ",
    "ივლ", "აგვ", "სექ", "ოქტ", "ნოე", "დეკ",
]


def _resolve_range(period: str) -> tuple[date, date]:
    """Return (date_from, date_to) for a period key."""
    today = date.today()
    if period == "7d":
        return today - timedelta(days=7), today
    if period == "30d":
        return today - timedelta(days=30), today
    if period == "90d":
        return today - timedelta(days=90), today
    if period == "12m":
        return today.replace(year=today.year - 1, day=1), today
    # "all" — earliest possible date (1970-01-01)
    return date(1970, 1, 1), today


async def _get_or_create_preferences(db: AsyncSession, company_id) -> ReportPreference:
    result = await db.execute(
        select(ReportPreference).where(ReportPreference.company_id == company_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = ReportPreference(
            company_id=company_id,
            default_date_range="30d",
            default_export_scope="current",
            group_by_month=False,
        )
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


async def _revenue_kpis(db: AsyncSession, company_id, date_from: date, date_to: date) -> ReportsKPIs:
    """KPIs computed from the issued-invoices semantic layer within the range."""
    rev_row = (await db.execute(
        select(
            func.coalesce(func.sum(Invoice.total), 0),
            func.count(Invoice.id),
        )
        .where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
    )).one()
    total_rev = Decimal(str(rev_row[0] or 0))
    total_invoices = int(rev_row[1] or 0)
    avg = (total_rev / total_invoices) if total_invoices else Decimal("0")

    # Paid / outstanding revenue from receivables linked to issued invoices in range.
    recv_row = (await db.execute(
        select(
            func.coalesce(func.sum(CustomerReceivable.paid_amount), 0),
            func.coalesce(func.sum(CustomerReceivable.outstanding_amount), 0),
        )
        .join(Invoice, Invoice.id == CustomerReceivable.invoice_id)
        .where(
            CustomerReceivable.company_id == company_id,
            Invoice.status == "issued",
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
    )).one()

    return ReportsKPIs(
        total_revenue=float(total_rev),
        total_invoices=total_invoices,
        avg_invoice_value=float(avg),
        paid_revenue=float(recv_row[0] or 0),
        outstanding_revenue=float(recv_row[1] or 0),
    )


async def _revenue_by_month(
    db: AsyncSession, company_id, date_from: date, date_to: date
) -> List[RevenueByMonthPoint]:
    """Group issued-invoice revenue by calendar month."""
    month_expr = func.date_trunc("month", Invoice.invoice_date)
    rows = (await db.execute(
        select(
            month_expr.label("month"),
            func.coalesce(func.sum(Invoice.total), 0),
            func.count(Invoice.id),
        )
        .where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
        .group_by(month_expr)
        .order_by(month_expr)
    )).all()

    points = []
    for month_dt, amount, count in rows:
        m = month_dt.date()
        points.append(RevenueByMonthPoint(
            month=m.strftime("%Y-%m"),
            label=f"{_MONTH_LABELS[m.month - 1]} {m.year}",
            amount=float(amount or 0),
            invoice_count=int(count or 0),
        ))
    return points


async def _top_products(
    db: AsyncSession, company_id, date_from: date, date_to: date, limit: int
) -> List[TopProduct]:
    """Top products by revenue from issued-invoice items in the range."""
    rows = (await db.execute(
        select(
            InvoiceItem.product_name,
            func.coalesce(func.sum(InvoiceItem.quantity), 0),
            func.coalesce(func.sum(InvoiceItem.line_total), 0),
        )
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
        .group_by(InvoiceItem.product_name)
        .order_by(func.sum(InvoiceItem.line_total).desc())
        .limit(limit)
    )).all()

    return [
        TopProduct(name=name, quantity=float(qty or 0), revenue=float(rev or 0))
        for name, qty, rev in rows
    ]


async def _top_clients(
    db: AsyncSession, company_id, date_from: date, date_to: date, limit: int
) -> List[TopClient]:
    """Top clients by revenue from issued invoices in the range."""
    rows = (await db.execute(
        select(
            Invoice.client_id,
            Invoice.client_name,
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.total), 0),
        )
        .where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        )
        .group_by(Invoice.client_id, Invoice.client_name)
        .order_by(func.sum(Invoice.total).desc())
        .limit(limit)
    )).all()

    return [
        TopClient(
            client_id=str(cid),
            name=cname,
            invoice_count=int(cnt or 0),
            revenue=float(rev or 0),
        )
        for cid, cname, cnt, rev in rows
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=ResponseBase[ReportsSummary])
async def reports_summary(
    period: str = Query("30d", description="7d | 30d | 90d | 12m | all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    """Full reports payload: KPIs, charts, metric definitions, export scope."""
    if period not in VALID_RANGES:
        raise HTTPException(status_code=422, detail="პერიოდი უნდა იყოს: 7d, 30d, 90d, 12m, all")
    company_id = current_user.company_id
    date_from, date_to = _resolve_range(period)

    kpi = await _revenue_kpis(db, company_id, date_from, date_to)
    charts = ReportsCharts(
        revenue_by_month=await _revenue_by_month(db, company_id, date_from, date_to),
        top_products=await _top_products(db, company_id, date_from, date_to, limit=5),
        top_clients=await _top_clients(db, company_id, date_from, date_to, limit=5),
    )
    pref = await _get_or_create_preferences(db, company_id)
    export_scope = ExportScope(
        default_date_range=pref.default_date_range,
        default_export_scope=pref.default_export_scope,
        group_by_month=pref.group_by_month,
    )

    return ResponseBase(data=ReportsSummary(
        period=period,
        date_from=date_from,
        date_to=date_to,
        kpi=kpi,
        charts=charts,
        metric_definitions=METRIC_DEFINITIONS,
        export_scope=export_scope,
    ))


@router.get("/revenue", response_model=ResponseBase[dict])
async def reports_revenue(
    period: str = Query("30d", description="7d | 30d | 90d | 12m | all"),
    group_by: str = Query("month", description="month | day"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    """Revenue series for charts: grouped by month or by day."""
    if period not in VALID_RANGES:
        raise HTTPException(status_code=422, detail="პერიოდი უნდა იყოს: 7d, 30d, 90d, 12m, all")
    if group_by not in {"month", "day"}:
        raise HTTPException(status_code=422, detail="group_by უნდა იყოს: month ან day")
    company_id = current_user.company_id
    date_from, date_to = _resolve_range(period)

    if group_by == "month":
        points = [
            ReportsRevenueRow(period_label=p.month, amount=p.amount, invoice_count=p.invoice_count)
            for p in await _revenue_by_month(db, company_id, date_from, date_to)
        ]
    else:
        day_expr = func.date_trunc("day", Invoice.invoice_date)
        rows = (await db.execute(
            select(
                day_expr.label("day"),
                func.coalesce(func.sum(Invoice.total), 0),
                func.count(Invoice.id),
            )
            .where(
                Invoice.company_id == company_id,
                Invoice.status == "issued",
                Invoice.invoice_date >= date_from,
                Invoice.invoice_date <= date_to,
            )
            .group_by(day_expr)
            .order_by(day_expr)
        )).all()
        points = [
            ReportsRevenueRow(
                period_label=d.date().strftime("%Y-%m-%d"),
                amount=float(amount or 0),
                invoice_count=int(cnt or 0),
            )
            for d, amount, cnt in rows
        ]

    return ResponseBase(data={
        "period": period,
        "group_by": group_by,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "data": [p.model_dump() for p in points],
    })


@router.get("/definitions", response_model=ResponseBase[list[MetricDefinition]])
async def reports_definitions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    """Metric explanations/definitions for the reports UI (tooltips, help)."""
    return ResponseBase(data=METRIC_DEFINITIONS)


@router.get("/export-scope", response_model=ResponseBase[ExportScope])
async def get_export_scope(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    """Get the company's default report date-range + export-scope settings."""
    pref = await _get_or_create_preferences(db, current_user.company_id)
    return ResponseBase(data=ExportScope(
        default_date_range=pref.default_date_range,
        default_export_scope=pref.default_export_scope,
        group_by_month=pref.group_by_month,
    ))


@router.patch("/export-scope", response_model=ResponseBase[ExportScope])
async def update_export_scope(
    payload: ExportScopeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_edit")),
):
    """Update the company's default export scope settings."""
    pref = await _get_or_create_preferences(db, current_user.company_id)
    if payload.default_date_range is not None:
        pref.default_date_range = payload.default_date_range
    if payload.default_export_scope is not None:
        pref.default_export_scope = payload.default_export_scope
    if payload.group_by_month is not None:
        pref.group_by_month = payload.group_by_month
    await db.commit()
    await db.refresh(pref)
    return ResponseBase(data=ExportScope(
        default_date_range=pref.default_date_range,
        default_export_scope=pref.default_export_scope,
        group_by_month=pref.group_by_month,
    ))
