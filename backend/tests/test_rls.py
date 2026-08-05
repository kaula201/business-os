"""RLS (Row-Level Security) verification — tenant isolation at the DB layer.

Proves that once a company is pinned via app.current_company_id, direct SQL
reads cannot see another company's rows — even without any ORM-level company
filter. This is the defense-in-depth guarantee RLS adds on top of the
application-layer scoping already covered by test_tenant_isolation.py.
"""
import pytest
from sqlalchemy import func, select, text

from app.models.client import Client


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
    await db_session.execute(
        text("SELECT set_config('app.current_company_id', :cid, true)"),
        {"cid": str(test_company.id)},
    )

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
async def test_rls_without_pin_sees_all_rows_for_tooling(
    db_session, test_company, other_company
):
    db_session.add_all([
        Client(
            company_id=test_company.id,
            name="RLS Tooling A",
            client_type="legal",
            identification_code="RLS-TOOL-A",
            status="active",
        ),
        Client(
            company_id=other_company.id,
            name="RLS Tooling B",
            client_type="legal",
            identification_code="RLS-TOOL-B",
            status="active",
        ),
    ])
    await db_session.commit()

    # No pin → migrations/seeds/admin tooling keep full visibility.
    await db_session.execute(
        text("SELECT set_config('app.current_company_id', NULL, true)")
    )
    total = (
        await db_session.execute(select(func.count()).select_from(Client))
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

    # Pin in one transaction...
    await db_session.execute(
        text("SELECT set_config('app.current_company_id', :cid, true)"),
        {"cid": str(test_company.id)},
    )
    # ...commit ends the local scope...
    await db_session.commit()
    # ...next transaction starts unpinned → full visibility restored.
    total = (
        await db_session.execute(select(func.count()).select_from(Client))
    ).scalar_one()
    assert total == 1
