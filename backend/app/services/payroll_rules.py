"""Payroll tax rules — Georgian legal basis with explicit, per-line justification.

Every figure in a payslip must be explainable:
- which rate applies,
- the legal reference,
- the effective period,
- why a different rule (e.g. 15% instead of the general 20%) is used,
- why pension contribution is 0.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


# Legal constants
GENERAL_INCOME_TAX_RATE = Decimal("0.20")   # Tax Code of Georgia, Art. 81 (general)
REDUCED_INCOME_TAX_RATE = Decimal("0.15")   # employment income, transitional rate
REDUCED_RATE_FROM = date(2025, 1, 1)

PENSION_EMPLOYEE_RATE = Decimal("0.02")
PENSION_EMPLOYER_RATE = Decimal("0.02")
PENSION_CEILING_MONTHLY = Decimal("200000")  # contribution base cap (GEL)

TAX_CODE_REF = "საქართველოს საგადასახადო კოდექსი, მუხლი 81"
TAX_CODE_REF_EN = "Tax Code of Georgia, Art. 81"
PENSION_LAW_REF = "კანონი „დაგროვებითი პენსიის შესახებ“, მუხლი 37"
PENSION_LAW_REF_EN = "Law on Funded Pensions, Art. 37"


@dataclass
class TaxLine:
    label_ka: str
    label_en: str
    basis_ka: str
    basis_en: str
    note_ka: str
    note_en: str
    rate: str
    amount: float


@dataclass
class PayrollExplanation:
    lines: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def income_tax_rate_for(period_year: int, period_month: int) -> tuple[Decimal, str]:
    """Return the applicable income-tax rate + legal note.

    Employment income earned from 2025-01-01 benefits from the reduced 15%
    flat rate (Tax Code transitional provision); earlier periods are taxed
    at the general 20% rate.
    """
    period = date(period_year, period_month, 1)
    if period >= REDUCED_RATE_FROM:
        return REDUCED_INCOME_TAX_RATE, (
            "მოქმედებს შემცირებული 15%-იანი განაკვეთი (2025-01-01-დან). "
            "ზოგადი 20%-იანი განაკვეთი ვრცელდება მხოლოდ იმ შემოსავალზე, "
            "რომელზეც სპეციალური განაკვეთი არ მოქმედებს."
        )
    return GENERAL_INCOME_TAX_RATE, (
        "პერიოდი 2025-01-01-მდე — ზოგადი 20%-იანი განაკვეთი."
    )


def compute_payroll(
    gross_pay: Decimal,
    pension_participant: bool,
    period_year: int,
    period_month: int,
    additions: Decimal = Decimal("0"),
    deductions: Decimal = Decimal("0"),
) -> dict:
    """Compute payroll + full per-line legal explanation."""
    taxable = gross_pay + additions - deductions
    rate, rate_note_ka = income_tax_rate_for(period_year, period_month)

    # ── Pension ─────────────────────────────────────────────────────────
    if pension_participant:
        pension_base = min(gross_pay, PENSION_CEILING_MONTHLY)
        pension = (pension_base * PENSION_EMPLOYEE_RATE).quantize(Decimal("0.01"))
        pension_note_ka = (
            "თანამშრომელი მონაწილეობს საპენსიო ფონდში — 2% (დამსაქმებელი იხდის კიდევ 2%). "
            "ბაზა: {:.2f} ₾ (ზღვარი 200 000 ₾).".format(pension_base)
        )
        pension_note_en = (
            "Employee participates in the pension fund — 2% withheld "
            "(employer adds 2%). Base: {:.2f} GEL (cap 200,000).".format(pension_base)
        )
        pension_rate = "2%"
    else:
        pension = Decimal("0.00")
        pension_note_ka = (
            "0.00 ₾ — დასაქმებული არ მონაწილეობს დაგოვრებით პენსიაში "
            "(არ მოქმედებს ვალდებულება/გათავისუფლება)."
        )
        pension_note_en = (
            "0.00 — employee is not a pension-fund participant (exempt/opted out)."
        )
        pension_rate = "0%"

    tax = (taxable * rate).quantize(Decimal("0.01"))
    net = (gross_pay + additions - deductions - pension - tax).quantize(Decimal("0.01"))

    return {
        "gross_pay": gross_pay,
        "additions": additions,
        "deductions": deductions,
        "pension_contribution": pension,
        "income_tax": tax,
        "net_pay": net,
        "explanation": PayrollExplanation(
            lines=[
                TaxLine(
                    label_ka="საშემოსავლო გადასახადი",
                    label_en="Income tax",
                    basis_ka=TAX_CODE_REF,
                    basis_en=TAX_CODE_REF_EN,
                    note_ka=rate_note_ka,
                    note_en="Reduced 15% flat rate applies to employment income from 2025-01-01; the general 20% rate applies only when no special rate applies.",
                    rate=f"{rate * 100:.0f}%",
                    amount=float(tax),
                ),
                TaxLine(
                    label_ka="საპენსიო შენატანი",
                    label_en="Pension contribution",
                    basis_ka=PENSION_LAW_REF,
                    basis_en=PENSION_LAW_REF_EN,
                    note_ka=pension_note_ka,
                    note_en=pension_note_en,
                    rate=pension_rate,
                    amount=float(pension),
                ),
            ],
            meta={
                "general_rate": "20%",
                "applied_rate": f"{rate * 100:.0f}%",
                "rate_effective_from": REDUCED_RATE_FROM.isoformat(),
                "legal_basis_ka": TAX_CODE_REF,
                "legal_basis_en": TAX_CODE_REF_EN,
            },
        ),
    }
