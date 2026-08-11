"""Price lists + payment terms API."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.endpoints.purchase_orders import add_audit
from app.core.database import get_db
from app.core.dependencies import get_current_user
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
                                        price=float(i.price), min_quantity=float(i.min_quantity))
               for i in p.items],
        created_at=p.created_at, updated_at=p.updated_at,
    )


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
        found = (await db.execute(select(Product.id).where(
            Product.company_id == current_user.company_id, Product.id.in_(product_ids),
        ))).scalars().all()
        if len(found) != len(set(product_ids)):
            raise HTTPException(status_code=400, detail="ერთი ან მეტი პროდუქტი ვერ მოიძებნა")

    if data.is_default:
        from sqlalchemy import update
        await db.execute(
            update(PriceList).where(PriceList.company_id == current_user.company_id)
            .values(is_default=False)
        )
    pl = PriceList(
        company_id=current_user.company_id, name=data.name, currency=data.currency,
        is_default=data.is_default, description=data.description, created_by=current_user.id,
    )
    db.add(pl)
    await db.flush()
    for item in data.items:
        db.add(PriceListItem(price_list_id=pl.id, product_id=item.product_id,
                             price=item.price, min_quantity=item.min_quantity))
    await db.commit()
    await db.refresh(pl)
    add_audit(db, current_user, "price_list.created", "price_list", pl.id, {"name": pl.name})
    await db.commit()
    result = (await db.execute(
        select(PriceList).options(selectinload(PriceList.items)).where(PriceList.id == pl.id)
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
    if data.is_default:
        from sqlalchemy import update
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
        select(PriceList).options(selectinload(PriceList.items)).where(PriceList.id == pl.id)
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
