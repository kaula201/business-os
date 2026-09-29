"""Safely adopt the legacy schema and run versioned Alembic migrations."""
import asyncio
import logging
import os
import sys
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
from app.core.db_roles import (
    MANAGED_ROLES,
    attribute_statement,
    create_role_if_missing,
    grant_statements,
    matview_event_statements,
    matview_owner_statements,
    revoke_excess_statements,
    revoke_public_schema_create_statements,
)
from app.core.secret_redaction import hides_password, install_log_redaction, public_migration_error

BASELINE_REVISION = "001_initial"
logger = logging.getLogger(__name__)


class UnexpectedDatabase(RuntimeError):
    """The connection is not the database restore asked to reconcile."""


def expected_database_name() -> str | None:
    """Target database from the environment, if restore set one.

    ``EXPECTED_DATABASE`` and ``TARGET_DB`` are optional. When both are set
    they must agree. When neither is set, migrate does not guess a name.
    """
    expected = os.environ.get("EXPECTED_DATABASE", "").strip()
    target = os.environ.get("TARGET_DB", "").strip()
    if expected and target and expected != target:
        raise UnexpectedDatabase(
            "EXPECTED_DATABASE and TARGET_DB name different databases."
        )
    return expected or target or None


def assert_expected_database(current: str, expected: str | None) -> None:
    """Abort when this connection is not the restore target.

    An unset expected name does not abort. A compose migrate service whose
    URL still points at ``business_os`` must not reconcile production while
    restore asked for another database.
    """
    if expected and current != expected:
        raise UnexpectedDatabase(
            f"Refusing to migrate database {current}; expected {expected}."
        )


async def _require_expected_database(bind) -> str:
    """Log ``current_database()`` and abort on a target mismatch.

    Called before roles-only work, before Alembic, and again immediately
    before full reconcile. The name is the connected database, not a
    hardcoded ``business_os``.
    """
    async with bind.connect() as connection:
        current = await connection.scalar(text("SELECT current_database()"))
    current = str(current)
    print(f"migrate current_database={current}", flush=True)
    logger.info("migrate current_database=%s", current)
    assert_expected_database(current, expected_database_name())
    return current


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


async def _ensure_managed_roles(bind, *, roles_only: bool = False) -> None:
    """Reconcile every role in ``MANAGED_ROLES``.

    Skipped when this connection is not a superuser, so local dev keeps using
    ``DATABASE_URL`` unchanged. Adding a role is a new ``RoleSpec`` in that
    tuple; this loop does not change.

    Attributes, grants, and (for the backup role) revokes run on every call,
    not only when the role is created. Existing passwords are left alone.

    ``roles_only`` creates and resets attributes and then stops. It does not
    grant, create the matview event trigger, or touch schema objects. Restore
    uses that mode on an empty database so ``pg_restore`` can load the trigger
    itself.
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
            sync_conn.execute(text(attribute_statement(spec)))
        if roles_only:
            return
        database = sync_conn.engine.url.database
        for spec in MANAGED_ROLES:
            for statement in revoke_excess_statements(spec, database):
                sync_conn.execute(text(statement))
            for statement in grant_statements(spec, database):
                sync_conn.execute(text(statement))
        # After the grants. PUBLIC grants are not cleared by revoke_excess,
        # and a previous ALL on the schema would otherwise leave CREATE.
        for statement in revoke_public_schema_create_statements(database, MANAGED_ROLES):
            sync_conn.execute(text(statement))
        for statement in matview_owner_statements():
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


def _roles_only(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv != ["--roles-only"]:
        raise SystemExit("usage: python -m app.core.migrate_schema [--roles-only]")
    return True


def main() -> None:
    roles_only = _roles_only(sys.argv[1:])
    url = settings.migration_database_url()
    install_log_redaction(url)
    bind = create_async_engine(url, poolclass=NullPool, echo=False)
    try:
        # Before any DDL. Restore sets EXPECTED_DATABASE to the target, so a
        # URL that still names business_os stops here.
        asyncio.run(_require_expected_database(bind))
        if roles_only:
            # No Alembic and no object grants. The target database stays empty
            # so a following pg_restore is the first writer of schema objects.
            asyncio.run(_ensure_managed_roles(bind, roles_only=True))
            return
        version_exists = asyncio.run(_prepare(bind))
        config = alembic_config()
        if not version_exists:
            command.stamp(config, BASELINE_REVISION)
        asyncio.run(_widen_alembic_version(bind))
        command.upgrade(config, "head")
        asyncio.run(_ensure_tenant_rls(bind))
        asyncio.run(_require_expected_database(bind))
        asyncio.run(_ensure_managed_roles(bind, roles_only=False))
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
