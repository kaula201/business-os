"""151_tenant_plan_is_active

Revision ID: 151_tenant_plan_is_active
Revises: 150_saas_tenant_billing
Create Date: 2026-09-29

The ORM catalog includes tenant_plans.is_active. Databases created only by
replaying migrations never added the column.
"""
import sqlalchemy as sa
from alembic import op

revision = "151_tenant_plan_is_active"
down_revision = "150_saas_tenant_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_plans",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("tenant_plans", "is_active")
