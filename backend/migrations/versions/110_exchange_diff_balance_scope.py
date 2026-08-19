"""110_exchange_diff_balance_scope

Revision ID: 110_exchange_diff_balance_scope
Revises: 109_vendor_portal_auth
Create Date: 2026-08-19

Widen exchange_differences to cover payables, cash and bank balances:
- receivable_id becomes nullable
- add payable_id, cash_account_id, bank_account_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "110_exchange_diff_balance_scope"
down_revision = "109_vendor_portal_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("exchange_differences", "receivable_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("exchange_differences", sa.Column("payable_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("supplier_payables.id"), nullable=True))
    op.add_column("exchange_differences", sa.Column("cash_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cash_accounts.id"), nullable=True))
    op.add_column("exchange_differences", sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=True))
    op.create_index("ix_exchange_differences_payable_id", "exchange_differences", ["payable_id"])
    op.create_index("ix_exchange_differences_cash_account_id", "exchange_differences", ["cash_account_id"])
    op.create_index("ix_exchange_differences_bank_account_id", "exchange_differences", ["bank_account_id"])


def downgrade() -> None:
    op.drop_index("ix_exchange_differences_bank_account_id", table_name="exchange_differences")
    op.drop_index("ix_exchange_differences_cash_account_id", table_name="exchange_differences")
    op.drop_index("ix_exchange_differences_payable_id", table_name="exchange_differences")
    op.drop_column("exchange_differences", "bank_account_id")
    op.drop_column("exchange_differences", "cash_account_id")
    op.drop_column("exchange_differences", "payable_id")
    op.alter_column("exchange_differences", "receivable_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
