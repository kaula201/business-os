"""097_fiscal_position_application

Revision ID: 097_fiscal_application
Revises: 096_acct_strict_rls
Create Date: 2026-08-18

Apply company fiscal positions to partners and new sales/purchase documents.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "097_fiscal_application"
down_revision = "096_acct_strict_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fiscal position drives configurable VAT GL posting; values are account codes
    # so document snapshots remain self-contained when a mapping is later edited.
    op.add_column("fiscal_positions", sa.Column("sales_tax_account_code", sa.String(20), nullable=False, server_default="2200"))
    op.add_column("fiscal_positions", sa.Column("purchase_tax_account_code", sa.String(20), nullable=False, server_default="5300"))
    for table in ("clients", "suppliers", "purchase_orders", "supplier_invoices", "invoices"):
        op.add_column(table, sa.Column("fiscal_position_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f"fk_{table}_fiscal_position", table, "fiscal_positions", ["fiscal_position_id"], ["id"])
        op.create_index(f"ix_{table}_fiscal_position_id", table, ["fiscal_position_id"])
    # Invoice/Supplier invoice snapshot tax account prevents later config edits
    # from changing an already-issued document's GL semantics.
    op.add_column("invoices", sa.Column("tax_account_code", sa.String(20), nullable=True))
    op.add_column("supplier_invoices", sa.Column("tax_account_code", sa.String(20), nullable=True))


def downgrade() -> None:
    for table in ("invoices", "supplier_invoices"):
        op.drop_column(table, "tax_account_code")
    for table in ("clients", "suppliers", "purchase_orders", "supplier_invoices", "invoices"):
        op.drop_index(f"ix_{table}_fiscal_position_id", table_name=table)
        op.drop_constraint(f"fk_{table}_fiscal_position", table, type_="foreignkey")
        op.drop_column(table, "fiscal_position_id")
    op.drop_column("fiscal_positions", "purchase_tax_account_code")
    op.drop_column("fiscal_positions", "sales_tax_account_code")
