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
    finally:
        asyncio.run(bind.dispose())
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
