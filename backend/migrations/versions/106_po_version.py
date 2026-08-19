"""106_po_version

Revision ID: 106_po_version
Revises: 105_replenishment_supplier
Create Date: 2026-08-18

Add version column to purchase_orders for PO versioning.
"""
from alembic import op
import sqlalchemy as sa

revision = "106_po_version"
down_revision = "105_replenishment_supplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("purchase_orders", "version")
