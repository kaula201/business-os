"""#24 / REQ-PKG: a newly registered company owns BASE only.

Each paid module is sold separately, so after POST /auth/register every role,
admin included, must get 403 on paid-module routes until the module is bought.
"""
import uuid
import pytest
from app.core.security import create_access_token
from app.models.user import User
from app.core.modules import BASE_MODULE_CODES

PAID_ROUTES = [
    # SAL: /orders/analytics would be the natural pick, but /orders/{order_id}
    # shadows it (422), so the SAL invoice list is used instead.
    ("invoices", "/api/v1/invoices/"),
    ("helpdesk", "/api/v1/helpdesk/"),
    ("accounting-controls", "/api/v1/accounting-controls/fiscal-positions"),  # FIN
    ("inventory", "/api/v1/wms/batches"),
    ("gl", "/api/v1/gl/analytics"),
]


async def _register_user(client, email, password, full_name, company_name):
    """Helper to register a new user and return token, user_id, company_id."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "company_name": company_name,
            "is_vat_payer": False,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    return data["access_token"], data["user"]["id"], data["user"]["company_id"]


async def _invite_user(client, admin_token, email, full_name, role):
    """Invite a user with the given role and return the invited user's id."""
    resp = await client.post(
        "/api/v1/users/invite",
        json={"email": email, "full_name": full_name, "role": role},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _role_values():
    """Return list of role values from User.Role.CHOICES."""
    return [choice[0] if isinstance(choice, tuple) else choice for choice in User.Role.CHOICES]


@pytest.mark.asyncio
async def test_registered_company_has_only_base_enabled(client):
    """Issue #24 / REQ-PKG: a fresh company should have only the base modules enabled."""
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_{suffix}@test.ge"
    company_name = f"Company {suffix}"
    token, _, _ = await _register_user(client, email, "password123", "Admin", company_name)

    resp = await client.get(
        "/api/v1/modules/company",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    if isinstance(data, dict) and "modules" in data:
        modules = data["modules"]
    else:
        modules = data
    enabled_codes = {m["module"]["code"] for m in modules if m.get("enabled")}
    assert enabled_codes == set(BASE_MODULE_CODES)


@pytest.mark.asyncio
async def test_every_role_gets_403_on_paid_routes(client):
    """Every role (including admin) should get 403 on paid module routes until purchased."""
    suffix = uuid.uuid4().hex[:8]
    admin_email = f"admin_{suffix}@test.ge"
    company_name = f"Company {suffix}"
    admin_token, admin_user_id, company_id = await _register_user(
        client, admin_email, "password123", "Admin", company_name
    )

    # Store tokens for all roles; start with admin
    role_tokens = {"admin": admin_token}
    all_roles = _role_values()
    non_admin_roles = [r for r in all_roles if r != "admin"]

    # Invite each non-admin role and mint tokens
    for role in non_admin_roles:
        invite_suffix = uuid.uuid4().hex[:6]
        invited_email = f"{role}_{invite_suffix}@test.ge"
        invited_full_name = f"{role.capitalize()} User"
        invited_id = await _invite_user(
            client, admin_token, invited_email, invited_full_name, role
        )
        token = create_access_token(
            {"sub": invited_id, "company_id": company_id, "role": role}
        )
        role_tokens[role] = token

    # Ensure we have tokens for all roles
    assert set(role_tokens.keys()) == set(all_roles)

    failures = []
    for role, token in role_tokens.items():
        for module_code, route in PAID_ROUTES:
            resp = await client.get(
                route,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 403:
                failures.append(
                    f"Role={role}, Route={route} -> status={resp.status_code}, "
                    f"body={resp.text[:200]}"
                )

    assert not failures, "Some paid routes did not return 403:\n" + "\n".join(failures)


@pytest.mark.asyncio
async def test_base_route_still_allowed_for_admin(client):
    """Base module route (e.g., clients) should remain accessible to the registered admin."""
    suffix = uuid.uuid4().hex[:8]
    email = f"admin_{suffix}@test.ge"
    company_name = f"Company {suffix}"
    token, _, _ = await _register_user(client, email, "password123", "Admin", company_name)

    resp = await client.get(
        "/api/v1/clients/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_inactive_paid_module_is_403_for_admin(client):
    """An inactive (is_active=false) registered module is closed for every role,
    admin included; the admin pass-through only covers codes absent from the catalog."""
    import os
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    suffix = uuid.uuid4().hex[:8]
    token, _, _ = await _register_user(
        client, f"admin_{suffix}@test.ge", "password123", "Admin", f"Company {suffix}"
    )
    hdr = {"Authorization": f"Bearer {token}"}
    engine = create_async_engine(os.environ["TEST_SUPERUSER_DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            helpdesk_id = (await conn.execute(
                text("SELECT id FROM app_modules WHERE code = 'helpdesk'")
            )).scalar_one()
        r = await client.post(
            f"/api/v1/modules/company/{helpdesk_id}/toggle", json={"enabled": True}, headers=hdr
        )
        assert r.status_code == 200, r.text
        assert (await client.get("/api/v1/helpdesk/", headers=hdr)).status_code == 200

        async with engine.begin() as conn:
            await conn.execute(text("UPDATE app_modules SET is_active = false WHERE code = 'helpdesk'"))
        r = await client.get("/api/v1/helpdesk/", headers=hdr)
        assert r.status_code == 403, r.text
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE app_modules SET is_active = true WHERE code = 'helpdesk'"))
        await engine.dispose()
