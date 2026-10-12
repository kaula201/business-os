"""#24: data migration 155 backfills BASE company_modules rows only."""
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company

# Base codes that the backfill is expected to insert (must match migration)
BASE_CODES = {"settings", "clients"}


def load_migration_module():
    """Load the migration module from its file path."""
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "155_backfill_base_company_modules.py"
    )
    spec = importlib.util.spec_from_file_location(
        "backfill_base_company_modules", migration_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = load_migration_module()


async def read_company_module_rows(db_session: AsyncSession, company_id) -> list[tuple[str, bool]]:
    """
    Read all company_module rows for a given company, joined with app_modules.code.
    Pins the GUC for the company before selecting.
    Returns a list of (code, enabled) tuples.
    """
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
    rows = result.fetchall()
    return [(row[0], row[1]) for row in rows]


async def insert_company_module(
    db_session: AsyncSession,
    company_id,
    module_code: str,
    enabled: bool,
):
    """Insert a CompanyModule row for a given company and module code, pinning GUC first."""
    # Pin GUC for the insert
    await db_session.execute(
        text("SELECT set_config('app.current_company_id', :c, true)"),
        {"c": str(company_id)},
    )
    # Get the AppModule id
    result = await db_session.execute(
        text("SELECT id FROM app_modules WHERE code = :code"),
        {"code": module_code},
    )
    module_id = result.scalar_one()
    # Insert the CompanyModule
    await db_session.execute(
        text(
            """
            INSERT INTO company_modules (id, company_id, module_id, enabled)
            VALUES (gen_random_uuid(), :cid, :mid, :enabled)
            """
        ),
        {"cid": company_id, "mid": module_id, "enabled": enabled},
    )
    # Flush to ensure it's in the transaction
    await db_session.flush()


@pytest.mark.asyncio
async def test_backfill_company_with_no_rows(db_session: AsyncSession):
    """Company with no rows -> after backfill has exactly BASE rows, all enabled, no other rows."""
    # Create a company
    company = Company(
        name="Test Company 1",
        identification_code=f"test-{uuid.uuid4()}",
        vat_status=False,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.flush()  # get id without committing
    company_id = company.id

    # Run backfill
    conn = await db_session.connection()
    inserted = await conn.run_sync(mod.backfill_base_company_modules)
    assert inserted >= 2  # at least the two BASE rows for this company

    # Read rows
    rows = await read_company_module_rows(db_session, company_id)
    codes = [code for code, _ in rows]
    enabled_flags = [enabled for _, enabled in rows]

    # Exactly BASE codes, all enabled
    assert set(codes) == BASE_CODES
    assert all(enabled_flags)

    # No other rows beyond BASE
    assert len(rows) == len(BASE_CODES)


@pytest.mark.asyncio
async def test_backfill_respects_existing_rows(db_session: AsyncSession):
    """Existing rows (settings=False, helpdesk=True, crm=False) are untouched; clients added enabled."""
    # Create a company
    company = Company(
        name="Test Company 2",
        identification_code=f"test-{uuid.uuid4()}",
        vat_status=False,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    # Insert explicit rows: settings=False, helpdesk=True, crm=False
    await insert_company_module(db_session, company_id, "settings", False)
    await insert_company_module(db_session, company_id, "helpdesk", True)
    await insert_company_module(db_session, company_id, "crm", False)
    await db_session.flush()

    # Run backfill
    conn = await db_session.connection()
    inserted = await conn.run_sync(mod.backfill_base_company_modules)
    # Should insert at least one row (clients) for this company
    assert inserted >= 1

    # Read rows
    rows = await read_company_module_rows(db_session, company_id)
    row_dict = {code: enabled for code, enabled in rows}

    # Existing rows untouched
    assert row_dict["settings"] is False
    assert row_dict["helpdesk"] is True
    assert row_dict["crm"] is False
    # clients row added and enabled
    assert "clients" in row_dict
    assert row_dict["clients"] is True


@pytest.mark.asyncio
async def test_backfill_idempotent(db_session: AsyncSession):
    """Running backfill twice: second call returns 0 and row count unchanged."""
    # Create a company
    company = Company(
        name="Test Company 3",
        identification_code=f"test-{uuid.uuid4()}",
        vat_status=False,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    # First run
    conn = await db_session.connection()
    inserted_first = await conn.run_sync(mod.backfill_base_company_modules)
    assert inserted_first >= 2  # at least BASE for this company

    # Read rows and count
    rows_after_first = await read_company_module_rows(db_session, company_id)
    count_after_first = len(rows_after_first)

    # Second run
    inserted_second = await conn.run_sync(mod.backfill_base_company_modules)
    assert inserted_second == 0

    # Read rows again and count
    rows_after_second = await read_company_module_rows(db_session, company_id)
    count_after_second = len(rows_after_second)

    assert count_after_first == count_after_second
    # Also ensure rows are identical (optional)
    assert rows_after_first == rows_after_second


@pytest.mark.asyncio
async def test_backfill_only_base_modules(db_session: AsyncSession):
    """For a fresh company, enabled codes are exactly BASE and all row codes subset of BASE."""
    # Create a company
    company = Company(
        name="Test Company 4",
        identification_code=f"test-{uuid.uuid4()}",
        vat_status=False,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.flush()
    company_id = company.id

    # Run backfill
    conn = await db_session.connection()
    inserted = await conn.run_sync(mod.backfill_base_company_modules)
    assert inserted >= 2

    # Read rows
    rows = await read_company_module_rows(db_session, company_id)
    codes = [code for code, _ in rows]
    enabled_codes = {code for code, enabled in rows if enabled}

    # All row codes are subset of BASE
    assert set(codes).issubset(BASE_CODES)
    # Enabled codes exactly BASE
    assert enabled_codes == BASE_CODES


@pytest.mark.asyncio
async def test_backfill_resets_guc(db_session: AsyncSession):
    """After backfill, current_setting('app.current_company_id', true) is '' or None."""
    # Create a company
    company = Company(
        name="Test Company 5",
        identification_code=f"test-{uuid.uuid4()}",
        vat_status=False,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.flush()

    # Run backfill
    conn = await db_session.connection()
    inserted = await conn.run_sync(mod.backfill_base_company_modules)
    assert inserted >= 2

    # Immediately check GUC (before any further pinning)
    result = await db_session.execute(
        text("SELECT current_setting('app.current_company_id', true)")
    )
    guc_value = result.scalar_one()
    # It should be reset to empty string or None (SQL NULL returns None in asyncpg)
    assert guc_value in ("", None)
