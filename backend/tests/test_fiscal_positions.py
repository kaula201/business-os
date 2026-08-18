"""Fiscal position invariants: partner/default resolution and immutable account selection."""
from decimal import Decimal

import pytest

from app.models.accounting_controls import FiscalPosition
from app.services.fiscal import resolve_fiscal_position

pytestmark = pytest.mark.asyncio


async def test_fiscal_position_partner_precedes_company_default(db_session, test_company):
    default = FiscalPosition(
        company_id=test_company.id, code="STD18", name="Standard", vat_rate=Decimal("18"),
        sales_tax_account_code="2200", purchase_tax_account_code="5300", is_default=True,
    )
    exempt = FiscalPosition(
        company_id=test_company.id, code="EXEMPT", name="Exempt", vat_rate=Decimal("0"),
        sales_tax_account_code="2200", purchase_tax_account_code="5300", applies_to="sale",
    )
    db_session.add_all([default, exempt])
    await db_session.commit()

    partner = await resolve_fiscal_position(
        db_session, test_company.id, partner_fiscal_position_id=exempt.id, applies_to="sale"
    )
    default_purchase = await resolve_fiscal_position(
        db_session, test_company.id, partner_fiscal_position_id=None, applies_to="purchase"
    )
    assert partner.id == exempt.id and partner.vat_rate == Decimal("0")
    assert default_purchase.id == default.id and default_purchase.tax_account_code == "5300"


async def test_fiscal_position_legacy_fallback_when_no_position(db_session, test_company):
    result = await resolve_fiscal_position(
        db_session, test_company.id, partner_fiscal_position_id=None, applies_to="sale"
    )
    assert result.id is None
    assert result.vat_rate == Decimal("18.0000")
    assert result.tax_account_code == "2200"
