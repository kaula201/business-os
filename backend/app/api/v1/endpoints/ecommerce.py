"""eCommerce API: categories, products, storefront."""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.ecommerce import EcomCategory, EcomProduct
from app.models.product import Product
from app.schemas.common import ResponseBase, PaginatedResponse
from app.schemas.ecommerce import (
    EcomCategoryCreate, EcomCategoryResponse,
    EcomProductCreate, EcomProductUpdate, EcomProductResponse,
)

router = APIRouter(prefix="/ecommerce", tags=["eCommerce — ონლაინ მაღაზია"])


# ── Categories ──────────────────────────────────────────────────────────────

@router.get("/categories", response_model=ResponseBase[list[EcomCategoryResponse]])
async def list_ecom_categories(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_access")),
):
    filters = [EcomCategory.company_id == current_user.company_id]
    if not include_inactive:
        filters.append(EcomCategory.is_active == True)

    rows = (await db.execute(
        select(EcomCategory, func.count(EcomProduct.id).label("product_count"))
        .outerjoin(EcomProduct, EcomProduct.category_id == EcomCategory.id)
        .where(*filters)
        .group_by(EcomCategory.id)
        .order_by(EcomCategory.sort_order, EcomCategory.name)
    )).all()

    items = []
    for cat, count in rows:
        resp = EcomCategoryResponse.model_validate(cat)
        resp.product_count = count
        items.append(resp)
    return ResponseBase(data=items)


@router.post("/categories", response_model=ResponseBase[EcomCategoryResponse], status_code=201)
async def create_ecom_category(
    data: EcomCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_create")),
):
    cat = EcomCategory(company_id=current_user.company_id, **data.model_dump())
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return ResponseBase(data=EcomCategoryResponse.model_validate(cat))


@router.patch("/categories/{cat_id}", response_model=ResponseBase[EcomCategoryResponse])
async def update_ecom_category(
    cat_id: UUID,
    data: EcomCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_edit")),
):
    cat = (await db.execute(
        select(EcomCategory).where(EcomCategory.id == cat_id, EcomCategory.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    await db.flush()
    await db.refresh(cat)
    return ResponseBase(data=EcomCategoryResponse.model_validate(cat))


@router.delete("/categories/{cat_id}", response_model=ResponseBase)
async def delete_ecom_category(
    cat_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_delete")),
):
    cat = (await db.execute(
        select(EcomCategory).where(EcomCategory.id == cat_id, EcomCategory.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")
    await db.delete(cat)
    await db.flush()
    return ResponseBase(message="კატეგორია წაიშალა")


# ── Products ────────────────────────────────────────────────────────────────

@router.get("/products", response_model=ResponseBase[PaginatedResponse[EcomProductResponse]])
async def list_ecom_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: UUID | None = None,
    published_only: bool = True,
    search: str | None = None,
    featured: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_access")),
):
    filters = [EcomProduct.company_id == current_user.company_id]
    if published_only:
        filters.append(EcomProduct.is_published == True)
    if category_id:
        filters.append(EcomProduct.category_id == category_id)
    if featured is not None:
        filters.append(EcomProduct.is_featured == featured)
    if search:
        term = f"%{search.strip()}%"
        filters.append(EcomProduct.name.ilike(term) | EcomProduct.description.ilike(term))

    total = (await db.execute(select(func.count(EcomProduct.id)).where(*filters))).scalar()
    rows = (await db.execute(
        select(EcomProduct)
        .where(*filters)
        .options(selectinload(EcomProduct.category))
        .order_by(EcomProduct.is_featured.desc(), EcomProduct.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).unique().scalars().all()

    items = []
    for p in rows:
        resp = EcomProductResponse.model_validate(p)
        resp.category_name = p.category.name if p.category else None
        if p.image_urls:
            try:
                resp.image_urls = json.loads(p.image_urls)
            except (json.JSONDecodeError, TypeError):
                resp.image_urls = [p.image_urls] if p.image_urls else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))


@router.post("/products", response_model=ResponseBase[EcomProductResponse], status_code=201)
async def create_ecom_product(
    data: EcomProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_create")),
):
    # Verify product exists
    product = (await db.execute(
        select(Product).where(Product.id == data.product_id, Product.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    dump = data.model_dump()
    if dump.get("image_urls"):
        dump["image_urls"] = json.dumps(dump["image_urls"], ensure_ascii=False)
    dump.pop("image_urls", None) if not dump.get("image_urls") else None

    ecom = EcomProduct(company_id=current_user.company_id, **{k: v for k, v in dump.items() if k != "image_urls"})
    if data.image_urls:
        ecom.image_urls = json.dumps(data.image_urls, ensure_ascii=False)
    db.add(ecom)
    await db.flush()
    await db.refresh(ecom)

    resp = EcomProductResponse.model_validate(ecom)
    if ecom.image_urls:
        try:
            resp.image_urls = json.loads(ecom.image_urls)
        except (json.JSONDecodeError, TypeError):
            pass
    return ResponseBase(data=resp)


@router.patch("/products/{product_id}", response_model=ResponseBase[EcomProductResponse])
async def update_ecom_product(
    product_id: UUID,
    data: EcomProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_edit")),
):
    ecom = (await db.execute(
        select(EcomProduct).where(EcomProduct.id == product_id, EcomProduct.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not ecom:
        raise HTTPException(status_code=404, detail="eCommerce პროდუქტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    if "image_urls" in update_data:
        update_data["image_urls"] = json.dumps(update_data["image_urls"], ensure_ascii=False) if update_data["image_urls"] else None
    for field, value in update_data.items():
        setattr(ecom, field, value)
    await db.flush()
    await db.refresh(ecom)

    resp = EcomProductResponse.model_validate(ecom)
    if ecom.image_urls:
        try:
            resp.image_urls = json.loads(ecom.image_urls)
        except (json.JSONDecodeError, TypeError):
            pass
    return ResponseBase(data=resp)


@router.delete("/products/{product_id}", response_model=ResponseBase)
async def delete_ecom_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_delete")),
):
    ecom = (await db.execute(
        select(EcomProduct).where(EcomProduct.id == product_id, EcomProduct.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not ecom:
        raise HTTPException(status_code=404, detail="eCommerce პროდუქტი არ მოიძებნა")
    await db.delete(ecom)
    await db.flush()
    return ResponseBase(message="eCommerce პროდუქტი წაიშალა")


# ── Public Storefront (no auth required) ─────────────────────────────────────

@router.get("/storefront/categories", response_model=ResponseBase[list[EcomCategoryResponse]])
async def public_categories(
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(EcomCategory, func.count(EcomProduct.id).label("product_count"))
        .outerjoin(EcomProduct, EcomProduct.category_id == EcomCategory.id)
        .where(EcomCategory.is_active == True, EcomProduct.is_published == True)
        .group_by(EcomCategory.id)
        .order_by(EcomCategory.sort_order, EcomCategory.name)
    )).all()
    items = []
    for cat, count in rows:
        resp = EcomCategoryResponse.model_validate(cat)
        resp.product_count = count
        items.append(resp)
    return ResponseBase(data=items)


@router.get("/storefront/products", response_model=ResponseBase[PaginatedResponse[EcomProductResponse]])
async def public_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: UUID | None = None,
    search: str | None = None,
    featured: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    filters = [EcomProduct.is_published == True]
    if category_id:
        filters.append(EcomProduct.category_id == category_id)
    if featured is not None:
        filters.append(EcomProduct.is_featured == featured)
    if search:
        term = f"%{search.strip()}%"
        filters.append(EcomProduct.name.ilike(term) | EcomProduct.description.ilike(term))

    total = (await db.execute(select(func.count(EcomProduct.id)).where(*filters))).scalar()
    rows = (await db.execute(
        select(EcomProduct).where(*filters)
        .options(selectinload(EcomProduct.category))
        .order_by(EcomProduct.is_featured.desc(), EcomProduct.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).unique().scalars().all()

    items = []
    for p in rows:
        resp = EcomProductResponse.model_validate(p)
        resp.category_name = p.category.name if p.category else None
        if p.image_urls:
            try:
                resp.image_urls = json.loads(p.image_urls)
            except (json.JSONDecodeError, TypeError):
                resp.image_urls = [p.image_urls] if p.image_urls else None
        items.append(resp)

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    ))
