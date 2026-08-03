"""Add immutable customer bank reconciliation reversals.

Revision ID: 006_financial_hardening
Revises: 005_customer_receivables
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_financial_hardening"
down_revision: Union[str, None] = "005_customer_receivables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "customer_bank_reconciliation_reversals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("company_id", UUID, sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "reconciliation_id",
            UUID,
            sa.ForeignKey("customer_bank_reconciliations.id"),
            nullable=False,
        ),
        sa.Column("bank_transaction_id", UUID, sa.ForeignKey("bank_transactions.id"), nullable=False),
        sa.Column(
            "customer_receivable_id",
            UUID,
            sa.ForeignKey("customer_receivables.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reversed_by", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "reconciliation_id",
            name="uq_customer_bank_reconciliation_reversal_parent",
        ),
        sa.UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_customer_bank_reconciliation_reversal_key",
        ),
    )
    for index_name, column in (
        ("ix_cbrr_company", "company_id"),
        ("ix_cbrr_reconciliation", "reconciliation_id"),
        ("ix_cbrr_bank_transaction", "bank_transaction_id"),
        ("ix_cbrr_receivable", "customer_receivable_id"),
    ):
        op.create_index(
            index_name,
            "customer_bank_reconciliation_reversals",
            [column],
        )

    # Preserve already-reversed 005 records as immutable child events.
    op.execute("""
        INSERT INTO customer_bank_reconciliation_reversals (
            id, company_id, reconciliation_id, bank_transaction_id,
            customer_receivable_id, amount, idempotency_key, reason,
            reversed_by, created_at
        )
        SELECT gen_random_uuid(), company_id, id, bank_transaction_id,
               customer_receivable_id, amount, reversal_idempotency_key,
               reversal_reason, reversed_by, reversed_at
        FROM customer_bank_reconciliations
        WHERE status = 'reversed'
          AND reversal_idempotency_key IS NOT NULL
          AND reversal_reason IS NOT NULL
          AND reversed_at IS NOT NULL
        ON CONFLICT (reconciliation_id) DO NOTHING
    """)


def downgrade() -> None:
    # Financial reversal history is intentionally preserved.
    pass
