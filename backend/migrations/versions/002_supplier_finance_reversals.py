"""Add supplier credit notes and payment reversals.

Revision ID: 002_supplier_finance_reversals
Revises: 001_initial
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "002_supplier_finance_reversals"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "supplier_payables",
        sa.Column(
            "credited_amount",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_table(
        "supplier_credit_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_payable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("supplier_credit_note_number", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("credit_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["supplier_payable_id"], ["supplier_payables.id"]),
        sa.ForeignKeyConstraint(["supplier_invoice_id"], ["supplier_invoices.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_supplier_credit_note_idempotency"),
        sa.UniqueConstraint(
            "company_id", "supplier_id", "supplier_credit_note_number",
            name="uq_supplier_credit_note_number",
        ),
    )
    op.create_index("ix_supplier_credit_notes_company_id", "supplier_credit_notes", ["company_id"])
    op.create_index("ix_supplier_credit_notes_supplier_id", "supplier_credit_notes", ["supplier_id"])
    op.create_index("ix_supplier_credit_notes_supplier_payable_id", "supplier_credit_notes", ["supplier_payable_id"])
    op.create_index("ix_supplier_credit_notes_supplier_invoice_id", "supplier_credit_notes", ["supplier_invoice_id"])
    op.create_index("ix_supplier_credit_notes_credit_date", "supplier_credit_notes", ["credit_date"])

    op.create_table(
        "supplier_payment_reversals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_payable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["supplier_payment_id"], ["supplier_payments.id"]),
        sa.ForeignKeyConstraint(["supplier_payable_id"], ["supplier_payables.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supplier_payment_id", name="uq_supplier_payment_reversal_payment"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_supplier_payment_reversal_idempotency"),
    )
    op.create_index("ix_supplier_payment_reversals_company_id", "supplier_payment_reversals", ["company_id"])
    op.create_index("ix_supplier_payment_reversals_supplier_payment_id", "supplier_payment_reversals", ["supplier_payment_id"])
    op.create_index("ix_supplier_payment_reversals_supplier_payable_id", "supplier_payment_reversals", ["supplier_payable_id"])


def downgrade() -> None:
    # Production rollback is intentionally data-preserving. Use a separately
    # reviewed archival migration if these records ever need to be retired.
    pass
