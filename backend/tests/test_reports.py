"""Tests for the Reports module: revenue analytics, definitions, export scope."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.product import Product
from app.models.receivable import CustomerReceivable
from app.models.report import ReportPreference
from app.models.user import User


async def _make_issued_invoice(client, auth_headers, test_company, db_session, suffix, total, invoice_date):
    """Create an order + issued invoice, backdating invoice_date for range testing."""
    customer = Client(
        company_id=test_company.id,
        name=f"Report Client {suffix}",
        client_type="legal",
        identification_code=f"REP-CLIENT-{suffix}",
        vat_status=True,
        address="თბილისი",
        status="active",
    )
    product = Product(
        company_id=test_company.id,
        sku=f"REP-SKU-{suffix}",
        name=f"Report Product {suffix}",
        sale_price=Decimal("100.00"),
        current_stock=50,
    )
    db_session.add_all([customer, product])
    await db_session.commit()
    await db_session.refresh(customer)
    await db_session.refresh(product)

    resp = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": str(customer.id),
            "items": [{
                "product_id": str(product.id),
                "product_name": product.name,
                "quantity": 1,
                "unit_price": total,
                "discount_percent": 0,
            }],
            "delivery_address": customer.address,
            "notes": f"Report order {suffix}",
            "is_vat_payer": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    order_id = resp.json()["data"]["id"]

    invoice = (await db_session.execute(
        select(Invoice).where(Invoice.order_id == order_id)
    )).scalar_one()

    # Issue it (admin) then backdate to control which month it lands in.
    issued = await client.post(f"/api/v1/invoices/{invoice.id}/issue", headers=auth_headers)
    assert issued.status_code == 200, issued.text

    invoice.invoice_date = invoice_date
    await db_session.commit()
    await db_session.refresh(invoice)
    return invoice, customer, product


@pytest.mark.asyncio
async def test_reports_summary_computes_revenue_from_issued_invoices(
    client, auth_headers, test_company, db_session
):
    """Revenue must reflect issued invoices — the semantic layer, not 0."""
    now = date.today()
    await _make_issued_invoice(client, auth_headers, test_company, db_session, "SUM-A", "150.00", now)
    await _make_issued_invoice(client, auth_headers, test_company, db_session, "SUM-B", "50.00", now)

    resp = await client.get("/api/v1/reports/summary?period=30d", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Revenue is gross (Invoice.total incl. 18% VAT): 200 subtotal -> 236 total
    assert data["kpi"]["total_revenue"] == 236.0
    assert data["kpi"]["total_invoices"] == 2
    assert data["kpi"]["avg_invoice_value"] == 118.0
    assert data["kpi"]["outstanding_revenue"] == 236.0

    # Definitions present
    keys = {d["key"] for d in data["metric_definitions"]}
    assert {"total_revenue", "total_invoices", "avg_invoice_value", "paid_revenue", "outstanding_revenue"} <= keys
    assert data["metric_definitions"][0]["formula"] and data["metric_definitions"][0]["source"]

    # Charts populated
    assert len(data["charts"]["revenue_by_month"]) >= 1
    total_charted = sum(p["amount"] for p in data["charts"]["revenue_by_month"])
    assert total_charted == 236.0
    assert len(data["charts"]["top_products"]) >= 1
    assert len(data["charts"]["top_clients"]) >= 1

    # Export scope default created
    assert data["export_scope"]["default_date_range"] == "30d"
    pref = (await db_session.execute(
        select(ReportPreference).where(ReportPreference.company_id == test_company.id)
    )).scalar_one()
    assert pref.default_export_scope == "current"


@pytest.mark.asyncio
async def test_reports_revenue_groups_by_month_and_respects_range(
    client, auth_headers, test_company, db_session
):
    now = date.today()
    first_this_month = now.replace(day=1)
    # A previous-month invoice should be excluded from a 7d window but counted in 12m.
    last_month = (first_this_month - timedelta(days=1)).replace(day=1)

    await _make_issued_invoice(client, auth_headers, test_company, db_session, "M-CUR", "100.00", first_this_month)
    await _make_issued_invoice(client, auth_headers, test_company, db_session, "M-PREV", "300.00", last_month)

    # 7d window: only current-month invoice if within 7 days, or none if older.
    seven = await client.get("/api/v1/reports/revenue?period=7d&group_by=month", headers=auth_headers)
    assert seven.status_code == 200, seven.text
    seven_total = sum(r["amount"] for r in seven.json()["data"]["data"])

    twelve = await client.get("/api/v1/reports/revenue?period=12m&group_by=month", headers=auth_headers)
    assert twelve.status_code == 200, twelve.text
    twelve_data = twelve.json()["data"]["data"]
    # Gross totals incl. 18% VAT: 118 + 354 = 472
    assert sum(r["amount"] for r in twelve_data) == 472.0
    # Two distinct months present.
    assert len(twelve_data) == 2

    # Day grouping works.
    day = await client.get("/api/v1/reports/revenue?period=12m&group_by=day", headers=auth_headers)
    assert day.status_code == 200, day.text
    assert sum(r["amount"] for r in day.json()["data"]["data"]) == 472.0

    # Sanity: 7d should not exceed the 118.00 that falls inside (or 0 if outside).
    assert seven_total <= 118.0


@pytest.mark.asyncio
async def test_reports_definitions_and_export_scope_crud(
    client, auth_headers, test_company, db_session
):
    defs = await client.get("/api/v1/reports/definitions", headers=auth_headers)
    assert defs.status_code == 200
    assert len(defs.json()["data"]) >= 5

    get_scope = await client.get("/api/v1/reports/export-scope", headers=auth_headers)
    assert get_scope.status_code == 200
    assert get_scope.json()["data"]["default_date_range"] == "30d"

    update = await client.patch(
        "/api/v1/reports/export-scope",
        headers=auth_headers,
        json={"default_date_range": "12m", "default_export_scope": "all", "group_by_month": True},
    )
    assert update.status_code == 200, update.text
    scope = update.json()["data"]
    assert scope["default_date_range"] == "12m"
    assert scope["default_export_scope"] == "all"
    assert scope["group_by_month"] is True

    # Persisted.
    reget = await client.get("/api/v1/reports/export-scope", headers=auth_headers)
    assert reget.json()["data"]["default_date_range"] == "12m"

    # Invalid value rejected.
    bad = await client.patch(
        "/api/v1/reports/export-scope",
        headers=auth_headers,
        json={"default_date_range": "999d"},
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_reports_rejects_invalid_period_and_employee_access(
    client, auth_headers, employee_auth_headers, test_company, db_session
):
    bad = await client.get("/api/v1/reports/summary?period=5y", headers=auth_headers)
    assert bad.status_code == 422

    # Seed the reports module + company enablement so require_module resolves for a
    # non-admin (employee) caller. Default fallback grants employee can_access.
    # The module may already exist from the global catalog seed, so reuse it.
    from app.models.module import AppModule, CompanyModule
    module = (await db_session.execute(
        select(AppModule).where(AppModule.code == "reports")
    )).scalar_one_or_none()
    if module is None:
        module = AppModule(code="reports", name="რეპორტები", description="", icon="BarChart3",
                           route="/reports", category="other", sort_order=270)
        db_session.add(module)
        await db_session.flush()
    db_session.add(CompanyModule(company_id=test_company.id, module_id=module.id, enabled=True))
    await db_session.commit()

    ok = await client.get("/api/v1/reports/summary?period=30d", headers=employee_auth_headers)
    assert ok.status_code == 200, ok.text
