"""eCommerce API: categories, products, storefront."""
import json
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.ecommerce import EcomCart, EcomCartItem, EcomCategory, EcomOrder, EcomProduct
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


# ── Cart & checkout ──────────────────────────────────────────────────


@router.post("/cart", response_model=ResponseBase[dict], status_code=201)
async def create_cart(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = EcomCart(
        company_id=current_user.company_id,
        client_id=data.get("client_id"),
        session_token=data.get("session_token"),
    )
    db.add(cart)
    await db.flush()
    return ResponseBase(data={"id": str(cart.id)}, message="კალათა შეიქმნა")


@router.post("/cart/{cart_id}/items", response_model=ResponseBase[dict], status_code=201)
async def add_cart_item(
    cart_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = (await db.execute(
        select(EcomCart).where(EcomCart.id == cart_id, EcomCart.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="კალათა არ მოიძებნა")
    product = (await db.execute(
        select(EcomProduct).where(EcomProduct.id == data.get("ecom_product_id"), EcomProduct.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
    item = EcomCartItem(
        cart_id=cart.id,
        ecom_product_id=product.id,
        quantity=int(data.get("quantity", 1)),
        unit_price=product.price,
    )
    db.add(item)
    await db.flush()
    return ResponseBase(data={"id": str(item.id), "unit_price": float(item.unit_price)}, message="პროდუქტი დაემატა")


@router.get("/cart/{cart_id}", response_model=ResponseBase[dict])
async def get_cart(
    cart_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = (await db.execute(
        select(EcomCart).where(EcomCart.id == cart_id, EcomCart.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="კალათა არ მოიძებნა")
    items = (await db.execute(
        select(EcomCartItem).where(EcomCartItem.cart_id == cart.id)
    )).scalars().all()
    subtotal = sum(i.unit_price * i.quantity for i in items)
    return ResponseBase(data={
        "id": str(cart.id), "status": cart.status,
        "items": [{"id": str(i.id), "ecom_product_id": str(i.ecom_product_id), "quantity": i.quantity, "unit_price": float(i.unit_price)} for i in items],
        "subtotal": float(subtotal),
    })


@router.post("/cart/{cart_id}/checkout", response_model=ResponseBase[dict])
async def checkout(
    cart_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert cart to an e-commerce order. When Stripe is configured the
    charge is attempted for real; otherwise the order is created as 'paid'
    in sandbox (demo) mode."""
    from app.core.config import settings

    cart = (await db.execute(
        select(EcomCart).where(EcomCart.id == cart_id, EcomCart.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not cart:
        raise HTTPException(status_code=404, detail="კალათა არ მოიძებნა")
    items = (await db.execute(
        select(EcomCartItem).where(EcomCartItem.cart_id == cart.id)
    )).scalars().all()
    if not items:
        raise HTTPException(status_code=422, detail="კალათა ცარიელია")
    subtotal = sum(i.unit_price * i.quantity for i in items)
    shipping = Decimal(str(data.get("shipping_fee", 0)))
    from app.api.v1.endpoints.purchase_orders import allocate_document_number
    number = await allocate_document_number(db, current_user.company_id, "ecom_order", "ECOMM")

    payment_method = data.get("payment_method", "card")
    payment_status = "paid"  # sandbox default
    payment_reference = None

    # Real Stripe charge when configured
    if settings.STRIPE_SECRET_KEY:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            charge = stripe.PaymentIntent.create(
                amount=int((subtotal + shipping) * 100),
                currency="gel",
                payment_method_types=["card"],
                metadata={"order_number": number, "company_id": str(current_user.company_id)},
            )
            payment_status = "paid"
            payment_reference = charge.id
        except Exception:
            payment_status = "failed"

    order = EcomOrder(
        company_id=current_user.company_id,
        cart_id=cart.id,
        client_id=cart.client_id or data.get("client_id"),
        order_number=number,
        status="paid" if payment_status == "paid" else "pending",
        subtotal=subtotal,
        shipping_fee=shipping,
        total=subtotal + shipping,
        shipping_address=data.get("shipping_address"),
        payment_method=payment_method,
        payment_status=payment_status,
        payment_reference=payment_reference,
    )
    db.add(order)
    cart.status = "converted"
    await db.flush()
    return ResponseBase(data={
        "id": str(order.id), "order_number": order.order_number, "total": float(order.total),
        "payment_status": payment_status, "payment_reference": payment_reference,
        "gateway": "stripe" if settings.STRIPE_SECRET_KEY else "sandbox",
    }, message="შეკვეთა შეიქმნა")


@router.get("/orders", response_model=ResponseBase[list[dict]])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(EcomOrder).where(EcomOrder.company_id == current_user.company_id).order_by(EcomOrder.created_at.desc()).limit(50)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(o.id), "order_number": o.order_number, "status": o.status,
        "subtotal": float(o.subtotal), "shipping_fee": float(o.shipping_fee), "total": float(o.total),
        "payment_method": o.payment_method, "payment_status": o.payment_status,
        "payment_reference": o.payment_reference, "created_at": o.created_at.isoformat(),
    } for o in rows])
