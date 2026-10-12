"""#41: both toggle paths share one guard; API keys may never toggle."""
import pytest
from sqlalchemy import select
from tests.test_module_toggle_auth import seed_toggle_modules, create_headers
from app.models.module import AppModule, CompanyModule
from app.models.platform import CustomRole
from app.models.user import User


async def _enabled(db_session, company_id, module_id):
    """Return current enabled flag for a company-module pair."""
    db_session.expire_all()
    result = await db_session.execute(
        select(CompanyModule.enabled).where(
            CompanyModule.company_id == company_id,
            CompanyModule.module_id == module_id
        )
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_manager_with_settings_can_edit_gets_403_on_settings_path(
    client, db_session, test_company
):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    headers = await create_headers(
        client, db_session, test_company.id, "mgr-settings@test.ge", "manager"
    )
    resp = await client.post(
        "/api/v1/settings/modules/toggle",
        json={"module_id": str(module_id), "enabled": False},
        headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "მხოლოდ ადმინისტრატორს შეუძლია"
    assert await _enabled(db_session, test_company.id, module_id) is True


@pytest.mark.asyncio
async def test_employee_gets_403_on_settings_path(
    client, db_session, test_company, employee_auth_headers
):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    resp = await client.post(
        "/api/v1/settings/modules/toggle",
        json={"module_id": str(module_id), "enabled": False},
        headers=employee_auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_toggle_via_settings_path(
    client, db_session, test_company, auth_headers
):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    resp = await client.post(
        "/api/v1/settings/modules/toggle",
        json={"module_id": str(module_id), "enabled": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert await _enabled(db_session, test_company.id, module_id) is False


@pytest.mark.asyncio
async def test_inactive_module_403_on_both_paths(
    client, db_session, test_company, auth_headers
):
    inactive_mod = AppModule(
        code="inactive_mod_x",
        name="Inactive",
        category="test",
        is_active=False,
    )
    db_session.add(inactive_mod)
    await db_session.commit()
    await db_session.refresh(inactive_mod)

    # Path A: /company/{module_id}/toggle
    resp_a = await client.post(
        f"/api/v1/modules/company/{inactive_mod.id}/toggle",
        json={"enabled": False},
        headers=auth_headers,
    )
    assert resp_a.status_code == 403

    # Path B: /settings/modules/toggle
    resp_b = await client.post(
        "/api/v1/settings/modules/toggle",
        json={"module_id": str(inactive_mod.id), "enabled": False},
        headers=auth_headers,
    )
    assert resp_b.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("scopes", ["*", "settings"])
async def test_api_key_forbidden_on_both_paths(
    client, db_session, test_company, auth_headers, scopes
):
    module_id = await seed_toggle_modules(db_session, test_company.id)

    # create API key as admin
    create_key_resp = await client.post(
        "/api/v1/api-keys/",
        json={"name": f"k-{scopes}", "scopes": scopes, "ttl_days": 30},
        headers=auth_headers,
    )
    assert create_key_resp.status_code == 201
    api_key = create_key_resp.json()["data"]["key"]

    # Path A with X-API-Key
    resp_a = await client.post(
        f"/api/v1/modules/company/{module_id}/toggle",
        json={"enabled": False},
        headers={"X-API-Key": api_key},
    )
    assert resp_a.status_code == 403

    # Path B with X-API-Key
    resp_b = await client.post(
        "/api/v1/settings/modules/toggle",
        json={"module_id": str(module_id), "enabled": False},
        headers={"X-API-Key": api_key},
    )
    assert resp_b.status_code == 403

    # Row remains enabled
    assert await _enabled(db_session, test_company.id, module_id) is True


@pytest.mark.asyncio
async def test_api_key_with_bearer_still_forbidden(
    client, db_session, test_company, auth_headers
):
    module_id = await seed_toggle_modules(db_session, test_company.id)

    create_key_resp = await client.post(
        "/api/v1/api-keys/",
        json={"name": "k-star", "scopes": "*", "ttl_days": 30},
        headers=auth_headers,
    )
    assert create_key_resp.status_code == 201
    api_key = create_key_resp.json()["data"]["key"]

    # Combine admin Bearer token and X-API-Key
    headers = {
        "Authorization": auth_headers["Authorization"],
        "X-API-Key": api_key,
    }
    resp = await client.post(
        f"/api/v1/modules/company/{module_id}/toggle",
        json={"enabled": False},
        headers=headers,
    )
    assert resp.status_code == 403


async def _assert_403_on_both_paths(client, db_session, company_id, module_id, headers):
    resp_a = await client.post(
        f"/api/v1/modules/company/{module_id}/toggle",
        json={"enabled": False},
        headers=headers,
    )
    assert resp_a.status_code == 403, resp_a.text
    resp_b = await client.post(
        "/api/v1/settings/modules/toggle",
        json={"module_id": str(module_id), "enabled": False},
        headers=headers,
    )
    assert resp_b.status_code == 403, resp_b.text
    assert await _enabled(db_session, company_id, module_id) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["manager", "driver", "employee", "accountant"])
async def test_non_admin_roles_403_on_both_paths(client, db_session, test_company, role):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    headers = await create_headers(
        client, db_session, test_company.id, f"{role}-both@test.ge", role
    )
    await _assert_403_on_both_paths(client, db_session, test_company.id, module_id, headers)


@pytest.mark.asyncio
async def test_custom_role_with_settings_can_edit_403_on_both_paths(
    client, db_session, test_company
):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    custom = CustomRole(
        company_id=test_company.id,
        name="Settings editor",
        permissions={"settings": {"can_access": True, "can_create": True, "can_edit": True, "can_delete": True}},
    )
    db_session.add(custom)
    await db_session.commit()
    headers = await create_headers(
        client, db_session, test_company.id, "custom-settings@test.ge", "manager"
    )
    user = (await db_session.execute(
        select(User).where(User.email == "custom-settings@test.ge")
    )).scalar_one()
    user.custom_role_id = custom.id
    await db_session.commit()
    await _assert_403_on_both_paths(client, db_session, test_company.id, module_id, headers)
