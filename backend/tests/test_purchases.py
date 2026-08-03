import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.product import Product
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse


async def create_purchase_inventory(db_session, company_id, suffix: str):
    product = Product(
        company_id=company_id,
        sku=f"PUR-{suffix}",
        name=f"Purchase Product {suffix}",
        sale_price=20,
        purchase_price=10,
        unit="ცალი",
        min_stock=1,
        current_stock=5,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=company_id,
        code=f"PUR-{suffix}-WH",
        name=f"Purchase Warehouse {suffix}",
        is_default=True,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.flush()
    balance = InventoryBalance(
        company_id=company_id,
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=Decimal("5"),
    )
    db_session.add(balance)
    await db_session.commit()
    await db_session.refresh(product)
    await db_session.refresh(warehouse)
    await db_session.refresh(balance)
    return product, warehouse, balance


async def create_supplier(client, auth_headers, suffix: str):
    response = await client.post(
        "/api/v1/suppliers/",
        json={
            "code": f"SUP-{suffix}",
            "name": f"Supplier {suffix}",
            "identification_code": f"ID-{suffix}",
            "is_vat_payer": True,
            "contact_name": "ნინო მენაბდე",
            "phone": "+995555000111",
            "email": f"{suffix.lower()}@supplier.ge",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()["data"]


async def create_purchase_order(
    client, auth_headers, supplier_id, warehouse_id, product_id, quantity=3
):
    response = await client.post(
        "/api/v1/purchase-orders/",
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "expected_delivery_date": "2026-08-15",
            "notes": "Integration purchase order",
            "items": [
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": 10,
                    "discount_percent": 0,
                    "vat_rate": 18,
                }
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.asyncio
async def test_supplier_crud_and_duplicate_code(client, auth_headers):
    supplier = await create_supplier(client, auth_headers, "CRUD")
    assert supplier["code"] == "SUP-CRUD"
    assert supplier["name"] == "Supplier CRUD"
    assert supplier["is_active"] is True

    listed = await client.get("/api/v1/suppliers/", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    updated = await client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        json={"contact_name": "გიორგი გელაშვილი", "payment_terms_days": 45},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["payment_terms_days"] == 45

    duplicate = await client.post(
        "/api/v1/suppliers/",
        json={"code": "sup-crud", "name": "Duplicate"},
        headers=auth_headers,
    )
    assert duplicate.status_code == 409

    second = await create_supplier(client, auth_headers, "SECOND")
    cross_collision = await client.post(
        "/api/v1/suppliers/",
        json={
            "code": supplier["code"],
            "name": "Cross collision",
            "identification_code": second["identification_code"],
        },
        headers=auth_headers,
    )
    assert cross_collision.status_code == 409


@pytest.mark.asyncio
async def test_purchase_order_receipt_lifecycle_is_transactional_and_idempotent(
    client, auth_headers, test_company, db_session
):
    product, warehouse, balance = await create_purchase_inventory(
        db_session, test_company.id, "FLOW"
    )
    supplier = await create_supplier(client, auth_headers, "FLOW")
    purchase_order = await create_purchase_order(
        client,
        auth_headers,
        supplier["id"],
        str(warehouse.id),
        str(product.id),
        quantity=3,
    )
    assert purchase_order["status"] == "draft"
    assert purchase_order["items"][0]["received_quantity"] == 0

    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 5
    assert balance.quantity == Decimal("5")

    illegal = await client.patch(
        f"/api/v1/purchase-orders/{purchase_order['id']}/status",
        json={"status": "received"},
        headers=auth_headers,
    )
    assert illegal.status_code == 409

    approved = await client.patch(
        f"/api/v1/purchase-orders/{purchase_order['id']}/status",
        json={"status": "approved", "notes": "Approved for receipt"},
        headers=auth_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"

    receipt_payload = {
        "idempotency_key": "flow-receipt-1",
        "notes": "Partial delivery",
        "items": [
            {
                "purchase_order_item_id": purchase_order["items"][0]["id"],
                "quantity": 2,
            }
        ],
    }
    partial = await client.post(
        f"/api/v1/purchase-orders/{purchase_order['id']}/receipts",
        json=receipt_payload,
        headers=auth_headers,
    )
    assert partial.status_code == 200
    first_receipt = partial.json()["data"]
    assert first_receipt["status"] == "posted"
    assert first_receipt["items"][0]["quantity"] == 2
    assert first_receipt["purchase_order_status"] == "partially_received"

    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 7
    assert balance.quantity == Decimal("7")

    duplicate = await client.post(
        f"/api/v1/purchase-orders/{purchase_order['id']}/receipts",
        json=receipt_payload,
        headers=auth_headers,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["data"]["id"] == first_receipt["id"]
    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 7
    assert balance.quantity == Decimal("7")

    over_receipt = await client.post(
        f"/api/v1/purchase-orders/{purchase_order['id']}/receipts",
        json={
            "idempotency_key": "flow-receipt-over",
            "items": [
                {
                    "purchase_order_item_id": purchase_order["items"][0]["id"],
                    "quantity": 2,
                }
            ],
        },
        headers=auth_headers,
    )
    assert over_receipt.status_code == 409

    final = await client.post(
        f"/api/v1/purchase-orders/{purchase_order['id']}/receipts",
        json={
            "idempotency_key": "flow-receipt-final",
            "items": [
                {
                    "purchase_order_item_id": purchase_order["items"][0]["id"],
                    "quantity": 1,
                }
            ],
        },
        headers=auth_headers,
    )
    assert final.status_code == 200
    assert final.json()["data"]["purchase_order_status"] == "received"

    detail = await client.get(
        f"/api/v1/purchase-orders/{purchase_order['id']}", headers=auth_headers
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "received"
    assert detail.json()["data"]["items"][0]["received_quantity"] == 3

    history = await client.get(
        f"/api/v1/purchase-orders/{purchase_order['id']}/history",
        headers=auth_headers,
    )
    assert history.status_code == 200
    assert [row["status"] for row in history.json()["data"]] == [
        "draft",
        "approved",
        "partially_received",
        "received",
    ]

    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 8
    assert balance.quantity == Decimal("8")
    movements = (
        await db_session.execute(
            select(InventoryMovement).where(
                InventoryMovement.company_id == test_company.id,
                InventoryMovement.product_id == product.id,
                InventoryMovement.movement_type == "purchase_receipt",
            )
        )
    ).scalars().all()
    assert len(movements) == 2
    assert sum(movement.quantity for movement in movements) == Decimal("3")


@pytest.mark.asyncio
async def test_cancelled_purchase_order_cannot_be_received(
    client, auth_headers, test_company, db_session
):
    product, warehouse, _ = await create_purchase_inventory(
        db_session, test_company.id, "CANCEL"
    )
    supplier = await create_supplier(client, auth_headers, "CANCEL")
    purchase_order = await create_purchase_order(
        client, auth_headers, supplier["id"], str(warehouse.id), str(product.id)
    )
    approved = await client.patch(
        f"/api/v1/purchase-orders/{purchase_order['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200
    cancelled = await client.patch(
        f"/api/v1/purchase-orders/{purchase_order['id']}/status",
        json={"status": "cancelled"},
        headers=auth_headers,
    )
    assert cancelled.status_code == 200

    receipt = await client.post(
        f"/api/v1/purchase-orders/{purchase_order['id']}/receipts",
        json={
            "idempotency_key": "cancelled-receipt",
            "items": [
                {
                    "purchase_order_item_id": purchase_order["items"][0]["id"],
                    "quantity": 1,
                }
            ],
        },
        headers=auth_headers,
    )
    assert receipt.status_code == 409


@pytest.mark.asyncio
async def test_concurrent_receipts_cannot_over_receive(
    client, auth_headers, test_company, db_session
):
    product, warehouse, balance = await create_purchase_inventory(
        db_session, test_company.id, "CONCURRENT"
    )
    supplier = await create_supplier(client, auth_headers, "CONCURRENT")
    purchase_order = await create_purchase_order(
        client,
        auth_headers,
        supplier["id"],
        str(warehouse.id),
        str(product.id),
        quantity=3,
    )
    approved = await client.patch(
        f"/api/v1/purchase-orders/{purchase_order['id']}/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert approved.status_code == 200

    async def receive(key: str):
        return await client.post(
            f"/api/v1/purchase-orders/{purchase_order['id']}/receipts",
            json={
                "idempotency_key": key,
                "items": [
                    {
                        "purchase_order_item_id": purchase_order["items"][0]["id"],
                        "quantity": 2,
                    }
                ],
            },
            headers=auth_headers,
        )

    responses = await asyncio.gather(receive("concurrent-1"), receive("concurrent-2"))
    assert sorted(response.status_code for response in responses) == [200, 409]
    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 7
    assert balance.quantity == Decimal("7")


@pytest.mark.asyncio
async def test_warehouse_used_by_active_purchase_order_cannot_be_archived_or_deleted(
    client, auth_headers, test_company, db_session
):
    product = Product(
        company_id=test_company.id,
        sku="PUR-WH-GUARD",
        name="Warehouse Guard Product",
        sale_price=20,
        purchase_price=10,
        unit="ცალი",
        min_stock=1,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="PUR-WH-GUARD",
        name="Purchase Guard Warehouse",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.commit()
    await db_session.refresh(product)
    await db_session.refresh(warehouse)

    supplier = await create_supplier(client, auth_headers, "WH-GUARD")
    await create_purchase_order(
        client,
        auth_headers,
        supplier["id"],
        str(warehouse.id),
        str(product.id),
        quantity=1,
    )

    archived = await client.post(
        f"/api/v1/warehouses/{warehouse.id}/archive", headers=auth_headers
    )
    assert archived.status_code == 409
    deleted = await client.delete(
        f"/api/v1/warehouses/{warehouse.id}", headers=auth_headers
    )
    assert deleted.status_code == 409
