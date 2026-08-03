"""Add bank statement import and reconciliation.

Revision ID: 003_bank_reconciliation
Revises: 002_supplier_finance_reversals
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_bank_reconciliation"
down_revision: Union[str, None] = "002_supplier_finance_reversals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_name", sa.String(150), nullable=False),
        sa.Column("account_name", sa.String(150), nullable=False),
        sa.Column("iban", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GEL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "iban", name="uq_bank_account_company_iban"),
    )
    op.create_index("ix_bank_accounts_company_id", "bank_accounts", ["company_id"])
    op.create_index("ix_bank_accounts_status", "bank_accounts", ["status"])

    op.create_table(
        "bank_statement_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("debit_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit_total", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("imported_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_bank_statement_import_idempotency"),
        sa.UniqueConstraint("company_id", "bank_account_id", "content_hash", name="uq_bank_statement_import_hash"),
    )
    op.create_index("ix_bank_statement_imports_company_id", "bank_statement_imports", ["company_id"])
    op.create_index("ix_bank_statement_imports_bank_account_id", "bank_statement_imports", ["bank_account_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_import_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("counterparty", sa.String(255), nullable=False, server_default=""),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("matched_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="unmatched"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
        sa.ForeignKeyConstraint(["statement_import_id"], ["bank_statement_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "bank_account_id", "fingerprint", name="uq_bank_transaction_fingerprint"),
    )
    for column in ("company_id", "bank_account_id", "statement_import_id", "transaction_date", "direction", "status"):
        op.create_index(f"ix_bank_transactions_{column}", "bank_transactions", [column])

    op.create_table(
        "bank_reconciliations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_payable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reconciled_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reversal_idempotency_key", sa.String(100), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["bank_transaction_id"], ["bank_transactions.id"]),
        sa.ForeignKeyConstraint(["supplier_payable_id"], ["supplier_payables.id"]),
        sa.ForeignKeyConstraint(["supplier_payment_id"], ["supplier_payments.id"]),
        sa.ForeignKeyConstraint(["reconciled_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reversed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_payment_id"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_bank_reconciliation_idempotency"),
        sa.UniqueConstraint("company_id", "reversal_idempotency_key", name="uq_bank_reconciliation_reversal_idempotency"),
    )
    for column in ("company_id", "bank_transaction_id", "supplier_payable_id", "supplier_payment_id", "status"):
        op.create_index(f"ix_bank_reconciliations_{column}", "bank_reconciliations", [column])


def downgrade() -> None:
    # Intentionally data-preserving; use a separately reviewed archival migration.
    pass
