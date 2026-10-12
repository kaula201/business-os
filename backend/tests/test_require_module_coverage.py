"""Tests for #52 / REQ-PKG: every API route must be protected by a module guard.

Router-level guards are implemented in app/api/v1/router.py.
Real HTTP requests are used to catch require_module 500s (#40).
"""
import re
import uuid
from typing import Dict, List, Set, Tuple

import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.core.modules import BASE_MODULE_CODES
from app.core.security import create_access_token
from seed_modules import MODULES
from tests.test_register_paid_routes_forbidden import _register_user, _invite_user, _role_values


# ---------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------

def guard_codes(dependant) -> Set[str]:
    """Recursively collect module codes from require_module dependencies."""
    codes: Set[str] = set()
    for dep in dependant.dependencies:
        call = dep.call
        if call and call.__qualname__.startswith("require_module.<locals>"):
            if call.__closure__:
                for var, cell in zip(call.__code__.co_freevars, call.__closure__):
                    if var == "module_code":
                        codes.add(cell.cell_contents)
        elif call is not None and getattr(call, "__name__", "") == "require_module_toggler":
            # app/core/module_toggle.py runs require_module("settings", "can_edit") inline.
            codes.add("settings")
        codes.update(guard_codes(dep))
    return codes


# Allowlist: paths that are public or BASE‑only and need no module guard
ALLOWLIST_PREFIXES = (
    "/api/v1/auth/",                  # auth endpoints (login, register, password reset)
    "/api/v1/users/",                 # user management (own account, invitations) - BASE
    "/api/v1/companies/me",           # own company settings - BASE
    "/api/v1/clients/",               # clients module is BASE
    "/api/v1/modules/",               # module catalog and entitlement; POST /modules/permissions/{id} 500 is #47
    "/api/v1/notifications/",         # cross-module inbox, own rows only
    "/api/v1/saas/",                  # billing needed to buy modules
    "/api/v1/vendor-auth/",           # vendor portal own auth
    "/api/v1/ecommerce/storefront/",  # public storefront
    "/api/v1/search",                 # BASE; per-section module filtering in search.py
    "/api/v1/dashboard/",             # BASE (#52 decision); paid widgets gated per module in dashboard*.py
    "/api/v1/api-keys/",              # BASE (#52 decision)
)

# Products catalog (name, price, VAT, categories, variants, images) is BASE (#52
# decision); stock routes in the same router stay under inventory.
PRODUCTS_PREFIX = "/api/v1/products/"
PRODUCTS_INVENTORY_PATHS = {"/api/v1/products/adjust-stock", "/api/v1/products/stock-movements"}
ALLOWLIST_EXACT = {"/", "/health"}

# Routes that can never be reached because an earlier route shadows them
# (pre-existing on main, reported separately). The request would hit the
# shadowing route instead, so the 403 check would test the wrong endpoint.
SHADOWED = {
    ("GET", "/api/v1/products/stock-movements"),  # shadowed by GET /products/{product_id} (422)
}

# Pre-existing 500s unrelated to entitlement; the entitled-router smoke test
# picks another route of the same router. Reported separately.
KNOWN_500 = {
    "/api/v1/warehouses/valuation",  # Product.cost_price does not exist (warehouses_enhanced.py)
    "/api/v1/modules/permissions/{module_id}",  # #47
}


ROUTES = [r for r in app.routes if isinstance(r, APIRoute)]


def is_allowlisted(path: str) -> bool:
    if path in ALLOWLIST_EXACT:
        return True
    if path.startswith(PRODUCTS_PREFIX) and path not in PRODUCTS_INVENTORY_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in ALLOWLIST_PREFIXES)


# Guarded routes: non-allowlisted and with at least one require_module code
GUARDED: List[Tuple[APIRoute, str, List[str]]] = []
for r in ROUTES:
    if not is_allowlisted(r.path):
        codes = guard_codes(r.dependant)
        if codes:
            for method in sorted(r.methods):
                GUARDED.append((r, method, sorted(codes)))


def concrete(path: str) -> str:
    """Replace path parameters with a UUID."""
    return re.sub(r"\{[^}]*\}", "00000000-0000-0000-0000-000000000001", path)


# ---------------------------------------------------------------
# Static coverage tests
# ---------------------------------------------------------------

def test_every_non_allowlisted_route_has_require_module():
    missing = []
    for r in ROUTES:
        if not is_allowlisted(r.path) and not guard_codes(r.dependant):
            missing.append(r.path)
    assert missing == [], f"Routes missing require_module guard: {missing}"


def test_every_guard_code_is_in_catalog():
    valid_codes = {m[0] for m in MODULES}
    violations = []
    for r in ROUTES:
        codes = guard_codes(r.dependant)
        for code in codes:
            if code not in valid_codes:
                violations.append((code, r.path))
    assert violations == [], f"Guard codes not in catalog: {violations}"


def test_allowlist_entries_are_used():
    unused_prefixes = []
    for prefix in ALLOWLIST_PREFIXES:
        if not any(r.path.startswith(prefix) for r in ROUTES):
            unused_prefixes.append(prefix)
    unused_exact = []
    for exact in ALLOWLIST_EXACT:
        if not any(r.path == exact for r in ROUTES):
            unused_exact.append(exact)
    assert unused_prefixes == [] and unused_exact == [], (
        f"Unused allowlist entries: prefixes={unused_prefixes}, exact={unused_exact}"
    )


# ---------------------------------------------------------------
# Dynamic tests (real HTTP)
# ---------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("role", _role_values())
async def test_base_only_company_gets_403_on_every_guarded_route(client, role):
    """A company without the required modules must receive 403 on guarded routes."""
    suffix = uuid.uuid4().hex[:8]
    email = f"user_{suffix}@example.com"
    token, user_id, company_id = await _register_user(client, email, "password123", "Test User", "Test Company")

    if role == "admin":
        headers = {"Authorization": f"Bearer {token}"}
    else:
        invited_id = await _invite_user(client, token, f"invite_{suffix}@example.com", "Invited User", role)
        access_token = create_access_token({"sub": invited_id, "company_id": company_id, "role": role})
        headers = {"Authorization": f"Bearer {access_token}"}

    failures = []
    for route, method, codes in GUARDED:
        path = route.path
        if set(codes).issubset(set(BASE_MODULE_CODES)):
            continue  # base modules are allowed
        if (method, path) in SHADOWED:
            continue
        concrete_path = concrete(path)
        json_body = {} if method in ("POST", "PUT", "PATCH") else None
        response = await client.request(method, concrete_path, headers=headers, json=json_body)
        if response.status_code != 403:
            failures.append((path, method, response.status_code))

    assert failures == [], f"Expected 403 for base-only company, got: {failures[:30]}"


@pytest.mark.asyncio
async def test_entitled_company_reaches_each_guarded_router(client, auth_headers):
    """A company with all modules enabled should not get 403/500 on any guarded router."""
    module_route: Dict[str, APIRoute] = {}
    for route, method, codes in GUARDED:
        module = route.endpoint.__module__
        if module not in module_route:
            # choose a representative route for this module
            candidates = [
                r for r in ROUTES
                if r.endpoint.__module__ == module and not is_allowlisted(r.path) and guard_codes(r.dependant)
                and r.path not in KNOWN_500
            ]
            best = None
            # prefer GET without path parameters
            for r in candidates:
                if "GET" in r.methods and "{" not in r.path:
                    best = r
                    break
            if not best:
                for r in candidates:
                    if "GET" in r.methods:
                        best = r
                        break
            if not best and candidates:
                best = candidates[0]
            if best:
                module_route[module] = best

    failures = []
    for module, route in module_route.items():
        path = route.path
        if path == "/api/v1/modules/permissions/{module_id}":
            continue  # known issue #47
        method = sorted(route.methods)[0]
        concrete_path = concrete(path)
        json_body = {} if method in ("POST", "PUT", "PATCH") else None
        try:
            response = await client.request(method, concrete_path, headers=auth_headers, json=json_body)
        except Exception as exc:  # the ASGI test transport re-raises server errors
            failures.append((path, method, f"500 {type(exc).__name__}: {exc}"[:200]))
            continue
        if response.status_code in (403, 500):
            failures.append((path, method, response.status_code))

    assert failures == [], f"Entitled company got unexpected status: {failures}"


@pytest.mark.asyncio
async def test_base_only_company_gets_base_dashboard_products_and_api_keys(client):
    """#52 decisions: dashboard, product catalog and API keys are BASE; paid widgets are neutral."""
    suffix = uuid.uuid4().hex[:8]
    token, _, _ = await _register_user(
        client, f"base_{suffix}@example.com", "password123", "Base User", f"Base {suffix}"
    )
    headers = {"Authorization": f"Bearer {token}"}

    for path in ("/api/v1/dashboard/summary", "/api/v1/products/", "/api/v1/api-keys/"):
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200, (path, resp.status_code, resp.text[:200])

    kpi = (await client.get("/api/v1/dashboard/summary", headers=headers)).json()["data"]["kpi"]
    for key in ("active_orders", "total_revenue", "receivables_outstanding", "payables_outstanding",
                "stock_value", "pipeline_value", "production_backlog", "fleet_unavailable"):
        assert not kpi.get(key), (key, kpi.get(key))

    # Paid-module drill-down stays closed.
    resp = await client.get("/api/v1/dashboard/kpi-detail/orders", headers=headers)
    assert resp.status_code in (403, 404), resp.text[:200]

    # Initial stock needs the inventory module.
    resp = await client.post(
        "/api/v1/products/",
        json={"name": f"P {suffix}", "sku": f"SKU-{suffix}", "sale_price": 10, "current_stock": 5},
        headers=headers,
    )
    assert resp.status_code in (403, 422), resp.text[:200]
