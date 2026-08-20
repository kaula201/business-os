"""120_pos_currency

Revision ID: 120_pos_currency
Revises: 119_pos_pricelist
Create Date: 2026-08-20

Multi-currency POS orders.
"""
import sqlalchemy as sa
from alembic import op

revision = "120_pos_currency"
down_revision = "119_pos_pricelist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_orders", sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"))
    op.add_column("pos_orders", sa.Column("currency_rate", sa.Numeric(18, 6), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("pos_orders", "currency_rate")
    op.drop_column("pos_orders", "currency")
