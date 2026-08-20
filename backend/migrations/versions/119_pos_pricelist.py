"""119_pos_pricelist

Revision ID: 119_pos_pricelist
Revises: 118_pos_kitchen
Create Date: 2026-08-20

Client price lists for POS.
"""
import sqlalchemy as sa
from alembic import op

revision = "119_pos_pricelist"
down_revision = "118_pos_kitchen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_price_lists",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("product_id", sa.UUID(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("client_id", "product_id", name="uq_client_price_client_product"),
    )
    op.create_index("ix_client_price_lists_company", "client_price_lists", ["company_id"])
    op.create_index("ix_client_price_lists_client", "client_price_lists", ["client_id"])
    op.create_index("ix_client_price_lists_product", "client_price_lists", ["product_id"])


def downgrade() -> None:
    op.drop_table("client_price_lists")
