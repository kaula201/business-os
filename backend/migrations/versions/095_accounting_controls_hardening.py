"""095_accounting_controls_hardening

Revision ID: 095_acct_hardening
Revises: 094_accounting_controls
Create Date: 2026-08-17

Permit controlled group-consolidation scope and enforce one fiscal default.
"""
from alembic import op

revision = "095_acct_hardening"
down_revision = "094_accounting_controls"
branch_labels = None
depends_on = None

TABLES = ("fiscal_positions", "consolidation_account_mappings", "fx_translation_rates")
# Consolidation reads controls one company at a time with an explicitly pinned
# context; RLS itself remains strict for every table access.
POLICY = "company_id::text = current_setting('app.current_company_id', true)"


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_policy" ON "{table}"')
        op.execute(f'CREATE POLICY "{table}_tenant_policy" ON "{table}" USING ({POLICY}) WITH CHECK ({POLICY})')
    op.execute("CREATE UNIQUE INDEX uq_fiscal_position_one_default ON fiscal_positions (company_id) WHERE is_default")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_fiscal_position_one_default")
    restrictive = "company_id::text = current_setting('app.current_company_id', true)"
    for table in TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_policy" ON "{table}"')
        op.execute(f'CREATE POLICY "{table}_tenant_policy" ON "{table}" USING ({restrictive}) WITH CHECK ({restrictive})')
