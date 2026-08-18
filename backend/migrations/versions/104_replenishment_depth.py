"""104_replenishment_depth

Revision ID: 104_replenishment_depth
Revises: 103_supplier_price_history
Create Date: 2026-08-18

Add safety_stock and lead_time_days to replenishment_rules.
"""
from alembic import op
import sqlalchemy as sa

revision = "104_replenishment_depth"
down_revision = "103_supplier_price_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("replenishment_rules", sa.Column("safety_stock", sa.Numeric(18, 3), nullable=False, server_default="0"))
    op.add_column("replenishment_rules", sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("replenishment_rules", "lead_time_days")
    op.drop_column("replenishment_rules", "safety_stock")
