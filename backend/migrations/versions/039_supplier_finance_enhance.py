"""Enhance Supplier Finance: overpayment, tolerance, currency diff, duplicate detection.

Adds overpaid_amount, currency_code, exchange_rate to supplier_payables.
Creates supplier_overpayments, supplier_invoice_tolerances,
and supplier_credit_note_currency_diffs tables.

Revision ID: 039_supplier_finance_enhance
Revises: 038_documents_enhance
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039_supplier_finance_enhance"
down_revision: Union[str, None] = "038_documents_enhance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Supplier payables enhancements ──────────────────────────────────
    op.add_column(
        "supplier_payables",
        sa.Column(
            "overpaid_amount",
            sa.Numeric(18, 2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "supplier_payables",
        sa.Column(
            "currency_code",
            sa.String(3),
            server_default=sa.text("'GEL'"),
            nullable=False,
        ),
    )
    op.add_column(
        "supplier_payables",
        sa.Column(
            "exchange_rate",
            sa.Numeric(18, 6),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )

    # ── Supplier overpayments table ─────────────────────────────────────
    op.create_table(
        "supplier_overpayments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("supplier_id", sa.UUID(), nullable=False, index=True),
        sa.Column("supplier_payable_id", sa.UUID(), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), server_default=sa.text("'GEL'"), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(18, 6), server_default=sa.text("1"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["supplier_payable_id"], ["supplier_payables.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id", "idempotency_key", name="uq_supplier_overpayment_idempotency"
        ),
    )

    # ── Supplier invoice tolerances table ───────────────────────────────
    op.create_table(
        "supplier_invoice_tolerances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column(
            "quantity_tolerance_percent",
            sa.Numeric(7, 4),
            server_default=sa.text("5"),
            nullable=False,
        ),
        sa.Column(
            "price_tolerance_percent",
            sa.Numeric(7, 4),
            server_default=sa.text("2"),
            nullable=False,
        ),
        sa.Column(
            "amount_tolerance",
            sa.Numeric(18, 2),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "enable_duplicate_detection",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "duplicate_lookback_days",
            sa.Integer(),
            server_default=sa.text("90"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", name="uq_supplier_invoice_tolerance_company"),
    )

    # ── Supplier credit note currency diffs table ────────────────────────
    op.create_table(
        "supplier_credit_note_currency_diffs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False, index=True),
        sa.Column("credit_note_id", sa.UUID(), nullable=False),
        sa.Column("payable_currency", sa.String(3), nullable=False),
        sa.Column("credit_note_currency", sa.String(3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("amount_in_payable_currency", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount_in_credit_note_currency", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency_difference", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["credit_note_id"], ["supplier_credit_notes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "credit_note_id", name="uq_credit_note_currency_diff_credit_note"
        ),
    )


def downgrade() -> None:
    op.drop_table("supplier_credit_note_currency_diffs")
    op.drop_table("supplier_invoice_tolerances")
    op.drop_table("supplier_overpayments")
    op.drop_column("supplier_payables", "exchange_rate")
    op.drop_column("supplier_payables", "currency_code")
    op.drop_column("supplier_payables", "overpaid_amount")
