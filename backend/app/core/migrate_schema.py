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


async def _ensure_app_grants(bind) -> None:
    """Give business_os_app access to objects the superuser created.

    ``GRANT ALL ON ALL TABLES`` does not include materialized views.
    ``ALTER DEFAULT PRIVILEGES`` covers tables and sequences created later
    by ``business_os`` (future migrations). Skipped when this connection is
    not a superuser, so local dev keeps using DATABASE_URL unchanged.
    """
    async with bind.connect() as connection:
        is_super = bool(
            await connection.scalar(
                text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
            )
        )
        role_exists = bool(
            await connection.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname = 'business_os_app'")
            )
        )
    if not is_super or not role_exists:
        return
    async with bind.begin() as connection:
        await connection.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO business_os_app"))
        await connection.execute(
            text("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO business_os_app")
        )
        await connection.execute(
            text(
                """
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
                        EXECUTE format(
                            'GRANT SELECT ON TABLE %I TO business_os_app',
                            mv
                        );
                    END LOOP;
                END
                $$;
                """
            )
        )
        await connection.execute(
            text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
                "GRANT ALL ON TABLES TO business_os_app"
            )
        )
        await connection.execute(
            text(
                "ALTER DEFAULT PRIVILEGES FOR ROLE business_os IN SCHEMA public "
                "GRANT ALL ON SEQUENCES TO business_os_app"
            )
        )


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
    bind = create_async_engine(settings.migration_database_url(), poolclass=NullPool)
    try:
        version_exists = asyncio.run(_prepare(bind))
        config = alembic_config()
        if not version_exists:
            command.stamp(config, BASELINE_REVISION)
        asyncio.run(_widen_alembic_version(bind))
        command.upgrade(config, "head")
        asyncio.run(_ensure_app_grants(bind))
    finally:
        asyncio.run(bind.dispose())


if __name__ == "__main__":
    main()
