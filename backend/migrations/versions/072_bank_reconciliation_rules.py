"""072_bank_reconciliation_rules

Revision ID: 072_bank_reconciliation_rules
Revises: 071_exchange_differences
Create Date: 2026-08-09

Bank reconciliation rules for automatic matching/categorization.
"""
import sqlalchemy as sa
from alembic import op

revision: str = "072_bank_reconciliation_rules"
down_revision: str | None = "071_exchange_differences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_reconciliation_rules",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("action", sa.String(30), nullable=False, server_default="categorize"),
        sa.Column("match_text", sa.Text(), nullable=True),
        sa.Column("match_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("date_window_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("direction", sa.String(10), nullable=False, server_default="any"),
        sa.Column("gl_account_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("gl_accounts.id"), nullable=True),
        sa.Column("gl_description", sa.String(255), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="uq_bank_reconciliation_rule_name"),
    )
    op.create_index("ix_bank_reconciliation_rules_company_id", "bank_reconciliation_rules", ["company_id"])
    op.create_index("ix_bank_reconciliation_rules_rule_type", "bank_reconciliation_rules", ["rule_type"])


def downgrade() -> None:
    op.drop_index("ix_bank_reconciliation_rules_rule_type", table_name="bank_reconciliation_rules")
    op.drop_index("ix_bank_reconciliation_rules_company_id", table_name="bank_reconciliation_rules")
    op.drop_table("bank_reconciliation_rules")
