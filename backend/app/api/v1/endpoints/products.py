# backend/app/api/v1/endpoints/products.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from decimal import Decimal
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.product import (
    Product, ProductCategory, ProductVariant, ProductImage, StockMovement
)
from app.models.purchase import Supplier
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse,
    StockAdjustment, StockMovementResponse,
    CategoryCreate, CategoryUpdate, CategoryResponse,
    ProductVariantCreate, ProductVariantUpdate, ProductVariantResponse,
    ProductImageCreate, ProductImageUpdate, ProductImageResponse,
)
from app.schemas.common import ResponseBase, PaginatedResponse

router = APIRouter(prefix="/products", tags=["პროდუქტები"])


def get_stock_status(current: float, min_stock: float) -> str:
    if current <= 0:
        return "critical"
    elif current <= min_stock:
        return "low"
    return "good"


def _build_product_response(product: Product) -> ProductResponse:
    """Build a full ProductResponse with variants, images, and supplier info."""
    variants = []
    for v in (product.variants or []):
        variants.append(ProductVariantResponse(
            id=v.id,
            product_id=v.product_id,
            sku=v.sku,
            barcode=v.barcode,
            gtin=v.gtin,
            name=v.name,
            attr_1_name=v.attr_1_name,
            attr_1_value=v.attr_1_value,
            attr_2_name=v.attr_2_name,
            attr_2_value=v.attr_2_value,
            attr_3_name=v.attr_3_name,
            attr_3_value=v.attr_3_value,
            sale_price=float(v.sale_price) if v.sale_price is not None else None,
            purchase_price=float(v.purchase_price) if v.purchase_price is not None else None,
            current_stock=float(v.current_stock),
            min_stock=float(v.min_stock),
            stock_status=get_stock_status(float(v.current_stock), float(v.min_stock)),
            is_active=v.is_active,
            sort_order=v.sort_order,
            created_at=v.created_at,
            updated_at=v.updated_at,
        ))

    images = []
    for img in (product.images or []):
        images.append(ProductImageResponse(
            id=img.id,
            product_id=img.product_id,
            variant_id=img.variant_id,
            url=img.url,
            thumbnail_url=img.thumbnail_url,
            alt_text=img.alt_text,
            is_primary=img.is_primary,
            file_type=img.file_type,
            file_size_bytes=img.file_size_bytes,
            sort_order=img.sort_order,
            created_at=img.created_at,
        ))

    return ProductResponse(
        id=product.id,
        sku=product.sku,
        barcode=product.barcode,
        gtin=product.gtin,
        name=product.name,
        description=product.description,
        category_id=product.category_id,
        category_name=product.category.name if product.category else None,
        supplier_id=product.supplier_id,
        supplier_name=product.supplier.name if product.supplier else None,
        sale_price=float(product.sale_price),
        purchase_price=float(product.purchase_price) if product.purchase_price is not None else None,
        average_cost=float(product.purchase_price) if product.purchase_price is not None else None,
        unit=product.unit,
        conversion_factor=float(product.conversion_factor),
        min_stock=float(product.min_stock),
        current_stock=float(product.current_stock),
        stock_status=get_stock_status(float(product.current_stock), float(product.min_stock)),
        image_url=product.image_url,
        is_active=product.is_active,
        variants=variants,
        images=images,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT CRUD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=ResponseBase[PaginatedResponse[ProductListResponse]])
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[UUID] = None,
    stock_status: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    supplier_id: Optional[UUID] = None,
    barcode: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Product)
        .where(Product.company_id == current_user.company_id)
        .options(selectinload(Product.category), selectinload(Product.supplier), selectinload(Product.variants))
    )

    if category_id:
        query = query.where(Product.category_id == category_id)
    if supplier_id:
        query = query.where(Product.supplier_id == supplier_id)
    if barcode:
        query = query.where(
            or_(Product.barcode == barcode, Product.gtin == barcode)
        )
    if search:
        query = query.where(
            Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%")
        )
    if is_active is not None:
        query = query.where(Product.is_active == is_active)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(Product.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.unique().scalars().all()

    items = []
    for p in products:
        status = get_stock_status(float(p.current_stock), float(p.min_stock))
        if stock_status and status != stock_status:
            continue
        items.append(ProductListResponse(
            id=p.id,
            sku=p.sku,
            barcode=p.barcode,
            name=p.name,
            category_name=p.category.name if p.category else None,
            supplier_name=p.supplier.name if p.supplier else None,
            current_stock=float(p.current_stock),
            min_stock=float(p.min_stock),
            stock_status=status,
            sale_price=float(p.sale_price),
            purchase_price=float(p.purchase_price) if p.purchase_price is not None else None,
            average_cost=float(p.purchase_price) if p.purchase_price is not None else None,
            is_active=p.is_active,
            variant_count=len(p.variants) if p.variants else 0,
        ))

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    ))


# Static routes must be registered before /{product_id}, otherwise FastAPI
# tries to parse the literal "categories" as a UUID and returns 422.
@router.get("/categories/", response_model=ResponseBase[list[CategoryResponse]], include_in_schema=False)
@router.get("/categories", response_model=ResponseBase[list[CategoryResponse]])
async def list_categories(
    parent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(ProductCategory)
        .where(ProductCategory.company_id == current_user.company_id)
    )
    if parent_id is not None:
        query = query.where(ProductCategory.parent_id == parent_id)
    query = query.order_by(ProductCategory.sort_order, ProductCategory.name)

    result = await db.execute(query)
    categories = result.scalars().all()

    # Count children and products for each category
    items = []
    for cat in categories:
        children_count = await _count_children(db, cat.id, current_user.company_id)
        product_count = await _count_products_in_category(db, cat.id, current_user.company_id)
        items.append(CategoryResponse(
            id=cat.id,
            name=cat.name,
            parent_id=cat.parent_id,
            description=cat.description,
            sort_order=cat.sort_order,
            is_active=cat.is_active,
            children_count=children_count,
            product_count=product_count,
        ))

    return ResponseBase(data=items)


async def _count_children(db: AsyncSession, category_id: UUID, company_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(ProductCategory)
        .where(ProductCategory.parent_id == category_id, ProductCategory.company_id == company_id)
    )
    return result.scalar() or 0


async def _count_products_in_category(db: AsyncSession, category_id: UUID, company_id: UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Product)
        .where(Product.category_id == category_id, Product.company_id == company_id)
    )
    return result.scalar() or 0


@router.get("/categories/tree", response_model=ResponseBase[list[CategoryResponse]])
async def list_category_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all categories in a flat list (client builds tree from parent_id)."""
    return await list_categories(parent_id=None, db=db, current_user=current_user)


@router.post("/categories/", response_model=ResponseBase[CategoryResponse], include_in_schema=False)
@router.post("/categories", response_model=ResponseBase[CategoryResponse])
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate parent exists if set
    if data.parent_id:
        parent = await db.get(ProductCategory, data.parent_id)
        if not parent or parent.company_id != current_user.company_id:
            raise HTTPException(status_code=404, detail="მშობელი კატეგორია არ მოიძებნა")

    category = ProductCategory(
        company_id=current_user.company_id,
        name=data.name,
        parent_id=data.parent_id,
        description=data.description,
        sort_order=data.sort_order,
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return ResponseBase(data=CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        children_count=0,
        product_count=0,
    ))


@router.patch("/categories/{category_id}", response_model=ResponseBase[CategoryResponse])
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.company_id == current_user.company_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await db.flush()
    await db.refresh(category)

    children_count = await _count_children(db, category.id, current_user.company_id)
    product_count = await _count_products_in_category(db, category.id, current_user.company_id)

    return ResponseBase(data=CategoryResponse(
        id=category.id,
        name=category.name,
        parent_id=category.parent_id,
        description=category.description,
        sort_order=category.sort_order,
        is_active=category.is_active,
        children_count=children_count,
        product_count=product_count,
    ))


@router.delete("/categories/{category_id}", response_model=ResponseBase)
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.company_id == current_user.company_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="კატეგორია არ მოიძებნა")

    # Check for child categories
    child_count = await _count_children(db, category_id, current_user.company_id)
    if child_count > 0:
        raise HTTPException(status_code=400, detail="წაშლა შეუძლებელია: კატეგორიას გააჩნია ქვეკატეგორიები")

    # Unlink products from this category
    await db.execute(
        select(Product).where(Product.category_id == category_id)
    )
    await db.execute(
        Product.__table__.update().where(Product.category_id == category_id).values(category_id=None)
    )

    await db.delete(category)
    await db.flush()
    return ResponseBase(message="კატეგორია წაიშალა")


@router.get("/{product_id}", response_model=ResponseBase[ProductResponse])
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.company_id == current_user.company_id)
        .options(
            selectinload(Product.category),
            selectinload(Product.supplier),
            selectinload(Product.variants),
            selectinload(Product.images),
        )
    )
    product = result.unique().scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    return ResponseBase(data=_build_product_response(product))


@router.post("/", response_model=ResponseBase[ProductResponse])
async def create_product(
    data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    initial_stock = Decimal(str(data.current_stock))
    default_warehouse = None
    if initial_stock > 0:
        default_warehouse = (
            await db.execute(
                select(Warehouse).where(
                    Warehouse.company_id == current_user.company_id,
                    Warehouse.is_default.is_(True),
                    Warehouse.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if default_warehouse is None:
            raise HTTPException(
                status_code=409,
                detail="საწყისი ნაშთისთვის ჯერ შექმენით აქტიური მთავარი საწყობი",
            )

    product = Product(
        company_id=current_user.company_id,
        sku=data.sku,
        barcode=data.barcode,
        gtin=data.gtin,
        name=data.name,
        description=data.description,
        category_id=data.category_id,
        supplier_id=data.supplier_id,
        sale_price=data.sale_price,
        purchase_price=data.purchase_price,
        unit=data.unit,
        conversion_factor=data.conversion_factor,
        min_stock=data.min_stock,
        current_stock=data.current_stock,
        image_url=data.image_url,
    )
    db.add(product)
    await db.flush()

    if default_warehouse is not None:
        db.add(
            InventoryBalance(
                company_id=current_user.company_id,
                warehouse_id=default_warehouse.id,
                product_id=product.id,
                quantity=initial_stock,
                reserved_quantity=Decimal("0"),
            )
        )
        db.add(
            InventoryMovement(
                company_id=current_user.company_id,
                warehouse_id=default_warehouse.id,
                product_id=product.id,
                movement_type="in",
                quantity=initial_stock,
                balance_before=Decimal("0"),
                balance_after=initial_stock,
                reserved_before=Decimal("0"),
                reserved_after=Decimal("0"),
                reason="initial_stock",
                reason_category="adjustment",
                notes="პროდუქტის საწყისი ნაშთი",
                created_by=current_user.id,
            )
        )
    await db.refresh(product)

    # Reload with relationships
    result = await db.execute(
        select(Product)
        .where(Product.id == product.id)
        .options(
            selectinload(Product.category),
            selectinload(Product.supplier),
            selectinload(Product.variants),
            selectinload(Product.images),
        )
    )
    product = result.unique().scalar_one()

    return ResponseBase(data=_build_product_response(product))


@router.patch("/{product_id}", response_model=ResponseBase[ProductResponse])
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    if "current_stock" in update_data:
        raise HTTPException(
            status_code=400,
            detail="ნაშთი შეცვალეთ საწყობის ოპერაციით",
        )
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.flush()

    # Reload with relationships
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.category),
            selectinload(Product.supplier),
            selectinload(Product.variants),
            selectinload(Product.images),
        )
    )
    product = result.unique().scalar_one()

    return ResponseBase(data=_build_product_response(product))


@router.delete("/{product_id}", response_model=ResponseBase)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    await db.delete(product)
    await db.flush()
    return ResponseBase(message="პროდუქტი წაიშალა")


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT VARIANTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{product_id}/variants", response_model=ResponseBase[list[ProductVariantResponse]])
async def list_variants(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify product belongs to user's company
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .order_by(ProductVariant.sort_order, ProductVariant.name)
    )
    variants = result.scalars().all()

    items = []
    for v in variants:
        items.append(ProductVariantResponse(
            id=v.id,
            product_id=v.product_id,
            sku=v.sku,
            barcode=v.barcode,
            gtin=v.gtin,
            name=v.name,
            attr_1_name=v.attr_1_name,
            attr_1_value=v.attr_1_value,
            attr_2_name=v.attr_2_name,
            attr_2_value=v.attr_2_value,
            attr_3_name=v.attr_3_name,
            attr_3_value=v.attr_3_value,
            sale_price=float(v.sale_price) if v.sale_price is not None else None,
            purchase_price=float(v.purchase_price) if v.purchase_price is not None else None,
            current_stock=float(v.current_stock),
            min_stock=float(v.min_stock),
            stock_status=get_stock_status(float(v.current_stock), float(v.min_stock)),
            is_active=v.is_active,
            sort_order=v.sort_order,
            created_at=v.created_at,
            updated_at=v.updated_at,
        ))

    return ResponseBase(data=items)


@router.post("/{product_id}/variants", response_model=ResponseBase[ProductVariantResponse])
async def create_variant(
    product_id: UUID,
    data: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    # Map attributes list to columns
    attr_1_name = attr_1_value = None
    attr_2_name = attr_2_value = None
    attr_3_name = attr_3_value = None
    for i, attr in enumerate(data.attributes):
        if i == 0:
            attr_1_name, attr_1_value = attr.name, attr.value
        elif i == 1:
            attr_2_name, attr_2_value = attr.name, attr.value
        elif i == 2:
            attr_3_name, attr_3_value = attr.name, attr.value

    variant = ProductVariant(
        product_id=product_id,
        sku=data.sku,
        barcode=data.barcode,
        gtin=data.gtin,
        name=data.name,
        attr_1_name=attr_1_name,
        attr_1_value=attr_1_value,
        attr_2_name=attr_2_name,
        attr_2_value=attr_2_value,
        attr_3_name=attr_3_name,
        attr_3_value=attr_3_value,
        sale_price=data.sale_price,
        purchase_price=data.purchase_price,
        current_stock=data.current_stock,
        min_stock=data.min_stock,
        is_active=data.is_active,
        sort_order=data.sort_order,
    )
    db.add(variant)
    await db.flush()
    await db.refresh(variant)

    return ResponseBase(data=ProductVariantResponse(
        id=variant.id,
        product_id=variant.product_id,
        sku=variant.sku,
        barcode=variant.barcode,
        gtin=variant.gtin,
        name=variant.name,
        attr_1_name=variant.attr_1_name,
        attr_1_value=variant.attr_1_value,
        attr_2_name=variant.attr_2_name,
        attr_2_value=variant.attr_2_value,
        attr_3_name=variant.attr_3_name,
        attr_3_value=variant.attr_3_value,
        sale_price=float(variant.sale_price) if variant.sale_price is not None else None,
        purchase_price=float(variant.purchase_price) if variant.purchase_price is not None else None,
        current_stock=float(variant.current_stock),
        min_stock=float(variant.min_stock),
        stock_status=get_stock_status(float(variant.current_stock), float(variant.min_stock)),
        is_active=variant.is_active,
        sort_order=variant.sort_order,
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    ))


@router.patch("/{product_id}/variants/{variant_id}", response_model=ResponseBase[ProductVariantResponse])
async def update_variant(
    product_id: UUID,
    variant_id: UUID,
    data: ProductVariantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify product ownership
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="ვარიანტი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    # Handle attributes specially
    if "attributes" in update_data and update_data["attributes"] is not None:
        attrs = update_data.pop("attributes")
        attr_1_name = attr_1_value = None
        attr_2_name = attr_2_value = None
        attr_3_name = attr_3_value = None
        for i, attr in enumerate(attrs):
            if i == 0:
                attr_1_name, attr_1_value = attr.name, attr.value
            elif i == 1:
                attr_2_name, attr_2_value = attr.name, attr.value
            elif i == 2:
                attr_3_name, attr_3_value = attr.name, attr.value
        variant.attr_1_name = attr_1_name
        variant.attr_1_value = attr_1_value
        variant.attr_2_name = attr_2_name
        variant.attr_2_value = attr_2_value
        variant.attr_3_name = attr_3_name
        variant.attr_3_value = attr_3_value

    for field, value in update_data.items():
        setattr(variant, field, value)

    await db.flush()
    await db.refresh(variant)

    return ResponseBase(data=ProductVariantResponse(
        id=variant.id,
        product_id=variant.product_id,
        sku=variant.sku,
        barcode=variant.barcode,
        gtin=variant.gtin,
        name=variant.name,
        attr_1_name=variant.attr_1_name,
        attr_1_value=variant.attr_1_value,
        attr_2_name=variant.attr_2_name,
        attr_2_value=variant.attr_2_value,
        attr_3_name=variant.attr_3_name,
        attr_3_value=variant.attr_3_value,
        sale_price=float(variant.sale_price) if variant.sale_price is not None else None,
        purchase_price=float(variant.purchase_price) if variant.purchase_price is not None else None,
        current_stock=float(variant.current_stock),
        min_stock=float(variant.min_stock),
        stock_status=get_stock_status(float(variant.current_stock), float(variant.min_stock)),
        is_active=variant.is_active,
        sort_order=variant.sort_order,
        created_at=variant.created_at,
        updated_at=variant.updated_at,
    ))


@router.delete("/{product_id}/variants/{variant_id}", response_model=ResponseBase)
async def delete_variant(
    product_id: UUID,
    variant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="ვარიანტი არ მოიძებნა")

    await db.delete(variant)
    await db.flush()
    return ResponseBase(message="ვარიანტი წაიშალა")


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT IMAGES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{product_id}/images", response_model=ResponseBase[list[ProductImageResponse]])
async def list_images(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.sort_order, ProductImage.created_at)
    )
    images = result.scalars().all()

    items = [
        ProductImageResponse(
            id=img.id,
            product_id=img.product_id,
            variant_id=img.variant_id,
            url=img.url,
            thumbnail_url=img.thumbnail_url,
            alt_text=img.alt_text,
            is_primary=img.is_primary,
            file_type=img.file_type,
            file_size_bytes=img.file_size_bytes,
            sort_order=img.sort_order,
            created_at=img.created_at,
        )
        for img in images
    ]
    return ResponseBase(data=items)


@router.post("/{product_id}/images", response_model=ResponseBase[ProductImageResponse])
async def create_image(
    product_id: UUID,
    data: ProductImageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    # If this is set as primary, unset other primary images
    if data.is_primary:
        await db.execute(
            ProductImage.__table__.update()
            .where(
                ProductImage.product_id == product_id,
                ProductImage.is_primary == True,
            )
            .values(is_primary=False)
        )

    image = ProductImage(
        product_id=product_id,
        variant_id=data.variant_id,
        url=data.url,
        thumbnail_url=data.thumbnail_url,
        alt_text=data.alt_text,
        is_primary=data.is_primary,
        file_type=data.file_type,
        file_size_bytes=data.file_size_bytes,
        sort_order=data.sort_order,
    )
    db.add(image)
    await db.flush()
    await db.refresh(image)

    return ResponseBase(data=ProductImageResponse(
        id=image.id,
        product_id=image.product_id,
        variant_id=image.variant_id,
        url=image.url,
        thumbnail_url=image.thumbnail_url,
        alt_text=image.alt_text,
        is_primary=image.is_primary,
        file_type=image.file_type,
        file_size_bytes=image.file_size_bytes,
        sort_order=image.sort_order,
        created_at=image.created_at,
    ))


@router.patch("/{product_id}/images/{image_id}", response_model=ResponseBase[ProductImageResponse])
async def update_image(
    product_id: UUID,
    image_id: UUID,
    data: ProductImageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    result = await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="სურათი არ მოიძებნა")

    # If setting as primary, unset others
    if data.is_primary is True and not image.is_primary:
        await db.execute(
            ProductImage.__table__.update()
            .where(
                ProductImage.product_id == product_id,
                ProductImage.is_primary == True,
            )
            .values(is_primary=False)
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(image, field, value)

    await db.flush()
    await db.refresh(image)

    return ResponseBase(data=ProductImageResponse(
        id=image.id,
        product_id=image.product_id,
        variant_id=image.variant_id,
        url=image.url,
        thumbnail_url=image.thumbnail_url,
        alt_text=image.alt_text,
        is_primary=image.is_primary,
        file_type=image.file_type,
        file_size_bytes=image.file_size_bytes,
        sort_order=image.sort_order,
        created_at=image.created_at,
    ))


@router.delete("/{product_id}/images/{image_id}", response_model=ResponseBase)
async def delete_image(
    product_id: UUID,
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.company_id == current_user.company_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    result = await db.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="სურათი არ მოიძებნა")

    await db.delete(image)
    await db.flush()
    return ResponseBase(message="სურათი წაიშალა")


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK ADJUSTMENT (with UoM conversion support)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/adjust-stock", response_model=ResponseBase[StockMovementResponse])
async def adjust_stock(
    data: StockAdjustment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("inventory", "can_create")),
):
    raise HTTPException(
        status_code=410,
        detail="ეს endpoint გაუქმებულია; გამოიყენეთ /warehouses/adjust-stock",
    )

    result = await db.execute(
        select(Product).where(Product.id == data.product_id, Product.company_id == current_user.company_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი არ მოიძებნა")

    qty = float(data.quantity)
    conversion = float(product.conversion_factor) if product.conversion_factor else 1.0

    # Calculate quantity in base units for accurate KPI
    qty_base = qty * conversion

    if data.movement_type == "out":
        product.current_stock -= qty_base
    elif data.movement_type == "in":
        product.current_stock += qty_base
    elif data.movement_type == "adjustment":
        product.current_stock = qty_base

    # Also adjust variant stock if variant_id is provided
    variant_name = None
    if data.variant_id:
        result = await db.execute(
            select(ProductVariant).where(
                ProductVariant.id == data.variant_id,
                ProductVariant.product_id == data.product_id,
            )
        )
        variant = result.scalar_one_or_none()
        if variant:
            if data.movement_type == "out":
                variant.current_stock -= qty
            elif data.movement_type == "in":
                variant.current_stock += qty
            elif data.movement_type == "adjustment":
                variant.current_stock = qty
            variant_name = variant.name

    movement = StockMovement(
        product_id=data.product_id,
        variant_id=data.variant_id,
        movement_type=data.movement_type,
        quantity=qty,
        quantity_base_unit=qty_base,
        unit=data.unit or product.unit,
        reason=data.reason,
        notes=data.notes,
        created_by=current_user.id,
    )
    db.add(movement)
    await db.flush()
    await db.refresh(movement)

    resp = StockMovementResponse(
        id=movement.id,
        product_id=movement.product_id,
        variant_id=movement.variant_id,
        product_name=product.name,
        variant_name=variant_name,
        movement_type=movement.movement_type,
        quantity=float(movement.quantity),
        quantity_base_unit=float(movement.quantity_base_unit) if movement.quantity_base_unit is not None else None,
        unit=movement.unit,
        reason=movement.reason,
        notes=movement.notes,
        created_at=movement.created_at,
    )
    return ResponseBase(data=resp)


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK MOVEMENT HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/stock-movements", response_model=ResponseBase[PaginatedResponse[StockMovementResponse]])
async def list_stock_movements(
    product_id: Optional[UUID] = None,
    variant_id: Optional[UUID] = None,
    movement_type: Optional[str] = None,
    reason: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(StockMovement)
        .join(Product, StockMovement.product_id == Product.id)
        .where(Product.company_id == current_user.company_id)
        .options(selectinload(StockMovement.product), selectinload(StockMovement.variant))
    )

    if product_id:
        query = query.where(StockMovement.product_id == product_id)
    if variant_id:
        query = query.where(StockMovement.variant_id == variant_id)
    if movement_type:
        query = query.where(StockMovement.movement_type == movement_type)
    if reason:
        query = query.where(StockMovement.reason == reason)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(StockMovement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    movements = result.unique().scalars().all()

    items = [
        StockMovementResponse(
            id=m.id,
            product_id=m.product_id,
            variant_id=m.variant_id,
            product_name=m.product.name if m.product else None,
            variant_name=m.variant.name if m.variant else None,
            movement_type=m.movement_type,
            quantity=float(m.quantity),
            quantity_base_unit=float(m.quantity_base_unit) if m.quantity_base_unit is not None else None,
            unit=m.unit,
            reason=m.reason,
            notes=m.notes,
            created_at=m.created_at,
        )
        for m in movements
    ]

    return ResponseBase(data=PaginatedResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    ))
