"""Row-Level Security for multi-tenant isolation (PostgreSQL).

Revision ID: 062_rls_tenant_isolation
Revises: 061_inventory_stock_consistency
Create Date: 2026-08-05

Enables PostgreSQL Row-Level Security on every table that carries a
company_id column. The backend pins the tenant per transaction via
SET LOCAL app.current_company_id = '<company-uuid>' (see
app/core/dependencies.py get_current_user). Policies:

  - when app.current_company_id IS SET -> rows of that company only;
  - when it is NULL/absent (alembic migrations, seeds, admin tooling,
    backups) -> all rows visible, so operational tooling keeps working.

This is a defense-in-depth layer on top of the ORM-level company scoping:
even a query that forgets its company filter cannot leak another tenant's
rows once the session variable is pinned.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "062_rls_tenant_isolation"
down_revision: Union[str, None] = "061_inventory_stock_consistency"
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
                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON %I '
                    'USING ('
                    '  current_setting(''app.current_company_id'', true) IS NULL '
                    '  OR current_setting(''app.current_company_id'', true) = '''' '
                    '  OR company_id::text = current_setting(''app.current_company_id'', true)'
                    ')',
                    t
                );
                EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
                -- The app role owns the tables; without FORCE the owner would
                -- bypass RLS entirely. FORCE applies the policy to every role,
                -- including the owner — while the unpinned branch of the policy
                -- still lets migrations/seeds/admin tooling see everything.
                EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
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
                EXECUTE format('ALTER TABLE %I DISABLE ROW LEVEL SECURITY', t);
            END LOOP;
        END
        $$;
        """
    )
