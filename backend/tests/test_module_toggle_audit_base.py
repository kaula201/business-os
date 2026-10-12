"""#41: audit and base-module protections across both toggle paths."""
import pytest
from sqlalchemy import select

from tests.test_module_toggle_auth import seed_toggle_modules
from app.models.module import AppModule, CompanyModule
from app.models.audit import AuditLog


async def _post_toggle(client, path, module_id, enabled, headers):
    if path == "/api/v1/settings/modules/toggle":
        payload = {"module_id": str(module_id), "enabled": enabled}
    else:
        payload = {"enabled": enabled}

    url = path.format(module_id=module_id)
    return await client.post(url, json=payload, headers=headers)


async def _audit_rows(db_session, company_id, module_id, action=None):
    """Return audit rows for a company-module pair, optionally filtered by action."""
    db_session.expire_all()
    stmt = select(AuditLog).where(
        AuditLog.company_id == company_id,
        AuditLog.entity_id == module_id,
        AuditLog.entity_type == "company_module",
    )
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)

    result = await db_session.execute(stmt)
    return result.scalars().all()


async def _enabled_value(db_session, company_id, module_id):
    """Return current enabled flag for a company-module pair, or None if no row."""
    db_session.expire_all()
    result = await db_session.execute(
        select(CompanyModule.enabled).where(
            CompanyModule.company_id == company_id,
            CompanyModule.module_id == module_id,
        )
    )
    return result.scalar_one_or_none()


async def _ensure_base_module(db_session, code):
    """Get or create an active base AppModule by code; return its id."""
    result = await db_session.execute(select(AppModule).where(AppModule.code == code))
    mod = result.scalar_one_or_none()

    if mod is None:
        mod = AppModule(code=code, name=code.capitalize(), category="base", is_active=True)
        db_session.add(mod)
        await db_session.commit()
        await db_session.refresh(mod)
    mod_id = mod.id
    if not mod.is_active:
        mod.is_active = True
        await db_session.commit()

    # Return the id only: the instance is expired after commit and a later
    # attribute access would lazy-load outside the async context.
    return mod_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/modules/company/{module_id}/toggle",
        "/api/v1/settings/modules/toggle",
    ],
)
async def test_paid_module_toggle_writes_audit_logs(
    client, db_session, test_company, auth_headers, path
):
    module_id = await seed_toggle_modules(db_session, test_company.id)

    resp = await _post_toggle(client, path, module_id, False, auth_headers)
    assert resp.status_code == 200

    disabled_rows = await _audit_rows(
        db_session, test_company.id, module_id, "module.disabled"
    )
    assert len(disabled_rows) == 1
    row = disabled_rows[0]
    assert row.company_id == test_company.id
    assert row.entity_id == module_id
    assert row.old_value == "true"
    assert row.new_value == "false"
    assert await _enabled_value(db_session, test_company.id, module_id) is False

    resp = await _post_toggle(client, path, module_id, True, auth_headers)
    assert resp.status_code == 200

    enabled_rows = await _audit_rows(
        db_session, test_company.id, module_id, "module.enabled"
    )
    assert len(enabled_rows) == 1
    row = enabled_rows[0]
    assert row.old_value == "false"
    assert row.new_value == "true"
    assert await _enabled_value(db_session, test_company.id, module_id) is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/modules/company/{module_id}/toggle",
        "/api/v1/settings/modules/toggle",
    ],
)
@pytest.mark.parametrize("code", ["settings", "clients"])
async def test_base_module_disable_rejected_without_audit(
    client, db_session, test_company, auth_headers, path, code
):
    await seed_toggle_modules(db_session, test_company.id)
    mod_id = await _ensure_base_module(db_session, code)

    resp = await _post_toggle(client, path, mod_id, False, auth_headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "საბაზო მოდულის გამორთვა შეუძლებელია"

    audit_rows = await _audit_rows(db_session, test_company.id, mod_id)
    assert audit_rows == []

    enabled = await _enabled_value(db_session, test_company.id, mod_id)
    if enabled is not None:
        assert enabled is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/modules/company/{module_id}/toggle",
        "/api/v1/settings/modules/toggle",
    ],
)
@pytest.mark.parametrize("code", ["settings", "clients"])
async def test_base_module_enable_succeeds(
    client, db_session, test_company, auth_headers, path, code
):
    await seed_toggle_modules(db_session, test_company.id)
    mod_id = await _ensure_base_module(db_session, code)

    resp = await _post_toggle(client, path, mod_id, True, auth_headers)
    assert resp.status_code == 200
    assert await _enabled_value(db_session, test_company.id, mod_id) is True

    enabled_rows = await _audit_rows(
        db_session, test_company.id, mod_id, "module.enabled"
    )
    assert len(enabled_rows) == 1
    assert enabled_rows[0].new_value == "true"
