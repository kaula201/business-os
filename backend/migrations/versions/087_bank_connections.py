"""087_bank_connections

Revision ID: 087_bank_connections
Revises: 086_integrations
Create Date: 2026-08-16

Bank connections: TBC/BOG sync config.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "087_bank_connections"
down_revision = "086_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("bank", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("account_number", sa.String(50), nullable=False),
        sa.Column("client_id", sa.String(100), nullable=True),
        sa.Column("client_secret", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bank_connections_company_id", "bank_connections", ["company_id"])


def downgrade() -> None:
    op.drop_table("bank_connections")
