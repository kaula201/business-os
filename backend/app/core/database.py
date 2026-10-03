# backend/app/core/database.py
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Session
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


class TenantSession(Session):
    """Sync session class behind every application AsyncSession.

    RLS fails closed (#7): ``app.current_company_id`` is transaction-local, so
    a ``commit()`` in the middle of a request would otherwise leave the next
    transaction unpinned (zero rows). After every BEGIN the tenant pinned for
    this request/task (the ``current_company_id`` ContextVar, set only by
    ``app.core.tenant_scope.pin_tenant``) is applied again. ``app.rls_bypass``
    is never re-applied: a system scope ends at commit.
    """


@event.listens_for(TenantSession, "after_begin")
def _repin_tenant(session, transaction, connection) -> None:
    company_id = current_company_id.get()
    if company_id is not None:
        connection.execute(
            text("SELECT set_config('app.current_company_id', :cid, true)"),
            {"cid": str(company_id)},
        )


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    sync_session_class=TenantSession,
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


async def init_db(bind=None):
    # Import all model modules before create_all so a fresh database gets every table.
    import app.models  # noqa: F401

    target = bind or engine
    async with target.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)