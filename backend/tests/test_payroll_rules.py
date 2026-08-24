"""Payroll legal rules — rate by period, pension participation, explanation."""
from datetime import date
from decimal import Decimal

import pytest

from app.services.payroll_rules import (
    GENERAL_INCOME_TAX_RATE,
    REDUCED_INCOME_TAX_RATE,
    compute_payroll,
    income_tax_rate_for,
)

pytestmark = pytest.mark.asyncio


def test_income_tax_rate_2026_is_15_percent():
    rate, _ = income_tax_rate_for(2026, 8)
    assert rate == REDUCED_INCOME_TAX_RATE == Decimal("0.15")


def test_income_tax_rate_before_2025_is_20_percent():
    rate, _ = income_tax_rate_for(2024, 12)
    assert rate == GENERAL_INCOME_TAX_RATE == Decimal("0.20")


def test_compute_payroll_3000_participant():
    r = compute_payroll(Decimal("3000"), pension_participant=True, period_year=2026, period_month=8)
    assert r["pension_contribution"] == Decimal("60.00")   # 2% of 3000
    assert r["income_tax"] == Decimal("450.00")            # 15% of 3000
    assert r["net_pay"] == Decimal("2490.00")              # 3000 - 60 - 450
    lines = r["explanation"].lines
    assert len(lines) == 2
    tax_line = lines[0]
    assert tax_line.rate == "15%"
    assert "მუხლი 81" in tax_line.basis_ka
    assert "2025" in tax_line.note_ka
    pension_line = lines[1]
    assert pension_line.rate == "2%"
    assert "მუხლი 37" in pension_line.basis_ka


def test_compute_payroll_pension_optout_explains_zero():
    r = compute_payroll(Decimal("3000"), pension_participant=False, period_year=2026, period_month=8)
    assert r["pension_contribution"] == Decimal("0.00")
    assert r["income_tax"] == Decimal("450.00")
    assert r["net_pay"] == Decimal("2550.00")
    pension_line = r["explanation"].lines[1]
    assert pension_line.rate == "0%"
    assert "არ მონაწილეობს" in pension_line.note_ka


def test_compute_payroll_pre_2025_uses_20_percent():
    r = compute_payroll(Decimal("3000"), pension_participant=True, period_year=2024, period_month=12)
    assert r["income_tax"] == Decimal("600.00")           # 20%
    assert r["explanation"].lines[0].rate == "20%"
    assert r["explanation"].meta["applied_rate"] == "20%"
