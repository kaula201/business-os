"""Recreate tenant policies to allow unpinned (empty) tenant scope.

Revision ID: 064_rls_policy_empty_scope
Revises: 063_rls_app_role
Create Date: 2026-08-05

set_config('app.current_company_id', NULL, true) surfaces as an empty
string (''), not SQL NULL. The original policy only checked IS NULL, so
tooling that explicitly clears the tenant got zero rows. This migration
recreates every tenant policy with the '' branch included.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "064_rls_policy_empty_scope"
down_revision: Union[str, None] = "063_rls_app_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t TEXT;
        BEGIN
            FOR t IN
                SELECT table_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name = 'company_id'
                ORDER BY table_name
            LOOP
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON %I '
                    'USING ('
                    '  current_setting(''app.current_company_id'', true) IS NULL '
                    '  OR current_setting(''app.current_company_id'', true) = '''' '
                    '  OR company_id::text = current_setting(''app.current_company_id'', true)'
                    ')',
                    t
                );
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t TEXT;
        BEGIN
            FOR t IN
                SELECT table_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name = 'company_id'
                ORDER BY table_name
            LOOP
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON %I '
                    'USING ('
                    '  current_setting(''app.current_company_id'', true) IS NULL '
                    '  OR company_id::text = current_setting(''app.current_company_id'', true)'
                    ')',
                    t
                );
            END LOOP;
        END
        $$;
        """
    )
