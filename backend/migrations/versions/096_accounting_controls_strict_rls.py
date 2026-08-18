"""096_accounting_controls_strict_rls

Revision ID: 096_acct_strict_rls
Revises: 095_acct_hardening
Create Date: 2026-08-18

Restore strict tenant RLS for accounting control tables.
"""
from alembic import op

revision = "096_acct_strict_rls"
down_revision = "095_acct_hardening"
branch_labels = None
depends_on = None

TABLES = ("fiscal_positions", "consolidation_account_mappings", "fx_translation_rates")
POLICY = "company_id::text = current_setting('app.current_company_id', true)"


def upgrade() -> None:
    for table in TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_tenant_policy" ON "{table}"')
        op.execute(f'CREATE POLICY "{table}_tenant_policy" ON "{table}" USING ({POLICY}) WITH CHECK ({POLICY})')


def downgrade() -> None:
    # Keep strict policy on downgrade as well: there is no safe broad fallback.
    pass
