"""Create subscriptions table.

Revision ID: 054_subscriptions
Revises: 051_contracts
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054_subscriptions"
down_revision: Union[str, None] = "053_recruitment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("client_id", sa.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False, index=True),
        sa.Column("plan", sa.String(255), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("frequency", sa.String(20), server_default="monthly", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
