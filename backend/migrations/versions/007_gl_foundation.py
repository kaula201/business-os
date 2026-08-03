"""Add General Ledger tables: Chart of Accounts, Journal Entries.

Revision ID: 007_gl_foundation
Revises: 006_financial_hardening
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_gl_foundation"
down_revision: Union[str, None] = "006_financial_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gl_accounts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.UUID(as_uuid=True), sa.ForeignKey("gl_accounts.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_gl_account_company_code"),
    )
    op.create_index("ix_gl_accounts_company_id", "gl_accounts", ["company_id"])
    op.create_index("ix_gl_accounts_account_type", "gl_accounts", ["account_type"])

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("entry_number", sa.String(50), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_type", sa.String(50), nullable=False),
        sa.Column("reference_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("is_reversal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reversed_entry_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "entry_number", name="uq_journal_entry_company_number"),
    )
    op.create_index("ix_journal_entries_company_id", "journal_entries", ["company_id"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_reference_type", "journal_entries", ["reference_type"])
    op.create_index("ix_journal_entries_reference_id", "journal_entries", ["reference_id"])

    op.create_table(
        "journal_entry_lines",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("journal_entry_id", sa.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("gl_account_id", sa.UUID(as_uuid=True), sa.ForeignKey("gl_accounts.id"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("debit_amount", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("credit_amount", sa.Numeric(18, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("journal_entry_id", "line_number", name="uq_journal_entry_line_number"),
    )
    op.create_index("ix_journal_entry_lines_journal_entry_id", "journal_entry_lines", ["journal_entry_id"])
    op.create_index("ix_journal_entry_lines_gl_account_id", "journal_entry_lines", ["gl_account_id"])


def downgrade() -> None:
    op.drop_table("journal_entry_lines")
    op.drop_table("journal_entries")
    op.drop_table("gl_accounts")
