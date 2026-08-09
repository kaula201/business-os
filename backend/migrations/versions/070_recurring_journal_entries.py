"""070_recurring_journal_entries

Revision ID: 070_recurring_journal_entries
Revises: 069_wms_fk_indexes
Create Date: 2026-08-09

Recurring journal entry templates (daily/weekly/monthly auto-posting).
"""
import sqlalchemy as sa
from alembic import op

revision: str = "070_recurring_journal_entries"
down_revision: str | None = "069_wms_fk_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_journal_entries",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("last_run_date", sa.Date(), nullable=True),
        sa.Column("lines", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("entry_description", sa.String(1000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("total_posted", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("company_id", "name", name="uq_recurring_journal_company_name"),
    )
    op.create_index("ix_recurring_journal_company_id", "recurring_journal_entries", ["company_id"])
    op.create_index("ix_recurring_journal_frequency", "recurring_journal_entries", ["frequency"])
    op.create_index("ix_recurring_journal_next_run", "recurring_journal_entries", ["next_run_date"])


def downgrade() -> None:
    op.drop_index("ix_recurring_journal_next_run", table_name="recurring_journal_entries")
    op.drop_index("ix_recurring_journal_frequency", table_name="recurring_journal_entries")
    op.drop_index("ix_recurring_journal_company_id", table_name="recurring_journal_entries")
    op.drop_table("recurring_journal_entries")
