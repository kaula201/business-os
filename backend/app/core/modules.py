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
    - no CompanyModule row -> True (default enabled)
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
        return True
    return company_module.enabled


async def enabled_module_codes(db: AsyncSession, company_id: UUID, codes) -> set[str]:
    """Return the subset of ``codes`` enabled for the company in one query."""
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
        if is_enabled is None:
            is_enabled = True
        if is_enabled:
            enabled.add(module_code)
    return enabled
