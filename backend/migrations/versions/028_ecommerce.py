"""Create eCommerce tables: ecom_categories, ecom_products.

Revision ID: 028_ecommerce
Revises: 027_pos
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_ecommerce"
down_revision: Union[str, None] = "027_pos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ecom_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ecom_categories_company", "ecom_categories", ["company_id"])

    op.create_table(
        "ecom_products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("compare_at_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("image_urls", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), server_default="false"),
        sa.Column("is_featured", sa.Boolean(), server_default="false"),
        sa.Column("stock_quantity", sa.Integer(), server_default="0"),
        sa.Column("seo_title", sa.String(255), nullable=True),
        sa.Column("seo_description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["ecom_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ecom_products_company", "ecom_products", ["company_id"])
    op.create_index("ix_ecom_products_category", "ecom_products", ["category_id"])
    op.create_index("ix_ecom_products_published", "ecom_products", ["is_published"])


def downgrade() -> None:
    op.drop_table("ecom_products")
    op.drop_table("ecom_categories")
