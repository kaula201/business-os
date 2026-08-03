import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Float, Text, func, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class StockStatus(str, enum.Enum):
    GOOD = "good"
    LOW = "low"
    CRITICAL = "critical"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    gtin: Mapped[str | None] = mapped_column(String(14), nullable=True, comment="Global Trade Item Number (GTIN-8/12/13/14)")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sale_price: Mapped[float] = mapped_column(Float, default=0)
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(50), default="ცალი")
    # Conversion factor to base unit (e.g. 1 box = 12 pieces → conversion_factor=12)
    # Used for accurate stock KPI when products are received/sold in different UoM
    conversion_factor: Mapped[float] = mapped_column(Float, default=1.0)
    min_stock: Mapped[float] = mapped_column(Float, default=0)
    current_stock: Mapped[float] = mapped_column(Float, default=0)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="products")
    category = relationship("ProductCategory", back_populates="products")
    supplier = relationship("Supplier", backref="products")
    order_items = relationship("OrderItem", back_populates="product")
    stock_movements = relationship("StockMovement", back_populates="product")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan",
                          foreign_keys="ProductImage.product_id")


class ProductVariant(Base):
    """Product variants (size, color, material, etc.)"""
    __tablename__ = "product_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(100), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gtin: Mapped[str | None] = mapped_column(String(14), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="e.g. 'Red / Large'")
    # Attribute key-value pairs stored as JSON-like columns for queryability
    attr_1_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="e.g. 'color'")
    attr_1_value: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="e.g. 'Red'")
    attr_2_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="e.g. 'size'")
    attr_2_value: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="e.g. 'L'")
    attr_3_name: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="e.g. 'material'")
    attr_3_value: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="e.g. 'Cotton'")
    sale_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="Override parent price if set")
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_stock: Mapped[float] = mapped_column(Float, default=0)
    min_stock: Mapped[float] = mapped_column(Float, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="variants")


class ProductImage(Base):
    """Product images and attachments"""
    __tablename__ = "product_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    file_type: Mapped[str] = mapped_column(String(20), default="image", comment="image, document, video")
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product = relationship("Product", back_populates="images", foreign_keys=[product_id])
    variant = relationship("ProductVariant", backref="images")


class ProductCategory(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    company = relationship("Company")
    products = relationship("Product", back_populates="category")
    parent = relationship("ProductCategory", remote_side="ProductCategory.id", backref="children")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    # Stock in base units for accurate KPI regardless of transaction UoM
    quantity_base_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="UoM at time of transaction")
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    product = relationship("Product", back_populates="stock_movements")
    variant = relationship("ProductVariant", backref="stock_movements")
