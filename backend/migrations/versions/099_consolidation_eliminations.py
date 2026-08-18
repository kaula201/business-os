"""099_consolidation_eliminations

Revision ID: 099_consolidation_elims
Revises: 098_fiscal_tenant_guard
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "099_consolidation_elims"
down_revision = "098_fiscal_tenant_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consolidation_eliminations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("counterparty_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("elimination_date", sa.Date(), nullable=False),
        sa.Column("source_revenue_account_code", sa.String(20), nullable=False),
        sa.Column("source_expense_account_code", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id")),
        sa.Column("reversal_journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("reversed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "idempotency_key", name="uq_consolidation_elimination_key"),
        sa.CheckConstraint("amount > 0", name="ck_consolidation_elimination_amount_positive"),
        sa.CheckConstraint("company_id <> counterparty_company_id", name="ck_consolidation_elimination_distinct_company"),
    )
    op.create_index("ix_consolidation_eliminations_company_id", "consolidation_eliminations", ["company_id"])
    op.create_index("ix_consolidation_eliminations_status", "consolidation_eliminations", ["status"])
    policy = "company_id::text = current_setting('app.current_company_id', true)"
    op.execute('ALTER TABLE "consolidation_eliminations" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "consolidation_eliminations" FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY "consolidation_eliminations_tenant_policy" ON "consolidation_eliminations" USING ({policy}) WITH CHECK ({policy})')


def downgrade() -> None:
    op.drop_table("consolidation_eliminations")
