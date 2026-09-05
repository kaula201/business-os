"""Price lists + payment terms API."""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.approval import ApprovalRequest
from app.models.client import Client, ClientGroupDef
from app.models.payment_term import PaymentTerm
from app.models.pricing import PriceList, PriceListItem
from app.models.product import Product
from app.models.user import User
from app.schemas.common import PaginatedResponse, ResponseBase
from app.schemas.sales_tools import (
    PaymentTermCreate,
    PaymentTermResponse,
    PaymentTermUpdate,
    PriceListCreate,
    PriceListItemResponse,
    PriceListResponse,
    PriceListUpdate,
)

router = APIRouter(tags=["კომერციული ინსტრუმენტები"])


# ── Price lists ──────────────────────────────────────────────────────────────

def _to_response(p: PriceList) -> PriceListResponse:
    return PriceListResponse(
        id=p.id, company_id=p.company_id, name=p.name, currency=p.currency,
        is_default=p.is_default, description=p.description, is_active=p.is_active,
        items=[PriceListItemResponse(id=i.id, product_id=i.product_id,
                                        price=float(i.price), min_quantity=float(i.min_quantity),
                                        currency=i.currency, margin_percent=float(i.margin_percent) if i.margin_percent is not None else None)
               for i in p.items],
        created_at=p.created_at, updated_at=p.updated_at,
        valid_from=p.valid_from.date() if p.valid_from else None,
        valid_until=p.valid_until.date() if p.valid_until else None,
        segment_id=p.segment_id,
        segment_name=p.segment.name if p.segment else None,
        pricing_method=p.pricing_method,
        markup_percent=float(p.markup_percent),
        min_margin_percent=float(p.min_margin_percent) if p.min_margin_percent is not None else None,
        approval_required=p.approval_required,
    )


def _resolve_price(pl: PriceList, item: PriceListItem, product: Product) -> tuple[float, str]:
    """Rule engine: compute effective price for an item.

    Returns (price, source) where source describes which rule applied.
    """
    if pl.pricing_method == "cost_plus_markup":
        cost = product.purchase_price or 0
        markup = float(item.margin_percent if item.margin_percent is not None else pl.markup_percent)
        price = round(cost * (1 + markup / 100), 2)
        return price, f"cost+{markup}%"
    return float(item.price), "fixed"


def _check_margin(pl: PriceList, price: float, product: Product) -> float | None:
    """Return the minimum allowed price if the margin floor is violated, else None."""
    if pl.min_margin_percent is None:
        return None
    cost = product.purchase_price or 0
    if cost <= 0:
        return None
    min_price = round(cost * (1 + float(pl.min_margin_percent) / 100), 2)
    if price < min_price:
        return min_price
    return None


async def _create_approval(db: AsyncSession, current_user: User, pl: PriceList, product: Product, price: float, min_price: float) -> ApprovalRequest:
    req = ApprovalRequest(
        company_id=current_user.company_id,
        title=f"ფასის დამტკიცება: {product.name}",
        description=f"ფასი {price} ₾ მინიმალურ მარჟაზე დაბალია (მინიმუმი {min_price} ₾) — ფასების სია: {pl.name}",
        approval_type="price_list",
        amount=price,
        status=ApprovalRequest.Status.PENDING,
        requested_by=current_user.id,
    )
    db.add(req)
    await db.flush()
    return req


@router.get("/price-lists/resolve", response_model=ResponseBase[dict])
async def resolve_price(
    product_id: uuid.UUID,
    quantity: float = Query(1, ge=0),
    client_id: uuid.UUID | None = None,
    currency: str | None = Query(None, max_length=3),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rule engine: find the best price for a product.

    Priority: client segment match → date-valid lists → quantity tiers →
    currency override → cost+markup formula. Returns price + applied rule.
    """
    product = (await db.execute(select(Product).where(
        Product.id == product_id, Product.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი ვერ მოიძებნა")

    # client segment (if client given)
    segment_id = None
    if client_id:
        client = (await db.execute(select(Client).where(
            Client.id == client_id, Client.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        if client:
            from sqlalchemy import text as sa_text
            row = (await db.execute(sa_text(
                "SELECT group_id FROM client_groups WHERE client_id = :cid LIMIT 1"
            ), {"cid": str(client.id)})).first()
            if row:
                segment_id = row[0]

    today = date.today()
    lists = (await db.execute(
        select(PriceList).options(selectinload(PriceList.items), selectinload(PriceList.segment))
        .where(PriceList.company_id == current_user.company_id, PriceList.is_active == True)
        .order_by(PriceList.is_default.desc())
    )).scalars().all()

    candidates: list[tuple[int, PriceList, PriceListItem]] = []
    for pl in lists:
        # date validity
        if pl.valid_from and pl.valid_from.date() > today:
            continue
        if pl.valid_until and pl.valid_until.date() < today:
            continue
        # segment match: exact segment first, then any (non-segment) list
        if segment_id and pl.segment_id and pl.segment_id != segment_id:
            continue
        for item in pl.items:
            if item.product_id != product_id:
                continue
            if item.min_quantity and quantity < float(item.min_quantity):
                continue
            # currency override: prefer matching currency, else list currency
            if currency and item.currency and item.currency != currency:
                continue
            if currency and not item.currency and pl.currency != currency:
                continue
            candidates.append((0 if pl.segment_id == segment_id else 1, pl, item))

    if not candidates:
        raise HTTPException(status_code=404, detail="ფასი ვერ მოიძებნა არცერთ აქტიურ ფასების სიაში")

    # best: segment match, then highest min_quantity tier (most specific), then default list
    candidates.sort(key=lambda c: (c[0], -float(c[2].min_quantity), 0 if c[1].is_default else 1))
    _, pl, item = candidates[0]

    price, source = _resolve_price(pl, item, product)
    min_price = _check_margin(pl, price, product)
    return ResponseBase(data={
        "product_id": str(product_id),
        "price": price,
        "currency": item.currency or pl.currency,
        "price_list_id": str(pl.id),
        "price_list_name": pl.name,
        "rule": source,
        "min_quantity": float(item.min_quantity),
        "margin_floor_violated": min_price is not None,
        "min_allowed_price": min_price,
        "approval_required": pl.approval_required and min_price is not None,
    })


@router.get("/price-lists/", response_model=ResponseBase[PaginatedResponse[PriceListResponse]])
async def list_price_lists(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [PriceList.company_id == current_user.company_id]
    if is_active is not None:
        filters.append(PriceList.is_active == is_active)
    total = (await db.execute(select(func.count(PriceList.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(PriceList).options(selectinload(PriceList.items))
            .where(*filters).order_by(PriceList.name.asc())
            .offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size, items=[_to_response(r) for r in rows],
    ))


@router.post("/price-lists/", response_model=ResponseBase[PriceListResponse], status_code=201)
async def create_price_list(
    data: PriceListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product_ids = [i.product_id for i in data.items]
    if product_ids:
        found = (await db.execute(select(Product).where(
            Product.company_id == current_user.company_id, Product.id.in_(product_ids),
        ))).scalars().all()
        if len(found) != len(set(product_ids)):
            raise HTTPException(status_code=400, detail="ერთი ან მეტი პროდუქტი ვერ მოიძებნა")

    # segment validation
    if data.segment_id:
        seg = (await db.execute(select(ClientGroupDef).where(
            ClientGroupDef.id == data.segment_id, ClientGroupDef.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        if not seg:
            raise HTTPException(status_code=400, detail="კლიენტის სეგმენტი ვერ მოიძებნა")

    if data.is_default:
        await db.execute(
            update(PriceList).where(PriceList.company_id == current_user.company_id)
            .values(is_default=False)
        )
    pl = PriceList(
        company_id=current_user.company_id, name=data.name, currency=data.currency,
        is_default=data.is_default, description=data.description, created_by=current_user.id,
        valid_from=data.valid_from, valid_until=data.valid_until, segment_id=data.segment_id,
        pricing_method=data.pricing_method, markup_percent=data.markup_percent,
        min_margin_percent=data.min_margin_percent, approval_required=data.approval_required,
    )
    db.add(pl)
    await db.flush()

    # rule engine: cost+markup resolution + margin floor + approval
    products = {p.id: p for p in (await db.execute(select(Product).where(
        Product.company_id == current_user.company_id, Product.id.in_(product_ids),
    ))).scalars().all()} if product_ids else {}
    for item in data.items:
        product = products.get(item.product_id)
        price = float(item.price)
        if data.pricing_method == "cost_plus_markup" and product:
            markup = float(item.margin_percent if item.margin_percent is not None else data.markup_percent)
            price = round((product.purchase_price or 0) * (1 + markup / 100), 2)
        if data.approval_required and product:
            min_price = _check_margin(pl, price, product)
            if min_price is not None:
                await _create_approval(db, current_user, pl, product, price, min_price)
        db.add(PriceListItem(price_list_id=pl.id, product_id=item.product_id,
                             price=price, min_quantity=item.min_quantity,
                             currency=item.currency, margin_percent=item.margin_percent))
    await db.commit()
    await db.refresh(pl)
    add_audit(db, current_user, "price_list.created", "price_list", pl.id, {"name": pl.name})
    await db.commit()
    result = (await db.execute(
        select(PriceList).options(selectinload(PriceList.items), selectinload(PriceList.segment)).where(PriceList.id == pl.id)
    )).scalar_one()
    return ResponseBase(data=_to_response(result))


@router.patch("/price-lists/{price_list_id}", response_model=ResponseBase[PriceListResponse])
async def update_price_list(
    price_list_id: uuid.UUID,
    data: PriceListUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pl = (await db.execute(select(PriceList).where(
        PriceList.id == price_list_id, PriceList.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="ფასების სია ვერ მოიძებნა")
    if data.segment_id is not None:
        seg = (await db.execute(select(ClientGroupDef).where(
            ClientGroupDef.id == data.segment_id, ClientGroupDef.company_id == current_user.company_id,
        ))).scalar_one_or_none()
        if not seg:
            raise HTTPException(status_code=400, detail="კლიენტის სეგმენტი ვერ მოიძებნა")
    if data.is_default:
        await db.execute(
            update(PriceList).where(PriceList.company_id == current_user.company_id)
            .values(is_default=False)
        )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pl, field, value)
    add_audit(db, current_user, "price_list.updated", "price_list", pl.id, {})
    await db.commit()
    await db.refresh(pl)
    result = (await db.execute(
        select(PriceList).options(selectinload(PriceList.items), selectinload(PriceList.segment)).where(PriceList.id == pl.id)
    )).scalar_one()
    return ResponseBase(data=_to_response(result))


@router.delete("/price-lists/{price_list_id}", response_model=ResponseBase)
async def delete_price_list(
    price_list_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pl = (await db.execute(select(PriceList).where(
        PriceList.id == price_list_id, PriceList.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="ფასების სია ვერ მოიძებნა")
    await db.delete(pl)
    add_audit(db, current_user, "price_list.deleted", "price_list", pl.id, {})
    await db.commit()
    return ResponseBase(message="ფასების სია წაშლილია")


# ── Payment terms ────────────────────────────────────────────────────────────

@router.get("/payment-terms/", response_model=ResponseBase[PaginatedResponse[PaymentTermResponse]])
async def list_payment_terms(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = [PaymentTerm.company_id == current_user.company_id]
    if is_active is not None:
        filters.append(PaymentTerm.is_active == is_active)
    total = (await db.execute(select(func.count(PaymentTerm.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(select(PaymentTerm).where(*filters).order_by(PaymentTerm.days.asc())
                         .offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return ResponseBase(data=PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[PaymentTermResponse(
            id=r.id, company_id=r.company_id, name=r.name, days=r.days,
            description=r.description, is_active=r.is_active,
            created_at=r.created_at, updated_at=r.updated_at,
        ) for r in rows],
    ))


@router.post("/payment-terms/", response_model=ResponseBase[PaymentTermResponse], status_code=201)
async def create_payment_term(
    data: PaymentTermCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    term = PaymentTerm(company_id=current_user.company_id, name=data.name,
                       days=data.days, description=data.description)
    db.add(term)
    await db.flush()
    add_audit(db, current_user, "payment_term.created", "payment_term", term.id, {"name": term.name})
    await db.commit()
    await db.refresh(term)
    return ResponseBase(data=PaymentTermResponse(
        id=term.id, company_id=term.company_id, name=term.name, days=term.days,
        description=term.description, is_active=term.is_active,
        created_at=term.created_at, updated_at=term.updated_at,
    ))


@router.patch("/payment-terms/{term_id}", response_model=ResponseBase[PaymentTermResponse])
async def update_payment_term(
    term_id: uuid.UUID,
    data: PaymentTermUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    term = (await db.execute(select(PaymentTerm).where(
        PaymentTerm.id == term_id, PaymentTerm.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="გადახდის პირობა ვერ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(term, field, value)
    add_audit(db, current_user, "payment_term.updated", "payment_term", term.id, {})
    await db.commit()
    await db.refresh(term)
    return ResponseBase(data=PaymentTermResponse(
        id=term.id, company_id=term.company_id, name=term.name, days=term.days,
        description=term.description, is_active=term.is_active,
        created_at=term.created_at, updated_at=term.updated_at,
    ))


@router.delete("/payment-terms/{term_id}", response_model=ResponseBase)
async def delete_payment_term(
    term_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    term = (await db.execute(select(PaymentTerm).where(
        PaymentTerm.id == term_id, PaymentTerm.company_id == current_user.company_id,
    ))).scalar_one_or_none()
    if not term:
        raise HTTPException(status_code=404, detail="გადახდის პირობა ვერ მოიძებნა")
    await db.delete(term)
    add_audit(db, current_user, "payment_term.deleted", "payment_term", term.id, {})
    await db.commit()
    return ResponseBase(message="გადახდის პირობა წაშლილია")
