"""137_pos_customer_deposit

Revision ID: 137_pos_customer_deposit
Revises: 136_pos_registers_cashiers_terminals
Create Date: 2026-08-24

Customer credit/deposit ledger for POS (store credit).
"""
import sqlalchemy as sa
from alembic import op

revision = "137_pos_customer_deposit"
down_revision = "136_pos_registers_cashiers_terminals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_customer_balances",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("company_id", sa.UUID(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("client_id", sa.UUID(), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_pos_customer_credit_client", "pos_customer_balances", ["client_id"])


def downgrade() -> None:
    op.drop_table("pos_customer_balances")
