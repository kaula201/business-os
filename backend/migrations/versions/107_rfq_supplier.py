"""107_rfq_supplier

Revision ID: 107_rfq_supplier
Revises: 106_po_version
Create Date: 2026-08-18

Add supplier_id to rfqs for RFQ email sending.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "107_rfq_supplier"
down_revision = "106_po_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rfqs", sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=True))
    op.create_index("ix_rfqs_supplier_id", "rfqs", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("ix_rfqs_supplier_id", table_name="rfqs")
    op.drop_column("rfqs", "supplier_id")
