"""Module enablement helpers shared by endpoint guards."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import AppModule, CompanyModule

BASE_MODULE_CODES = frozenset({"settings", "clients"})


async def is_module_enabled(db: AsyncSession, company_id: UUID, code: str) -> bool:
    """Return True if the module is enabled for the company.

    BASE module codes are always enabled. For other codes, look up the active
    AppModule and then the CompanyModule row:
    - no CompanyModule row -> False (fail closed, #24)
    - enabled False -> False
    - enabled True -> True
    Unknown or inactive module codes -> False.
    """
    if code in BASE_MODULE_CODES:
        return True

    module = (
        await db.execute(
            select(AppModule).where(
                AppModule.code == code,
                AppModule.is_active == True,
            )
        )
    ).scalar_one_or_none()
    if module is None:
        return False

    company_module = (
        await db.execute(
            select(CompanyModule).where(
                CompanyModule.company_id == company_id,
                CompanyModule.module_id == module.id,
            )
        )
    ).scalar_one_or_none()
    if company_module is None:
        return False
    return company_module.enabled


async def enabled_module_codes(db: AsyncSession, company_id: UUID, codes) -> set[str]:
    """Return the subset of ``codes`` enabled for the company in one query.

    BASE module codes are always enabled. For other codes, a module is enabled
    only when an active AppModule exists and a CompanyModule row has enabled=True
    (#24). Missing CompanyModule rows are treated as disabled.
    """
    codes = set(codes)
    enabled = set(codes & BASE_MODULE_CODES)
    non_base = codes - BASE_MODULE_CODES
    if not non_base:
        return enabled

    rows = (
        await db.execute(
            select(AppModule.code, CompanyModule.enabled)
            .outerjoin(
                CompanyModule,
                (CompanyModule.module_id == AppModule.id)
                & (CompanyModule.company_id == company_id),
            )
            .where(
                AppModule.code.in_(non_base),
                AppModule.is_active == True,
            )
        )
    ).all()

    for module_code, is_enabled in rows:
        if is_enabled is True:
            enabled.add(module_code)
    return enabled


async def seed_base_company_modules(db: AsyncSession, company_id: UUID) -> int:
    """Give a brand-new company exactly its BASE entitlements (#24 item 1).

    ``POST /auth/register`` created a company with no ``company_modules`` rows at
    all, which the UI used to read as "every module enabled" while guards denied
    non-admins on every paid module. Now that a missing row means disabled, a new
    company must be given its BASE rows explicitly.

    Idempotent: existing rows are left untouched, so calling it twice is safe and
    an operator's manual enable/disable is never overwritten.
    """
    from sqlalchemy import insert

    base_modules = (
        await db.execute(
            select(AppModule.id).where(
                AppModule.code.in_(BASE_MODULE_CODES),
                AppModule.is_active == True,
            )
        )
    ).scalars().all()
    if not base_modules:
        return 0

    existing = set(
        (
            await db.execute(
                select(CompanyModule.module_id).where(
                    CompanyModule.company_id == company_id,
                    CompanyModule.module_id.in_(base_modules),
                )
            )
        ).scalars()
    )
    missing = [module_id for module_id in base_modules if module_id not in existing]
    if not missing:
        return 0

    # company_modules is RLS-protected; register runs pinned to the new company,
    # so the insert already satisfies the policy.
    await db.execute(
        insert(CompanyModule).values(
            [
                {"company_id": company_id, "module_id": module_id, "enabled": True}
                for module_id in missing
            ]
        )
    )
    return len(missing)
