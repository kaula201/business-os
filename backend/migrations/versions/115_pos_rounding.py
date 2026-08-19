"""115_pos_rounding

Revision ID: 115_pos_rounding
Revises: 114_pos_discounts
Create Date: 2026-08-19

Cash rounding (1 tetri) on POS orders.
"""
import sqlalchemy as sa
from alembic import op

revision = "115_pos_rounding"
down_revision = "114_pos_discounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_orders", sa.Column("rounding_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("pos_orders", "rounding_amount")
