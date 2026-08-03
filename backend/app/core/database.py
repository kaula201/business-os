# backend/app/core/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings


def _create_engine_kwargs():
    url = settings.DATABASE_URL
    kwargs = {"echo": settings.DEBUG}
    if not url.startswith("sqlite"):
        kwargs["poolclass"] = NullPool
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