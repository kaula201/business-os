"""121_pos_loyalty_tiers_coupons

Revision ID: 121_pos_loyalty_tiers_coupons
Revises: 120_pos_currency
Create Date: 2026-08-20

Loyalty tiers and coupons for POS.
"""
import sqlalchemy as sa
from alembic import op

revision = "121_pos_loyalty_tiers_coupons"
down_revision = "120_pos_currency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_loyalty_accounts", sa.Column("tier", sa.String(20), nullable=False, server_default="bronze"))
    op.create_table(
        "pos_coupons",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_coupons_company", "pos_coupons", ["company_id"])
    op.create_index("ix_pos_coupons_code", "pos_coupons", ["code"])


def downgrade() -> None:
    op.drop_table("pos_coupons")
    op.drop_column("pos_loyalty_accounts", "tier")
