"""103_supplier_price_history

Revision ID: 103_supplier_price_history
Revises: 102_tender_po_link
Create Date: 2026-08-18

Add supplier_price_history table for vendor price trend/history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "103_supplier_price_history"
down_revision = "102_tender_po_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_price_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GEL"),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_supplier_price_history_company_id", "supplier_price_history", ["company_id"])
    op.create_index("ix_supplier_price_history_supplier_id", "supplier_price_history", ["supplier_id"])
    op.create_index("ix_supplier_price_history_product_id", "supplier_price_history", ["product_id"])
    op.create_index("ix_supplier_price_history_changed_at", "supplier_price_history", ["changed_at"])

    # Tenant RLS on the new table.
    policy = "company_id::text = current_setting('app.current_company_id', true)"
    op.execute('ALTER TABLE "supplier_price_history" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "supplier_price_history" FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY "supplier_price_history_tenant_policy" ON "supplier_price_history" USING ({policy}) WITH CHECK ({policy})')


def downgrade() -> None:
    op.drop_index("ix_supplier_price_history_changed_at", table_name="supplier_price_history")
    op.drop_index("ix_supplier_price_history_product_id", table_name="supplier_price_history")
    op.drop_index("ix_supplier_price_history_supplier_id", table_name="supplier_price_history")
    op.drop_index("ix_supplier_price_history_company_id", table_name="supplier_price_history")
    op.drop_table("supplier_price_history")
