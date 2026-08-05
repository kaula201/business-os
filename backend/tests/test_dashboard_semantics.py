"""Dashboard revenue semantics: issued-invoice revenue + invoiced/total order counts."""
import pytest
from decimal import Decimal
from sqlalchemy import select

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.order import Order
from app.models.product import Product
from app.models.warehouse import InventoryBalance, Warehouse


async def create_dashboard_company_context(
    client, auth_headers, test_company, db_session, suffix: str
):
    customer = Client(
        company_id=test_company.id,
        name=f"Dash Customer {suffix}",
        client_type="legal",
        identification_code=f"DASH-CUST-{suffix}",
        status="active",
    )
    product = Product(
        company_id=test_company.id,
        sku=f"DASH-SKU-{suffix}",
        name=f"Dash Product {suffix}",
        sale_price=100,
        current_stock=50,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"WH-{suffix}",
        name=f"Dash Warehouse {suffix}",
        is_default=True,
        is_active=True,
    )
    db_session.add_all([customer, product, warehouse])
    await db_session.flush()
    db_session.add(
        InventoryBalance(
            company_id=test_company.id,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=Decimal("50"),
        )
    )
    await db_session.commit()
    await db_session.refresh(customer)
    await db_session.refresh(product)
    return customer, product, warehouse


async def create_order(client, auth_headers, customer, product, warehouse, statuses: list[str]):
    response = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": str(customer.id),
            "warehouse_id": str(warehouse.id),
            "items": [
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "quantity": 2,
                    "unit_price": 100,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    order_id = response.json()["data"]["id"]
    for status in statuses:
        status_response = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": status},
            headers=auth_headers,
        )
        assert status_response.status_code == 200, status_response.text
    return order_id


@pytest.mark.asyncio
async def test_dashboard_reports_invoiced_and_total_order_counts(
    client, auth_headers, test_company, db_session
):
    customer, product, warehouse = await create_dashboard_company_context(
        client, auth_headers, test_company, db_session, "SEM"
    )

    invoiced_order = await create_order(
        client, auth_headers, customer, product, warehouse, statuses=["confirmed"]
    )
    non_invoiced_order = await create_order(
        client, auth_headers, customer, product, warehouse, statuses=["confirmed", "preparing"]
    )

    # Invoice + issue only the first order.
    invoice_response = await client.post(
        "/api/v1/invoices/generate",
        json={
            "order_id": invoiced_order,
            "idempotency_key": "dash-sem-invoice",
            "invoice_date": "2026-08-05",
            "due_date": "2026-08-19",
        },
        headers=auth_headers,
    )
    assert invoice_response.status_code == 200, invoice_response.text
    invoice = invoice_response.json()["data"]
    assert invoice["status"] == "issued"

    dashboard_response = await client.get(
        "/api/v1/dashboard/summary?period=30d",
        headers=auth_headers,
    )
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()["data"]

    # Revenue is the issued invoice total only (2 x 100 = 200, no VAT).
    assert dashboard["total_revenue"] == 200.0
    # One of the two active orders has an invoice.
    assert dashboard["invoiced_orders_count"] == 1
    assert dashboard["total_orders_count"] == 2

    # KPI card must expose revenue directly (frontend bug: used monthly_revenue).
    assert dashboard["kpi"]["total_revenue"] == 200.0

    # Tooltip explains the semantics for the revenue KPI.
    revenue_tooltip = next(
        t for t in dashboard["kpi_tooltips"] if t["key"] == "total_revenue"
    )
    assert "ინვოის" in revenue_tooltip["formula"]


@pytest.mark.asyncio
async def test_dashboard_revenue_counts_only_issued_invoices(
    client, auth_headers, test_company, db_session
):
    customer, product, warehouse = await create_dashboard_company_context(
        client, auth_headers, test_company, db_session, "ONLY-ISSUED"
    )

    order_id = await create_order(
        client, auth_headers, customer, product, warehouse, statuses=["confirmed"]
    )

    # Order creation auto-creates a DRAFT invoice; drafts must not count as revenue.
    invoice = (
        await db_session.execute(
            select(Invoice).where(Invoice.order_id == order_id)
        )
    ).scalar_one_or_none()
    assert invoice is not None
    assert invoice.status == "draft"

    dashboard_response = await client.get(
        "/api/v1/dashboard/summary?period=30d",
        headers=auth_headers,
    )
    dashboard = dashboard_response.json()["data"]
    assert dashboard["total_revenue"] == 0.0
