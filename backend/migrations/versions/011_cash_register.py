"""Add cash register tables: cash_accounts, cash_transactions.

Revision ID: 011_cash_register
Revises: 010_fleet_management
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_cash_register"
down_revision: Union[str, None] = "010_fleet_management"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cash_accounts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("currency", sa.String(3), server_default=sa.text("'GEL'"), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "cash_transactions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("cash_account_id", sa.UUID(as_uuid=True), sa.ForeignKey("cash_accounts.id"), nullable=False, index=True),
        sa.Column("transaction_date", sa.Date(), nullable=False, index=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("counterparty", sa.String(255), nullable=True),
        sa.Column("receipt_number", sa.String(100), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cash_transactions_cash_account_id", "cash_transactions", ["cash_account_id"])
    op.create_index("ix_cash_transactions_company_id", "cash_transactions", ["company_id"])


def downgrade() -> None:
    op.drop_table("cash_transactions")
    op.drop_table("cash_accounts")
