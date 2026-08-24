"""131_helpdesk_ticket_client_queue_attachment

Revision ID: 131_helpdesk_ticket_client_queue_attachment
Revises: 130_pos_session_opening_cash
Create Date: 2026-08-20

Client, queue and attachment on helpdesk tickets.
"""
import sqlalchemy as sa
from alembic import op

revision = "131_helpdesk_ticket_client_queue_attachment"
down_revision = "130_pos_session_opening_cash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("helpdesk_tickets", sa.Column("client_id", sa.UUID(), sa.ForeignKey("clients.id"), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("queue_id", sa.UUID(), sa.ForeignKey("helpdesk_queues.id"), nullable=True))
    op.add_column("helpdesk_tickets", sa.Column("attachment_url", sa.String(500), nullable=True))
    op.create_index("ix_helpdesk_tickets_client", "helpdesk_tickets", ["client_id"])
    op.create_index("ix_helpdesk_tickets_queue", "helpdesk_tickets", ["queue_id"])


def downgrade() -> None:
    op.drop_index("ix_helpdesk_tickets_queue", table_name="helpdesk_tickets")
    op.drop_index("ix_helpdesk_tickets_client", table_name="helpdesk_tickets")
    op.drop_column("helpdesk_tickets", "attachment_url")
    op.drop_column("helpdesk_tickets", "queue_id")
    op.drop_column("helpdesk_tickets", "client_id")
