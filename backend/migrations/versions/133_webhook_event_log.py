"""133_webhook_event_log

Revision ID: 133_webhook_event_log
Revises: 132_helpdesk_sla_timers
Create Date: 2026-08-24

Webhook execution log fields (response code, error).
"""
import sqlalchemy as sa
from alembic import op

revision = "133_webhook_event_log"
down_revision = "132_helpdesk_sla_timers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("webhook_events", sa.Column("last_response_code", sa.Integer(), nullable=True))
    op.add_column("webhook_events", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("webhook_events", "last_error")
    op.drop_column("webhook_events", "last_response_code")
