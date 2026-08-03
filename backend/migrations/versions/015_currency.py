"""Add currency_rates table for multi-currency support.

Revision ID: 015_currency
Revises: 014_budgeting
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015_currency"
down_revision: Union[str, None] = "014_budgeting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "currency_rates",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("from_currency", sa.String(3), nullable=False),
        sa.Column("to_currency", sa.String(3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False, index=True),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(50), server_default=sa.text("'manual'"), nullable=False),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "from_currency", "to_currency", "rate_date", name="uq_currency_rate"),
    )


def downgrade() -> None:
    op.drop_table("currency_rates")
