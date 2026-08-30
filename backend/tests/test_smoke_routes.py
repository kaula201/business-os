"""Phase A — automated smoke tests for every route family.

Every registered module router must:
  1. reject unauthenticated GETs (401/403 — auth guard present);
  2. answer authenticated reads without raising 500 (server errors).
This catches dead routes, broken auth, and schema drift across the whole app
surface — the automated trust gate before every financial change.
"""
import pytest

# (path, method) — representative read endpoint per module family
SMOKE_PATHS = [
    ("/api/v1/dashboard/summary", "get"),
    ("/api/v1/clients/", "get"),
    ("/api/v1/crm/opportunities", "get"),
    ("/api/v1/orders/", "get"),
    ("/api/v1/invoices/", "get"),
    ("/api/v1/products/", "get"),
    ("/api/v1/hr/employees", "get"),
    ("/api/v1/hr/payroll", "get"),
    ("/api/v1/hr/payslips", "get"),
    ("/api/v1/payroll-engine/structures", "get"),
    ("/api/v1/payroll-engine/parameters", "get"),
    ("/api/v1/payroll-engine/work-entries", "get"),
    ("/api/v1/payroll-engine/adjustments", "get"),
    ("/api/v1/suppliers/", "get"),
    ("/api/v1/procurement/rfqs", "get"),
    ("/api/v1/purchase-orders/", "get"),
    ("/api/v1/projects/", "get"),
    ("/api/v1/projects/templates", "get"),
    ("/api/v1/analytic/accounts", "get"),
    ("/api/v1/analytic/ar-ap-reconciliation", "get"),
    ("/api/v1/accounting-periods", "get"),
    ("/api/v1/gl/consolidated/checks", "get"),
    ("/api/v1/gl/trial-balance/", "get"),
    ("/api/v1/gl/profit-loss/", "get"),
    ("/api/v1/bank-accounts/", "get"),
    ("/api/v1/tax-reports/vat", "get"),
    ("/api/v1/automations/", "get"),
    ("/api/v1/studio/apps", "get"),
    ("/api/v1/platform/custom-fields", "get"),
    ("/api/v1/helpdesk/teams", "get"),
    ("/api/v1/marketplace/apps", "get"),
    ("/api/v1/quality-control/control-points", "get"),
    ("/api/v1/pos/orders", "get"),
    ("/api/v1/maintenance/plans", "get"),
    ("/api/v1/notifications/", "get"),
    ("/api/v1/recruitment/", "get"),
    ("/api/v1/inventory/valuation/methods", "get"),
    ("/api/v1/approvals/", "get"),
]


@pytest.mark.parametrize("path,method", SMOKE_PATHS)
async def test_route_requires_auth(client, path, method):
    """All route families must reject anonymous access (guard present)."""
    resp = await client.request(method, path)
    assert resp.status_code in (401, 403), (
        f"{path} → {resp.status_code}: auth guard missing"
    )


@pytest.mark.parametrize("path,method", SMOKE_PATHS)
async def test_route_answers_authed(client, auth_headers, path, method):
    """Authenticated reads must never 500 (dead routes / schema drift)."""
    resp = await client.request(method, path, headers=auth_headers)
    assert resp.status_code < 500, f"{path} → {resp.status_code}: {resp.text[:300]}"


async def test_auth_login_flow(client, test_admin):
    """Auth itself works (positive control)."""
    resp = await client.post("/api/v1/auth/login", json={"email": test_admin.email, "password": "admin123"})
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]
