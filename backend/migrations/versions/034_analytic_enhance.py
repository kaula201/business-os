"""Create analytic_allocation_rules table.

Revision ID: 034_analytic_enhance
Revises: 033_assets_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034_analytic_enhance"
down_revision: Union[str, None] = "033_assets_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytic_allocation_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_gl_account_id", sa.Uuid(), nullable=False),
        sa.Column("target_analytic_account_id", sa.Uuid(), nullable=False),
        sa.Column("allocation_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["source_gl_account_id"], ["gl_accounts.id"],),
        sa.ForeignKeyConstraint(["target_analytic_account_id"], ["analytic_accounts.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analytic_allocation_rules_company", "analytic_allocation_rules", ["company_id"])


def downgrade() -> None:
    op.drop_table("analytic_allocation_rules")
