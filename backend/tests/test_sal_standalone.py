"""SAL standalone module-boundary tests.

Issue #21 first slice: SAL (quotations, orders, invoices, price-lists) must
work with only BASE modules. Client registry is BASE master data.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from app.core.modules import is_module_enabled
from app.core.security import hash_password
from app.core.tenant_scope import TENANT_POLICY_PREDICATE
from app.models.company import Company
from app.models.gl import JournalEntry
from app.models.invoice import Invoice, InvoicePayment
from app.models.module import AppModule, CompanyModule, ModulePermission
from app.models.order import InventoryReservation, Order, OrderFulfillment
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
    """Replace CompanyModule rows so only enabled_codes have rows (fail-closed)."""
    modules = (await db_session.execute(select(AppModule))).scalars().all()
    existing_rows = (await db_session.execute(
        select(CompanyModule).where(CompanyModule.company_id == company_id)
    )).scalars().all()
    existing_by_module = {row.module_id: row for row in existing_rows}

    for module in modules:
        if module.code not in enabled_codes:
            if module.id in existing_by_module:
                await db_session.delete(existing_by_module[module.id])
            continue
        row = existing_by_module.get(module.id)
        if row is None:
            db_session.add(CompanyModule(company_id=company_id, module_id=module.id, enabled=True))
        else:
            row.enabled = True
    await db_session.commit()


async def _create_company(db_session, name="SAL Standalone"):
    company = Company(
        name=name,
        identification_code=f"SAL-{uuid.uuid4().hex[:8]}",
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


async def _create_admin_headers(client, db_session, company_id, suffix):
    email = f"sal-admin-{suffix}@test.ge"
    user = User(
        company_id=company_id,
        email=email,
        hashed_password=hash_password("admin123"),
        full_name="SAL Admin",
        role=User.Role.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "admin123"},
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
            "identification_code": "123456789",
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
@pytest.mark.asyncio
async def test_sal_no_rows_for_fin_and_gl_confirm_no_stock_and_payment_succeeds(client, db_session):
    enabled = SAL_CODES
    company, headers = await _create_sal_context(client, db_session, enabled, "FAILCLOSED")
    client_id = await _create_client(client, headers, "FAILCLOSED")
    product = await _create_product(db_session, company.id, "FAILCLOSED")
    order = await _create_order(client, headers, client_id, product)

    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "FAILCLOSED"),
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["data"]["status"] == "issued"

    assert await _count(db_session, CustomerReceivable, company.id) == 0
    assert await _count(db_session, JournalEntry, company.id) == 0
    assert await _count(db_session, OrderFulfillment, company.id) == 0
    assert await _count(db_session, InventoryReservation, company.id) == 0

    invoice_id = generated.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers=headers,
        json={"amount": 100, "payment_date": date.today().isoformat()},
    )
    assert resp.status_code == 200, resp.text
    assert await _count(db_session, InvoicePayment, company.id) == 1


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
    assert "ანგარიშ" in response.json()["detail"]

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
async def test_is_module_enabled_missing_row_false(db_session):
    company = await _create_company(db_session, "Module Unit Missing")
    module = AppModule(code="module-b", name="Module B", category="test", is_active=True)
    db_session.add(module)
    await db_session.commit()

    assert await is_module_enabled(db_session, company.id, "module-b") is False


@pytest.mark.asyncio
async def test_is_module_enabled_unknown_code_false(db_session):
    company = await _create_company(db_session, "Module Unit Unknown")
    assert await is_module_enabled(db_session, company.id, "module-unknown") is False


@pytest.mark.asyncio
async def test_cross_tenant_order_references_are_rejected(client, db_session):
    company_a, headers_a = await _create_sal_context(client, db_session, SAL_CODES, "XA")
    company_b, headers_b = await _create_sal_context(client, db_session, SAL_CODES, "XB")
    client_a = await _create_client(client, headers_a, "XA")
    client_b = await _create_client(client, headers_b, "XB")
    product_a = await _create_product(db_session, company_a.id, "XA")
    product_b = await _create_product(db_session, company_b.id, "XB")

    resp = await client.post(
        "/api/v1/orders/",
        headers=headers_a,
        json={
            "client_id": client_b,
            "items": [
                {
                    "product_id": str(product_a.id),
                    "product_name": product_a.name,
                    "quantity": 1,
                    "unit_price": 10,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": False,
        },
    )
    assert resp.status_code == 404

    resp = await client.post(
        "/api/v1/orders/",
        headers=headers_a,
        json={
            "client_id": client_a,
            "items": [
                {
                    "product_id": str(product_b.id),
                    "product_name": product_b.name,
                    "quantity": 1,
                    "unit_price": 10,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": False,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_quotation_references_are_rejected(client, db_session):
    company_a, headers_a = await _create_sal_context(client, db_session, SAL_CODES, "QA")
    company_b, headers_b = await _create_sal_context(client, db_session, SAL_CODES, "QB")
    client_a = await _create_client(client, headers_a, "QA")
    client_b = await _create_client(client, headers_b, "QB")
    product_a = await _create_product(db_session, company_a.id, "QA")
    product_b = await _create_product(db_session, company_b.id, "QB")
    today = date.today()
    base_payload = {
        "client_id": client_b,
        "quotation_date": today.isoformat(),
        "valid_until": (today + timedelta(days=30)).isoformat(),
        "currency": "GEL",
        "discount_percent": 0,
        "items": [
            {
                "product_id": str(product_a.id),
                "description": "x",
                "quantity": 1,
                "unit_price": 10,
                "discount_percent": 0,
                "is_optional": False,
            }
        ],
    }
    resp = await client.post("/api/v1/quotations/", headers=headers_a, json=base_payload)
    assert resp.status_code in (400, 404, 422)

    base_payload["client_id"] = client_a
    base_payload["items"][0]["product_id"] = str(product_b.id)
    resp = await client.post("/api/v1/quotations/", headers=headers_a, json=base_payload)
    assert resp.status_code in (400, 404, 422)


@pytest.mark.asyncio
async def test_cross_tenant_invoice_reference_is_rejected(client, db_session):
    company_a, headers_a = await _create_sal_context(client, db_session, SAL_CODES, "IA")
    company_b, headers_b = await _create_sal_context(client, db_session, SAL_CODES, "IB")
    client_b = await _create_client(client, headers_b, "IB")
    product_b = await _create_product(db_session, company_b.id, "IB")
    order_b_resp = await client.post(
        "/api/v1/orders/",
        headers=headers_b,
        json={
            "client_id": client_b,
            "items": [
                {
                    "product_id": str(product_b.id),
                    "product_name": product_b.name,
                    "quantity": 1,
                    "unit_price": 10,
                    "discount_percent": 0,
                }
            ],
            "is_vat_payer": False,
        },
    )
    assert order_b_resp.status_code == 200
    order_b = order_b_resp.json()["data"]
    resp = await client.post(
        "/api/v1/invoices/generate",
        headers=headers_a,
        json=invoice_payload(order_b["id"], "X"),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_individual_identification_code_masked_in_list_and_full_for_admin(client, db_session):
    company, _ = await _create_sal_context(client, db_session, SAL_CODES, "MASK")
    admin_headers = await _create_admin_headers(client, db_session, company.id, "MASK")
    resp = await client.post(
        "/api/v1/clients/",
        headers=admin_headers,
        json={
            "name": "Person Client",
            "client_type": "individual",
            "identification_code": "01234567890",
            "vat_status": True,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    client_data = resp.json()["data"]
    assert client_data["identification_code"] == "01234567890"

    list_resp = await client.get("/api/v1/clients/", headers=admin_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    target = next(i for i in items if i["id"] == client_data["id"])
    assert target["identification_code"] == "012*****890"

    get_resp = await client.get(f"/api/v1/clients/{client_data['id']}", headers=admin_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["identification_code"] == "01234567890"


async def _create_issued_invoice(client, headers, db_session, company, suffix):
    client_id = await _create_client(client, headers, suffix)
    product = await _create_product(db_session, company.id, suffix)
    order = await _create_order(client, headers, client_id, product)
    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], suffix),
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    return generated.json()["data"]


@pytest.mark.asyncio
async def test_sal_base_payment_partial_and_paid(client, db_session):
    company, headers = await _create_sal_context(client, db_session, SAL_CODES, "PAY")
    invoice = await _create_issued_invoice(client, headers, db_session, company, "PAY")
    invoice_id = invoice["id"]

    base_payment = {"amount": 100, "payment_date": date.today().isoformat()}
    resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/payments", headers=headers, json=base_payment
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["paid_amount"] == 100.0
    assert data["payment_status"] == "partial"

    resp2 = await client.post(
        f"/api/v1/invoices/{invoice_id}/payments", headers=headers, json=base_payment
    )
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()["data"]
    assert data2["paid_amount"] == 200.0
    assert data2["payment_status"] == "paid"

    overpay = await client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers=headers,
        json={"amount": 0.01, "payment_date": date.today().isoformat()},
    )
    assert overpay.status_code == 422

    assert await _count(db_session, CustomerReceivable, company.id) == 0
    assert await _count(db_session, InvoicePayment, company.id) == 2


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_invoice_payment_future_date_rejected(client, db_session):
    company, headers = await _create_sal_context(client, db_session, SAL_CODES, "FUTURE")
    invoice = await _create_issued_invoice(client, headers, db_session, company, "FUTURE")
    resp = await client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        headers=headers,
        json={"amount": 10, "payment_date": (date.today() + timedelta(days=1)).isoformat()},
    )
    assert resp.status_code == 422
    assert await _count(db_session, InvoicePayment, company.id) == 0


@pytest.mark.asyncio
async def test_invoice_payment_idempotency_key_replay_creates_one_row(client, db_session):
    company, headers = await _create_sal_context(client, db_session, SAL_CODES, "IDEM")
    invoice = await _create_issued_invoice(client, headers, db_session, company, "IDEM")
    payload = {"amount": 100, "payment_date": date.today().isoformat()}
    headers_with_key = {**headers, "Idempotency-Key": "pay-idem-1"}

    resp1 = await client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        headers=headers_with_key,
        json=payload,
    )
    assert resp1.status_code == 200, resp1.text

    resp2 = await client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        headers=headers_with_key,
        json=payload,
    )
    assert resp2.status_code == 200, resp2.text
    assert await _count(db_session, InvoicePayment, company.id) == 1


@pytest.mark.asyncio
async def test_sal_fin_payment_rejected_use_fin(client, db_session):
    enabled = SAL_CODES | {"customer-finance"}
    company, headers = await _create_sal_context(client, db_session, enabled, "FINPAY")
    invoice = await _create_issued_invoice(client, headers, db_session, company, "FINPAY")

    resp = await client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        headers=headers,
        json={"amount": 10, "payment_date": date.today().isoformat()},
    )
    assert resp.status_code == 409
    assert "კლიენტის ფინანსებში" in resp.json()["detail"]
    assert await _count(db_session, InvoicePayment, company.id) == 0
    assert await _count(db_session, CustomerReceivable, company.id) == 1


@pytest.mark.asyncio
async def test_cross_tenant_invoice_payment_is_rejected(client, db_session):
    company_a, headers_a = await _create_sal_context(client, db_session, SAL_CODES, "TPA")
    company_b, headers_b = await _create_sal_context(client, db_session, SAL_CODES, "TPB")
    invoice = await _create_issued_invoice(client, headers_a, db_session, company_a, "TPA")

    resp = await client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        headers=headers_b,
        json={"amount": 1, "payment_date": date.today().isoformat()},
    )
    assert resp.status_code == 404
    assert await _count(db_session, InvoicePayment, company_b.id) == 0


@pytest.mark.asyncio
async def test_invoice_payments_has_tenant_isolation_rls(db_session):
    result = await db_session.execute(text("""
        SELECT pol.policyname, c.relforcerowsecurity
        FROM pg_policies pol
        JOIN pg_class c ON c.relname = pol.tablename AND c.relnamespace = 'public'::regnamespace
        WHERE pol.schemaname = 'public'
          AND pol.tablename = 'invoice_payments'
          AND pol.policyname = 'tenant_isolation'
    """))
    row = result.first()
    assert row is not None
    assert row.policyname == "tenant_isolation"
    assert row.relforcerowsecurity is True


def test_invoice_payments_migration_has_rls_and_predicate():
    migration_file = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "154_invoice_payments.py"
    source = migration_file.read_text()
    assert "FORCE ROW LEVEL SECURITY" in source
    assert TENANT_POLICY_PREDICATE in source


@pytest.mark.asyncio
async def test_order_and_invoice_default_currency_gel(client, db_session):
    company, headers = await _create_sal_context(client, db_session, SAL_CODES, "GEL")
    client_id = await _create_client(client, headers, "GEL")
    product = await _create_product(db_session, company.id, "GEL")
    order = await _create_order(client, headers, client_id, product)

    order_obj = await db_session.get(Order, uuid.UUID(order["id"]))
    assert order_obj.currency == "GEL"

    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "GEL"),
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["data"]["currency"] == "GEL"


@pytest.mark.asyncio
async def test_quotation_default_currency_gel(client, db_session):
    company, headers = await _create_sal_context(client, db_session, SAL_CODES, "QTGEL")
    client_id = await _create_client(client, headers, "QTGEL")
    product = await _create_product(db_session, company.id, "QTGEL")
    today = date.today()
    payload = {
        "client_id": client_id,
        "quotation_date": today.isoformat(),
        "valid_until": (today + timedelta(days=30)).isoformat(),
        "discount_percent": 0,
        "items": [
            {
                "product_id": str(product.id),
                "description": "x",
                "quantity": 1,
                "unit_price": 10,
                "discount_percent": 0,
                "is_optional": False,
            }
        ],
    }
    resp = await client.post("/api/v1/quotations/", headers=headers, json=payload)
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["data"]["currency"] == "GEL"


@pytest.mark.asyncio
async def test_invoice_vat_18_line_rounding(client, db_session):
    company, headers = await _create_sal_context(client, db_session, SAL_CODES, "VAT18")
    client_id = await _create_client(client, headers, "VAT18")
    product = await _create_product(db_session, company.id, "VAT18")
    items = [
        {
            "product_id": str(product.id),
            "product_name": product.name,
            "quantity": 1,
            "unit_price": 0.10,
            "discount_percent": 0,
        }
        for _ in range(3)
    ]
    order_resp = await client.post(
        "/api/v1/orders/",
        headers=headers,
        json={"client_id": client_id, "items": items, "is_vat_payer": True},
    )
    assert order_resp.status_code == 200, order_resp.text
    order = order_resp.json()["data"]

    confirmed = await client.patch(
        f"/api/v1/orders/{order['id']}/status",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text

    generated = await client.post(
        "/api/v1/invoices/generate",
        json=invoice_payload(order["id"], "VAT18"),
        headers=headers,
    )
    assert generated.status_code == 200, generated.text
    data = generated.json()["data"]

    # rounding rule needs verification (RS.ge): each line VAT is rounded to 2
    # decimals with ROUND_HALF_UP before summing; 0.10*18% = 0.018 -> 0.02.
    assert data["subtotal"] == 0.30
    assert data["vat_amount"] == 0.06
    assert data["total"] == 0.36
    assert [item["vat_amount"] for item in data["items"]] == [0.02, 0.02, 0.02]
