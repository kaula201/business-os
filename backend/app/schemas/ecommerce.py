"""Pydantic schemas for eCommerce module."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EcomCategoryCreate(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int = 0


class EcomCategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    product_count: int = 0

    model_config = {"from_attributes": True}


class EcomProductCreate(BaseModel):
    product_id: UUID
    category_id: Optional[UUID] = None
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    compare_at_price: Optional[Decimal] = None
    image_url: Optional[str] = None
    image_urls: Optional[list[str]] = None
    is_published: bool = False
    is_featured: bool = False
    stock_quantity: int = 0
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None


class EcomProductUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    compare_at_price: Optional[Decimal] = None
    image_url: Optional[str] = None
    image_urls: Optional[list[str]] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None
    category_id: Optional[UUID] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None


class EcomProductResponse(BaseModel):
    id: UUID
    product_id: UUID
    category_id: Optional[UUID] = None
    category_name: Optional[str] = None
    name: str
    slug: str
    description: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    image_url: Optional[str] = None
    image_urls: Optional[list[str]] = None
    is_published: bool
    is_featured: bool
    stock_quantity: int
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
