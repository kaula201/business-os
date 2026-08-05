# backend/app/core/database.py
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.core.config import settings

# Current tenant (company) for this request — consumed by get_db to set the
# PostgreSQL Row-Level Security session variable.
current_company_id: ContextVar[UUID | None] = ContextVar(
    "current_company_id", default=None
)


def _create_engine_kwargs():
    url = settings.DATABASE_URL
    kwargs = {"echo": settings.DATABASE_ECHO}
    if url.startswith("sqlite"):
        # SQLite (local tests) cannot pool across threads.
        from sqlalchemy.pool import NullPool
        kwargs["poolclass"] = NullPool
    else:
        # asyncpg default pool is a QueuePool — tune it for 20-30 concurrent
        # users with bursts on financial reports / exports.
        kwargs["pool_size"] = settings.DB_POOL_SIZE
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
        kwargs["pool_pre_ping"] = True
    return kwargs


engine = create_async_engine(settings.DATABASE_URL, **_create_engine_kwargs())
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    # Import all model modules before create_all so a fresh database gets every table.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)