"""Quotations API — CRUD, status workflow, convert-to-order."""
import hashlib
import json
import secrets
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.tenant_scope import pin_tenant, system_scope
from app.core.time import utc_now
from app.models.approval import ApprovalRequest
from app.models.client import Client
from app.models.product import Product
from app.models.quotation import Quotation, QuotationItem, QuotationVersion
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.sales_tools import (
    QuotationCreate,
    QuotationItemResponse,
    QuotationResponse,
    QuotationStatusUpdate,
    QuotationUpdate,
    QuotationVersionResponse,
    QuotationSignRequest,
    PortalRespondRequest,
)

router = APIRouter(prefix="/quotations", tags=["კომერციული შემოთავაზებები"])


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_response(q: Quotation, client_name: str | None = None) -> QuotationResponse:
    return QuotationResponse(
        id=q.id, company_id=q.company_id, client_id=q.client_id, client_name=client_name,
        quotation_number=q.quotation_number, quotation_date=q.quotation_date,
        valid_until=q.valid_until, status=q.status, currency=q.currency,
        subtotal=float(q.subtotal), vat_amount=float(q.vat_amount), total=float(q.total),
        discount_percent=float(q.discount_percent), notes=q.notes, order_id=q.order_id,
        items=[QuotationItemResponse(
            id=i.id, product_id=i.product_id, line_number=i.line_number,
            description=i.description, quantity=float(i.quantity), unit_price=float(i.unit_price),
            discount_percent=float(i.discount_percent), line_total=float(i.line_total),
            is_optional=i.is_optional, config=i.config,
        ) for i in q.items],
        created_at=q.created_at, updated_at=q.updated_at,
        version_number=q.version_number,
        approval_required=q.approval_required, approval_request_id=q.approval_request_id,
        signed_at=q.signed_at, signed_by=q.signed_by, signature_hash=q.signature_hash,
        signature_method=q.signature_method, portal_token=q.portal_token,
        portal_responded_at=q.portal_responded_at,
    )


async def _load_quotation(db, company_id, quotation_id, for_update=False) -> Quotation:
    stmt = select(Quotation).options(selectinload(Quotation.items)).where(
        Quotation.id == quotation_id, Quotation.company_id == company_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    q = (await db.execute(stmt)).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="შემოთავაზება ვერ მოიძებნა")
    return q


@router.get("/", response_model=ResponseBase[PaginatedResponse[QuotationResponse]])
async def list_quotations(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [Quotation.company_id == current_user.company_id]
    if status:
        filters.append(Quotation.status == status)
    if client_id:
        filters.append(Quotation.client_id == client_id)
    total = (await db.execute(select(func.count(Quotation.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(Quotation).options(selectinload(Quotation.items), selectinload(Quotation.client))
            .where(*filters)
            .order_by(Quotation.quotation_date.desc(), Quotation.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_to_response(q, q.client.name if q.client else None) for q in rows],
    ))


@router.post("/", response_model=ResponseBase[QuotationResponse], status_code=201)
async def create_quotation(
    data: QuotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (
        await db.execute(select(Client).where(
            Client.id == data.client_id, Client.company_id == current_user.company_id,
        ))
    ).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=400, detail="კლიენტი ვერ მოიძებნა")

    # Validate products belong to company when product_id given
    product_ids = [i.product_id for i in data.items if i.product_id]
    if product_ids:
        found = (await db.execute(select(Product.id).where(
            Product.company_id == current_user.company_id, Product.id.in_(product_ids),
        ))).scalars().all()
        if len(found) != len(set(product_ids)):
            raise HTTPException(status_code=400, detail="ერთი ან მეტი პროდუქტი ვერ მოიძებნა")

    prefix = f"QT-{data.quotation_date.strftime('%Y%m%d')}"
    same_day = (await db.execute(select(func.count(Quotation.id)).where(
        Quotation.company_id == current_user.company_id,
        Quotation.quotation_number.like(f"{prefix}-%"),
    ))).scalar_one()
    number = f"{prefix}-{same_day + 1:03d}"

    subtotal = sum(money(i.quantity * i.unit_price) for i in data.items)
    discount = money(subtotal * data.discount_percent / 100)
    vat = money((subtotal - discount) * Decimal("0.18"))
    total = money(subtotal - discount + vat)

    q = Quotation(
        company_id=current_user.company_id, client_id=data.client_id,
        quotation_number=number, quotation_date=data.quotation_date,
        valid_until=data.valid_until, status="draft", currency=data.currency,
        subtotal=subtotal, vat_amount=vat, total=total,
        discount_percent=data.discount_percent, notes=data.notes,
        created_by=current_user.id,
    )
    db.add(q)
    await db.flush()
    for idx, item in enumerate(data.items, start=1):
        line_total = money(money(item.quantity * item.unit_price) * (1 - item.discount_percent / 100))
        db.add(QuotationItem(
            quotation_id=q.id, product_id=item.product_id, line_number=idx,
            description=item.description, quantity=item.quantity, unit_price=item.unit_price,
            discount_percent=item.discount_percent, line_total=line_total,
            is_optional=item.is_optional, config=item.config,
        ))
    # Version 1 is the initial state — no snapshot row needed (created on first revision)
    await db.commit()
    await db.refresh(q)

    add_audit(db, current_user, "quotation.created", "quotation", q.id, {"number": number})
    await db.commit()

    result = await _load_quotation(db, current_user.company_id, q.id)
    return ResponseBase(data=_to_response(result, client.name))


@router.get("/{quotation_id}", response_model=ResponseBase[QuotationResponse])
async def get_quotation(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _load_quotation(db, current_user.company_id, quotation_id)
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    return ResponseBase(data=_to_response(q, client.name if client else None))


@router.patch("/{quotation_id}/status", response_model=ResponseBase[QuotationResponse])
async def update_quotation_status(
    quotation_id: uuid.UUID,
    data: QuotationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    q.status = data.status
    add_audit(db, current_user, "quotation.status_changed", "quotation", q.id, {"status": data.status})
    await db.commit()
    await db.refresh(q)
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    return ResponseBase(data=_to_response(q, client.name if client else None))


@router.post("/{quotation_id}/convert", response_model=ResponseBase[dict])
async def convert_quotation_to_order(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert an accepted quotation into a sales order."""
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    if q.status != "accepted":
        raise HTTPException(status_code=400, detail="მხოლოდ accepted სტატუსის შემოთავაზების კონვერტაცია შეიძლება")
    if q.order_id:
        raise HTTPException(status_code=400, detail="შემოთავაზება უკვე კონვერტირებულია")

    from app.models.order import Order, OrderItem

    order = Order(
        company_id=current_user.company_id, client_id=q.client_id,
        order_number=f"ORD-{q.quotation_number}", status="confirmed",
        subtotal=float(q.subtotal - q.vat_amount), vat_amount=float(q.vat_amount),
        total=float(q.total), created_by=current_user.id,
    )
    db.add(order)
    await db.flush()
    for item in q.items:
        if item.product_id:
            db.add(OrderItem(
                order_id=order.id, product_id=item.product_id,
                product_name=item.description, quantity=float(item.quantity),
                unit_price=float(item.unit_price), discount_percent=float(item.discount_percent),
            ))
    q.order_id = order.id
    q.status = "converted"
    add_audit(db, current_user, "quotation.converted", "quotation", q.id, {"order_id": str(order.id)})
    await db.commit()
    return ResponseBase(data={"order_id": str(order.id), "order_number": order.order_number})


@router.delete("/{quotation_id}", response_model=ResponseBase)
async def delete_quotation(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _load_quotation(db, current_user.company_id, quotation_id)
    if q.status in ("accepted", "converted"):
        raise HTTPException(status_code=400, detail="accepted/converted შემოთავაზების წაშლა არ შეიძლება")
    await db.delete(q)
    add_audit(db, current_user, "quotation.deleted", "quotation", q.id, {})
    await db.commit()
    return ResponseBase(message="შემოთავაზება წაშლილია")


# ── Quotation 2.0: versions, approval, e-signature, portal, configurator ─────

def _snapshot_items(q: Quotation) -> list[dict]:
    return [{
        "line_number": i.line_number, "description": i.description,
        "quantity": float(i.quantity), "unit_price": float(i.unit_price),
        "discount_percent": float(i.discount_percent), "line_total": float(i.line_total),
        "is_optional": i.is_optional, "config": i.config,
    } for i in q.items]


@router.get("/{quotation_id}/versions", response_model=ResponseBase[list[QuotationVersionResponse]])
async def list_versions(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = await _load_quotation(db, current_user.company_id, quotation_id)
    versions = (await db.execute(
        select(QuotationVersion).where(QuotationVersion.quotation_id == q.id)
        .order_by(QuotationVersion.version_number.desc())
    )).scalars().all()
    return ResponseBase(data=[QuotationVersionResponse(
        id=v.id, version_number=v.version_number, status=v.status,
        subtotal=float(v.subtotal), vat_amount=float(v.vat_amount), total=float(v.total),
        discount_percent=float(v.discount_percent), items_snapshot=v.items_snapshot,
        notes=v.notes, change_reason=v.change_reason, created_at=v.created_at,
    ) for v in versions])


@router.put("/{quotation_id}", response_model=ResponseBase[QuotationResponse])
async def update_quotation(
    quotation_id: uuid.UUID,
    data: QuotationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full revision — bumps version_number and snapshots the previous state."""
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    if q.status in ("accepted", "converted"):
        raise HTTPException(status_code=400, detail="accepted/converted შემოთავაზების რედაქტირება არ შეიძლება")

    # snapshot current state as the new version BEFORE applying changes
    db.add(QuotationVersion(
        quotation_id=q.id, version_number=q.version_number, status=q.status,
        subtotal=q.subtotal, vat_amount=q.vat_amount, total=q.total,
        discount_percent=q.discount_percent, items_snapshot=_snapshot_items(q),
        notes=q.notes, change_reason=data.change_reason, created_by=current_user.id,
    ))

    # apply new state
    q.valid_until = data.valid_until
    q.discount_percent = data.discount_percent
    q.notes = data.notes
    q.version_number += 1
    q.status = "draft"  # revision resets to draft

    # replace items
    for old in list(q.items):
        await db.delete(old)
    await db.flush()
    subtotal = sum(money(i.quantity * i.unit_price) for i in data.items)
    discount = money(subtotal * data.discount_percent / 100)
    vat = money((subtotal - discount) * Decimal("0.18"))
    q.subtotal = subtotal
    q.vat_amount = vat
    q.total = money(subtotal - discount + vat)
    for idx, item in enumerate(data.items, start=1):
        line_total = money(money(item.quantity * item.unit_price) * (1 - item.discount_percent / 100))
        db.add(QuotationItem(
            quotation_id=q.id, product_id=item.product_id, line_number=idx,
            description=item.description, quantity=item.quantity, unit_price=item.unit_price,
            discount_percent=item.discount_percent, line_total=line_total,
            is_optional=item.is_optional, config=item.config,
        ))
    add_audit(db, current_user, "quotation.revised", "quotation", q.id, {"version": q.version_number})
    await db.commit()
    result = await _load_quotation(db, current_user.company_id, q.id)
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    return ResponseBase(data=_to_response(result, client.name if client else None))


@router.post("/{quotation_id}/approval", response_model=ResponseBase[QuotationResponse])
async def request_approval(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an approval request when discount or amount exceeds thresholds."""
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    if q.approval_request_id:
        raise HTTPException(status_code=400, detail="დამტკიცება უკვე მოთხოვნილია")

    # Thresholds: discount > 10% OR total > 50,000 GEL
    needs_approval = float(q.discount_percent) > 10 or float(q.total) > 50000
    if not needs_approval:
        raise HTTPException(status_code=400, detail="დამტკიცება არ არის საჭირო (ფასდაკლება ≤ 10% და თანხა ≤ 50,000 ₾)")

    req = ApprovalRequest(
        company_id=current_user.company_id,
        title=f"შემოთავაზების დამტკიცება {q.quotation_number}",
        description=f"თანხა: {q.total} ₾, ფასდაკლება: {q.discount_percent}%",
        approval_type="quotation",
        amount=q.total,
        requested_by=current_user.id,
    )
    db.add(req)
    await db.flush()
    q.approval_request_id = req.id
    q.approval_required = True
    add_audit(db, current_user, "quotation.approval_requested", "quotation", q.id, {"approval_id": str(req.id)})
    await db.commit()
    result = await _load_quotation(db, current_user.company_id, q.id)
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    return ResponseBase(data=_to_response(result, client.name if client else None))


@router.post("/{quotation_id}/sign", response_model=ResponseBase[QuotationResponse])
async def sign_quotation(
    quotation_id: uuid.UUID,
    data: QuotationSignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Electronic signature — records signer, timestamp and content hash."""
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    if q.status != "sent":
        raise HTTPException(status_code=400, detail="ხელმოწერა მხოლოდ sent სტატუსზე შეიძლება")
    if q.signed_at:
        raise HTTPException(status_code=400, detail="შემოთავაზება უკვე ხელმოწერილია")

    content = json.dumps({
        "id": str(q.id), "number": q.quotation_number, "total": float(q.total),
        "discount": float(q.discount_percent), "version": q.version_number,
        "items": _snapshot_items(q),
    }, sort_keys=True, ensure_ascii=False)
    q.signature_hash = hashlib.sha256(content.encode()).hexdigest()
    q.signed_at = utc_now()
    q.signed_by = data.signer_name
    q.signature_method = data.method
    q.status = "accepted"
    add_audit(db, current_user, "quotation.signed", "quotation", q.id, {"signer": data.signer_name})
    await db.commit()
    result = await _load_quotation(db, current_user.company_id, q.id)
    client = (await db.execute(select(Client).where(Client.id == q.client_id))).scalar_one_or_none()
    return ResponseBase(data=_to_response(result, client.name if client else None))


@router.post("/{quotation_id}/portal-token", response_model=ResponseBase[dict])
async def generate_portal_token(
    quotation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a client portal access token for accept/reject."""
    q = await _load_quotation(db, current_user.company_id, quotation_id, for_update=True)
    if not q.portal_token:
        q.portal_token = secrets.token_urlsafe(32)
        await db.commit()
    return ResponseBase(data={"portal_token": q.portal_token, "portal_url": f"/portal/quotations/{q.portal_token}"})


@router.post("/portal/{portal_token}", response_model=ResponseBase[dict])
async def portal_respond(
    portal_token: str,
    data: PortalRespondRequest,
    db: AsyncSession = Depends(get_db),
):
    """Client-facing endpoint — no auth, token-based. Accept or reject a quotation."""
    async with system_scope(db, "portal token lookup"):
        q = (await db.execute(
            select(Quotation).options(selectinload(Quotation.items)).where(Quotation.portal_token == portal_token)
        )).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="შემოთავაზება ვერ მოიძებნა")
    await pin_tenant(db, q.company_id)
    if q.status != "sent":
        raise HTTPException(status_code=400, detail="შემოთავაზება აღარ არის sent სტატუსში")

    if data.action == "accept":
        q.status = "accepted"
        q.portal_responded_at = utc_now()
        if data.signer_name:
            content = json.dumps({
                "id": str(q.id), "number": q.quotation_number, "total": float(q.total),
                "version": q.version_number, "items": _snapshot_items(q),
            }, sort_keys=True, ensure_ascii=False)
            q.signature_hash = hashlib.sha256(content.encode()).hexdigest()
            q.signed_at = utc_now()
            q.signed_by = data.signer_name
            q.signature_method = "portal"
    else:
        q.status = "rejected"
        q.portal_responded_at = utc_now()

    await db.commit()
    return ResponseBase(data={"status": q.status, "quotation_number": q.quotation_number})
