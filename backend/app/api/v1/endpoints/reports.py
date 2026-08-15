"""Reports module — revenue analytics, metric definitions, charts, export scope settings.

Revenue is computed from the canonical issued-invoices semantic layer
(`Invoice.status == "issued"`, `Invoice.total`, `Invoice.invoice_date`), the same
single source of truth used by Dashboard, AI, GL and customer finance.
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.core.time import utc_now
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceItem
from app.models.module import AppModule
from app.models.reporting import SavedReport, ReportSchedule, ReportDimension
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


# ── Saved reports ─────────────────────────────────────────────────────────────

@router.get("/saved", response_model=ResponseBase[list[dict]])
async def list_saved_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    result = await db.execute(
        select(SavedReport).where(SavedReport.company_id == current_user.company_id).order_by(SavedReport.name)
    )
    return ResponseBase(data=[{"id": str(r.id), "name": r.name, "report_type": r.report_type, "config": r.config, "created_at": r.created_at.isoformat()} for r in result.scalars().all()])


@router.post("/saved", response_model=ResponseBase[dict], status_code=201)
async def create_saved_report(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_create")),
):
    r = SavedReport(
        company_id=current_user.company_id,
        name=data.get("name", ""),
        report_type=data.get("report_type", "custom"),
        config=data.get("config", "{}"),
        created_by=current_user.id,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return ResponseBase(data={"id": str(r.id), "name": r.name}, message="რეპორტი შეინახა")


@router.delete("/saved/{report_id}", response_model=ResponseBase[dict])
async def delete_saved_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_delete")),
):
    result = await db.execute(
        select(SavedReport).where(SavedReport.id == report_id, SavedReport.company_id == current_user.company_id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="რეპორტი არ მოიძებნა")
    await db.delete(r)
    await db.commit()
    return ResponseBase(data={"id": str(report_id)}, message="რეპორტი წაიშალა")


# ── Schedules ──────────────────────────────────────────────────────────────────

@router.get("/schedules", response_model=ResponseBase[list[dict]])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    result = await db.execute(
        select(ReportSchedule).where(ReportSchedule.company_id == current_user.company_id).order_by(ReportSchedule.created_at.desc())
    )
    return ResponseBase(data=[{"id": str(s.id), "report_id": str(s.report_id), "frequency": s.frequency, "recipients": s.recipients, "is_active": s.is_active} for s in result.scalars().all()])


@router.post("/schedules", response_model=ResponseBase[dict], status_code=201)
async def create_schedule(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_create")),
):
    s = ReportSchedule(
        company_id=current_user.company_id,
        report_id=data.get("report_id"),
        frequency=data.get("frequency", "weekly"),
        recipients=data.get("recipients", ""),
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return ResponseBase(data={"id": str(s.id), "frequency": s.frequency}, message="განრიგი შეიქმნა")


# ── Dimensions ─────────────────────────────────────────────────────────────────

@router.get("/dimensions", response_model=ResponseBase[list[dict]])
async def list_dimensions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    result = await db.execute(
        select(ReportDimension).where(ReportDimension.company_id == current_user.company_id).order_by(ReportDimension.name)
    )
    return ResponseBase(data=[{"id": str(d.id), "name": d.name, "label": d.label, "is_active": d.is_active} for d in result.scalars().all()])


@router.post("/dimensions", response_model=ResponseBase[dict], status_code=201)
async def create_dimension(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_create")),
):
    d = ReportDimension(company_id=current_user.company_id, name=data.get("name", ""), label=data.get("label", ""))
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return ResponseBase(data={"id": str(d.id), "name": d.name}, message="განზომილება შეიქმნა")


# ── Pivot ──────────────────────────────────────────────────────────────────────

@router.get("/pivot", response_model=ResponseBase[dict])
async def pivot_report(
    metric: str = "revenue",
    group_by: str = "month",
    dimension: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("reports", "can_access")),
):
    """Pivot-style aggregation: revenue/expenses grouped by month, branch, product or manager."""
    from sqlalchemy import text

    if metric not in ("revenue", "expenses"):
        raise HTTPException(status_code=400, detail="მეტრიკა უნდა იყოს revenue ან expenses")

    group_col = {
        "month": "to_char(i.invoice_date, 'YYYY-MM')",
        "branch": "i.branch_id::text",
        "product": "ii.product_id::text",
        "manager": "i.manager_id::text",
    }.get(group_by, "to_char(i.invoice_date, 'YYYY-MM')")

    where = "i.company_id = :cid AND i.status = 'issued'"
    params: dict = {"cid": current_user.company_id}
    if date_from:
        where += " AND i.invoice_date >= :df"
        params["df"] = date_from
    if date_to:
        where += " AND i.invoice_date <= :dt"
        params["dt"] = date_to

    if metric == "revenue":
        sql = f"SELECT {group_col} AS grp, SUM(ii.line_total) AS value FROM invoice_items ii JOIN invoices i ON i.id = ii.invoice_id WHERE {where} GROUP BY grp ORDER BY grp"
    else:
        sql = f"SELECT {group_col} AS grp, SUM(e.amount) AS value FROM expenses e WHERE {where.replace('i.', 'e.')} GROUP BY grp ORDER BY grp"

    result = await db.execute(text(sql), params)
    rows = [{"group": str(r[0]), "value": float(r[1] or 0)} for r in result.fetchall()]
    return ResponseBase(data={"metric": metric, "group_by": group_by, "rows": rows})
