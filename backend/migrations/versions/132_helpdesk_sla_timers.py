"""132_helpdesk_sla_timers

Revision ID: 132_helpdesk_sla_timers
Revises: 131_helpdesk_ticket_client_queue_attachment
Create Date: 2026-08-24

SLA timers on helpdesk tickets (response/resolution deadlines).
"""
import sqlalchemy as sa
from alembic import op

revision = "132_helpdesk_sla_timers"
down_revision = "131_helpdesk_ticket_client_queue_attachment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("helpdesk_tickets", sa.Column("sla_id", sa.UUID(), sa.ForeignKey("helpdesk_slas.id"), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("response_deadline", sa.DateTime(), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("resolution_deadline", sa.DateTime(), nullable=True))
    op.create_index("ix_helpdesk_tickets_sla", "helpdesk_tickets", ["sla_id"])


def downgrade() -> None:
    op.drop_index("ix_helpdesk_tickets_sla", table_name="helpdesk_tickets")
    op.drop_column("helpdesk_tickets", "resolution_deadline")
    op.drop_column("helpdesk_tickets", "response_deadline")
    op.drop_column("helpdesk_tickets", "sla_id")
