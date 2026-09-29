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
tests) must use the business_os_app role. Production takes that role's
password from APP_DB_PASSWORD. Local docker-compose.yml leaves the variable
unset and keeps its dev password. The same role must be granted on the
*_test databases (see skill notes).

If this revision already ran, it will not change an existing password.
Set the new password as the Postgres superuser before switching DATABASE_URL:

    ALTER ROLE business_os_app PASSWORD '...';
"""
from typing import Sequence, Union

from alembic import op

from app.core.db_roles import (
    APP_ROLE,
    create_role_if_missing,
    dollar_quote,
    grant_statements,
    matview_event_statements,
)

revision: str = "063_rls_app_role"
down_revision: Union[str, None] = "062_rls_tenant_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dollar_quote(value: str) -> str:
    """Backward-compatible wrapper. New roles use ``dollar_quote`` directly."""
    return dollar_quote(value, APP_ROLE.name)


def upgrade() -> None:
    # This revision only bootstraps the app role. Later roles are entries in
    # MANAGED_ROLES and are created by the migrate service, not here.
    bind = op.get_bind()
    create_role_if_missing(bind, APP_ROLE)
    database = bind.engine.url.database
    for statement in grant_statements(APP_ROLE, database):
        op.execute(statement)
    for statement in matview_event_statements((APP_ROLE,)):
        op.execute(statement)
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
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE.name}")
