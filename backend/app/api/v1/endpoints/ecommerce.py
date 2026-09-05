"""eCommerce API: categories, products, storefront."""
import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.ecommerce import (
    EcomCart, EcomCartItem, EcomCategory, EcomContentPage, EcomOrder, EcomOrderItem,
    EcomOrderTracking, EcomProduct, EcomPromotion, EcomReturn, EcomShippingRule,
)
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


# ── eCommerce 2.0 — promotions / shipping / stock / tracking / returns / content ──


@router.get("/promotions", response_model=ResponseBase[list[dict]])
async def list_promotions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_access")),
):
    rows = (await db.execute(
        select(EcomPromotion).where(EcomPromotion.company_id == current_user.company_id).order_by(EcomPromotion.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(p.id), "code": p.code, "name": p.name, "discount_type": p.discount_type,
        "discount_value": float(p.discount_value), "min_subtotal": float(p.min_subtotal),
        "valid_from": p.valid_from.isoformat() if p.valid_from else None,
        "valid_until": p.valid_until.isoformat() if p.valid_until else None,
        "max_uses": p.max_uses, "used_count": p.used_count, "is_active": p.is_active,
    } for p in rows])


@router.post("/promotions", response_model=ResponseBase[dict], status_code=201)
async def create_promotion(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_create")),
):
    promo = EcomPromotion(
        company_id=current_user.company_id, code=data["code"].upper(), name=data["name"],
        discount_type=data.get("discount_type", "percent"), discount_value=Decimal(str(data["discount_value"])),
        min_subtotal=Decimal(str(data.get("min_subtotal", 0))),
        valid_from=datetime.fromisoformat(data["valid_from"]) if data.get("valid_from") else None,
        valid_until=datetime.fromisoformat(data["valid_until"]) if data.get("valid_until") else None,
        max_uses=int(data.get("max_uses", 0)),
    )
    db.add(promo)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(promo.id), "code": promo.code}, message="პრომოცია შეიქმნა")


@router.get("/shipping-rules", response_model=ResponseBase[list[dict]])
async def list_shipping_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_access")),
):
    rows = (await db.execute(
        select(EcomShippingRule).where(EcomShippingRule.company_id == current_user.company_id).order_by(EcomShippingRule.name)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "name": r.name, "zone": r.zone, "flat_rate": float(r.flat_rate),
        "free_above": float(r.free_above) if r.free_above is not None else None,
        "weight_rate": float(r.weight_rate), "is_active": r.is_active,
    } for r in rows])


@router.post("/shipping-rules", response_model=ResponseBase[dict], status_code=201)
async def create_shipping_rule(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_create")),
):
    rule = EcomShippingRule(
        company_id=current_user.company_id, name=data["name"], zone=data.get("zone", "default"),
        flat_rate=Decimal(str(data.get("flat_rate", 0))),
        free_above=Decimal(str(data["free_above"])) if data.get("free_above") is not None else None,
        weight_rate=Decimal(str(data.get("weight_rate", 0))),
    )
    db.add(rule)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(rule.id), "name": rule.name}, message="მიწოდების წესი შეიქმნა")


@router.post("/shipping/calculate", response_model=ResponseBase[dict])
async def calculate_shipping(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Shipping calculation: flat rate, free above threshold, weight-based."""
    subtotal = Decimal(str(data.get("subtotal", 0)))
    weight = Decimal(str(data.get("weight_kg", 0)))
    zone = data.get("zone", "default")
    rules = (await db.execute(
        select(EcomShippingRule).where(
            EcomShippingRule.company_id == current_user.company_id,
            EcomShippingRule.is_active == True,
            EcomShippingRule.zone == zone,
        )
    )).scalars().all()
    if not rules:
        rules = (await db.execute(
            select(EcomShippingRule).where(
                EcomShippingRule.company_id == current_user.company_id,
                EcomShippingRule.is_active == True,
                EcomShippingRule.zone == "default",
            )
        )).scalars().all()
    if not rules:
        raise HTTPException(status_code=404, detail="მიწოდების წესი არ მოიძებნა")
    rule = rules[0]
    if rule.free_above is not None and subtotal >= rule.free_above:
        fee = Decimal("0")
        applied = "free"
    else:
        fee = rule.flat_rate + weight * rule.weight_rate
        applied = "flat+weight"
    return ResponseBase(data={
        "shipping_fee": float(fee), "rule": rule.name, "applied": applied,
        "free_above": float(rule.free_above) if rule.free_above is not None else None,
    })


@router.post("/promotions/validate", response_model=ResponseBase[dict])
async def validate_promo(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate a promo code against subtotal; returns discount amount."""
    code = data.get("code", "").upper()
    subtotal = Decimal(str(data.get("subtotal", 0)))
    promo = (await db.execute(
        select(EcomPromotion).where(
            EcomPromotion.company_id == current_user.company_id,
            EcomPromotion.code == code,
            EcomPromotion.is_active == True,
        )
    )).scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="პრომო კოდი არ მოიძებნა")
    now = datetime.utcnow()
    if promo.valid_from and promo.valid_from > now:
        raise HTTPException(status_code=400, detail="პრომო ჯერ არ მოქმედებს")
    if promo.valid_until and promo.valid_until < now:
        raise HTTPException(status_code=400, detail="პრომო ვადაგასულია")
    if promo.max_uses and promo.used_count >= promo.max_uses:
        raise HTTPException(status_code=400, detail="პრომოს გამოყენების ლიმიტი ამოწურულია")
    if subtotal < promo.min_subtotal:
        raise HTTPException(status_code=400, detail=f"მინიმალური თანხა: {promo.min_subtotal}")
    if promo.discount_type == "percent":
        discount = subtotal * promo.discount_value / 100
    else:
        discount = min(promo.discount_value, subtotal)
    return ResponseBase(data={
        "code": promo.code, "discount_amount": float(discount),
        "discount_type": promo.discount_type, "discount_value": float(promo.discount_value),
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
    in sandbox (demo) mode. Stock is reserved at checkout."""
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

    # stock reservation: verify availability, then reserve
    ecom_ids = [i.ecom_product_id for i in items]
    ecom_products = (await db.execute(
        select(EcomProduct).where(EcomProduct.id.in_(ecom_ids))
    )).scalars().all()
    ecom_map = {p.id: p for p in ecom_products}
    for i in items:
        p = ecom_map.get(i.ecom_product_id)
        if not p:
            raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")
        if p.stock_quantity < i.quantity:
            raise HTTPException(status_code=400, detail=f"მარაგი არასაკმარისია: {p.name} (ხელმისაწვდომია {p.stock_quantity})")
    for i in items:
        ecom_map[i.ecom_product_id].stock_quantity -= i.quantity

    subtotal = sum(i.unit_price * i.quantity for i in items)
    shipping = Decimal(str(data.get("shipping_fee", 0)))

    # promo discount
    discount = Decimal("0")
    promo_code = data.get("promo_code")
    if promo_code:
        promo = (await db.execute(
            select(EcomPromotion).where(
                EcomPromotion.company_id == current_user.company_id,
                EcomPromotion.code == promo_code.upper(),
                EcomPromotion.is_active == True,
            )
        )).scalar_one_or_none()
        if promo:
            if promo.discount_type == "percent":
                discount = subtotal * promo.discount_value / 100
            else:
                discount = min(promo.discount_value, subtotal)
            promo.used_count += 1

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
                amount=int((subtotal + shipping - discount) * 100),
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
        discount_amount=discount,
        total=subtotal + shipping - discount,
        shipping_address=data.get("shipping_address"),
        payment_method=payment_method,
        payment_status=payment_status,
        payment_reference=payment_reference,
        promo_code=promo_code.upper() if promo_code else None,
        guest_email=data.get("guest_email"),
    )
    db.add(order)
    await db.flush()
    # order items snapshot
    for i in items:
        p = ecom_map[i.ecom_product_id]
        db.add(EcomOrderItem(
            order_id=order.id, ecom_product_id=i.ecom_product_id,
            product_name=p.name, quantity=i.quantity, unit_price=i.unit_price,
        ))
    db.add(EcomOrderTracking(order_id=order.id, status=order.status, note="შეკვეთა შეიქმნა"))
    cart.status = "converted"
    await db.flush()
    await db.commit()
    return ResponseBase(data={
        "id": str(order.id), "order_number": order.order_number, "total": float(order.total),
        "discount_amount": float(discount), "payment_status": payment_status,
        "payment_reference": payment_reference,
        "gateway": "stripe" if settings.STRIPE_SECRET_KEY else "sandbox",
    }, message="შეკვეთა შეიქმნა")


@router.post("/orders/{order_id}/tracking", response_model=ResponseBase[dict])
async def add_tracking(
    order_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_edit")),
):
    """Order tracking: add a status event + optional carrier/tracking number."""
    order = (await db.execute(
        select(EcomOrder).where(EcomOrder.id == order_id, EcomOrder.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")
    status = data.get("status", order.status)
    order.status = status
    if data.get("tracking_number"):
        order.tracking_number = data["tracking_number"]
    if data.get("carrier"):
        order.carrier = data["carrier"]
    db.add(EcomOrderTracking(order_id=order.id, status=status, note=data.get("note")))
    await db.flush()
    await db.commit()
    return ResponseBase(data={"order_id": str(order.id), "status": status}, message="სტატუსი განახლდა")


@router.get("/orders/{order_id}/tracking", response_model=ResponseBase[list[dict]])
async def get_tracking(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (await db.execute(
        select(EcomOrder).where(EcomOrder.id == order_id, EcomOrder.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")
    rows = (await db.execute(
        select(EcomOrderTracking).where(EcomOrderTracking.order_id == order.id).order_by(EcomOrderTracking.created_at)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(t.id), "status": t.status, "note": t.note,
        "created_at": t.created_at.isoformat(),
    } for t in rows])


@router.post("/orders/{order_id}/return", response_model=ResponseBase[dict], status_code=201)
async def request_return(
    order_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """დაბრუნება: client requests a return/refund."""
    order = (await db.execute(
        select(EcomOrder).where(EcomOrder.id == order_id, EcomOrder.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="შეკვეთა არ მოიძებნა")
    ret = EcomReturn(
        company_id=current_user.company_id, order_id=order.id,
        reason=data.get("reason", "მომხმარებლის მოთხოვნით"),
    )
    db.add(ret)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(ret.id), "status": ret.status}, message="დაბრუნების მოთხოვნა შეიქმნა")


@router.get("/returns", response_model=ResponseBase[list[dict]])
async def list_returns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_access")),
):
    rows = (await db.execute(
        select(EcomReturn).where(EcomReturn.company_id == current_user.company_id).order_by(EcomReturn.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(r.id), "order_id": str(r.order_id), "reason": r.reason, "status": r.status,
        "refund_amount": float(r.refund_amount) if r.refund_amount is not None else None,
        "refund_reference": r.refund_reference, "created_at": r.created_at.isoformat(),
    } for r in rows])


@router.post("/returns/{return_id}/approve", response_model=ResponseBase[dict])
async def approve_return(
    return_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_edit")),
):
    """Approve a return → refund (sandbox: marks refunded)."""
    ret = (await db.execute(
        select(EcomReturn).where(EcomReturn.id == return_id, EcomReturn.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not ret:
        raise HTTPException(status_code=404, detail="დაბრუნება არ მოიძებნა")
    order = (await db.execute(
        select(EcomOrder).where(EcomOrder.id == ret.order_id)
    )).scalar_one_or_none()
    ret.status = "refunded"
    ret.refund_amount = data.get("refund_amount") or (order.total if order else 0)
    ret.refund_reference = data.get("refund_reference") or f"REF-{ret.id.hex[:8].upper()}"
    if order:
        order.payment_status = "refunded"
        order.status = "cancelled"
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(ret.id), "status": ret.status}, message="დაბრუნება დამტკიცდა")


@router.get("/content-pages", response_model=ResponseBase[list[dict]])
async def list_content_pages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_access")),
):
    rows = (await db.execute(
        select(EcomContentPage).where(EcomContentPage.company_id == current_user.company_id).order_by(EcomContentPage.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(p.id), "slug": p.slug, "title": p.title, "body": p.body,
        "seo_title": p.seo_title, "seo_description": p.seo_description,
        "is_published": p.is_published, "updated_at": p.updated_at.isoformat(),
    } for p in rows])


@router.post("/content-pages", response_model=ResponseBase[dict], status_code=201)
async def create_content_page(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("ecommerce", "can_create")),
):
    page = EcomContentPage(
        company_id=current_user.company_id, slug=data["slug"], title=data["title"],
        body=data.get("body"), seo_title=data.get("seo_title"),
        seo_description=data.get("seo_description"), is_published=data.get("is_published", False),
    )
    db.add(page)
    await db.flush()
    await db.commit()
    return ResponseBase(data={"id": str(page.id), "slug": page.slug}, message="გვერდი შეიქმნა")
