# backend/app/schemas/product.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ─── Category ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[UUID] = None
    description: Optional[str] = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[UUID] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID]
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    children_count: int = 0
    product_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ─── Product Variants ────────────────────────────────────────────────────────

class VariantAttribute(BaseModel):
    name: str = Field(..., max_length=50, description="e.g. 'color', 'size', 'material'")
    value: str = Field(..., max_length=100, description="e.g. 'Red', 'L', 'Cotton'")


class ProductVariantCreate(BaseModel):
    sku: str
    barcode: Optional[str] = None
    gtin: Optional[str] = None
    name: str
    attributes: list[VariantAttribute] = Field(default_factory=list, max_length=3)
    sale_price: Optional[float] = None
    purchase_price: Optional[float] = None
    current_stock: float = 0
    min_stock: float = 0
    is_active: bool = True
    sort_order: int = 0


class ProductVariantUpdate(BaseModel):
    sku: Optional[str] = None
    barcode: Optional[str] = None
    gtin: Optional[str] = None
    name: Optional[str] = None
    attributes: Optional[list[VariantAttribute]] = None
    sale_price: Optional[float] = None
    purchase_price: Optional[float] = None
    current_stock: Optional[float] = None
    min_stock: Optional[float] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ProductVariantResponse(BaseModel):
    id: UUID
    product_id: UUID
    sku: str
    barcode: Optional[str] = None
    gtin: Optional[str] = None
    name: str
    attr_1_name: Optional[str] = None
    attr_1_value: Optional[str] = None
    attr_2_name: Optional[str] = None
    attr_2_value: Optional[str] = None
    attr_3_name: Optional[str] = None
    attr_3_value: Optional[str] = None
    sale_price: Optional[float] = None
    purchase_price: Optional[float] = None
    current_stock: float
    min_stock: float
    stock_status: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Product Images ─────────────────────────────────────────────────────────

class ProductImageCreate(BaseModel):
    url: str
    thumbnail_url: Optional[str] = None
    alt_text: Optional[str] = None
    is_primary: bool = False
    file_type: str = "image"
    file_size_bytes: Optional[int] = None
    sort_order: int = 0
    variant_id: Optional[UUID] = None


class ProductImageUpdate(BaseModel):
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    alt_text: Optional[str] = None
    is_primary: Optional[bool] = None
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    sort_order: Optional[int] = None
    variant_id: Optional[UUID] = None


class ProductImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: Optional[UUID] = None
    url: str
    thumbnail_url: Optional[str] = None
    alt_text: Optional[str] = None
    is_primary: bool
    file_type: str
    file_size_bytes: Optional[int] = None
    sort_order: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Product ─────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    sku: str
    barcode: Optional[str] = None
    gtin: Optional[str] = None
    name: str
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    sale_price: float = Field(..., ge=0)
    purchase_price: Optional[float] = None
    unit: str = "ცალი"
    conversion_factor: float = 1.0
    min_stock: float = 0
    current_stock: float = 0
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    sku: Optional[str] = None
    barcode: Optional[str] = None
    gtin: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    sale_price: Optional[float] = None
    purchase_price: Optional[float] = None
    unit: Optional[str] = None
    conversion_factor: Optional[float] = None
    min_stock: Optional[float] = None
    current_stock: Optional[float] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: UUID
    sku: str
    barcode: Optional[str] = None
    gtin: Optional[str] = None
    name: str
    description: Optional[str]
    category_id: Optional[UUID]
    category_name: Optional[str] = None
    supplier_id: Optional[UUID] = None
    supplier_name: Optional[str] = None
    sale_price: float
    purchase_price: Optional[float]
    average_cost: Optional[float] = None
    unit: str
    conversion_factor: float = 1.0
    min_stock: float
    current_stock: float
    stock_status: Optional[str] = None  # good, low, critical
    image_url: Optional[str]
    is_active: bool
    variants: list[ProductVariantResponse] = []
    images: list[ProductImageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductListResponse(BaseModel):
    id: UUID
    sku: str
    barcode: Optional[str] = None
    name: str
    category_name: Optional[str]
    supplier_name: Optional[str] = None
    current_stock: float
    min_stock: float
    stock_status: str
    sale_price: float
    purchase_price: Optional[float] = None
    average_cost: Optional[float] = None
    is_active: bool
    variant_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ─── Stock ────────────────────────────────────────────────────────────────────

class StockAdjustment(BaseModel):
    product_id: UUID
    variant_id: Optional[UUID] = None
    movement_type: str  # in, out, adjustment
    quantity: float = Field(..., gt=0)
    unit: Optional[str] = None  # UoM at time of transaction; converted to base unit for KPI
    reason: str  # purchase, sale, inventory, loss, other
    notes: Optional[str] = None


class StockMovementResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: Optional[UUID] = None
    product_name: Optional[str] = None
    variant_name: Optional[str] = None
    movement_type: str
    quantity: float
    quantity_base_unit: Optional[float] = None
    unit: Optional[str] = None
    reason: str
    notes: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
