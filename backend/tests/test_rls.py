"""RLS (Row-Level Security) verification — tenant isolation at the DB layer.

Proves that once a company is pinned via app.current_company_id, direct SQL
reads cannot see another company's rows — even without any ORM-level company
filter. This is the defense-in-depth guarantee RLS adds on top of the
application-layer scoping already covered by test_tenant_isolation.py.
"""
import pytest
from sqlalchemy import func, select, text

from app.models.client import Client
from tests.conftest import AppSessionLocal
from app.core.database import current_company_id
from app.core.tenant_scope import clear_tenant, pin_tenant, system_scope


@pytest.mark.asyncio
async def test_rls_blocks_cross_company_reads_without_orm_filter(
    db_session, test_company, other_company
):
    # Seed: one client for each company.
    db_session.add_all([
        Client(
            company_id=test_company.id,
            name="RLS Own Client",
            client_type="legal",
            identification_code="RLS-OWN-001",
            status="active",
        ),
        Client(
            company_id=other_company.id,
            name="RLS Other Client",
            client_type="legal",
            identification_code="RLS-OTHER-001",
            status="active",
        ),
    ])
    await db_session.commit()

    # Pin the tenant for this transaction, exactly like get_current_user does.
    # pin_tenant also clears the fixture session's system scope.
    await pin_tenant(db_session, test_company.id)

    # NO company filter — RLS itself must hide the other company's row.
    total = (
        await db_session.execute(select(func.count()).select_from(Client))
    ).scalar_one()
    assert total == 1

    names = (
        await db_session.execute(select(Client.name).order_by(Client.name))
    ).scalars().all()
    assert names == ["RLS Own Client"]


@pytest.mark.asyncio
async def test_rls_without_pin_sees_no_rows(db_session, test_company, other_company):
    db_session.add_all([
        Client(
            company_id=test_company.id,
            name="RLS No Pin A",
            client_type="legal",
            identification_code="RLS-NOPIN-A",
            status="active",
        ),
        Client(
            company_id=other_company.id,
            name="RLS No Pin B",
            client_type="legal",
            identification_code="RLS-NOPIN-B",
            status="active",
        ),
    ])
    await db_session.commit()

    # A brand-new app session with nothing pinned (no setting, no ContextVar).
    current_company_id.set(None)
    async with AppSessionLocal() as session:
        total = (
            await session.execute(select(func.count()).select_from(Client))
        ).scalar_one()
        assert total == 0

    async with AppSessionLocal() as session:
        # Empty-string settings also fail closed.
        await clear_tenant(session)
        total = (
            await session.execute(select(func.count()).select_from(Client))
        ).scalar_one()
        assert total == 0

        # SQL NULL settings fail closed too.
        await session.execute(text("SELECT set_config('app.current_company_id', NULL, true)"))
        await session.execute(text("SELECT set_config('app.rls_bypass', NULL, true)"))
        total = (
            await session.execute(select(func.count()).select_from(Client))
        ).scalar_one()
        assert total == 0

    async with AppSessionLocal() as session:
        await clear_tenant(session)
        session.add(Client(
            company_id=test_company.id,
            name="RLS No Pin Insert",
            client_type="legal",
            identification_code="RLS-NOPIN-INSERT",
            status="active",
        ))
        with pytest.raises(Exception):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_rls_system_scope_sees_all_rows(db_session, test_company, other_company):
    db_session.add_all([
        Client(
            company_id=test_company.id,
            name="RLS System A",
            client_type="legal",
            identification_code="RLS-SYSTEM-A",
            status="active",
        ),
        Client(
            company_id=other_company.id,
            name="RLS System B",
            client_type="legal",
            identification_code="RLS-SYSTEM-B",
            status="active",
        ),
    ])
    await db_session.commit()

    async with AppSessionLocal() as session:
        async with system_scope(session, "test"):
            total = (
                await session.execute(select(func.count()).select_from(Client))
            ).scalar_one()
            assert total == 2


@pytest.mark.asyncio
async def test_rls_resets_between_transactions(db_session, test_company, other_company):
    db_session.add(Client(
        company_id=other_company.id,
        name="RLS Reset Other",
        client_type="legal",
        identification_code="RLS-RESET-001",
        status="active",
    ))
    await db_session.commit()

    async with AppSessionLocal() as session:
        # Pin to company A: sees none of B's rows.
        await pin_tenant(session, test_company.id)
        total = (
            await session.execute(select(func.count()).select_from(Client))
        ).scalar_one()
        assert total == 0

        # Pin to company B: sees its own row.
        await pin_tenant(session, other_company.id)
        total = (
            await session.execute(select(func.count()).select_from(Client))
        ).scalar_one()
        assert total == 1

        # Commit ends the transaction-local scope.
        await session.commit()

    # Next transaction starts unpinned and sees zero rows.
    async with AppSessionLocal() as session:
        await clear_tenant(session)
        total = (
            await session.execute(select(func.count()).select_from(Client))
        ).scalar_one()
        assert total == 0


@pytest.mark.asyncio
async def test_rls_pin_survives_commit_but_system_scope_does_not(
    db_session, test_company, other_company
):
    """Request sessions re-pin the request's tenant after commit; bypass is never re-applied."""
    db_session.add_all([
        Client(company_id=test_company.id, name="RLS Repin A", client_type="legal",
               identification_code="RLS-REPIN-A", status="active"),
        Client(company_id=other_company.id, name="RLS Repin B", client_type="legal",
               identification_code="RLS-REPIN-B", status="active"),
    ])
    await db_session.commit()

    async with AppSessionLocal() as session:
        await pin_tenant(session, test_company.id)
        async with system_scope(session, "test"):
            assert (await session.execute(select(func.count()).select_from(Client))).scalar_one() == 2
            await session.commit()
            # New transaction: re-pinned to A, system scope gone.
            names = (await session.execute(select(Client.name))).scalars().all()
            assert names == ["RLS Repin A"]
    current_company_id.set(None)
