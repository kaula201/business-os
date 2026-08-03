"""Enhance products: variants, barcode/GTIN, category hierarchy, images, supplier.

Revision ID: 041_products_enhance
Revises: 040_production_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041_products_enhance"
down_revision: Union[str, None] = "040_production_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Product enhancements
    op.add_column("products", sa.Column("supplier_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_product_supplier", "products", "suppliers", ["supplier_id"], ["id"])
    op.add_column("products", sa.Column("barcode", sa.String(100), nullable=True, index=True))
    op.add_column("products", sa.Column("gtin", sa.String(14), nullable=True))
    op.add_column("products", sa.Column("conversion_factor", sa.Float(), server_default=sa.text("1.0"), nullable=False))

    # ProductVariant table
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("barcode", sa.String(100), nullable=True),
        sa.Column("gtin", sa.String(14), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("attr_1_name", sa.String(50), nullable=True),
        sa.Column("attr_1_value", sa.String(100), nullable=True),
        sa.Column("attr_2_name", sa.String(50), nullable=True),
        sa.Column("attr_2_value", sa.String(100), nullable=True),
        sa.Column("attr_3_name", sa.String(50), nullable=True),
        sa.Column("attr_3_value", sa.String(100), nullable=True),
        sa.Column("sale_price", sa.Float(), nullable=True),
        sa.Column("purchase_price", sa.Float(), nullable=True),
        sa.Column("current_stock", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("min_stock", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_variants_product", "product_variants", ["product_id"])

    # ProductImage table
    op.create_table(
        "product_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("variant_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("alt_text", sa.String(255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("file_type", sa.String(20), server_default="image", nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"],),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_images_product", "product_images", ["product_id"])

    # Category hierarchy
    op.add_column("categories", sa.Column("parent_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_category_parent", "categories", "categories", ["parent_id"], ["id"])
    op.add_column("categories", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("categories", sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False))

    # StockMovement enhancements
    op.add_column("stock_movements", sa.Column("variant_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_stock_movement_variant", "stock_movements", "product_variants", ["variant_id"], ["id"])
    op.add_column("stock_movements", sa.Column("quantity_base_unit", sa.Float(), nullable=True))
    op.add_column("stock_movements", sa.Column("unit", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("stock_movements", "unit")
    op.drop_column("stock_movements", "quantity_base_unit")
    op.drop_constraint("fk_stock_movement_variant", "stock_movements", type_="foreignkey")
    op.drop_column("stock_movements", "variant_id")
    op.drop_column("categories", "sort_order")
    op.drop_column("categories", "description")
    op.drop_constraint("fk_category_parent", "categories", type_="foreignkey")
    op.drop_column("categories", "parent_id")
    op.drop_table("product_images")
    op.drop_table("product_variants")
    op.drop_column("products", "conversion_factor")
    op.drop_column("products", "gtin")
    op.drop_column("products", "barcode")
    op.drop_constraint("fk_product_supplier", "products", type_="foreignkey")
    op.drop_column("products", "supplier_id")
