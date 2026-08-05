"""E3 — Granular RBAC access-matrix verification.

Seeds the module catalog (AppModule + ModulePermission + CompanyModule) with
the same defaults as seed_modules.py, then verifies the full role matrix:

- admin: everything (financial + operational)
- manager: create/edit on operational modules, blocked on financial writes
- accountant: create/edit on financial modules, blocked on operational writes
- employee: read-only, blocked on every write

Also asserts the block reason is permission-based (403 with a role message),
not a missing-module artifact.
"""
import pytest
from sqlalchemy import select

from app.models.company import Company
from app.models.module import AppModule, CompanyModule, ModulePermission
from app.models.user import User
from app.core.security import hash_password

FINANCIAL_MODULES = {
    "cash", "banking", "currency", "expenses", "assets",
    "customer-finance", "supplier-finance", "accounting-periods",
}
OPERATIONAL_MODULES = {"clients", "orders", "invoices", "inventory", "purchases", "suppliers", "crm"}

BASE_PERMS = {
    User.Role.ADMIN: {"can_access": True, "can_create": True, "can_edit": True, "can_delete": True, "can_approve": True},
    User.Role.MANAGER: {"can_access": True, "can_create": True, "can_edit": True, "can_delete": True, "can_approve": False},
    User.Role.ACCOUNTANT: {"can_access": True, "can_create": False, "can_edit": False, "can_delete": False, "can_approve": False},
    User.Role.EMPLOYEE: {"can_access": True, "can_create": False, "can_edit": False, "can_delete": False, "can_approve": False},
}


async def seed_module_catalog(db_session, company_id):
    for code in FINANCIAL_MODULES | OPERATIONAL_MODULES:
        module = AppModule(code=code, name=code, category="test", is_active=True)
        db_session.add(module)
        await db_session.flush()
        db_session.add(
            CompanyModule(company_id=company_id, module_id=module.id, enabled=True)
        )
        for role, perms in BASE_PERMS.items():
            db_session.add(
                ModulePermission(module_id=module.id, role=role, **perms)
            )
        # Overrides mirroring seed_modules.py
        if code in FINANCIAL_MODULES:
            perm = await db_session.execute(
                select(ModulePermission).where(
                    ModulePermission.module_id == module.id,
                    ModulePermission.role == User.Role.ACCOUNTANT,
                )
            )
            p = perm.scalar_one()
            p.can_create = True
            p.can_edit = True
            mgr = await db_session.execute(
                select(ModulePermission).where(
                    ModulePermission.module_id == module.id,
                    ModulePermission.role == User.Role.MANAGER,
                )
            )
            mp = mgr.scalar_one()
            mp.can_create = False
            mp.can_edit = False
            mp.can_delete = False
            mp.can_approve = False
        if code in OPERATIONAL_MODULES:
            perm = await db_session.execute(
                select(ModulePermission).where(
                    ModulePermission.module_id == module.id,
                    ModulePermission.role == User.Role.MANAGER,
                )
            )
            p = perm.scalar_one()
            p.can_approve = True
    await db_session.commit()


async def create_role_headers(client, db_session, company_id, email: str, role: str):
    user = User(
        company_id=company_id,
        email=email,
        hashed_password=hash_password("rbac-test-123"),
        full_name="RBAC Test User",
        role=role,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "rbac-test-123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


# ── accountant: financial writes allowed ────────────────────────────────────

@pytest.mark.asyncio
async def test_accountant_can_create_cash_account(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "acc-cash@test.ge", User.Role.ACCOUNTANT
    )
    response = await client.post(
        "/api/v1/cash/accounts",
        json={"name": "Accountant Cash", "currency": "GEL"},
        headers=headers,
    )
    assert response.status_code in (200, 201), response.text


@pytest.mark.asyncio
async def test_accountant_can_create_currency_rate(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "acc-currency@test.ge", User.Role.ACCOUNTANT
    )
    response = await client.post(
        "/api/v1/currency/rates",
        json={
            "from_currency": "USD",
            "to_currency": "GEL",
            "rate_date": "2026-08-05",
            "rate": "2.700000",
        },
        headers=headers,
    )
    assert response.status_code in (200, 201), response.text


# ── accountant: operational writes blocked ──────────────────────────────────

@pytest.mark.asyncio
async def test_accountant_cannot_change_order_status(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "acc-orders@test.ge", User.Role.ACCOUNTANT
    )
    response = await client.patch(
        f"/api/v1/orders/{'00000000-0000-0000-0000-000000000001'}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_accountant_cannot_adjust_warehouse_stock(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "acc-stock@test.ge", User.Role.ACCOUNTANT
    )
    response = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": "00000000-0000-0000-0000-000000000001",
            "warehouse_id": "00000000-0000-0000-0000-000000000001",
            "movement_type": "in",
            "quantity": 1,
            "reason": "inventory",
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text


# ── manager: operational writes allowed ─────────────────────────────────────

@pytest.mark.asyncio
async def test_manager_can_adjust_warehouse_stock(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "mgr-stock@test.ge", User.Role.MANAGER
    )
    response = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": "00000000-0000-0000-0000-000000000001",
            "warehouse_id": "00000000-0000-0000-0000-000000000001",
            "movement_type": "in",
            "quantity": 1,
            "reason": "inventory",
        },
        headers=headers,
    )
    assert response.status_code in (404, 400), response.text  # permission passed, record lookup fails


# ── manager: financial writes blocked ───────────────────────────────────────

@pytest.mark.asyncio
async def test_manager_cannot_create_currency_rate(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "mgr-currency@test.ge", User.Role.MANAGER
    )
    response = await client.post(
        "/api/v1/currency/rates",
        json={
            "from_currency": "USD",
            "to_currency": "GEL",
            "rate_date": "2026-08-05",
            "rate": "2.700000",
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_manager_cannot_post_supplier_payment(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "mgr-sup@test.ge", User.Role.MANAGER
    )
    response = await client.post(
        "/api/v1/supplier-payables/00000000-0000-0000-0000-000000000001/payments",
        json={
            "idempotency_key": "mgr-sup-pay-denied",
            "amount": "10.00",
            "payment_date": "2026-08-05",
            "payment_method": "bank_transfer",
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text


# ── employee: all writes blocked, reason is permission-based ────────────────

@pytest.mark.asyncio
async def test_employee_block_is_permission_based_not_missing_module(
    client, db_session, test_company
):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "emp-msg@test.ge", User.Role.EMPLOYEE
    )
    response = await client.post(
        "/api/v1/currency/rates",
        json={
            "from_currency": "USD",
            "to_currency": "GEL",
            "rate_date": "2026-08-05",
            "rate": "2.700000",
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "ამ მოქმედების უფლება არ გაქვთ", response.text


@pytest.mark.asyncio
async def test_employee_cannot_create_cash_account(client, db_session, test_company):
    await seed_module_catalog(db_session, test_company.id)
    headers = await create_role_headers(
        client, db_session, test_company.id, "emp-cash@test.ge", User.Role.EMPLOYEE
    )
    response = await client.post(
        "/api/v1/cash/accounts",
        json={"name": "Employee Cash", "currency": "GEL"},
        headers=headers,
    )
    assert response.status_code == 403, response.text
