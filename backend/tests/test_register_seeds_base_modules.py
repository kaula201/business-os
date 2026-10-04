"""#24 item 1 — a newly registered company gets its BASE entitlements.

`POST /auth/register` created a company with no `company_modules` rows at all.
While the status APIs treated a missing row as enabled that looked harmless;
once a missing row correctly means disabled (#24), a fresh company would have
zero entitlements and even its own admin would hit fail-closed paths. Register
must therefore seed the BASE rows explicitly.
"""
import uuid

import pytest
from sqlalchemy import select

from app.core.modules import BASE_MODULE_CODES
from app.models.company import Company
from app.models.module import AppModule, CompanyModule
from app.models.user import User


def _register_payload():
    suffix = uuid.uuid4().hex[:8]
    return {
        "email": f"reg-{suffix}@test.ge",
        "password": "register-test-123",
        "full_name": "Registered Admin",
        "company_name": f"Registered Co {suffix}",
        "is_vat_payer": False,
    }


@pytest.mark.asyncio
async def test_register_seeds_base_company_modules(client, db_session):
    payload = _register_payload()
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text

    admin = (
        await db_session.execute(select(User).where(User.email == payload["email"]))
    ).scalar_one_or_none()
    assert admin is not None, "registration should create the admin user"

    rows = (
        await db_session.execute(
            select(AppModule.code, CompanyModule.enabled)
            .join(CompanyModule, CompanyModule.module_id == AppModule.id)
            .where(CompanyModule.company_id == admin.company_id)
        )
    ).all()
    by_code = {code: enabled for code, enabled in rows}

    assert set(by_code) == set(BASE_MODULE_CODES), (
        "register must seed exactly the BASE modules, got: "
        f"{sorted(by_code)} vs expected {sorted(BASE_MODULE_CODES)}"
    )
    assert all(by_code.values()), "seeded BASE modules must be enabled"


@pytest.mark.asyncio
async def test_register_does_not_enable_paid_modules(client, db_session):
    payload = _register_payload()
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text

    admin = (
        await db_session.execute(select(User).where(User.email == payload["email"]))
    ).scalar_one()
    enabled_codes = set(
        (
            await db_session.execute(
                select(AppModule.code)
                .join(CompanyModule, CompanyModule.module_id == AppModule.id)
                .where(
                    CompanyModule.company_id == admin.company_id,
                    CompanyModule.enabled.is_(True),
                )
            )
        ).scalars()
    )
    assert enabled_codes == set(BASE_MODULE_CODES), (
        f"a new company must own BASE only, but enabled: {sorted(enabled_codes)}"
    )


@pytest.mark.asyncio
async def test_seed_base_company_modules_is_idempotent(db_session):
    """Calling the helper twice must not duplicate rows or re-enable anything.

    Uses a standalone company rather than `test_company`, because the harness
    fixture enables the whole catalog for its tenant.
    """
    from app.core.modules import seed_base_company_modules

    company = Company(
        name=f"Idem {uuid.uuid4().hex[:6]}",
        identification_code=f"IDEM-{uuid.uuid4().hex[:8].upper()}",
        vat_status=False,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)

    first = await seed_base_company_modules(db_session, company.id)
    await db_session.commit()
    assert first == len(BASE_MODULE_CODES)

    second = await seed_base_company_modules(db_session, company.id)
    await db_session.commit()
    assert second == 0, "second call must insert nothing"

    rows = (
        await db_session.execute(
            select(CompanyModule).where(CompanyModule.company_id == company.id)
        )
    ).scalars().all()
    assert len(rows) == len(BASE_MODULE_CODES)

    # An operator disabling a BASE row is preserved on the next call.
    rows[0].enabled = False
    await db_session.commit()
    await seed_base_company_modules(db_session, company.id)
    await db_session.commit()
    await db_session.refresh(rows[0])
    assert rows[0].enabled is False, "the helper must not overwrite an explicit disable"
