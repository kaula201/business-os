"""Bulk export authorization — regression tests for the #40 CI failure.

`GET /api/v1/export/*` streams whole datasets as XLSX, including client
identification codes. A plain module read (`reports.can_access`) is not enough:
employees and accountants must be denied, admins and managers allowed.

Context: PR #40 made `require_module` treat modules missing a `CompanyModule`
row as disabled while conftest seeds the whole catalog as enabled, so the
employee export test flipped from 403 to 200. Both behaviours are asserted here
so this cannot regress silently again.
"""
import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.user import User


EXPORT_PATHS = [
    "/api/v1/export/clients",
    "/api/v1/export/products",
    "/api/v1/export/orders",
    "/api/v1/export/tasks",
]


async def _login_headers(client, db_session, company_id, email: str, role):
    user = User(
        company_id=company_id,
        email=email,
        hashed_password=hash_password("export-test-123"),
        full_name="Export Test User",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "export-test-123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", EXPORT_PATHS)
async def test_employee_cannot_export_any_dataset(client, employee_auth_headers, path):
    response = await client.get(path, headers=employee_auth_headers)
    assert response.status_code == 403, f"{path} -> {response.status_code}"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", EXPORT_PATHS)
async def test_accountant_cannot_export_any_dataset(client, db_session, test_company, path):
    headers = await _login_headers(
        client, db_session, test_company.id, "accountant-export@test.ge", User.Role.ACCOUNTANT
    )
    response = await client.get(path, headers=headers)
    assert response.status_code == 403, f"{path} -> {response.status_code}"


@pytest.mark.asyncio
async def test_manager_can_export_clients(client, db_session, test_company):
    headers = await _login_headers(
        client, db_session, test_company.id, "manager-export@test.ge", User.Role.MANAGER
    )
    response = await client.get("/api/v1/export/clients", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.asyncio
async def test_admin_can_export_clients(client, auth_headers):
    response = await client.get("/api/v1/export/clients", headers=auth_headers)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_export_denied_when_reports_module_disabled(client, db_session, test_company):
    """Module guard still applies: disabling `reports` denies even a manager."""
    from app.models.module import AppModule, CompanyModule

    module_id = (
        await db_session.execute(select(AppModule.id).where(AppModule.code == "reports"))
    ).scalar_one()
    row = (
        await db_session.execute(
            select(CompanyModule).where(
                CompanyModule.company_id == test_company.id,
                CompanyModule.module_id == module_id,
            )
        )
    ).scalar_one()
    row.enabled = False
    await db_session.commit()

    headers = await _login_headers(
        client, db_session, test_company.id, "manager-noreports@test.ge", User.Role.MANAGER
    )
    response = await client.get("/api/v1/export/clients", headers=headers)
    assert response.status_code == 403, f"expected 403, got {response.status_code}"
