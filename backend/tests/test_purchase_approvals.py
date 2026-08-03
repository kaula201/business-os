from decimal import Decimal

import pytest

from app.core.security import create_access_token, hash_password
from app.models.product import Product
from app.models.user import User
from app.models.warehouse import Warehouse


def headers_for(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id), "company_id": str(user.company_id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


async def create_order(client, headers, supplier_id: str, warehouse_id: str, product_id: str, total: Decimal):
    response = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "items": [{
                "product_id": product_id,
                "quantity": 1,
                "unit_price": float(total),
                "discount_percent": 0,
                "vat_rate": 0,
            }],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_purchase_approval_threshold_requires_manager_or_admin(
    client, auth_headers, test_company, db_session
):
    manager = User(
        company_id=test_company.id,
        email="manager-approval@test.ge",
        hashed_password=hash_password("manager123"),
        full_name="Approval Manager",
        role=User.Role.MANAGER,
        is_active=True,
    )
    employee = User(
        company_id=test_company.id,
        email="employee-approval@test.ge",
        hashed_password=hash_password("employee123"),
        full_name="Approval Employee",
        role=User.Role.EMPLOYEE,
        is_active=True,
    )
    accountant = User(
        company_id=test_company.id,
        email="accountant-approval@test.ge",
        hashed_password=hash_password("accountant123"),
        full_name="Approval Accountant",
        role=User.Role.ACCOUNTANT,
        is_active=True,
    )
    product = Product(
        company_id=test_company.id,
        sku="APPROVAL-001",
        name="Approval Product",
        sale_price=100,
        purchase_price=50,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="APPROVAL-WH",
        name="Approval Warehouse",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([manager, employee, accountant, product, warehouse])
    await db_session.commit()
    for row in (manager, employee, accountant, product, warehouse):
        await db_session.refresh(row)

    supplier = await client.post(
        "/api/v1/suppliers/",
        json={"code": "APPROVAL-SUP", "name": "Approval Supplier"},
        headers=auth_headers,
    )
    assert supplier.status_code == 200
    supplier_id = supplier.json()["data"]["id"]

    default_policy = await client.get("/api/v1/purchase-approval-policy/", headers=auth_headers)
    assert default_policy.status_code == 200, default_policy.text
    assert default_policy.json()["data"]["manager_approval_limit"] == 5000

    employee_update = await client.patch(
        "/api/v1/purchase-approval-policy/",
        json={"manager_approval_limit": 1000},
        headers=headers_for(employee),
    )
    assert employee_update.status_code == 403

    updated_policy = await client.patch(
        "/api/v1/purchase-approval-policy/",
        json={"manager_approval_limit": 1000},
        headers=auth_headers,
    )
    assert updated_policy.status_code == 200, updated_policy.text
    assert updated_policy.json()["data"]["manager_approval_limit"] == 1000

    low_order = await create_order(
        client, auth_headers, supplier_id, str(warehouse.id), str(product.id), Decimal("900")
    )
    low_approval = await client.patch(
        f"/api/v1/purchase-orders/{low_order['id']}/status",
        json={"status": "approved", "notes": "manager within limit"},
        headers=headers_for(manager),
    )
    assert low_approval.status_code == 200, low_approval.text
    assert low_approval.json()["data"]["status"] == "approved"
    assert low_approval.json()["data"]["approved_by"] == str(manager.id)

    high_order = await create_order(
        client, auth_headers, supplier_id, str(warehouse.id), str(product.id), Decimal("1200")
    )
    manager_denied = await client.patch(
        f"/api/v1/purchase-orders/{high_order['id']}/status",
        json={"status": "approved"},
        headers=headers_for(manager),
    )
    assert manager_denied.status_code == 403
    assert "admin" in manager_denied.json()["detail"].lower()

    employee_denied = await client.patch(
        f"/api/v1/purchase-orders/{high_order['id']}/status",
        json={"status": "approved"},
        headers=headers_for(employee),
    )
    assert employee_denied.status_code == 403

    accountant_denied = await client.patch(
        f"/api/v1/purchase-orders/{high_order['id']}/status",
        json={"status": "approved"},
        headers=headers_for(accountant),
    )
    assert accountant_denied.status_code == 403

    admin_approval = await client.patch(
        f"/api/v1/purchase-orders/{high_order['id']}/status",
        json={"status": "approved", "notes": "above manager limit"},
        headers=auth_headers,
    )
    assert admin_approval.status_code == 200, admin_approval.text
    assert admin_approval.json()["data"]["approved_by"] is not None


@pytest.mark.asyncio
async def test_purchase_order_exposes_required_approval_role(
    client, auth_headers, test_company, db_session
):
    product = Product(
        company_id=test_company.id,
        sku="APPROVAL-ROLE",
        name="Approval Role Product",
        sale_price=100,
        purchase_price=50,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="APPROVAL-ROLE",
        name="Approval Role Warehouse",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.commit()
    await db_session.refresh(product)
    await db_session.refresh(warehouse)
    supplier = await client.post(
        "/api/v1/suppliers/",
        json={"code": "APPROVAL-ROLE", "name": "Approval Role Supplier"},
        headers=auth_headers,
    )
    supplier_id = supplier.json()["data"]["id"]

    await client.patch(
        "/api/v1/purchase-approval-policy/",
        json={"manager_approval_limit": 1000},
        headers=auth_headers,
    )
    low = await create_order(client, auth_headers, supplier_id, str(warehouse.id), str(product.id), Decimal("999"))
    high = await create_order(client, auth_headers, supplier_id, str(warehouse.id), str(product.id), Decimal("1001"))
    assert low["required_approval_role"] == "manager"
    assert high["required_approval_role"] == "admin"
