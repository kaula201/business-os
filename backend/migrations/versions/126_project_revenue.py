"""126_project_revenue

Revision ID: 126_project_revenue
Revises: 125_project_templates
Create Date: 2026-08-20

Revenue field on projects for real profitability (revenue - spent).
"""
import sqlalchemy as sa
from alembic import op

revision = "126_project_revenue"
down_revision = "125_project_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("revenue_amount", sa.Numeric(14, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("projects", "revenue_amount")
