from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 — register every ORM table in Base.metadata
from app.core.config import settings
from app.core.database import Base
from app.core.duplicate_ddl import escape_alembic_config_value, install_duplicate_ddl_guard
from app.core.secret_redaction import hides_password, install_log_redaction, public_migration_error

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
# Migrations use the superuser URL when MIGRATION_DATABASE_URL is set.
# %% keeps a literal % in the password (ConfigParser interpolation).
config.set_main_option(
    "sqlalchemy.url",
    escape_alembic_config_value(settings.migration_database_url()),
)


def sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg", "postgresql+psycopg2")


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url(config.get_main_option("sqlalchemy.url")),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Fresh boots create_all the current models, then replay revisions whose
    # tables and columns are already present. Duplicate DDL is skipped;
    # every other error still aborts. Existing databases are not stamped at
    # head, so revisions they have not applied still run.
    install_duplicate_ddl_guard()
    url = sync_url(config.get_main_option("sqlalchemy.url"))
    install_log_redaction(url)
    engine = create_engine(url, poolclass=pool.NullPool, echo=False)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                transaction_per_migration=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    except Exception as exc:
        if hides_password(exc, url):
            raise public_migration_error(exc, url) from None
        raise
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
