"""Invoices enhanced: aging, analytics, bulk actions."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.invoice import Invoice
from app.schemas.common import ResponseBase
from pydantic import BaseModel, Field
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/invoices", tags=["ინვოისები — გაძლიერებული"])


# ── Aging Report ──────────────────────────────────────────────────────────────────

class AgingBucket(BaseModel):
    label: str
    min_days: int
    max_days: int
    count: int
    total: Decimal
    currency: str


class AgingReport(BaseModel):
    buckets: list[AgingBucket]
    total_overdue: Decimal
    total_outstanding: Decimal


@router.get("/aging", response_model=ResponseBase[AgingReport])
async def invoice_aging(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    today = date.today()
    company_id = current_user.company_id

    # Get all issued invoices with overdue status
    rows = (await db.execute(
        select(Invoice.due_date, Invoice.total, Invoice.currency, Invoice.status)
        .where(
            Invoice.company_id == company_id,
            Invoice.status == "issued",
        )
    )).all()

    buckets = [
        AgingBucket(label="0–30 დღე", min_days=0, max_days=30, count=0, total=Decimal("0"), currency="GEL"),
        AgingBucket(label="31–60 დღე", min_days=31, max_days=60, count=0, total=Decimal("0"), currency="GEL"),
        AgingBucket(label="61–90 დღე", min_days=61, max_days=90, count=0, total=Decimal("0"), currency="GEL"),
        AgingBucket(label="90+ დღე", min_days=91, max_days=9999, count=0, total=Decimal("0"), currency="GEL"),
    ]

    total_overdue = Decimal("0")
    total_outstanding = Decimal("0")

    for due_date, total, currency, status in rows:
        days_overdue = (today - due_date).days if due_date else 0
        amount = Decimal(str(total or 0))
        total_outstanding += amount

        if days_overdue > 0:
            total_overdue += amount
            for bucket in buckets:
                if bucket.min_days <= days_overdue <= bucket.max_days:
                    bucket.count += 1
                    bucket.total += amount
                    bucket.currency = currency or "GEL"
                    break

    return ResponseBase(data=AgingReport(buckets=buckets, total_overdue=total_overdue, total_outstanding=total_outstanding))


# ── Analytics ────────────────────────────────────────────────────────────────────

class InvoiceAnalytics(BaseModel):
    total_invoices: int
    total_revenue: Decimal
    draft_count: int
    issued_count: int
    revenue_this_month: Decimal
    revenue_today: Decimal
    avg_invoice_value: Decimal


@router.get("/analytics", response_model=ResponseBase[InvoiceAnalytics])
async def invoice_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    company_id = current_user.company_id
    today = datetime.combine(date.today(), datetime.min.time())
    month_start = today.replace(day=1)

    total = (await db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id)
    )).one()

    draft = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.company_id == company_id, Invoice.status == "draft")
    )).scalar()

    issued = (await db.execute(
        select(func.count(Invoice.id))
        .where(Invoice.company_id == company_id, Invoice.status == "issued")
    )).scalar()

    month_rev = (await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id, Invoice.created_at >= month_start, Invoice.status == "issued")
    )).scalar()

    today_rev = (await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
        .where(Invoice.company_id == company_id, Invoice.created_at >= today, Invoice.status == "issued")
    )).scalar()

    count = total[0]
    rev = Decimal(str(total[1] or 0))
    avg = rev / count if count > 0 else Decimal("0")

    return ResponseBase(data=InvoiceAnalytics(
        total_invoices=count, total_revenue=rev,
        draft_count=draft or 0, issued_count=issued or 0,
        revenue_this_month=Decimal(str(month_rev or 0)),
        revenue_today=Decimal(str(today_rev or 0)),
        avg_invoice_value=avg,
    ))


# ── Bulk Actions ──────────────────────────────────────────────────────────────────

class BulkInvoiceAction(BaseModel):
    ids: list[UUID]


@router.post("/bulk/issue", response_model=ResponseBase[dict])
async def bulk_issue_invoices(
    data: BulkInvoiceAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_approve")),
):
    result = await db.execute(
        update(Invoice)
        .where(Invoice.id.in_(data.ids), Invoice.company_id == current_user.company_id, Invoice.status == "draft")
        .values(status="issued")
    )
    await db.flush()
    return ResponseBase(data={"updated": result.rowcount})


@router.post("/bulk/cancel", response_model=ResponseBase[dict])
async def bulk_cancel_invoices(
    data: BulkInvoiceAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_approve")),
):
    result = await db.execute(
        update(Invoice)
        .where(Invoice.id.in_(data.ids), Invoice.company_id == current_user.company_id, Invoice.status == "draft")
        .values(status="cancelled")
    )
    await db.flush()
    return ResponseBase(data={"updated": result.rowcount})


# ── Export ────────────────────────────────────────────────────────────────────────

@router.get("/export")
async def export_invoices(
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("invoices", "can_access")),
):
    filters = [Invoice.company_id == current_user.company_id]
    if status:
        filters.append(Invoice.status == status)
    if date_from:
        filters.append(Invoice.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        filters.append(Invoice.created_at <= datetime.fromisoformat(date_to))

    rows = (await db.execute(
        select(Invoice).where(*filters).order_by(Invoice.created_at.desc())
    )).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ინვოისები"
    ws.append(["ნომერი", "კლიენტი", "სტატუსი", "თარიღი", "გადახდის ვადა", "ქვე-ჯამი", "დღგ", "სულ", "ვალუტა", "შეკვეთა"])
    for inv in rows:
        ws.append([inv.invoice_number, inv.client_name, inv.status, str(inv.invoice_date),
                   str(inv.due_date or ""), float(inv.subtotal), float(inv.vat_amount),
                   float(inv.total), inv.currency, inv.order_number])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=invoices.xlsx"})
