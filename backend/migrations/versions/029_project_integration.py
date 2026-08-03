"""Add project_id to tasks, analytic_entries, budget_lines.

Revision ID: 029_project_integration
Revises: 028_ecommerce
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_project_integration"
down_revision: Union[str, None] = "028_ecommerce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_tasks_project", "tasks", "projects", ["project_id"], ["id"])
    op.add_column("analytic_entries", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_analytic_entries_project", "analytic_entries", "projects", ["project_id"], ["id"])
    op.add_column("budget_lines", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_budget_lines_project", "budget_lines", "projects", ["project_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_tasks_project", "tasks", type_="foreignkey")
    op.drop_column("tasks", "project_id")
    op.drop_constraint("fk_analytic_entries_project", "analytic_entries", type_="foreignkey")
    op.drop_column("analytic_entries", "project_id")
    op.drop_constraint("fk_budget_lines_project", "budget_lines", type_="foreignkey")
    op.drop_column("budget_lines", "project_id")
