"""117_client_balance

Revision ID: 117_client_balance
Revises: 116_pos_tips
Create Date: 2026-08-19

Client balance for on-account (credit) POS payments.
"""
import sqlalchemy as sa
from alembic import op

revision = "117_client_balance"
down_revision = "116_pos_tips"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("clients", "balance")
