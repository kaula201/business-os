"""Fail closed: unpinned sessions see zero rows and cannot insert.

Revision ID: 152_rls_fail_closed
Revises: 151_tenant_plan_is_active
Create Date: 2026-10-01

The previous tenant_isolation policy (064) allowed ALL rows when
app.current_company_id was NULL or ''. This migration replaces it with the
fail-closed predicate from app.core.tenant_scope: a pinned company sees only
its own rows; an unpinned session sees zero rows and cannot insert. An
explicit transaction-local app.rls_bypass='on' system scope is required for
cross-tenant tooling. The downgrade restores the old fail-open policy for
rollback compatibility.
"""
from typing import Sequence, Union

from alembic import op

# Frozen copy of app.core.tenant_scope.TENANT_POLICY_PREDICATE at this revision
# (already quote-doubled for the format() literal). A migration must not change
# meaning when the runtime helper changes later.
_PREDICATE = (
    "company_id::text = NULLIF(current_setting(''app.current_company_id'', true), '''') "
    "OR current_setting(''app.rls_bypass'', true) = ''on''"
)

_FAIL_CLOSED = f"""
DO $$
DECLARE
    t text;
    p text;
BEGIN
    FOR t IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND a.attname = 'company_id'
          AND NOT a.attisdropped
        ORDER BY c.relname
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        -- Permissive policies are OR-ed: any other permissive policy (for
        -- example the fail-open tms_* policies from migration 149) would
        -- re-open the table. tenant_isolation is the only permissive policy
        -- allowed on a company_id table; restrictive policies are kept.
        FOR p IN
            SELECT pol.policyname
            FROM pg_policies pol
            WHERE pol.schemaname = 'public'
              AND pol.tablename = t
              AND pol.policyname <> 'tenant_isolation'
              AND pol.permissive = 'PERMISSIVE'
        LOOP
            EXECUTE format('DROP POLICY IF EXISTS %I ON %I', p, t);
        END LOOP;
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I USING ({_PREDICATE}) WITH CHECK ({_PREDICATE})',
            t
        );
    END LOOP;
END
$$;
"""

revision: str = "152_rls_fail_closed"
down_revision: Union[str, None] = "151_tenant_plan_is_active"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(_FAIL_CLOSED)


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            t TEXT;
        BEGIN
            FOR t IN
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                WHERE n.nspname = 'public'
                  AND c.relkind = 'r'
                  AND a.attname = 'company_id'
                  AND NOT a.attisdropped
                ORDER BY c.relname
            LOOP
                EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON %I '
                    'USING ('
                    '  current_setting(''app.current_company_id'', true) IS NULL '
                    '  OR current_setting(''app.current_company_id'', true) = '''' '
                    '  OR company_id::text = current_setting(''app.current_company_id'', true)'
                    ') '
                    'WITH CHECK ('
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
