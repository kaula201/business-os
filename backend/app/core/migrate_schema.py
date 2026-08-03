"""Safely adopt the legacy schema and run versioned Alembic migrations."""
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.database import engine, init_db

BASELINE_REVISION = "001_initial"


async def inspect_schema() -> tuple[bool, bool]:
    async with engine.connect() as connection:
        schema_exists = bool(
            await connection.scalar(text("SELECT to_regclass('public.companies') IS NOT NULL"))
        )
        version_exists = bool(
            await connection.scalar(text("SELECT to_regclass('public.alembic_version') IS NOT NULL"))
        )
    return schema_exists, version_exists


def alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return config


async def prepare_schema() -> bool:
    schema_exists, version_exists = await inspect_schema()
    if not schema_exists:
        # Transitional bootstrap for a fresh database. The resulting schema is
        # immediately adopted at the immutable baseline revision.
        await init_db()
    return version_exists


def main() -> None:
    version_exists = asyncio.run(prepare_schema())
    config = alembic_config()
    if not version_exists:
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
