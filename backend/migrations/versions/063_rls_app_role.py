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
import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "063_rls_app_role"
down_revision: Union[str, None] = "062_rls_tenant_isolation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "business_os_app"
# Local docker-compose.yml and tests omit APP_DB_PASSWORD.
_DEV_APP_PASSWORD = "business_os_app"


def _app_password() -> str:
    password = os.environ.get("APP_DB_PASSWORD", "").strip()
    if password:
        return password
    app_env = os.environ.get("APP_ENV", "").strip().lower()
    if app_env in {"production", "prod"}:
        raise RuntimeError("APP_DB_PASSWORD must be set when APP_ENV is production")
    return _DEV_APP_PASSWORD


def _dollar_quote(value: str) -> str:
    tag = "pw"
    while f"${tag}$" in value:
        tag += "x"
    return f"${tag}${value}${tag}$"


def upgrade() -> None:
    bind = op.get_bind()
    role_exists = bind.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": APP_ROLE},
    ).scalar()
    if not role_exists:
        op.execute(
            f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD {_dollar_quote(_app_password())} "
            "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
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
