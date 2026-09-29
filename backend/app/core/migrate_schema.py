"""Safely adopt the legacy schema and run versioned Alembic migrations."""
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

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
        # Transitional bootstrap for a fresh database. The resulting schema is
        # immediately adopted at the immutable baseline revision.
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


async def _widen_alembic_version(bind) -> None:
    """Revision ids are longer than Alembic's default varchar(32).

    ``122_pos_restaurant_courses_floorplan`` cannot be stored until the
    version column is widened. Do this outside the migration transaction:
    the UPDATE that records the new revision is what overflows.
    """
    async with bind.begin() as connection:
        exists = await connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
        if not exists:
            return
        await connection.execute(
            text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)")
        )


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
        asyncio.run(_ensure_managed_roles(bind))
    except Exception as exc:
        if hides_password(exc, url):
            raise public_migration_error(exc, url) from None
        raise
    finally:
        asyncio.run(bind.dispose())


if __name__ == "__main__":
    main()
