"""Focused accounting controls invariants: role gate, tenant scope, fiscal + FX config."""
from datetime import date

import pytest

pytestmark = pytest.mark.asyncio


async def test_accounting_controls_create_and_list(client, auth_headers, test_company):
    fiscal = await client.post("/api/v1/accounting-controls/fiscal-positions", json={
        "code": "GE-VAT-18", "name": "საქართველო — სტანდარტული დღგ", "vat_rate": 18,
        "tax_type": "vat_standard", "applies_to": "both", "is_default": True,
    }, headers=auth_headers)
    assert fiscal.status_code == 201, fiscal.text
    assert fiscal.json()["data"]["vat_rate"] == 18.0

    mapping = await client.post("/api/v1/accounting-controls/consolidation-mappings", json={
        "source_account_code": "5200", "target_account_code": "5200",
        "target_name": "Operating expenses", "target_account_type": "expense",
    }, headers=auth_headers)
    assert mapping.status_code == 201, mapping.text

    fx = await client.post("/api/v1/accounting-controls/fx-rates", json={
        "target_currency": "GEL", "rate_date": str(date.today()), "rate": 2.73,
        "method": "closing", "source": "nbg", "is_locked": True,
    }, headers=auth_headers)
    assert fx.status_code == 201, fx.text
    assert fx.json()["data"]["rate"] == 2.73

    listed = await client.get("/api/v1/accounting-controls/fiscal-positions", headers=auth_headers)
    assert listed.status_code == 200
    assert [x["code"] for x in listed.json()["data"]] == ["GE-VAT-18"]


async def test_accounting_controls_reject_invalid_fx_and_employee_access(client, auth_headers, employee_auth_headers, test_company):
    invalid = await client.post("/api/v1/accounting-controls/fx-rates", json={
        "target_currency": "GEL", "rate": 0, "method": "closing",
    }, headers=auth_headers)
    assert invalid.status_code == 422

    denied = await client.get("/api/v1/accounting-controls/fiscal-positions", headers=employee_auth_headers)
    assert denied.status_code == 403

    invalid_mapping = await client.post("/api/v1/accounting-controls/consolidation-mappings", json={
        "source_account_code": "4100", "target_account_code": "1000",
        "target_name": "Invalid classification", "target_account_type": "asset",
    }, headers=auth_headers)
    assert invalid_mapping.status_code == 422
