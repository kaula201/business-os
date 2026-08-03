"""Add budgeting tables: budget_plans, budget_lines.

Revision ID: 014_budgeting
Revises: 013_expenses
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_budgeting"
down_revision: Union[str, None] = "013_expenses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budget_plans",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False, index=True),
        sa.Column("period_type", sa.String(20), server_default=sa.text("'monthly'"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "budget_lines",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("plan_id", sa.UUID(as_uuid=True), sa.ForeignKey("budget_plans.id"), nullable=False, index=True),
        sa.Column("gl_account_id", sa.UUID(as_uuid=True), sa.ForeignKey("gl_accounts.id"), nullable=False, index=True),
        sa.Column("period", sa.String(7), nullable=False, index=True),
        sa.Column("planned_amount", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("budget_lines")
    op.drop_table("budget_plans")
