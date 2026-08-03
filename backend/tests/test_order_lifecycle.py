from decimal import Decimal
import asyncio

import pytest
from sqlalchemy import select

import seed
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.order import InventoryReservation, Order, OrderFulfillment, OrderItem
from app.models.product import Product
from app.models.warehouse import InventoryBalance, InventoryMovement, Warehouse


async def create_lifecycle_dependencies(db_session, company_id, suffix: str, stock: str = "5"):
    client_obj = Client(
        company_id=company_id,
        name=f"Lifecycle Client {suffix}",
        client_type="legal",
        identification_code=f"LC-{suffix}",
        status="active",
    )
    product = Product(
        company_id=company_id,
        sku=f"LIFE-{suffix}",
        name=f"Lifecycle Product {suffix}",
        sale_price=100,
        current_stock=float(stock),
    )
    warehouse = Warehouse(
        company_id=company_id,
        code=f"WH-{suffix}",
        name=f"Lifecycle Warehouse {suffix}",
        is_default=True,
        is_active=True,
    )
    db_session.add_all([client_obj, product, warehouse])
    await db_session.flush()
    balance = InventoryBalance(
        company_id=company_id,
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=Decimal(stock),
    )
    db_session.add(balance)
    await db_session.commit()
    for entity in (client_obj, product, warehouse, balance):
        await db_session.refresh(entity)
    return client_obj, product, warehouse, balance


def order_payload(client_obj, product, warehouse, quantity: float):
    return {
        "client_id": str(client_obj.id),
        "warehouse_id": str(warehouse.id),
        "items": [
            {
                "product_id": str(product.id),
                "product_name": product.name,
                "quantity": quantity,
                "unit_price": 100,
                "discount_percent": 0,
            }
        ],
        "is_vat_payer": False,
    }


@pytest.mark.asyncio
async def test_draft_does_not_change_stock_and_confirmation_reserves_it(
    client, auth_headers, test_company, db_session
):
    client_obj, product, warehouse, balance = await create_lifecycle_dependencies(
        db_session, test_company.id, "RESERVE"
    )

    created = await client.post(
        "/api/v1/orders/",
        json=order_payload(client_obj, product, warehouse, 3),
        headers=auth_headers,
    )
    assert created.status_code == 200
    order_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 5
    assert balance.quantity == Decimal("5")

    confirmed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed", "notes": "reserve stock"},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200

    reservations = await client.get(
        f"/api/v1/orders/{order_id}/reservations", headers=auth_headers
    )
    assert reservations.status_code == 200
    reservation = reservations.json()["data"][0]
    assert reservation["status"] == "active"
    assert float(reservation["quantity"]) == 3
    assert float(reservation["available_after_reservation"]) == 2

    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 5
    assert balance.quantity == Decimal("5")


@pytest.mark.asyncio
async def test_illegal_status_transition_is_rejected(
    client, auth_headers, test_company, db_session
):
    client_obj, product, warehouse, _ = await create_lifecycle_dependencies(
        db_session, test_company.id, "ILLEGAL"
    )
    created = await client.post(
        "/api/v1/orders/",
        json=order_payload(client_obj, product, warehouse, 1),
        headers=auth_headers,
    )
    order_id = created.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "shipping"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "დაუშვებელია" in response.json()["detail"]


@pytest.mark.asyncio
async def test_confirmation_rejects_insufficient_available_stock(
    client, auth_headers, test_company, db_session
):
    client_obj, product, warehouse, balance = await create_lifecycle_dependencies(
        db_session, test_company.id, "SHORT"
    )
    created = await client.post(
        "/api/v1/orders/",
        json=order_payload(client_obj, product, warehouse, 6),
        headers=auth_headers,
    )
    # Stock availability is now checked preventively at creation time.
    assert created.status_code == 409
    assert "საკმარისი ნაშთი" in created.json()["detail"]
    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 5
    assert balance.quantity == Decimal("5")


@pytest.mark.asyncio
async def test_cancellation_releases_active_reservation(
    client, auth_headers, test_company, db_session
):
    client_obj, product, warehouse, balance = await create_lifecycle_dependencies(
        db_session, test_company.id, "CANCEL"
    )
    created = await client.post(
        "/api/v1/orders/",
        json=order_payload(client_obj, product, warehouse, 2),
        headers=auth_headers,
    )
    order_id = created.json()["data"]["id"]
    confirmed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200

    cancelled = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "cancelled", "notes": "client cancelled"},
        headers=auth_headers,
    )
    assert cancelled.status_code == 200

    reservations = await client.get(
        f"/api/v1/orders/{order_id}/reservations", headers=auth_headers
    )
    assert reservations.json()["data"][0]["status"] == "released"
    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 5
    assert balance.quantity == Decimal("5")


@pytest.mark.asyncio
async def test_shipping_issues_stock_and_return_restores_it_once(
    client, auth_headers, test_company, db_session
):
    client_obj, product, warehouse, balance = await create_lifecycle_dependencies(
        db_session, test_company.id, "RETURN"
    )
    created = await client.post(
        "/api/v1/orders/",
        json=order_payload(client_obj, product, warehouse, 2),
        headers=auth_headers,
    )
    order_id = created.json()["data"]["id"]

    for status in ("confirmed", "preparing", "shipping"):
        changed = await client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": status},
            headers=auth_headers,
        )
        assert changed.status_code == 200, changed.text

    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 3
    assert balance.quantity == Decimal("3")

    duplicate_shipping = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "shipping"},
        headers=auth_headers,
    )
    assert duplicate_shipping.status_code == 409

    completed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert completed.status_code == 200
    generated_invoice = (
        await db_session.execute(select(Invoice).where(Invoice.order_id == order_id))
    ).scalar_one_or_none()
    assert generated_invoice is not None
    assert generated_invoice.status == "draft"
    assert generated_invoice.idempotency_key == f"auto-draft:{order_id}"
    assert (generated_invoice.due_date - generated_invoice.invoice_date).days == 14

    returned = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "returned", "notes": "full return"},
        headers=auth_headers,
    )
    assert returned.status_code == 200

    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 5
    assert balance.quantity == Decimal("5")

    movements = (
        await db_session.execute(
            select(InventoryMovement)
            .where(InventoryMovement.reference == f"order:{order_id}")
            .order_by(InventoryMovement.created_at)
        )
    ).scalars().all()
    assert [movement.movement_type for movement in movements] == ["issue", "return"]

    history = await client.get(
        f"/api/v1/orders/{order_id}/history", headers=auth_headers
    )
    assert history.status_code == 200
    assert [entry["status"] for entry in history.json()["data"]] == [
        "draft", "confirmed", "preparing", "shipping", "completed", "returned"
    ]


@pytest.mark.asyncio
async def test_manual_issue_cannot_consume_reserved_stock(
    client, auth_headers, test_company, db_session
):
    client_obj, product, warehouse, balance = await create_lifecycle_dependencies(
        db_session, test_company.id, "MANUAL"
    )
    created = await client.post(
        "/api/v1/orders/",
        json=order_payload(client_obj, product, warehouse, 3),
        headers=auth_headers,
    )
    order_id = created.json()["data"]["id"]
    confirmed = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "confirmed"},
        headers=auth_headers,
    )
    assert confirmed.status_code == 200

    blocked = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "warehouse_id": str(warehouse.id),
            "product_id": str(product.id),
            "movement_type": "out",
            "quantity": 3,
            "reason": "manual issue",
        },
        headers=auth_headers,
    )
    assert blocked.status_code == 409
    assert "დარეზერვებული" in blocked.json()["detail"]
    await db_session.refresh(balance)
    assert balance.quantity == Decimal("5")


@pytest.mark.asyncio
async def test_concurrent_confirmation_prevents_oversell_and_numbers_are_unique(
    client, auth_headers, test_company, db_session
):
    client_obj, product, warehouse, _ = await create_lifecycle_dependencies(
        db_session, test_company.id, "CONCURRENT"
    )
    first, second = await asyncio.gather(
        client.post(
            "/api/v1/orders/",
            json=order_payload(client_obj, product, warehouse, 3),
            headers=auth_headers,
        ),
        client.post(
            "/api/v1/orders/",
            json=order_payload(client_obj, product, warehouse, 3),
            headers=auth_headers,
        ),
    )
    assert first.status_code == second.status_code == 200
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["order_number"] != second_data["order_number"]

    confirmations = await asyncio.gather(
        client.patch(
            f"/api/v1/orders/{first_data['id']}/status",
            json={"status": "confirmed"},
            headers=auth_headers,
        ),
        client.patch(
            f"/api/v1/orders/{second_data['id']}/status",
            json={"status": "confirmed"},
            headers=auth_headers,
        ),
    )
    assert sorted(response.status_code for response in confirmations) == [200, 409]


@pytest.mark.asyncio
async def test_warehouse_linked_to_order_cannot_be_hard_deleted(
    client, auth_headers, test_company, db_session
):
    client_obj = Client(
        company_id=test_company.id,
        name="Fulfillment Client",
        client_type="legal",
        identification_code="FULFILLMENT-CLIENT",
        status="active",
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code="FULFILLMENT-WH",
        name="Fulfillment Warehouse",
        is_default=False,
        is_active=True,
    )
    db_session.add_all([client_obj, warehouse])
    await db_session.commit()
    await db_session.refresh(client_obj)
    await db_session.refresh(warehouse)

    created = await client.post(
        "/api/v1/orders/",
        json={
            "client_id": str(client_obj.id),
            "warehouse_id": str(warehouse.id),
            "items": [{
                "product_name": "Service line",
                "quantity": 1,
                "unit_price": 10,
                "discount_percent": 0,
            }],
            "is_vat_payer": False,
        },
        headers=auth_headers,
    )
    assert created.status_code == 200

    deleted = await client.delete(
        f"/api/v1/warehouses/{warehouse.id}", headers=auth_headers
    )
    assert deleted.status_code == 409
    assert "შეკვეთ" in deleted.json()["detail"]


@pytest.mark.asyncio
async def test_legacy_order_backfill_is_idempotent_and_does_not_change_stock(
    test_company, db_session
):
    client_obj, product, warehouse, balance = await create_lifecycle_dependencies(
        db_session, test_company.id, "BACKFILL"
    )
    order = Order(
        company_id=test_company.id,
        client_id=client_obj.id,
        order_number="ORD-LEGACY-00001",
        status="confirmed",
        subtotal=200,
        vat_amount=0,
        total=200,
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,
            quantity=2,
            unit_price=100,
            total=200,
        )
    )
    await db_session.commit()

    assert hasattr(seed, "ensure_order_lifecycle_backfill")
    await seed.ensure_order_lifecycle_backfill(db_session)
    await db_session.commit()
    await seed.ensure_order_lifecycle_backfill(db_session)
    await db_session.commit()

    fulfillment_count = (
        await db_session.execute(
            select(OrderFulfillment).where(OrderFulfillment.order_id == order.id)
        )
    ).scalars().all()
    reservations = (
        await db_session.execute(
            select(InventoryReservation).where(InventoryReservation.order_id == order.id)
        )
    ).scalars().all()
    assert len(fulfillment_count) == 1
    assert fulfillment_count[0].warehouse_id == warehouse.id
    assert len(reservations) == 1
    assert reservations[0].status == "active"
    await db_session.refresh(product)
    await db_session.refresh(balance)
    assert product.current_stock == 5
    assert balance.quantity == Decimal("5")
