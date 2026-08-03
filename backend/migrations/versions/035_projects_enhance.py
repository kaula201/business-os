"""Enhance Projects module: milestones, owner, progress, budget plan link.

Revision ID: 035_projects_enhance
Revises: 034_analytic_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_projects_enhance"
down_revision: Union[str, None] = "034_analytic_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to projects table
    op.add_column("projects", sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("projects", sa.Column("completion_percent", sa.Numeric(5, 2), server_default="0", nullable=False))
    op.add_column("projects", sa.Column("budget_plan_id", sa.Uuid(), sa.ForeignKey("budget_plans.id"), nullable=True))

    # Create project_milestones table
    op.create_table(
        "project_milestones",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("completion_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_project_milestones_project", "project_milestones", ["project_id"])


def downgrade() -> None:
    op.drop_table("project_milestones")
    op.drop_column("projects", "budget_plan_id")
    op.drop_column("projects", "completion_percent")
    op.drop_column("projects", "owner_id")
