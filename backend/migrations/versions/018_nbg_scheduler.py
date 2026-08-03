"""Add durable integration sync history for NBG scheduler.
Revision ID: 018_nbg_scheduler
Revises: 017_deferred
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018_nbg_scheduler"
down_revision: Union[str, None] = "017_deferred"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integration_sync_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("integration", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("currencies_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rates_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rates_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_isl_company_integration_started",
        "integration_sync_logs",
        ["company_id", "integration", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_isl_company_integration_started", table_name="integration_sync_logs")
    op.drop_table("integration_sync_logs")
