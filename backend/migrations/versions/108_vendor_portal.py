"""108_vendor_portal

Revision ID: 108_vendor_portal
Revises: 107_rfq_supplier
Create Date: 2026-08-19

Add vendor portal users for supplier self-service.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "108_vendor_portal"
down_revision = "107_rfq_supplier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_portal_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vendor_portal_users_company_id", "vendor_portal_users", ["company_id"])
    op.create_index("ix_vendor_portal_users_supplier_id", "vendor_portal_users", ["supplier_id"])
    op.create_index("ix_vendor_portal_users_email", "vendor_portal_users", ["email"])
    op.create_index("ix_vendor_portal_users_status", "vendor_portal_users", ["status"])


def downgrade() -> None:
    op.drop_index("ix_vendor_portal_users_status", table_name="vendor_portal_users")
    op.drop_index("ix_vendor_portal_users_email", table_name="vendor_portal_users")
    op.drop_index("ix_vendor_portal_users_supplier_id", table_name="vendor_portal_users")
    op.drop_index("ix_vendor_portal_users_company_id", table_name="vendor_portal_users")
    op.drop_table("vendor_portal_users")
