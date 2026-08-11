"""074_company_group

Revision ID: 074_company_group
Revises: 073_product_cost_layers
Create Date: 2026-08-09

Add company_group_id for consolidated (multi-company) reporting.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "074_company_group"
down_revision: str | None = "073_product_cost_layers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("company_group_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_companies_company_group_id", "companies", ["company_group_id"])


def downgrade() -> None:
    op.drop_index("ix_companies_company_group_id", table_name="companies")
    op.drop_column("companies", "company_group_id")
