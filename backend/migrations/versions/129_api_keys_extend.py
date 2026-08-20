"""129_api_keys_extend

Revision ID: 129_api_keys_extend
Revises: 128_helpdesk_ticket_team_stage
Create Date: 2026-08-20

Extend existing api_keys table: user_id, expires_at, rotated_from_id (Odoo JSON-2 API style).
"""
import sqlalchemy as sa
from alembic import op

revision = "129_api_keys_extend"
down_revision = "128_helpdesk_ticket_team_stage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("api_keys", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("api_keys", sa.Column("rotated_from_id", sa.UUID(), nullable=True))
    op.create_index("ix_api_keys_user", "api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_user", table_name="api_keys")
    op.drop_column("api_keys", "rotated_from_id")
    op.drop_column("api_keys", "expires_at")
    op.drop_column("api_keys", "user_id")
