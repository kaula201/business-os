"""118_pos_kitchen

Revision ID: 118_pos_kitchen
Revises: 117_client_balance
Create Date: 2026-08-20

Kitchen display system (KDS) status on POS orders.
"""
import sqlalchemy as sa
from alembic import op

revision = "118_pos_kitchen"
down_revision = "117_client_balance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pos_orders", sa.Column("kitchen_status", sa.String(20), nullable=False, server_default="new"))


def downgrade() -> None:
    op.drop_column("pos_orders", "kitchen_status")
