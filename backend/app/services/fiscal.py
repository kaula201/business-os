"""Fiscal position resolution for new draft documents and immutable GL snapshots."""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting_controls import FiscalPosition


@dataclass(frozen=True)
class ResolvedFiscalPosition:
    id: UUID | None
    vat_rate: Decimal
    tax_account_code: str


async def resolve_fiscal_position(
    db: AsyncSession,
    company_id: UUID,
    *,
    partner_fiscal_position_id: UUID | None,
    applies_to: str,
) -> ResolvedFiscalPosition:
    """Resolve partner position first, then company default; legacy fallback is 18%."""
    position = None
    if partner_fiscal_position_id:
        position = (await db.execute(select(FiscalPosition).where(
            FiscalPosition.id == partner_fiscal_position_id,
            FiscalPosition.company_id == company_id,
            FiscalPosition.is_active.is_(True),
            FiscalPosition.applies_to.in_([applies_to, "both"]),
        ))).scalar_one_or_none()
    if position is None:
        position = (await db.execute(select(FiscalPosition).where(
            FiscalPosition.company_id == company_id,
            FiscalPosition.is_default.is_(True),
            FiscalPosition.is_active.is_(True),
            FiscalPosition.applies_to.in_([applies_to, "both"]),
        ).limit(1))).scalar_one_or_none()
    if position is None:
        return ResolvedFiscalPosition(None, Decimal("18.0000"), "2200" if applies_to == "sale" else "5300")
    return ResolvedFiscalPosition(
        position.id,
        Decimal(position.vat_rate),
        position.sales_tax_account_code if applies_to == "sale" else position.purchase_tax_account_code,
    )
