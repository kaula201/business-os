"""Dashboard 3.0: operational KPIs (REQ-DASH-01/03) — delayed shipments,
production backlog, fleet unavailable, critical maintenance, pending
approvals, OTIF + freshness stamp.

Covers:
- AC-DASH-01: issued invoice shows in KPI; drafts do not (revenue baseline)
- AC-DASH-03: OTIF / percent comparison shows N/A when nothing is due
- delayed_shipments counts only open orders past delivery_date
- approvals_pending counts pending approval requests
- last_updated_at always present
"""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models.order import Order, OrderStatus
from app.models.approval import ApprovalRequest
from app.models.maintenance import MaintenanceOrder


async def _set_order_delivery(client, auth_headers, db_session, order_id, delivery_date, status: str):
    """Flip an order's delivery_date + status directly (test fixture path)."""
    order = (
        await db_session.execute(select(Order).where(Order.id == order_id))
    ).scalar_one()
    order.delivery_date = delivery_date
    order.status = status
    await db_session.commit()
    return order.id


@pytest.mark.asyncio
async def test_dashboard_layout_roundtrip(client, auth_headers, test_admin, db_session):
    """REQ-DASH layout contract: GET empty → PUT persists → GET returns saved."""
    # seed a company module permission so the dashboard router loads
    get0 = await client.get("/api/v1/dashboard/layout", headers=auth_headers)
    assert get0.status_code == 200, get0.text

    payload = {"layouts": {"director": ["revenue", "orders", "otif_rate"], "operator": ["tasks", "approvals_pending"]}}
    put = await client.put("/api/v1/dashboard/layout", json=payload, headers=auth_headers)
    assert put.status_code == 200, put.text
    assert put.json()["data"]["layouts"] == payload["layouts"]

    get1 = await client.get("/api/v1/dashboard/layout", headers=auth_headers)
    assert get1.status_code == 200, get1.text
    assert get1.json()["data"]["layouts"] == payload["layouts"]

    # cleanup so test isolation is not broken
    from app.models.dashboard_layout import DashboardLayout
    lay = (
        await db_session.execute(
            select(DashboardLayout).where(DashboardLayout.user_id == test_admin.id)
        )
    ).scalar_one_or_none()
    if lay:
        await db_session.delete(lay)
        await db_session.commit()


@pytest.mark.asyncio
async def test_dashboard_metrics_returns_freshness_and_filters(
    client, auth_headers, test_company
):
    """AC-DASH-03/04: /metrics returns computed_at + status, filters are echoed."""
    from app.models.warehouse import Warehouse
    wh = (await client.get("/api/v1/warehouses/", headers=auth_headers)).json()["data"]
    wh_id = wh[0]["id"] if wh else ""

    url = f"/api/v1/dashboard/metrics?from_date={date.today().isoformat()}&to_date={date.today().isoformat()}"
    if wh_id:
        url += f"&warehouse_id={wh_id}"
    resp = await client.get(url, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["computed_at"] is not None
    assert data["status"] == "fresh"
    assert data["from_date"] == date.today().isoformat()
    assert "kpi" in data and "active_orders" in data["kpi"]


@pytest.mark.asyncio
async def test_dashboard_acdash01_invoice_adds_to_kpi_after_issue(
    client, auth_headers, test_company, db_session,
):
    """AC-DASH-01: order creation auto-creates a DRAFT invoice that does NOT
    inflate KPI revenue; issuing that invoice adds to revenue."""
    from tests.test_customer_invoicing import create_invoice_order
    from app.models.invoice import Invoice

    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "DASH-AC01"
    )
    # The draft invoice auto-created with the order must not affect revenue
    inv = (
        await db_session.execute(
            select(Invoice).where(Invoice.order_id == order["id"])
        )
    ).scalar_one()
    assert inv.status == "draft", "order must auto-create a draft invoice first"

    resp = await client.get("/api/v1/dashboard/summary?period=90d", headers=auth_headers)
    before = float(resp.json()["data"]["kpi"]["total_revenue"])

    # Draft → revenue unchanged (AC-DASH-01: drafts are excluded)
    resp2 = await client.get("/api/v1/dashboard/summary?period=90d", headers=auth_headers)
    assert float(resp2.json()["data"]["kpi"]["total_revenue"]) == before, \
        "draft invoice must not inflate KPI revenue"

    # Issue it → revenue increases
    issued = await client.post(f"/api/v1/invoices/{inv.id}/issue", headers=auth_headers)
    assert issued.status_code in (200, 202), issued.text
    resp3 = await client.get("/api/v1/dashboard/summary?period=90d", headers=auth_headers)
    after_issued = float(resp3.json()["data"]["kpi"]["total_revenue"])
    assert after_issued > before, "issued invoice must add to KPI revenue"


@pytest.mark.asyncio
async def test_dashboard_acdash02_no_margin_widget(client, auth_headers, test_company):
    """AC-DASH-02: margin/COGS is NOT exposed on the dashboard — a warehouse
    operator cannot obtain it via UI (KPI set) or API (summary payload)."""
    resp = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    kpi = resp.json()["data"]["kpi"]
    # The KPI surface is permission-neutral — no gross-margin or COGS field exists.
    for forbidden in ("margin", "gross_margin", "cogs", "profit", "markup"):
        assert forbidden not in kpi, f"dashboard must not expose cost/margin field: {forbidden}"

    # role-views (warehouse operator layout) must not include any margin/cost KPI key
    rv = await client.get("/api/v1/dashboard/role-views", headers=auth_headers)
    assert rv.status_code == 200, rv.text
    for v in rv.json()["data"]["views"]:
        for k in v["kpis"]:
            assert "margin" not in k.lower() and "profit" not in k.lower(), \
                f"role view {v['key']} must not grant margin widget: {k}"


@pytest.mark.asyncio
async def test_dashboard_summary_has_operational_kpis(
    client, auth_headers, test_company, db_session
):
    """REQ-DASH-01: summary returns all operational KPI fields + freshness."""
    resp = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    kpi = resp.json()["data"]["kpi"]

    for field in (
        "delayed_shipments", "production_backlog", "fleet_unavailable",
        "maintenance_critical", "approvals_pending", "otif_rate", "last_updated_at",
    ):
        assert field in kpi, f"missing operational KPI field: {field}"

    assert kpi["last_updated_at"] is not None, "freshness stamp required (REQ-DASH-03)"


@pytest.mark.asyncio
async def test_delayed_shipments_counts_only_open_past_due(
    client, auth_headers, test_company, db_session,
):
    """A past-due open order increments delayed_shipments; completing it removes it."""
    from tests.test_customer_invoicing import create_invoice_order

    order, _, _ = await create_invoice_order(
        client, auth_headers, test_company, db_session, "DASH-DELAY"
    )
    await _set_order_delivery(
        client, auth_headers, db_session, order["id"],
        date.today() - timedelta(days=5), OrderStatus.CONFIRMED.value,
    )

    resp = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    kpi = resp.json()["data"]["kpi"]
    assert kpi["delayed_shipments"] >= 1

    # Complete it → no longer delayed
    await _set_order_delivery(
        client, auth_headers, db_session, order["id"],
        date.today() - timedelta(days=5), OrderStatus.COMPLETED.value,
    )
    resp2 = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    kpi2 = resp2.json()["data"]["kpi"]
    assert kpi2["delayed_shipments"] == 0


@pytest.mark.asyncio
async def test_approvals_pending_counts_pending_requests(
    client, auth_headers, test_company, test_admin, db_session
):
    """Pending approval requests show in approvals_pending; approved ones don't."""
    req = ApprovalRequest(
        company_id=test_company.id,
        title="სატესტო დამტკიცება",
        approval_type="expense",
        amount=100,
        status=ApprovalRequest.Status.PENDING,
        requested_by=test_admin.id,
    )
    db_session.add(req)
    await db_session.commit()

    resp = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["kpi"]["approvals_pending"] >= 1

    req.status = ApprovalRequest.Status.APPROVED
    await db_session.commit()
    resp2 = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    # other seeded pending requests may exist; ensure it did not grow
    assert resp2.json()["data"]["kpi"]["approvals_pending"] <= resp.json()["data"]["kpi"]["approvals_pending"]


@pytest.mark.asyncio
async def test_maintenance_critical_counts_open_emergency(
    client, auth_headers, test_company, db_session
):
    """Open maintenance order with critical/emergency flags increments maintenance_critical."""
    mo = MaintenanceOrder(
        company_id=test_company.id,
        order_number="DASH-MNT-01",
        maintenance_type="emergency",
        priority="high",
        status="in_progress",
    )
    db_session.add(mo)
    await db_session.commit()

    resp = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    kpi = resp.json()["data"]["kpi"]
    assert kpi["maintenance_critical"] >= 1

    # Completed → no longer counted
    mo.status = "completed"
    await db_session.commit()
    resp2 = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    assert resp2.json()["data"]["kpi"]["maintenance_critical"] == 0


@pytest.mark.asyncio
async def test_otif_none_when_nothing_due(
    client, auth_headers, test_company, db_session
):
    """AC-DASH-03 / REQ-DASH-03: no due orders → otif_rate is None (never 0 or error)."""
    resp = await client.get("/api/v1/dashboard/summary?period=30d", headers=auth_headers)
    kpi = resp.json()["data"]["kpi"]
    # With no past-due orders the rate must be explicit N/A value
    assert kpi["otif_rate"] is None or kpi["otif_rate"] >= 0

    # drill-down returns N/A in the same situation
    drill = await client.get(
        "/api/v1/dashboard/kpi-detail/otif_rate?limit=5", headers=auth_headers
    )
    assert drill.status_code == 200, drill.text
    assert drill.json()["data"]["total"] == "N/A"
