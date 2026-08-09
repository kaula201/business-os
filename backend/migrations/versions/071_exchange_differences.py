"""071_exchange_differences

Revision ID: 071_exchange_differences
Revises: 070_recurring_journal_entries
Create Date: 2026-08-09

Revaluation log for open foreign-currency receivables.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "071_exchange_differences"
down_revision: str | None = "070_recurring_journal_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_differences",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("receivable_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("customer_receivables.id"), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("revaluation_date", sa.Date(), nullable=False),
        sa.Column("outstanding_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("gel_equivalent", sa.Numeric(18, 2), nullable=False),
        sa.Column("previous_gel_equivalent", sa.Numeric(18, 2), nullable=True),
        sa.Column("difference", sa.Numeric(18, 2), nullable=False),
        sa.Column("journal_entry_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_exchange_differences_company_id", "exchange_differences", ["company_id"])
    op.create_index("ix_exchange_differences_receivable_id", "exchange_differences", ["receivable_id"])
    op.create_index("ix_exchange_differences_revaluation_date", "exchange_differences", ["revaluation_date"])


def downgrade() -> None:
    op.drop_index("ix_exchange_differences_revaluation_date", table_name="exchange_differences")
    op.drop_index("ix_exchange_differences_receivable_id", table_name="exchange_differences")
    op.drop_index("ix_exchange_differences_company_id", table_name="exchange_differences")
    op.drop_table("exchange_differences")
