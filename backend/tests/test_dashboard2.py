"""Dashboard 2.0: AR/AP aging, cash flow, drill-down endpoints."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models.receivable import CustomerPayment
from app.models.purchase import SupplierPayable
from tests.test_customer_invoicing import create_invoice_order, invoice_payload
from tests.test_supplier_credit_reversals import create_approved_payable


@pytest.mark.asyncio
async def test_aging_and_drilldown_ar(
    client, auth_headers, test_company, db_session
):
    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, f"AR-D2"
    )
    issued = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "AR-D2"),
        headers=auth_headers,
    )
    assert issued.status_code == 200, issued.text

    # Age the receivable: due_date 45 days in the past -> 31-60 bucket
    await db_session.execute(
        select(CustomerPayment)  # no-op to keep import linted; actual update below
    )
    from app.models.receivable import CustomerReceivable
    rec = (
        await db_session.execute(
            select(CustomerReceivable).where(
                CustomerReceivable.company_id == test_company.id
            )
        )
    ).scalar_one()
    rec.due_date = date.today() - timedelta(days=45)
    await db_session.commit()

    aging = await client.get("/api/v1/dashboard/aging", headers=auth_headers)
    assert aging.status_code == 200, aging.text
    data = aging.json()["data"]
    assert float(data["ar_total"]) > 0
    buckets = {b["bucket"]: float(b["amount"]) for b in data["ar_buckets"]}
    assert buckets["31_60"] == float(data["ar_total"])

    drill = await client.get(
        "/api/v1/dashboard/drill-down/ar?bucket=31_60", headers=auth_headers
    )
    assert drill.status_code == 200, drill.text
    rows = drill.json()["data"]["rows"]
    assert len(rows) == 1
    assert rows[0]["days_overdue"] == 45


@pytest.mark.asyncio
async def test_cash_flow_aggregates_payments(
    client, auth_headers, test_company, db_session
):
    order, client_row, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "CF-D2"
    )
    issued = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "CF-D2"),
        headers=auth_headers,
    )
    assert issued.status_code == 200, issued.text
    invoice = issued.json()["data"]

    # Pay 100 today
    pay_res = await client.post(
        f"/api/v1/customer-receivables/{invoice['id']}/payments",
        json={
            "idempotency_key": "d2-cash-in",
            "amount": 100,
            "payment_date": date.today().isoformat(),
            "payment_method": "bank_transfer",
        },
        headers=auth_headers,
    )
    # The receivable id != invoice id; find it first
    if pay_res.status_code != 200:
        listing = await client.get(
            f"/api/v1/customer-receivables/?invoice_id={invoice['id']}&page_size=100",
            headers=auth_headers,
        )
        rec_id = listing.json()["data"]["items"][0]["id"]
        pay_res = await client.post(
            f"/api/v1/customer-receivables/{rec_id}/payments",
            json={
                "idempotency_key": "d2-cash-in",
                "amount": 100,
                "payment_date": date.today().isoformat(),
                "payment_method": "bank_transfer",
            },
            headers=auth_headers,
        )
    assert pay_res.status_code == 200, pay_res.text

    cf = await client.get("/api/v1/dashboard/cash-flow", headers=auth_headers)
    assert cf.status_code == 200, cf.text
    data = cf.json()["data"]
    assert len(data["series"]) == 6
    last = data["series"][-1]
    assert last["month"] == date.today().strftime("%Y-%m")
    assert float(last["inflow"]) == 100
    assert float(last["outflow"]) == 0


@pytest.mark.asyncio
async def test_ap_drilldown_reversal_currency_and_parameter_validation(
    client, auth_headers, test_company, db_session
):
    payable = await create_approved_payable(
        client, auth_headers, test_company, db_session, "D2-AP"
    )

    drill = await client.get(
        "/api/v1/dashboard/drill-down/ap", headers=auth_headers
    )
    assert drill.status_code == 200, drill.text
    drill_data = drill.json()["data"]
    assert drill_data["currency"] == "GEL"
    assert len(drill_data["rows"]) == 1
    assert drill_data["rows"][0]["counterparty"]
    assert drill_data["rows"][0]["number"]

    paid = await client.post(
        f"/api/v1/supplier-payables/{payable['id']}/payments",
        json={
            "idempotency_key": "d2-supplier-payment",
            "amount": 40,
            "payment_date": str(date.today()),
            "payment_method": "bank_transfer",
        },
        headers=auth_headers,
    )
    assert paid.status_code == 200, paid.text
    payment = paid.json()["data"]["payments"][0]

    before_reversal = await client.get(
        "/api/v1/dashboard/cash-flow", headers=auth_headers
    )
    assert before_reversal.status_code == 200, before_reversal.text
    assert float(before_reversal.json()["data"]["series"][-1]["outflow"]) == 40

    reversed_payment = await client.post(
        f"/api/v1/supplier-payments/{payment['id']}/reversal",
        json={
            "idempotency_key": "d2-supplier-reversal",
            "reason": "Dashboard reversal regression",
        },
        headers=auth_headers,
    )
    assert reversed_payment.status_code == 200, reversed_payment.text

    after_reversal = await client.get(
        "/api/v1/dashboard/cash-flow", headers=auth_headers
    )
    assert after_reversal.status_code == 200, after_reversal.text
    assert float(after_reversal.json()["data"]["series"][-1]["outflow"]) == 0

    payable_row = (
        await db_session.execute(
            select(SupplierPayable).where(SupplierPayable.id == payable["id"])
        )
    ).scalar_one()
    payable_row.currency_code = "USD"
    await db_session.commit()

    gel_aging = await client.get("/api/v1/dashboard/aging", headers=auth_headers)
    usd_aging = await client.get(
        "/api/v1/dashboard/aging?currency=usd", headers=auth_headers
    )
    assert gel_aging.status_code == 200, gel_aging.text
    assert usd_aging.status_code == 200, usd_aging.text
    assert gel_aging.json()["data"]["currency"] == "GEL"
    assert float(gel_aging.json()["data"]["ap_total"]) == 0
    assert usd_aging.json()["data"]["currency"] == "USD"
    assert float(usd_aging.json()["data"]["ap_total"]) == 100

    invalid_entity = await client.get(
        "/api/v1/dashboard/drill-down/invalid", headers=auth_headers
    )
    invalid_bucket = await client.get(
        "/api/v1/dashboard/drill-down/ap?bucket=invalid", headers=auth_headers
    )
    assert invalid_entity.status_code == 422
    assert invalid_bucket.status_code == 422
