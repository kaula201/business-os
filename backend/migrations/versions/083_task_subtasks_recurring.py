"""083_task_subtasks_recurring

Revision ID: 083_task_subtasks_recurring
Revises: 082_hr_pension_payslip
Create Date: 2026-08-14

Adds parent_id (subtasks), recurrence, recurrence_end to tasks.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "083_task_subtasks_recurring"
down_revision = "082_hr_pension_payslip"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=True))
    op.add_column("tasks", sa.Column("recurrence", sa.String(length=20), nullable=True))
    op.add_column("tasks", sa.Column("recurrence_end", sa.Date(), nullable=True))
    op.create_index("ix_tasks_parent_id", "tasks", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_parent_id", table_name="tasks")
    op.drop_column("tasks", "recurrence_end")
    op.drop_column("tasks", "recurrence")
    op.drop_column("tasks", "parent_id")
