import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company

OLD_CODES = [
    "warehouse",
    "quality-control",
    "leaves",
    "recruitment",
    "live-chat",
]
TARGET_CODES = ["wms", "quality", "hr", "helpdesk"]
NEW_CODES = ["ecommerce", "contracts", "approvals"]


def load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "157_module_code_renames.py"
    )
    spec = importlib.util.spec_from_file_location(
        "module_code_renames", migration_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_migration_module()


async def ensure_module(db_session: AsyncSession, code: str):
    """Insert an app_modules row for *code* if missing, activate it, and return its id."""
    result = await db_session.execute(
        text("SELECT id, is_active FROM app_modules WHERE code = :code"),
        {"code": code},
    )
    row = result.fetchone()

    if row is None:
        module_id = uuid.uuid4()
        await db_session.execute(
            text(
                """
                INSERT INTO app_modules
                    (id, code, name, description, icon, route, category, is_active, sort_order)
                VALUES
                    (:id, :code, CAST(:code AS varchar), CAST(:code AS text), :icon, :route, :category, true, :sort_order)
                """
            ),
            {
                "id": module_id,
                "code": code,
                "icon": "Puzzle",
                "route": "",
                "category": "test",
                "sort_order": 0,
            },
        )
        await db_session.flush()
        return module_id

    module_id, is_active = row
    if not is_active:
        await db_session.execute(
            text("UPDATE app_modules SET is_active = true WHERE id = :id"),
            {"id": module_id},
        )
        await db_session.flush()
    return module_id


async def ensure_catalog_modules(db_session: AsyncSession):
    """Ensure all old and target catalog modules exist before mapping."""
    for code in OLD_CODES + TARGET_CODES:
        await ensure_module(db_session, code)


async def set_row(
    db_session: AsyncSession,
    company_id,
    code: str,
    enabled: bool,
):
    """Pin the GUC and insert/update a company_modules row for *code*."""
    module_id = await ensure_module(db_session, code)

    await db_session.execute(
        text("SELECT set_config('app.current_company_id', :c, true)"),
        {"c": str(company_id)},
    )

    existing = await db_session.execute(
        text(
            """
            SELECT id
            FROM company_modules
            WHERE company_id = :cid
              AND module_id = :mid
            """
        ),
        {"cid": company_id, "mid": module_id},
    )
    existing_row = existing.fetchone()

    if existing_row is None:
        await db_session.execute(
            text(
                """
                INSERT INTO company_modules (id, company_id, module_id, enabled)
                VALUES (gen_random_uuid(), :cid, :mid, :enabled)
                """
            ),
            {"cid": company_id, "mid": module_id, "enabled": enabled},
        )
    else:
        await db_session.execute(
            text(
                """
                UPDATE company_modules
                SET enabled = :enabled,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": existing_row[0], "enabled": enabled},
        )

    await db_session.flush()


async def get_rows(db_session: AsyncSession, company_id) -> dict[str, bool]:
    """Return a dict {module_code: enabled} for one company."""
    await db_session.execute(
        text("SELECT set_config('app.current_company_id', :c, true)"),
        {"c": str(company_id)},
    )
    result = await db_session.execute(
        text(
            """
            SELECT am.code, cm.enabled
            FROM company_modules cm
            JOIN app_modules am ON am.id = cm.module_id
            WHERE cm.company_id = :cid
            ORDER BY am.code
            """
        ),
        {"cid": company_id},
    )
    return {row[0]: row[1] for row in result.fetchall()}


async def get_app_module_active(db_session: AsyncSession, code: str) -> bool:
    result = await db_session.execute(
        text("SELECT is_active FROM app_modules WHERE code = :code"),
        {"code": code},
    )
    return result.scalar_one()


async def create_company(db_session: AsyncSession, label: str):
    company = Company(
        name=f"Test {label}",
        identification_code=f"test-{uuid.uuid4()}",
        vat_status=False,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def prepare_migration(db_session: AsyncSession):
    conn = await db_session.connection()
    await conn.run_sync(mod.ensure_backup_table)
    await ensure_catalog_modules(db_session)
    return conn


@pytest.mark.asyncio
async def test_as_is_mapping(db_session: AsyncSession):
    conn = await prepare_migration(db_session)

    company_a = await create_company(db_session, "as-is A")
    company_b = await create_company(db_session, "as-is B")

    await set_row(db_session, company_a.id, "leaves", False)
    await set_row(db_session, company_b.id, "warehouse", True)

    await conn.run_sync(mod.map_renamed_codes)

    rows_a = await get_rows(db_session, company_a.id)
    rows_b = await get_rows(db_session, company_b.id)

    assert rows_a.get("hr") is False
    assert rows_b.get("wms") is True


@pytest.mark.asyncio
async def test_and_merge_of_several_old_rows(db_session: AsyncSession):
    conn = await prepare_migration(db_session)

    company_a = await create_company(db_session, "and-merge A")
    company_b = await create_company(db_session, "and-merge B")

    await set_row(db_session, company_a.id, "leaves", True)
    await set_row(db_session, company_a.id, "recruitment", False)

    await set_row(db_session, company_b.id, "leaves", True)
    await set_row(db_session, company_b.id, "recruitment", True)

    await conn.run_sync(mod.map_renamed_codes)

    rows_a = await get_rows(db_session, company_a.id)
    rows_b = await get_rows(db_session, company_b.id)

    assert rows_a.get("hr") is False
    assert rows_b.get("hr") is True


@pytest.mark.asyncio
async def test_and_with_existing_target_never_or(db_session: AsyncSession):
    conn = await prepare_migration(db_session)

    company_a = await create_company(db_session, "existing-target A")
    company_b = await create_company(db_session, "existing-target B")
    company_c = await create_company(db_session, "existing-target C")

    await set_row(db_session, company_a.id, "hr", True)
    await set_row(db_session, company_a.id, "leaves", False)

    await set_row(db_session, company_b.id, "hr", False)
    await set_row(db_session, company_b.id, "leaves", True)

    await set_row(db_session, company_c.id, "hr", True)
    await set_row(db_session, company_c.id, "leaves", True)

    await conn.run_sync(mod.map_renamed_codes)

    rows_a = await get_rows(db_session, company_a.id)
    rows_b = await get_rows(db_session, company_b.id)
    rows_c = await get_rows(db_session, company_c.id)

    assert rows_a.get("hr") is False
    assert rows_b.get("hr") is False
    assert rows_c.get("hr") is True


@pytest.mark.asyncio
async def test_no_auto_enable_for_new_catalog_codes(db_session: AsyncSession):
    conn = await prepare_migration(db_session)

    company = await create_company(db_session, "no-auto-enable")

    await conn.run_sync(mod.map_renamed_codes)

    rows = await get_rows(db_session, company.id)
    assert rows == {}

    await conn.run_sync(mod.insert_new_catalog_codes)

    result = await db_session.execute(
        text("SELECT code, is_active FROM app_modules WHERE code = ANY(:codes)"),
        {"codes": list(NEW_CODES)},
    )
    new_modules = {row[0]: row[1] for row in result.fetchall()}

    assert set(new_modules) == set(NEW_CODES)
    assert all(new_modules.values())

    rows_after_insert = await get_rows(db_session, company.id)
    assert not any(code in NEW_CODES for code in rows_after_insert)


@pytest.mark.asyncio
async def test_idempotency(db_session: AsyncSession):
    conn = await prepare_migration(db_session)

    company_a = await create_company(db_session, "idempotent A")
    company_b = await create_company(db_session, "idempotent B")

    await set_row(db_session, company_a.id, "hr", True)
    await set_row(db_session, company_a.id, "leaves", False)

    await set_row(db_session, company_b.id, "leaves", True)

    await conn.run_sync(mod.map_renamed_codes)
    rows_a_first = await get_rows(db_session, company_a.id)
    rows_b_first = await get_rows(db_session, company_b.id)

    await conn.run_sync(mod.map_renamed_codes)
    rows_a_second = await get_rows(db_session, company_a.id)
    rows_b_second = await get_rows(db_session, company_b.id)

    assert rows_a_first == rows_a_second
    assert rows_b_first == rows_b_second

    assert rows_a_first.get("hr") is False
    assert rows_b_first.get("hr") is True


@pytest.mark.asyncio
async def test_downgrade_restore(db_session: AsyncSession):
    conn = await prepare_migration(db_session)

    company_a = await create_company(db_session, "downgrade A")
    company_b = await create_company(db_session, "downgrade B")

    await set_row(db_session, company_a.id, "hr", True)
    await set_row(db_session, company_a.id, "leaves", False)

    await set_row(db_session, company_b.id, "leaves", True)

    await conn.run_sync(mod.map_renamed_codes)

    assert await get_app_module_active(db_session, "leaves") is False

    rows_a_after_map = await get_rows(db_session, company_a.id)
    rows_b_after_map = await get_rows(db_session, company_b.id)

    assert rows_a_after_map.get("hr") is False
    assert rows_b_after_map.get("hr") is True

    assert rows_a_after_map.get("leaves") is False
    assert rows_b_after_map.get("leaves") is True

    await conn.run_sync(mod.restore_renamed_codes)

    rows_a_restored = await get_rows(db_session, company_a.id)
    rows_b_restored = await get_rows(db_session, company_b.id)

    assert rows_a_restored.get("hr") is True
    assert "hr" not in rows_b_restored

    assert rows_a_restored.get("leaves") is False
    assert rows_b_restored.get("leaves") is True

    assert await get_app_module_active(db_session, "leaves") is True
