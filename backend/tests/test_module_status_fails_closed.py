"""#24 — one definition of "enabled": BASE is always on, a missing row is off.

Before this fix the module status APIs reported a missing `CompanyModule` row as
`enabled=True` (`modules.py:113`, `settings_enhanced.py:73`) while `require_module`
denied non-admins when no enabled row existed. The UI, the settings API and the
guards disagreed, and a freshly registered company appeared to own every paid
module while its employees were locked out of all of them.
"""
import pytest
from sqlalchemy import delete, select

from app.core.modules import BASE_MODULE_CODES
from app.models.module import AppModule, CompanyModule


async def _clear_company_modules(db_session, company_id):
    await db_session.execute(
        delete(CompanyModule).where(CompanyModule.company_id == company_id)
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_company_modules_endpoint_fails_closed_for_missing_rows(
    client, db_session, test_company, auth_headers
):
    """A module with no CompanyModule row must not be reported as enabled."""
    await _clear_company_modules(db_session, test_company.id)

    response = await client.get("/api/v1/modules/company", headers=auth_headers)
    assert response.status_code == 200, response.text

    by_code = {item["module"]["code"]: item["enabled"] for item in response.json()["data"]}
    assert by_code, "expected the catalog to be listed"

    for code, enabled in by_code.items():
        if code in BASE_MODULE_CODES:
            assert enabled is True, f"BASE module {code} must stay enabled"
        else:
            assert enabled is False, f"{code} has no CompanyModule row and must report disabled"


@pytest.mark.asyncio
async def test_settings_modules_endpoint_fails_closed_for_missing_rows(
    client, db_session, test_company, auth_headers
):
    """The settings view must agree with the guard, not assume enabled."""
    await _clear_company_modules(db_session, test_company.id)

    response = await client.get("/api/v1/settings/modules", headers=auth_headers)
    assert response.status_code == 200, response.text

    items = response.json()["data"]
    assert items, "expected the catalog to be listed"

    for item in items:
        if item["code"] in BASE_MODULE_CODES:
            assert item["enabled"] is True, f"BASE module {item['code']} must stay enabled"
        else:
            assert item["enabled"] is False, f"{item['code']} must report disabled"


@pytest.mark.asyncio
async def test_explicitly_enabled_module_is_still_reported_enabled(
    client, db_session, test_company, auth_headers
):
    """Control case: the fix must not break a module that really is enabled."""
    await _clear_company_modules(db_session, test_company.id)

    module_id = (
        await db_session.execute(
            select(AppModule.id).where(
                AppModule.code == "reports", AppModule.is_active.is_(True)
            )
        )
    ).scalar_one()
    db_session.add(
        CompanyModule(company_id=test_company.id, module_id=module_id, enabled=True)
    )
    await db_session.commit()

    response = await client.get("/api/v1/modules/company", headers=auth_headers)
    assert response.status_code == 200, response.text
    by_code = {item["module"]["code"]: item["enabled"] for item in response.json()["data"]}
    assert by_code["reports"] is True
