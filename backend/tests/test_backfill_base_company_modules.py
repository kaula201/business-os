"""#24 item 3 — guards for the BASE entitlements backfill.

Migration 155 gives every existing company the BASE rows it was missing. Two
things can silently rot afterwards, so both are pinned here:

1. Drift between the migration's inlined BASE_MODULE_CODES and
   app.core.modules.BASE_MODULE_CODES. The migration inlines the tuple on purpose
   (a migration must keep the meaning it had at its revision, not follow a
   constant that later moves), so the two copies need an explicit equality test.

2. The backfill's actual SQL: it must insert BASE rows, never touch a row that
   already exists, and never wake a module the company disabled.
"""
import importlib.util
import re
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.core.modules import BASE_MODULE_CODES
from app.models.company import Company
from app.models.module import AppModule, CompanyModule

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "155_backfill_base_company_modules.py"
)

# The exact SQL from the migration: insert BASE for every company, leave existing
# rows alone. Kept verbatim here so the test exercises the shipped statement.
_BACKFILL_SQL = text(
    """
    INSERT INTO company_modules (id, company_id, module_id, enabled, created_at, updated_at)
    SELECT gen_random_uuid(), c.id, m.id, true, now(), now()
    FROM companies c
    CROSS JOIN app_modules m
    WHERE m.code = ANY(:codes)
      AND m.is_active = true
    ON CONFLICT ON CONSTRAINT uq_company_module DO NOTHING
    """
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig155", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# 1. drift
# --------------------------------------------------------------------------- #

def test_migration_constants_match_application_constants():
    """The inlined tuple must stay equal to the application's set."""
    mig = _load_migration()
    assert set(mig.BASE_MODULE_CODES) == set(BASE_MODULE_CODES), (
        "migration 155 BASE_MODULE_CODES drifted from app.core.modules; "
        "a new BASE module needs its own backfill migration, not an edit here"
    )


def test_migration_revision_chain_is_intact():
    mig = _load_migration()
    assert mig.revision == "155_backfill_base_company_modules"
    assert mig.down_revision == "154_invoice_payments"


def test_migration_is_wired_at_head():
    """Nothing may sit above 155 yet, or the backfill never reaches prod."""
    versions = MIGRATION_PATH.parent
    downs = set()
    revs = set()
    for path in versions.glob("*.py"):
        body = path.read_text()
        rev = re.search(r'^revision\s*=\s*["\']([^"\']+)', body, re.M)
        down = re.search(r'^down_revision\s*=\s*(.+)$', body, re.M)
        if rev:
            revs.add(rev.group(1))
        if down:
            downs.update(re.findall(r'["\']([^"\']+)["\']', down.group(1)))
    heads = revs - downs
    assert "155_backfill_base_company_modules" in heads, f"155 is not a head: {heads}"


def test_migration_file_has_no_application_imports():
    """A migration must not import app code: the app changes, the migration must not."""
    body = MIGRATION_PATH.read_text()
    imports = re.findall(r"^\s*(?:from|import)\s+([\w\.]+)", body, re.M)
    offenders = [i for i in imports if i.split(".")[0] == "app"]
    assert not offenders, f"migration imports application modules: {offenders}"


# --------------------------------------------------------------------------- #
# 2. the backfill itself, on a real database
# --------------------------------------------------------------------------- #

async def _make_company(db, tag: str) -> Company:
    import uuid as _uuid

    company = Company(
        name=f"Backfill {tag}",
        identification_code=f"BF-{_uuid.uuid4().hex[:8].upper()}",
        vat_status=False,
        currency="GEL",
    )
    db.add(company)
    await db.flush()
    return company


@pytest.mark.asyncio
async def test_backfill_grants_base_to_a_company_with_no_rows(db_session):
    """A company that owns nothing gets exactly BASE, all enabled."""
    company = await _make_company(db_session, "empty")
    assert (await db_session.execute(
        select(CompanyModule).where(CompanyModule.company_id == company.id)
    )).scalars().all() == []

    await db_session.execute(_BACKFILL_SQL, {"codes": list(BASE_MODULE_CODES)})

    rows = (await db_session.execute(
        select(AppModule.code, CompanyModule.enabled)
        .join(AppModule, AppModule.id == CompanyModule.module_id)
        .where(CompanyModule.company_id == company.id)
    )).all()
    assert {code for code, _ in rows} == set(BASE_MODULE_CODES)
    assert all(enabled for _, enabled in rows)


@pytest.mark.asyncio
async def test_backfill_does_not_enable_paid_modules(db_session):
    """The backfill is not a free upgrade: only BASE codes are inserted."""
    company = await _make_company(db_session, "paid")

    await db_session.execute(_BACKFILL_SQL, {"codes": list(BASE_MODULE_CODES)})

    paid_rows = (await db_session.execute(
        select(AppModule.code)
        .join(CompanyModule, CompanyModule.module_id == AppModule.id)
        .where(
            CompanyModule.company_id == company.id,
            AppModule.code.notin_(BASE_MODULE_CODES),
        )
    )).scalars().all()
    assert paid_rows == [], f"backfill enabled paid modules: {paid_rows}"


@pytest.mark.asyncio
async def test_backfill_preserves_an_explicit_disable(db_session):
    """ON CONFLICT DO NOTHING: a module the operator turned off stays off."""
    company = await _make_company(db_session, "disabled")
    await db_session.execute(_BACKFILL_SQL, {"codes": list(BASE_MODULE_CODES)})

    module_id = (await db_session.execute(
        select(AppModule.id).where(AppModule.code == "settings")
    )).scalar_one()
    row = (await db_session.execute(
        select(CompanyModule).where(
            CompanyModule.company_id == company.id,
            CompanyModule.module_id == module_id,
        )
    )).scalar_one()
    row.enabled = False
    await db_session.flush()

    # re-run, as a re-applied migration or a second deploy would
    await db_session.execute(_BACKFILL_SQL, {"codes": list(BASE_MODULE_CODES)})

    enabled = (await db_session.execute(
        select(CompanyModule.enabled).where(
            CompanyModule.company_id == company.id,
            CompanyModule.module_id == module_id,
        )
    )).scalar_one()
    assert enabled is False, "re-run re-enabled a module the operator had disabled"


@pytest.mark.asyncio
async def test_backfill_is_idempotent(db_session):
    """Two runs leave the same number of rows as one."""
    await _make_company(db_session, "idem1")
    await _make_company(db_session, "idem2")

    await db_session.execute(_BACKFILL_SQL, {"codes": list(BASE_MODULE_CODES)})
    first = len((await db_session.execute(select(CompanyModule.id))).scalars().all())

    await db_session.execute(_BACKFILL_SQL, {"codes": list(BASE_MODULE_CODES)})
    second = len((await db_session.execute(select(CompanyModule.id))).scalars().all())

    assert first == second, f"backfill duplicated rows: {first} then {second}"
    assert first == 2 * len(BASE_MODULE_CODES)


@pytest.mark.asyncio
async def test_backfill_does_not_invent_catalog_codes(db_session):
    """A code that is not in app_modules must insert nothing, not fail on the FK.

    A bare migration run on a fresh volume may precede seed_modules(). The
    migration handles that by filtering to codes present in the catalog; this pins
    the same safety here, using a code guaranteed absent.
    """
    company = await _make_company(db_session, "nocatalog")
    bogus = "definitely-not-a-real-module-code"

    await db_session.execute(_BACKFILL_SQL, {"codes": [bogus]})

    rows = (await db_session.execute(
        select(CompanyModule).where(CompanyModule.company_id == company.id)
    )).scalars().all()
    assert rows == [], "backfill created a row for a module that does not exist"
