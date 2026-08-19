from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_module
from app.core.security import hash_password
from app.models.procurement import RFQ, RFQLine, SupplierPriceList
from app.models.purchase import PurchaseOrder, Supplier, SupplierInvoice
from app.models.user import User
from app.models.vendor_portal import VendorPortalUser
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.vendor_portal import (
    VendorPortalUserCreate,
    VendorPortalUserResponse,
    VendorPortalUserUpdate,
)

router = APIRouter(prefix="/vendor-portal", tags=["Vendor Portal"])


async def _require_supplier(db: AsyncSession, company_id: UUID, supplier_id: UUID) -> Supplier:
    s = (await db.execute(
        select(Supplier).where(Supplier.id == supplier_id, Supplier.company_id == company_id)
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="მომწოდებელი არ მოიძებნა")
    return s


@router.get("/", response_model=ResponseBase[PaginatedResponse[VendorPortalUserResponse]])
async def list_vendor_portal_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    supplier_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("vendor-portal", "can_access")),
):
    query = select(VendorPortalUser).where(VendorPortalUser.company_id == current_user.company_id)
    if status:
        query = query.where(VendorPortalUser.status == status)
    if supplier_id:
        query = query.where(VendorPortalUser.supplier_id == supplier_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    query = (
        query.order_by(VendorPortalUser.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).scalars().all()

    return ResponseBase(
        data=PaginatedResponse(
            items=[VendorPortalUserResponse.model_validate(u) for u in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{portal_user_id}", response_model=ResponseBase[VendorPortalUserResponse])
async def get_vendor_portal_user(
    portal_user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("vendor-portal", "can_access")),
):
    row = (await db.execute(
        select(VendorPortalUser).where(
            VendorPortalUser.id == portal_user_id,
            VendorPortalUser.company_id == current_user.company_id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="პორტალის მომხმარებელი არ მოიძებნა")
    return ResponseBase(data=VendorPortalUserResponse.model_validate(row))


@router.post("/", response_model=ResponseBase[VendorPortalUserResponse])
async def create_vendor_portal_user(
    data: VendorPortalUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("vendor-portal", "can_create")),
):
    await _require_supplier(db, current_user.company_id, data.supplier_id)
    row = VendorPortalUser(
        company_id=current_user.company_id,
        supplier_id=data.supplier_id,
        email=data.email,
        display_name=data.display_name,
        status=data.status,
        hashed_password=hash_password(data.password) if data.password else None,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return ResponseBase(data=VendorPortalUserResponse.model_validate(row))


@router.patch("/{portal_user_id}", response_model=ResponseBase[VendorPortalUserResponse])
async def update_vendor_portal_user(
    portal_user_id: UUID,
    data: VendorPortalUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("vendor-portal", "can_edit")),
):
    row = (await db.execute(
        select(VendorPortalUser).where(
            VendorPortalUser.id == portal_user_id,
            VendorPortalUser.company_id == current_user.company_id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="პორტალის მომხმარებელი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    if "supplier_id" in update_data and update_data["supplier_id"]:
        await _require_supplier(db, current_user.company_id, update_data["supplier_id"])
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
    for field, value in update_data.items():
        setattr(row, field, value)

    await db.flush()
    await db.refresh(row)
    return ResponseBase(data=VendorPortalUserResponse.model_validate(row))


@router.delete("/{portal_user_id}", response_model=ResponseBase[dict])
async def delete_vendor_portal_user(
    portal_user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("vendor-portal", "can_delete")),
):
    row = (await db.execute(
        select(VendorPortalUser).where(
            VendorPortalUser.id == portal_user_id,
            VendorPortalUser.company_id == current_user.company_id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="პორტალის მომხმარებელი არ მოიძებნა")
    await db.delete(row)
    await db.flush()
    return ResponseBase(data={"id": str(portal_user_id)}, message="წაშლილია")


# ── Supplier self-service summary ─────────────────────────────────────────────

@router.get("/suppliers/{supplier_id}/summary", response_model=ResponseBase[dict])
async def supplier_summary(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("vendor-portal", "can_access")),
):
    """Everything a supplier sees in its portal: RFQs, POs, invoices, price lists."""
    company_id = current_user.company_id
    await _require_supplier(db, company_id, supplier_id)

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
