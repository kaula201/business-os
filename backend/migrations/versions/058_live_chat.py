"""Create chat_messages table.

Revision ID: 058_live_chat
Revises: 057_quality_control

Live Chat module — support/communication chat messages between company users
and customers.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "058_live_chat"
down_revision: Union[str, None] = "057_quality_control"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("sender_type", sa.String(20), nullable=False, index=True),
        sa.Column("sender_id", sa.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(20), server_default="web", nullable=False),
        sa.Column("status", sa.String(20), server_default="delivered", nullable=False),
        sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
