"""Safely adopt the legacy schema and run versioned Alembic migrations."""
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.alembic_version import ensure_alembic_version_width
from app.core.config import settings
from app.core.database import init_db
from app.core.db_roles import MANAGED_ROLES, create_role_if_missing, grant_statements, matview_event_statements
from app.core.secret_redaction import hides_password, install_log_redaction, public_migration_error

BASELINE_REVISION = "001_initial"


def alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return config


async def _extension(bind, name: str) -> None:
    """Create an extension when this connection is allowed to.

    The dev app role is not a superuser. If the extension is already there,
    permission errors are ignored so local compose keeps working.
    """
    try:
        async with bind.begin() as connection:
            await connection.execute(text(f"CREATE EXTENSION IF NOT EXISTS {name}"))
    except (ProgrammingError, DBAPIError) as exc:
        message = str(exc).lower()
        if "permission denied" in message or "must be superuser" in message:
            return
        raise


async def _prepare(bind) -> bool:
    """Return whether alembic_version already exists.

    A fresh database is created from the current ORM metadata, then every
    revision is replayed. Stamping head here would skip RLS, the app role,
    grants, extensions, materialized views, and seed rows that are not part
    of the models. Replaying is safe because duplicate tables and columns
    (the ``credited_amount`` failure in 002) are skipped, while new DDL still
    runs. An existing database is left alone and ``upgrade`` applies only
    revisions it does not have yet — those columns are absent, so the same
    migrations are not no-ops.
    """
    async with bind.connect() as connection:
        schema_exists = bool(
            await connection.scalar(text("SELECT to_regclass('public.companies') IS NOT NULL"))
        )
        version_exists = bool(
            await connection.scalar(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            )
        )
    if not schema_exists:
        # embeddings.vector and later trigram indexes need these before DDL.
        await _extension(bind, "vector")
        await _extension(bind, "pg_trgm")
        # create_all builds tables only. It does not create RLS policies,
        # FORCE ROW LEVEL SECURITY, or the grants from 062/063 and later.
        # Those run in the upgrade below, then _ensure_tenant_rls repeats
        # them so a table create_all made early cannot miss the policy.
        await init_db(bind)
    return version_exists


async def _ensure_managed_roles(bind) -> None:
    """Create and grant every role in ``MANAGED_ROLES``.

    Skipped when this connection is not a superuser, so local dev keeps using
    ``DATABASE_URL`` unchanged. Adding a role is a new ``RoleSpec`` in that
    tuple; this loop does not change.
    """
    async with bind.connect() as connection:
        is_super = bool(
            await connection.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            )
        )
    if not is_super:
        return

    def _apply(sync_conn) -> None:
        for spec in MANAGED_ROLES:
            create_role_if_missing(sync_conn, spec)
        database = sync_conn.engine.url.database
        for spec in MANAGED_ROLES:
            for statement in grant_statements(spec, database):
                sync_conn.execute(text(statement))
        for statement in matview_event_statements(MANAGED_ROLES):
            sync_conn.execute(text(statement))

    async with bind.begin() as connection:
        await connection.run_sync(_apply)


# Same predicate as migration 064. Unpinned sessions (login, before
# set_config) still see rows. A pinned company sees only its own rows.
_TENANT_RLS = """
DO $$
DECLARE
    t text;
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


async def _ensure_tenant_rls(bind) -> None:
    """Re-apply tenant RLS after upgrade.

    ``create_all`` does not emit policies or FORCE ROW LEVEL SECURITY.
    Migrations 062/063 do, but only for tables that exist when they run.
    A later migration that is skipped as a duplicate table would also skip
    any RLS bundled with that create. This pass covers every company-scoped
    table. It is a no-op for privileges when the connection is not a
    superuser, so local dev is unchanged.
    """
    async with bind.connect() as connection:
        is_super = bool(
            await connection.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            )
        )
    if not is_super:
        return
    async with bind.begin() as connection:
        await connection.execute(text(_TENANT_RLS))


async def _widen_alembic_version(bind) -> None:
    """Widen version_num before upgrade. env.py does this again on upgrade."""
    async with bind.begin() as connection:
        await connection.run_sync(ensure_alembic_version_width)


def main() -> None:
    url = settings.migration_database_url()
    install_log_redaction(url)
    bind = create_async_engine(url, poolclass=NullPool, echo=False)
    try:
        version_exists = asyncio.run(_prepare(bind))
        config = alembic_config()
        if not version_exists:
            command.stamp(config, BASELINE_REVISION)
        asyncio.run(_widen_alembic_version(bind))
        command.upgrade(config, "head")
        asyncio.run(_ensure_tenant_rls(bind))
        asyncio.run(_ensure_managed_roles(bind))
        # Catalog only. Does not delete company module toggles or permissions.
        from seed_modules import seed_modules

        asyncio.run(seed_modules(bind))
    except Exception as exc:
        if hides_password(exc, url):
            raise public_migration_error(exc, url) from None
        raise
    finally:
        asyncio.run(bind.dispose())


if __name__ == "__main__":
    main()
