"""Fix #41 — POST /api/v1/modules/company/{module_id}/toggle requires admin + settings can_edit."""
import pytest
from sqlalchemy import select

from app.models.module import AppModule, CompanyModule, ModulePermission
from app.models.user import User
from app.core.security import hash_password


async def seed_toggle_modules(db_session, company_id):
    """Seed settings module (with can_edit for manager) and a target paid module.

    Tolerant of an already-seeded catalog: conftest's setup_db runs
    ``seed_modules``, so ``settings`` normally exists before this helper. The
    helper only adds what is missing and reuses existing rows, so it stays
    correct whether or not the catalog was seeded.
    """
    existing = {
        module.code: module
        for module in (
            await db_session.execute(
                select(AppModule).where(AppModule.code.in_(["settings", "paid_leave"]))
            )
        ).scalars()
    }

    settings = existing.get("settings")
    if settings is None:
        settings = AppModule(code="settings", name="Settings", category="test", is_active=True)
        db_session.add(settings)
    paid = existing.get("paid_leave")
    if paid is None:
        paid = AppModule(code="paid_leave", name="Paid Leave", category="test", is_active=True)
        db_session.add(paid)
    await db_session.flush()

    for module in (paid, settings):
        row = (
            await db_session.execute(
                select(CompanyModule).where(
                    CompanyModule.company_id == company_id,
                    CompanyModule.module_id == module.id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            db_session.add(
                CompanyModule(company_id=company_id, module_id=module.id, enabled=True)
            )
        else:
            row.enabled = True

    for role in (User.Role.ADMIN, User.Role.MANAGER, User.Role.EMPLOYEE):
        can_edit = role in (User.Role.ADMIN, User.Role.MANAGER)
        perm = (
            await db_session.execute(
                select(ModulePermission).where(
                    ModulePermission.module_id == settings.id,
                    ModulePermission.role == role,
                )
            )
        ).scalar_one_or_none()
        if perm is None:
            db_session.add(
                ModulePermission(
                    module_id=settings.id, role=role, can_access=True, can_edit=can_edit
                )
            )
        else:
            perm.can_access = True
            perm.can_edit = can_edit
    await db_session.commit()
    return paid.id



async def create_headers(client, db_session, company_id, email: str, role: str):
    user = User(
        company_id=company_id,
        email=email,
        hashed_password=hash_password("toggle-test-123"),
        full_name="Toggle Test User",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "toggle-test-123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_employee_cannot_toggle_module(client, db_session, test_company, employee_auth_headers):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    response = await client.post(
        f"/api/v1/modules/company/{module_id}/toggle",
        json={"enabled": False},
        headers=employee_auth_headers,
    )
    assert response.status_code == 403, response.text

    cm = (await db_session.execute(
        select(CompanyModule).where(
            CompanyModule.company_id == test_company.id,
            CompanyModule.module_id == module_id,
        )
    )).scalar_one()
    assert cm.enabled is True


@pytest.mark.asyncio
async def test_manager_cannot_toggle_module_even_with_settings_can_edit(
    client, db_session, test_company
):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    headers = await create_headers(
        client, db_session, test_company.id, "mgr-toggle@test.ge", User.Role.MANAGER
    )
    response = await client.post(
        f"/api/v1/modules/company/{module_id}/toggle",
        json={"enabled": False},
        headers=headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "მხოლოდ ადმინისტრატორს შეუძლია", response.text

    cm = (await db_session.execute(
        select(CompanyModule).where(
            CompanyModule.company_id == test_company.id,
            CompanyModule.module_id == module_id,
        )
    )).scalar_one()
    assert cm.enabled is True


@pytest.mark.asyncio
async def test_admin_can_toggle_module(client, db_session, test_company, auth_headers):
    module_id = await seed_toggle_modules(db_session, test_company.id)
    response = await client.post(
        f"/api/v1/modules/company/{module_id}/toggle",
        json={"enabled": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    cm = (await db_session.execute(
        select(CompanyModule).where(
            CompanyModule.company_id == test_company.id,
            CompanyModule.module_id == module_id,
        )
    )).scalar_one()
    assert cm.enabled is False