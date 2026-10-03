# backend/app/core/database.py
import logging
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy.exc import DisconnectionError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy import text
from app.core.config import settings

logger = logging.getLogger(__name__)

# Current tenant (company) for this request — consumed by get_db to set the
# PostgreSQL Row-Level Security session variable.
current_company_id: ContextVar[UUID | None] = ContextVar(
    "current_company_id", default=None
)

# Current HTTP route for audit logging (non-HTTP callers see None).
current_route: ContextVar[str | None] = ContextVar("current_route", default=None)


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


def install_guc_reset(engine) -> None:
    """Reset tenant RLS GUCs whenever a pooled connection is checked out/in.

    A pooled connection must never carry a session-level
    ``app.rls_bypass`` or ``app.current_company_id`` into the next checkout.
    The asyncpg adapter opens an implicit transaction, so a bare RESET would
    be rolled back when that transaction closes; the explicit commit makes
    the reset durable on the connection.

    checkout resets fail closed: if the reset cannot be performed the
    connection is discarded and the pool retries with a fresh one. checkin
    is best-effort (checkout reset still protects the next user) and skips
    connections the pool has already invalidated.
    """
    sync_engine = getattr(engine, "sync_engine", engine)
    if sync_engine.dialect.name != "postgresql":
        return

    def _reset(dbapi_connection) -> None:
        cur = dbapi_connection.cursor()
        cur.execute("RESET app.rls_bypass")
        cur.execute("RESET app.current_company_id")
        cur.close()
        dbapi_connection.commit()

    def _checkout(dbapi_connection, connection_record, connection_proxy):
        try:
            _reset(dbapi_connection)
        except Exception as exc:
            raise DisconnectionError(
                "Could not reset RLS GUCs on checkout; discarding pooled connection"
            ) from exc

    def _checkin(dbapi_connection, connection_record):
        if dbapi_connection is None:
            return
        try:
            _reset(dbapi_connection)
        except Exception:
            logger.warning("Could not reset RLS GUCs on checkin", exc_info=True)

    event.listen(sync_engine, "checkout", _checkout)
    event.listen(sync_engine, "checkin", _checkin)


engine = create_async_engine(settings.DATABASE_URL, **_create_engine_kwargs())
install_guc_reset(engine)


class TenantSession(Session):
    """Sync session class behind every application AsyncSession.

    RLS fails closed (#7): ``app.current_company_id`` is transaction-local, so
    a ``commit()`` in the middle of a request would otherwise leave the next
    transaction unpinned (zero rows). After every BEGIN the tenant pinned for
    this request/task (the ``current_company_id`` ContextVar, set only by
    ``app.core.tenant_scope.pin_tenant``) is applied again. ``app.rls_bypass``
    is always cleared locally, never re-applied: a system scope ends at commit.
    """


@event.listens_for(TenantSession, "after_begin")
def _repin_tenant(session, transaction, connection) -> None:
    company_id = current_company_id.get()
    cid = str(company_id) if company_id is not None else ""
    connection.execute(
        text(
            "SELECT set_config('app.rls_bypass', '', true), "
            "set_config('app.current_company_id', :cid, true)"
        ),
        {"cid": cid},
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