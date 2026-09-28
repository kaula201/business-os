"""Vendor self-service auth — suppliers log in with their portal credentials.

Separate from the main auth: tokens carry type='vendor' so they never
collide with internal user sessions.
"""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.core.time import utc_now
from app.models.procurement import RFQ, RFQLine, SupplierPriceList
from app.models.purchase import PurchaseOrder, Supplier, SupplierInvoice
from app.models.vendor_portal import VendorPortalUser
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/vendor-auth", tags=["Vendor Auth"])


class VendorLoginIn(BaseModel):
    email: EmailStr
    password: str


class VendorMeOut(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str
    email: str
    display_name: str
    status: str
    last_login_at: datetime | None


def _bearer_token(request: Request) -> str:
    """Vendor session token is accepted only via Authorization, never the query string."""
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise HTTPException(status_code=401, detail="ავტორიზაცია არ არის მოწოდებული")
    return value.strip()


async def get_vendor_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> VendorPortalUser:
    token = _bearer_token(request)
    payload = decode_token(token)
    if not payload or not payload.get("vendor"):
        raise HTTPException(status_code=401, detail="არასწორი ან ვადაგასული სესია")
    row = (await db.execute(
        select(VendorPortalUser).where(VendorPortalUser.id == payload["sub"])
    )).scalar_one_or_none()
    if not row or row.status != "active":
        raise HTTPException(status_code=401, detail="ანგარიში არააქტიურია")
    return row


@router.post("/login", response_model=ResponseBase[dict])
async def vendor_login(
    data: VendorLoginIn,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(VendorPortalUser).where(VendorPortalUser.email == data.email)
    )).scalar_one_or_none()
    if not row or not row.hashed_password or not verify_password(data.password, row.hashed_password):
        raise HTTPException(status_code=401, detail="არასწორი ელფოსტა ან პაროლი")
    if row.status != "active":
        raise HTTPException(status_code=403, detail="ანგარიში დეაქტივირებულია")

    row.last_login_at = utc_now()
    await db.flush()

    token_data = {"sub": str(row.id), "vendor": True, "supplier_id": str(row.supplier_id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    supplier = (await db.execute(select(Supplier).where(Supplier.id == row.supplier_id))).scalar_one_or_none()
    last_login = row.last_login_at
    return ResponseBase(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": str(row.id),
            "supplier_id": str(row.supplier_id),
            "supplier_name": supplier.name if supplier else "",
            "email": row.email,
            "display_name": row.display_name,
            "status": row.status,
            "last_login_at": last_login.isoformat() if last_login else None,
        },
    })


@router.get("/me", response_model=ResponseBase[VendorMeOut])
async def vendor_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    row = await get_vendor_user(request, db)
    supplier = (await db.execute(select(Supplier).where(Supplier.id == row.supplier_id))).scalar_one_or_none()
    return ResponseBase(data=VendorMeOut(
        id=row.id,
        supplier_id=row.supplier_id,
        supplier_name=supplier.name if supplier else "",
        email=row.email,
        display_name=row.display_name,
        status=row.status,
        last_login_at=row.last_login_at,
    ))


@router.get("/dashboard", response_model=ResponseBase[dict])
async def vendor_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Everything the supplier sees after login: RFQs, POs, invoices, price lists."""
    row = await get_vendor_user(request, db)
    company_id = row.company_id
    supplier_id = row.supplier_id

    rfqs = (await db.execute(
        select(RFQ).where(RFQ.company_id == company_id, RFQ.supplier_id == supplier_id)
        .order_by(RFQ.created_at.desc()).limit(100)
    )).scalars().all()
    rfq_rows = []
    for r in rfqs:
        lines = (await db.execute(select(RFQLine).where(RFQLine.rfq_id == r.id))).scalars().all()
        rfq_rows.append({
            "id": str(r.id), "rfq_number": r.rfq_number, "title": r.title,
            "status": r.status, "required_date": r.required_date.isoformat() if r.required_date else None,
            "line_count": len(lines),
            "created_at": r.created_at.isoformat(),
        })

    pos = (await db.execute(
        select(PurchaseOrder).where(PurchaseOrder.company_id == company_id, PurchaseOrder.supplier_id == supplier_id)
        .order_by(PurchaseOrder.created_at.desc()).limit(100)
    )).scalars().all()
    po_rows = [{
        "id": str(p.id), "purchase_order_number": p.purchase_order_number,
        "status": p.status, "total": float(p.total),
        "expected_delivery_date": p.expected_delivery_date.isoformat() if p.expected_delivery_date else None,
        "created_at": p.created_at.isoformat(),
    } for p in pos]

    invoices = (await db.execute(
        select(SupplierInvoice).where(SupplierInvoice.company_id == company_id, SupplierInvoice.supplier_id == supplier_id)
        .order_by(SupplierInvoice.created_at.desc()).limit(100)
    )).scalars().all()
    invoice_rows = [{
        "id": str(i.id), "supplier_invoice_number": i.supplier_invoice_number,
        "internal_invoice_number": i.internal_invoice_number,
        "status": i.status, "total": float(i.total),
        "invoice_date": i.invoice_date.isoformat(), "due_date": i.due_date.isoformat(),
    } for i in invoices]

    price_lists = (await db.execute(
        select(SupplierPriceList).where(SupplierPriceList.company_id == company_id, SupplierPriceList.supplier_id == supplier_id)
        .order_by(SupplierPriceList.valid_from.desc().nulls_last()).limit(100)
    )).scalars().all()
    price_rows = [{
        "id": str(pl.id), "product_id": str(pl.product_id),
        "price": float(pl.price), "currency": pl.currency,
        "valid_from": pl.valid_from.isoformat() if pl.valid_from else None,
        "valid_to": pl.valid_to.isoformat() if pl.valid_to else None,
    } for pl in price_lists]

    return ResponseBase(data={
        "supplier_id": str(supplier_id),
        "rfqs": rfq_rows,
        "purchase_orders": po_rows,
        "invoices": invoice_rows,
        "price_lists": price_rows,
        "counts": {
            "rfqs": len(rfq_rows),
            "purchase_orders": len(po_rows),
            "invoices": len(invoice_rows),
            "price_lists": len(price_rows),
        },
    })
