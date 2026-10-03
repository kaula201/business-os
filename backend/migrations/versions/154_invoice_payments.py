"""154_invoice_payments

Revision ID: 154_invoice_payments
Revises: 153_company_storefront_slug
Create Date: 2026-09-30

Adds standalone invoice payments (SAL without FIN) and default GEL currency on orders.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import UUID

revision = "154_invoice_payments"
down_revision = "153_company_storefront_slug"
branch_labels = None
depends_on = None

_TENANT_POLICY_PREDICATE = "company_id = NULLIF(current_setting('app.current_company_id', true), '')::uuid OR current_setting('app.rls_bypass', true) = 'on'"


def _column_exists(table: str, column: str) -> bool:
    insp = inspect(op.get_bind())
    return column in {c["name"] for c in insp.get_columns(table)}


def _table_exists(table: str) -> bool:
    insp = inspect(op.get_bind())
    return table in insp.get_table_names()


def upgrade() -> None:
    # Add payment tracking columns to invoices if missing.
    if not _column_exists("invoices", "paid_amount"):
        op.add_column(
            "invoices",
            sa.Column("paid_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        )
    if not _column_exists("invoices", "payment_status"):
        op.add_column(
            "invoices",
            sa.Column("payment_status", sa.String(20), nullable=False, server_default="unpaid"),
        )

    # Create invoice_payments table if missing.
    if not _table_exists("invoice_payments"):
        op.create_table(
            "invoice_payments",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "company_id",
                UUID(as_uuid=True),
                sa.ForeignKey("companies.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "invoice_id",
                UUID(as_uuid=True),
                sa.ForeignKey("invoices.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("amount", sa.Numeric(18, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False),
            sa.Column("payment_date", sa.Date(), nullable=False),
            sa.Column("method", sa.String(50), nullable=True),
            sa.Column("reference", sa.String(100), nullable=True),
            sa.Column(
                "created_by",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    op.execute("ALTER TABLE invoice_payments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_payments FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON invoice_payments")
    op.execute(
        f"CREATE POLICY tenant_isolation ON invoice_payments USING ({_TENANT_POLICY_PREDICATE}) WITH CHECK ({_TENANT_POLICY_PREDICATE})"
    )

    # Add default GEL currency to orders if missing.
    if not _column_exists("orders", "currency"):
        op.add_column(
            "orders",
            sa.Column("currency", sa.String(3), nullable=False, server_default="GEL"),
        )


def downgrade() -> None:
    if _table_exists("invoice_payments"):
        op.drop_table("invoice_payments")

    if _column_exists("orders", "currency"):
        op.drop_column("orders", "currency")

    if _column_exists("invoices", "payment_status"):
        op.drop_column("invoices", "payment_status")
    if _column_exists("invoices", "paid_amount"):
        op.drop_column("invoices", "paid_amount")
