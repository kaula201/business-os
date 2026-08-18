"""Vendor analytics: spend, on-time delivery, quality and price trend per supplier."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.purchase import GoodsReceipt, PurchaseOrder, Supplier, SupplierInvoice
from app.models.procurement import SupplierScorecard
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/procurement/vendor-analytics", tags=["Procurement — vendor analytics"])


@router.get("", response_model=ResponseBase[list[dict]])
async def vendor_analytics(
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("purchases", "can_view")),
):
    """Aggregate per-supplier spend, on-time delivery, quality and price trend."""
    company_id = current_user.company_id
    suppliers = (await db.execute(
        select(Supplier).where(Supplier.company_id == company_id).order_by(Supplier.name)
    )).scalars().all()

    invoice_filters = [SupplierInvoice.company_id == company_id, SupplierInvoice.status == "approved"]
    if date_from:
        invoice_filters.append(SupplierInvoice.invoice_date >= date_from)
    if date_to:
        invoice_filters.append(SupplierInvoice.invoice_date <= date_to)

    invoices = (await db.execute(
        select(SupplierInvoice).where(*invoice_filters)
    )).scalars().all()

    receipts = (await db.execute(
        select(GoodsReceipt).where(GoodsReceipt.company_id == company_id)
    )).scalars().all()
    orders = (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.company_id == company_id)
    )).scalars().all()
    order_by_id = {o.id: o for o in orders}

    scorecards = (await db.execute(
        select(SupplierScorecard).where(SupplierScorecard.company_id == company_id)
    )).scalars().all()

    # Group invoices by supplier
    spend_by_supplier: dict[UUID, Decimal] = {}
    invoice_count_by_supplier: dict[UUID, int] = {}
    for inv in invoices:
        spend_by_supplier[inv.supplier_id] = spend_by_supplier.get(inv.supplier_id, Decimal("0")) + inv.total
        invoice_count_by_supplier[inv.supplier_id] = invoice_count_by_supplier.get(inv.supplier_id, 0) + 1

    # On-time delivery: receipts where received date <= PO expected delivery date
    on_time_by_supplier: dict[UUID, list[bool]] = {}
    for gr in receipts:
        order = order_by_id.get(gr.purchase_order_id)
        if not order:
            continue
        if order.supplier_id not in on_time_by_supplier:
            on_time_by_supplier[order.supplier_id] = []
        expected = order.expected_delivery_date
        received = gr.received_at.date() if gr.received_at else None
        if expected and received:
            on_time_by_supplier[order.supplier_id].append(received <= expected)

    # Latest scorecard per supplier
    latest_score: dict[UUID, SupplierScorecard] = {}
    for sc in scorecards:
        if sc.supplier_id not in latest_score or sc.period > latest_score[sc.supplier_id].period:
            latest_score[sc.supplier_id] = sc

    result = []
    for s in suppliers:
        spend = spend_by_supplier.get(s.id, Decimal("0"))
        inv_count = invoice_count_by_supplier.get(s.id, 0)
        on_time_list = on_time_by_supplier.get(s.id, [])
        on_time_rate = (sum(on_time_list) / len(on_time_list) * 100) if on_time_list else None
        sc = latest_score.get(s.id)
        result.append({
            "supplier_id": str(s.id), "supplier_name": s.name,
            "total_spend": float(spend), "invoice_count": inv_count,
            "on_time_delivery_rate": round(on_time_rate, 2) if on_time_rate is not None else None,
            "quality_rate": float(sc.quality_rate) if sc and sc.quality_rate is not None else None,
            "overall_score": float(sc.overall_score) if sc and sc.overall_score is not None else None,
            "orders_count": sc.orders_count if sc else 0,
        })
    return ResponseBase(data=result)
