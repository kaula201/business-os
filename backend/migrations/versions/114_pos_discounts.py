"""114_pos_discounts

Revision ID: 114_pos_discounts
Revises: 113_pos_payments
Create Date: 2026-08-19

Discount fields on POS orders and items.
"""
import sqlalchemy as sa
from alembic import op

revision = "114_pos_discounts"
down_revision = "113_pos_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_orders", sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))
    op.add_column("pos_order_items", sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("pos_order_items", "discount_amount")
    op.drop_column("pos_orders", "discount_amount")
