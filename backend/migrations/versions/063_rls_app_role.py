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
    """Quote a password so the closer cannot collide with the value.

    ``$pw$secret$pw$pw$`` is parsed as the string ``secret`` plus leftover
    ``pw$`` when the password ends in ``$pw``. Grow the tag until the
    delimiter does not occur in the value and is not formed on the boundary
    with the closing delimiter.
    """
    tag = "pw"
    # Bound the loop: a tag longer than the value cannot sit inside it, and
    # the closer's trailing ``$`` is not part of the boundary check below.
    for _ in range(len(value) + 2):
        delimiter = f"${tag}$"
        if delimiter not in (value + delimiter)[:-1]:
            return f"{delimiter}{value}{delimiter}"
        tag += "x"
    raise RuntimeError(f"Could not quote a password for role {APP_ROLE}.")


def _create_app_role(password: str) -> None:
    """Create the role without echoing the statement if it fails.

    A colliding dollar-quote used to raise and put the password in the
    traceback (and in the Postgres error log). The tag above avoids that
    collision. If creation still fails, the driver exception — which embeds
    the SQL — is discarded.
    """
    statement = (
        f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD {_dollar_quote(password)} "
        "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
    )
    bind = op.get_bind()
    nested = bind.begin_nested()
    try:
        is_superuser = bind.execute(
            text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        ).scalar()
        if is_superuser:
            # Panic is above ERROR, so a failed statement is not written to
            # the server log. Restored before the savepoint commits so the
            # rest of this migration still logs real errors.
            bind.execute(text("SELECT set_config('log_min_error_statement', 'panic', true)"))
        bind.execute(text(statement))
        if is_superuser:
            bind.execute(text("SELECT set_config('log_min_error_statement', 'error', true)"))
        nested.commit()
    except Exception:
        try:
            nested.rollback()
        except Exception:
            pass
        raise RuntimeError(f"Failed to create database role {APP_ROLE}.") from None


def upgrade() -> None:
    bind = op.get_bind()
    role_exists = bind.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": APP_ROLE},
    ).scalar()
    if not role_exists:
        _create_app_role(_app_password())
    # Schema + DML + DDL for the app role on the current database.
    op.execute(f"GRANT CONNECT ON DATABASE {op.get_bind().engine.url.database} TO {APP_ROLE}")
    op.execute(f"GRANT ALL ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    # ALL TABLES does not include materialized views. Grant the ones that
    # already exist (migration 060). Later ones are covered by the event
    # trigger below; migration 065 also transfers ownership so REFRESH works.
    op.execute(
        f"""
        DO $$
        DECLARE
            mv text;
        BEGIN
            FOR mv IN
                SELECT c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'm'
            LOOP
                EXECUTE format('GRANT SELECT ON TABLE %I TO {APP_ROLE}', mv);
            END LOOP;
        END
        $$;
        """
    )
    # Defaults apply to objects created later by the migration superuser
    # (business_os), including tables added by revisions after this one.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
        f"GRANT ALL ON TABLES TO {APP_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
        f"GRANT ALL ON SEQUENCES TO {APP_ROLE}"
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION business_os_grant_matview()
        RETURNS event_trigger
        LANGUAGE plpgsql
        AS $fn$
        DECLARE
            obj record;
        BEGIN
            FOR obj IN
                SELECT object_identity
                FROM pg_event_trigger_ddl_commands()
                WHERE command_tag = 'CREATE MATERIALIZED VIEW'
            LOOP
                EXECUTE format(
                    'GRANT SELECT ON TABLE %s TO {APP_ROLE}',
                    obj.object_identity
                );
            END LOOP;
        END;
        $fn$;
        """
    )
    op.execute("DROP EVENT TRIGGER IF EXISTS business_os_grant_matview")
    op.execute(
        """
        CREATE EVENT TRIGGER business_os_grant_matview
        ON ddl_command_end
        WHEN TAG IN ('CREATE MATERIALIZED VIEW')
        EXECUTE FUNCTION business_os_grant_matview()
        """
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
