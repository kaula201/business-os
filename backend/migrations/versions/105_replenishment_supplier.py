"""105_replenishment_supplier

Revision ID: 105_replenishment_supplier
Revises: 104_replenishment_depth
Create Date: 2026-08-18

Add supplier_id to replenishment_rules so auto-replenish can create a valid PO.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "105_replenishment_supplier"
down_revision = "104_replenishment_depth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("replenishment_rules", sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True))
    op.create_index("ix_replenishment_rules_supplier_id", "replenishment_rules", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_replenishment_rules_supplier_id", table_name="replenishment_rules")
    op.drop_column("replenishment_rules", "supplier_id")
