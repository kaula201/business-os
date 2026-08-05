"""Dedicated non-superuser app role for Row-Level Security.

Revision ID: 063_rls_app_role
Revises: 062_rls_tenant_isolation
Create Date: 2026-08-05

The original 'business_os' role is a PostgreSQL superuser, and superusers
(and BYPASSRLS roles) bypass Row-Level Security entirely — FORCE ROW LEVEL
SECURITY does not apply to them. This migration creates a dedicated
application role without superuser/BYPASSRLS, grants it full DML on the
public schema (plus CREATE for Alembic), and FORCEs RLS on every
company-scoped table so the new role is filtered by tenant.

Deploy note: after this migration, DATABASE_URL (and TEST_DATABASE_URL in
tests) must switch to business_os_app:business_os_app@... and the same role
must be granted on the *_test databases (see skill notes).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "063_rls_app_role"
down_revision: Union[str, None] = "062_rls_tenant_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "business_os_app"
APP_PASSWORD = "business_os_app"  # same value used in docker-compose DATABASE_URL


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_PASSWORD}'
                    NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )
    # Schema + DML + DDL for the app role on the current database.
    op.execute(f"GRANT CONNECT ON DATABASE {op.get_bind().engine.url.database} TO {APP_ROLE}")
    op.execute(f"GRANT ALL ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {APP_ROLE}"
    )
    # Force RLS on every company-scoped table so the non-bypass app role is
    # always tenant-filtered (the unpinned branch of the policy keeps Alembic
    # migrations and seeds working).
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
                EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")
