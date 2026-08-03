"""Enhance tasks module: attachments, history, reminders, dependencies.

Revision ID: 041_tasks_enhance
Revises: 040_production_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041_tasks_enhance"
down_revision: Union[str, None] = "040_production_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TaskAttachments
    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_size", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("mime_type", sa.String(100), server_default="application/octet-stream", nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"],),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_attachments_company", "task_attachments", ["company_id"])

    # TaskHistory
    op.create_table(
        "task_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"],),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_history_company", "task_history", ["company_id"])

    # TaskReminders
    op.create_table(
        "task_reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("remind_at", sa.DateTime(), nullable=False),
        sa.Column("reminded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reminded_at", sa.DateTime(), nullable=True),
        sa.Column("notification_type", sa.String(20), server_default="email", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"],),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_reminders_company", "task_reminders", ["company_id"])

    # TaskDependencies
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("depends_on_task_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("company_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("dependency_type", sa.String(20), server_default="blocked_by", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"],),
        sa.ForeignKeyConstraint(["depends_on_task_id"], ["tasks.id"],),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"],),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_dependencies_company", "task_dependencies", ["company_id"])


def downgrade() -> None:
    op.drop_table("task_dependencies")
    op.drop_table("task_reminders")
    op.drop_table("task_history")
    op.drop_table("task_attachments")
