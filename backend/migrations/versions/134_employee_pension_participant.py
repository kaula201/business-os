"""134_employee_pension_participant

Revision ID: 134_employee_pension_participant
Revises: 133_webhook_event_log
Create Date: 2026-08-24

Pension fund participation flag on employees (explains 0% pension lines).
"""
import sqlalchemy as sa
from alembic import op

revision = "134_employee_pension_participant"
down_revision = "133_webhook_event_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("pension_participant", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("employees", "pension_participant")
