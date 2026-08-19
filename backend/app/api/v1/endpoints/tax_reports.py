"""Tax reports: VAT return summary, sales/purchases VAT registers."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.models.invoice import Invoice
from app.models.purchase import SupplierInvoice
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/tax-reports", tags=["საგადასახადო ანგარიშები"])


def _month_range(year: int, month: int) -> tuple[date, date]:
    if month == 12:
        return date(year, 12, 1), date(year + 1, 1, 1)
    return date(year, month, 1), date(year, month + 1, 1)


@router.get("/vat", response_model=ResponseBase[dict])
async def vat_return(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("srs", "can_access")),
):
    """VAT return for a period: output VAT (sales) vs input VAT (purchases)."""
    company_id = current_user.company_id
    start, end = _month_range(year, month)

    sales = (await db.execute(
        select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.invoice_date >= start,
            Invoice.invoice_date < end,
        )
    )).scalars().all()
    sales_subtotal = sum(i.subtotal for i in sales)
    sales_vat = sum(i.vat_amount for i in sales)
    sales_total = sum(i.total for i in sales)

    purchases = (await db.execute(
        select(SupplierInvoice).where(
            SupplierInvoice.company_id == company_id,
            SupplierInvoice.invoice_date >= start,
            SupplierInvoice.invoice_date < end,
        )
    )).scalars().all()
    purchases_subtotal = sum(i.subtotal for i in purchases)
    purchases_vat = sum(i.vat_amount for i in purchases)
    purchases_total = sum(i.total for i in purchases)

    net_vat = sales_vat - purchases_vat

    return ResponseBase(data={
        "period": f"{year}-{month:02d}",
        "sales": {
            "invoice_count": len(sales),
            "subtotal": float(sales_subtotal),
            "vat": float(sales_vat),
            "total": float(sales_total),
        },
        "purchases": {
            "invoice_count": len(purchases),
            "subtotal": float(purchases_subtotal),
            "vat": float(purchases_vat),
            "total": float(purchases_total),
        },
        "net_vat_payable": float(net_vat),
        "gl_accounts": {
            "sales_vat_account": "2200",
            "purchase_vat_account": "5300",
        },
    })


@router.get("/vat/register/sales", response_model=ResponseBase[list[dict]])
async def sales_vat_register(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("srs", "can_access")),
):
    """Sales VAT register — every issued invoice in the range."""
    company_id = current_user.company_id
    rows = (await db.execute(
        select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.invoice_date >= date_from,
            Invoice.invoice_date <= date_to,
        ).order_by(Invoice.invoice_date)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(i.id),
        "invoice_number": i.invoice_number,
        "invoice_date": i.invoice_date.isoformat(),
        "client_name": i.client_name,
        "client_identification_code": i.client_identification_code,
        "subtotal": float(i.subtotal),
        "vat_rate": 18.0 if i.vat_amount > 0 else 0.0,
        "vat": float(i.vat_amount),
        "total": float(i.total),
        "status": i.status,
    } for i in rows])


@router.get("/vat/register/purchases", response_model=ResponseBase[list[dict]])
async def purchases_vat_register(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("srs", "can_access")),
):
    """Purchases VAT register — every supplier invoice in the range."""
    company_id = current_user.company_id
    rows = (await db.execute(
        select(SupplierInvoice).where(
            SupplierInvoice.company_id == company_id,
            SupplierInvoice.invoice_date >= date_from,
            SupplierInvoice.invoice_date <= date_to,
        ).order_by(SupplierInvoice.invoice_date)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(i.id),
        "supplier_invoice_number": i.supplier_invoice_number,
        "invoice_date": i.invoice_date.isoformat(),
        "supplier_id": str(i.supplier_id),
        "subtotal": float(i.subtotal),
        "vat": float(i.vat_amount),
        "total": float(i.total),
        "status": i.status,
    } for i in rows])
