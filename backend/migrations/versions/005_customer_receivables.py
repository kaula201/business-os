"""Add customer receivables, payments, credits, and bank reconciliation.

Revision ID: 005_customer_receivables
Revises: 004_customer_invoicing
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_customer_receivables"
down_revision: Union[str, None] = "004_customer_invoicing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "customer_receivables",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("invoice_id", UUID, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("client_id", UUID, sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credited_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("outstanding_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="unpaid"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "invoice_id", name="uq_customer_receivable_invoice"),
    )
    for column in ("company_id", "invoice_id", "client_id", "invoice_number", "due_date", "status"):
        op.create_index(f"ix_customer_receivables_{column}", "customer_receivables", [column])

    op.create_table(
        "customer_payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("receivable_id", UUID, sa.ForeignKey("customer_receivables.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("reference", sa.String(255), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_customer_payment_idempotency"),
    )
    for column in ("company_id", "receivable_id", "payment_date", "status"):
        op.create_index(f"ix_customer_payments_{column}", "customer_payments", [column])

    op.create_table(
        "customer_payment_reversals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("payment_id", UUID, sa.ForeignKey("customer_payments.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reversed_by", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("payment_id", name="uq_customer_payment_reversal_payment"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_customer_payment_reversal_idempotency"),
    )
    op.create_index("ix_customer_payment_reversals_company_id", "customer_payment_reversals", ["company_id"])
    op.create_index("ix_customer_payment_reversals_payment_id", "customer_payment_reversals", ["payment_id"])

    op.create_table(
        "customer_credit_notes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("receivable_id", UUID, sa.ForeignKey("customer_receivables.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("credit_note_number", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("credit_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_customer_credit_idempotency"),
        sa.UniqueConstraint("company_id", "credit_note_number", name="uq_customer_credit_number"),
    )
    for column in ("company_id", "receivable_id", "credit_date"):
        op.create_index(f"ix_customer_credit_notes_{column}", "customer_credit_notes", [column])

    op.create_table(
        "customer_bank_reconciliations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("bank_transaction_id", UUID, sa.ForeignKey("bank_transactions.id"), nullable=False),
        sa.Column("customer_receivable_id", UUID, sa.ForeignKey("customer_receivables.id"), nullable=False),
        sa.Column("customer_payment_id", UUID, sa.ForeignKey("customer_payments.id"), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reconciled_by", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reversed_by", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reversal_idempotency_key", sa.String(100), nullable=True),
        sa.Column("reversal_reason", sa.Text(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_customer_bank_reconciliation_idempotency"),
        sa.UniqueConstraint("company_id", "reversal_idempotency_key", name="uq_customer_bank_reconciliation_reversal_idempotency"),
    )
    for column in ("company_id", "bank_transaction_id", "customer_receivable_id", "customer_payment_id", "status"):
        op.create_index(f"ix_customer_bank_reconciliations_{column}", "customer_bank_reconciliations", [column])

    op.execute("""
        INSERT INTO customer_receivables (
            id, company_id, invoice_id, client_id, invoice_number, client_name, currency,
            original_amount, paid_amount, credited_amount, outstanding_amount, due_date,
            status, created_at, updated_at
        )
        SELECT gen_random_uuid(), company_id, id, client_id, invoice_number, client_name,
               currency, total, 0, 0, total, due_date,
               CASE WHEN due_date < CURRENT_DATE THEN 'overdue' ELSE 'unpaid' END,
               created_at, COALESCE(updated_at, created_at)
        FROM invoices
        ON CONFLICT (company_id, invoice_id) DO NOTHING
    """)


def downgrade() -> None:
    # Financial records are intentionally preserved; downgrade is non-destructive.
    pass
