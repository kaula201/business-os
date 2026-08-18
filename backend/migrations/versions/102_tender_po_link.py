"""102_tender_po_link

Revision ID: 102_tender_po_link
Revises: 101_tender_child_rls
Create Date: 2026-08-18

Add warehouse_id and purchase_order_id to tenders for auto PO generation on award.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "102_tender_po_link"
down_revision = "101_tender_child_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenders", sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=True))
    op.add_column("tenders", sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id"), nullable=True))
    op.create_index("ix_tenders_warehouse_id", "tenders", ["warehouse_id"])


def downgrade() -> None:
    op.drop_index("ix_tenders_warehouse_id", table_name="tenders")
    op.drop_column("tenders", "purchase_order_id")
    op.drop_column("tenders", "warehouse_id")
