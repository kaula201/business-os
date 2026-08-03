"""Helpdesk module: create helpdesk_tickets table.

Revision ID: 049_helpdesk
Revises: 048_clients_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "049_helpdesk"
down_revision: Union[str, None] = "048_clients_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "helpdesk_tickets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), server_default="medium", nullable=False),
        sa.Column("status", sa.String(20), server_default="new", nullable=False),
        sa.Column("assignee_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("requester_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_helpdesk_tickets_company_id", "helpdesk_tickets", ["company_id"])
    op.create_index("ix_helpdesk_tickets_assignee_id", "helpdesk_tickets", ["assignee_id"])
    op.create_index("ix_helpdesk_tickets_requester_id", "helpdesk_tickets", ["requester_id"])


def downgrade() -> None:
    op.drop_index("ix_helpdesk_tickets_requester_id", table_name="helpdesk_tickets")
    op.drop_index("ix_helpdesk_tickets_assignee_id", table_name="helpdesk_tickets")
    op.drop_index("ix_helpdesk_tickets_company_id", table_name="helpdesk_tickets")
    op.drop_table("helpdesk_tickets")
