"""Connection-level GUC reset prevents session-level RLS settings surviving checkout."""
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import TenantSession, current_company_id, install_guc_reset

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://business_os_app:business_os_app@postgres:5432/business_os_test",
)


@pytest.mark.asyncio
async def test_session_level_bypass_does_not_survive_checkout():
    eng = create_async_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    install_guc_reset(eng)
    try:
        cid = str(uuid.uuid4())
        async with eng.connect() as conn:
            await conn.execute(text("SELECT set_config('app.rls_bypass', 'on', false)"))
            await conn.execute(
                text("SELECT set_config('app.current_company_id', :cid, false)"),
                {"cid": cid},
            )
            await conn.commit()
            first_pid = await conn.scalar(text("SELECT pg_backend_pid()"))

        async with eng.connect() as conn:
            second_pid = await conn.scalar(text("SELECT pg_backend_pid()"))
            assert second_pid == first_pid
            bypass = await conn.scalar(
                text("SELECT coalesce(current_setting('app.rls_bypass', true), '')")
            )
            company = await conn.scalar(
                text("SELECT coalesce(current_setting('app.current_company_id', true), '')")
            )
            assert bypass == ""
            assert company == ""
    finally:
        await eng.dispose()


@pytest.mark.asyncio
async def test_without_reset_session_level_setting_survives():
    eng = create_async_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    try:
        cid = str(uuid.uuid4())
        async with eng.connect() as conn:
            await conn.execute(text("SELECT set_config('app.rls_bypass', 'on', false)"))
            await conn.execute(
                text("SELECT set_config('app.current_company_id', :cid, false)"),
                {"cid": cid},
            )
            await conn.commit()
            first_pid = await conn.scalar(text("SELECT pg_backend_pid()"))

        async with eng.connect() as conn:
            second_pid = await conn.scalar(text("SELECT pg_backend_pid()"))
            assert second_pid == first_pid
            bypass = await conn.scalar(
                text("SELECT coalesce(current_setting('app.rls_bypass', true), '')")
            )
            company = await conn.scalar(
                text("SELECT coalesce(current_setting('app.current_company_id', true), '')")
            )
            assert bypass == "on"
            assert company == cid
    finally:
        await eng.dispose()


@pytest.mark.asyncio
async def test_after_begin_overrides_session_level_bypass():
    eng = create_async_engine(TEST_DATABASE_URL, pool_size=1, max_overflow=0)
    maker = async_sessionmaker(
        eng,
        class_=AsyncSession,
        expire_on_commit=False,
        sync_session_class=TenantSession,
    )
    try:
        async with eng.connect() as conn:
            await conn.execute(text("SELECT set_config('app.rls_bypass', 'on', false)"))
            await conn.commit()

        current_company_id.set(None)
        async with maker() as session:
            bypass = (
                await session.execute(
                    text("SELECT current_setting('app.rls_bypass', true)")
                )
            ).scalar_one()
            assert bypass == ""
            await session.rollback()
    finally:
        current_company_id.set(None)
        await eng.dispose()
