"""116_pos_tips

Revision ID: 116_pos_tips
Revises: 115_pos_rounding
Create Date: 2026-08-19

Tips on POS orders.
"""
import sqlalchemy as sa
from alembic import op

revision = "116_pos_tips"
down_revision = "115_pos_rounding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_orders", sa.Column("tip_amount", sa.Numeric(18, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("pos_orders", "tip_amount")
