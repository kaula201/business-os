"""SAL standalone module-boundary tests.

Issue #21 first slice: SAL (quotations, orders, invoices, price-lists) must
work with only BASE modules. Client registry is BASE master data.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.modules import is_module_enabled
from app.core.security import hash_password
from app.models.company import Company
from app.models.gl import JournalEntry
from app.models.invoice import Invoice
from app.models.module import AppModule, CompanyModule, ModulePermission
from app.models.order import InventoryReservation, OrderFulfillment
from app.models.product import Product
from app.models.receivable import CustomerReceivable
from app.models.user import User
from seed_modules import DEFAULT_PERMISSIONS, MODULES, permission_flags

SAL_CODES = {"settings", "quotations", "orders", "invoices", "price-lists"}


async def _seed_catalog(db_session):
    for code, name, description, icon, route, category, sort_order, depends_on in MODULES:
        module = (
            await db_session.execute(
                select(AppModule).where(AppModule.code == code)
            )
        ).scalar_one_or_none()
        if module is None:
            module = AppModule(
                code=code,
                name=name,
                description=description,
                icon=icon,
                route=route,
                category=category,
                sort_order=sort_order,
                depends_on=depends_on,
            )
            db_session.add(module)
            await db_session.flush()
        for role in DEFAULT_PERMISSIONS:
            perm = (
                await db_session.execute(
                    select(ModulePermission).where(
                        ModulePermission.module_id == module.id,
                        ModulePermission.role == role,
                    )
                )
            ).scalar_one_or_none()
            if perm is None:
                db_session.add(
                    ModulePermission(
                        module_id=module.id,
                        role=role,
                        **permission_flags(code, role),
                    )
                )
    await db_session.commit()


async def _set_modules(db_session, company_id, enabled_codes):
    modules = (await db_session.execute(select(AppModule))).scalars().all()
    for module in modules:
        db_session.add(
            CompanyModule(
                company_id=company_id,
                module_id=module.id,
                enabled=module.code in enabled_codes,
            )
        )
    await db_session.commit()


async def _create_company(db_session, name="SAL Standalone"):
    company = Company(
        name=name,
        identification_code="SAL-001",
        vat_status=True,
        currency="GEL",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company


async def _create_manager_headers(client, db_session, company_id, suffix):
    email = f"sal-manager-{suffix}@test.ge"
    user = User(
        company_id=company_id,
        email=email,
        hashed_password=hash_password("manager123"),
        full_name="SAL Manager",
        role=User.Role.MANAGER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "manager123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


async def _create_sal_context(client, db_session, enabled_codes, suffix):
    company = await _create_company(db_session, f"SAL {suffix}")
    await _seed_catalog(db_session)
    await _set_modules(db_session, company.id, enabled_codes)
    headers = await _create_manager_headers(client, db_session, company.id, suffix)
    return company, headers


async def _create_client(client, headers, suffix):
    response = await client.post(
        "/api/v1/clients/",
        headers=headers,
        json={
            "name": f"SAL Client {suffix}",
            "client_type": "legal",
            "identification_code": f"SAL-CLIENT-{suffix}",
            "vat_status": True,
            "address": "თბილისი",
            "status": "active",
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]["id"]


async def _create_product(db_session, company_id, suffix):
    # Products are created via TestSessionLocal because the products module is
    # outside SAL and not required for the standalone boundary test.
    product = Product(
        company_id=company_id,
        sku=f"SAL-SKU-{suffix}",
        name=f"SAL Product {suffix}",
        sale_price=Decimal("100.00"),
        current_stock=10,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


async def _create_order(client, headers, client_id, product):
    response = await client.post(
        "/api/v1/orders/",
        headers=headers,
        json={
            "client_id": client_id,
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
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def invoice_payload(order_id: str, suffix: str):
    today = date.today()
    return {
        "order_id": order_id,
        "idempotency_key": f"sal-invoice-{suffix}",
        "invoice_date": today.isoformat(),
        "due_date": (today + timedelta(days=14)).isoformat(),
    }


async def _count(db_session, model, company_id):
    return (
        await db_session.execute(
            select(func.count()).select_from(model).where(model.company_id == company_id)
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_sal_base_only_full_flow(client, db_session):
    enabled = {"settings", "quotations", "orders", "invoices", "price-lists"}
    company, headers = await _create_sal_context(client, db_session, enabled, "BASE")
    client_id = await _create_client(client, headers, "BASE")
    product = await _create_product(db_session, company.id, "BASE")
    order = await _create_order(client, headers, client_id, product)

    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "BASE"),
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["data"]["status"] == "issued"

    assert await _count(db_session, CustomerReceivable, company.id) == 0
    assert await _count(db_session, JournalEntry, company.id) == 0
    assert await _count(db_session, OrderFulfillment, company.id) == 0
    assert await _count(db_session, InventoryReservation, company.id) == 0


@pytest.mark.asyncio
async def test_sal_with_fin_writes_receivable_without_gl(client, db_session):
    enabled = SAL_CODES | {"customer-finance"}
    company, headers = await _create_sal_context(client, db_session, enabled, "FIN")
    client_id = await _create_client(client, headers, "FIN")
    product = await _create_product(db_session, company.id, "FIN")
    order = await _create_order(client, headers, client_id, product)

    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "FIN"),
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["data"]["status"] == "issued"

    assert await _count(db_session, CustomerReceivable, company.id) == 1
    assert await _count(db_session, JournalEntry, company.id) == 0


@pytest.mark.asyncio
async def test_sal_with_acc_missing_accounts_returns_422(client, db_session):
    enabled = SAL_CODES | {"gl"}
    company, headers = await _create_sal_context(client, db_session, enabled, "ACC")
    client_id = await _create_client(client, headers, "ACC")
    product = await _create_product(db_session, company.id, "ACC")
    order = await _create_order(client, headers, client_id, product)

    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    response = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "ACC"),
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert "ანგარიში" in response.json()["detail"]

    invoice = (
        await db_session.execute(
            select(Invoice).where(Invoice.order_id == order["id"])
        )
    ).scalar_one()
    assert invoice.status == "draft"
    assert await _count(db_session, CustomerReceivable, company.id) == 0


@pytest.mark.asyncio
async def test_sal_with_wms_requires_warehouse(client, db_session):
    enabled = SAL_CODES | {"inventory"}
    company, headers = await _create_sal_context(client, db_session, enabled, "WMS")
    client_id = await _create_client(client, headers, "WMS")
    product = await _create_product(db_session, company.id, "WMS")
    order = await _create_order(client, headers, client_id, product)

    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 409, confirmed.text


# ── unit tests for is_module_enabled ──────────────────────────────────────

@pytest.mark.asyncio
async def test_is_module_enabled_base_code_true(db_session):
    company_id = uuid.uuid4()
    assert await is_module_enabled(db_session, company_id, "settings") is True
    assert await is_module_enabled(db_session, company_id, "clients") is True


@pytest.mark.asyncio
async def test_is_module_enabled_disabled_row_false(db_session):
    company = await _create_company(db_session, "Module Unit Disabled")
    module = AppModule(code="module-a", name="Module A", category="test", is_active=True)
    db_session.add(module)
    await db_session.flush()
    db_session.add(CompanyModule(company_id=company.id, module_id=module.id, enabled=False))
    await db_session.commit()

    assert await is_module_enabled(db_session, company.id, "module-a") is False


@pytest.mark.asyncio
async def test_is_module_enabled_missing_row_true(db_session):
    company = await _create_company(db_session, "Module Unit Missing")
    module = AppModule(code="module-b", name="Module B", category="test", is_active=True)
    db_session.add(module)
    await db_session.commit()

    assert await is_module_enabled(db_session, company.id, "module-b") is True


@pytest.mark.asyncio
async def test_is_module_enabled_unknown_code_false(db_session):
    company = await _create_company(db_session, "Module Unit Unknown")
    assert await is_module_enabled(db_session, company.id, "module-unknown") is False
