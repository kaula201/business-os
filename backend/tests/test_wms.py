"""WMS: batch/lot and serial-number tracking tests."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.warehouse import InventoryBalance, ProductBatch, ProductSerial


async def create_wms_ctx(client, auth_headers, test_company, db_session, suffix: str):
    from app.models.product import Product
    from app.models.warehouse import Warehouse
    product = Product(
        company_id=test_company.id,
        sku=f"WMS-{suffix}",
        name=f"WMS Product {suffix}",
        sale_price=50,
        purchase_price=20,
        unit="ცალი",
        min_stock=0,
        current_stock=0,
        is_active=True,
    )
    warehouse = Warehouse(
        company_id=test_company.id,
        code=f"WMS-WH-{suffix}",
        name=f"WMS Warehouse {suffix}",
        is_default=True,
        is_active=True,
    )
    db_session.add_all([product, warehouse])
    await db_session.commit()
    await db_session.refresh(product)
    return product, warehouse


@pytest.mark.asyncio
async def test_batch_crud_and_receive(client, auth_headers, test_company, db_session):
    product, warehouse = await create_wms_ctx(
        client, auth_headers, test_company, db_session, "B"
    )

    # Create batch
    created = await client.post(
        "/api/v1/wms/batches",
        json={
            "warehouse_id": str(warehouse.id),
            "product_id": str(product.id),
            "batch_number": "LOT-2026-001",
            "expiry_date": (date.today() + timedelta(days=20)).isoformat(),
            "quantity": 10,
            "unit_cost": 20,
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    batch = created.json()["data"]
    assert float(batch["quantity"]) == 10

    # Receive more
    received = await client.post(
        f"/api/v1/wms/batches/{batch['id']}/receive?quantity=5",
        headers=auth_headers,
    )
    assert received.status_code == 200, received.text
    assert float(received.json()["data"]["quantity"]) == 15

    balance = (
        await db_session.execute(
            select(InventoryBalance).where(
                InventoryBalance.warehouse_id == warehouse.id,
                InventoryBalance.product_id == product.id,
            )
        )
    ).scalar_one()
    assert float(balance.quantity) == 15
    await db_session.refresh(product)
    assert float(product.current_stock) == 15

    # List + expiry-window filter
    listing = await client.get(
        f"/api/v1/wms/batches?product_id={product.id}",
        headers=auth_headers,
    )
    assert listing.status_code == 200, listing.text
    assert len(listing.json()["data"]) == 1

    expiring = await client.get(
        "/api/v1/wms/batches?expiring_soon=true",
        headers=auth_headers,
    )
    assert expiring.status_code == 200, expiring.text
    assert [row["batch_number"] for row in expiring.json()["data"]] == ["LOT-2026-001"]

    # Duplicate batch number -> 409
    dup = await client.post(
        "/api/v1/wms/batches",
        json={
            "warehouse_id": str(warehouse.id),
            "product_id": str(product.id),
            "batch_number": "LOT-2026-001",
            "quantity": 1,
        },
        headers=auth_headers,
    )
    assert dup.status_code == 409, dup.text

    # Generic warehouse writes cannot bypass lot-level accounting.
    generic = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "warehouse_id": str(warehouse.id),
            "product_id": str(product.id),
            "movement_type": "out",
            "quantity": 1,
            "reason": "must use WMS",
        },
        headers=auth_headers,
    )
    assert generic.status_code == 409, generic.text

    adjusted = await client.post(
        f"/api/v1/wms/batches/{batch['id']}/adjust",
        json={"quantity_delta": -3, "reason": "damaged units"},
        headers=auth_headers,
    )
    assert adjusted.status_code == 200, adjusted.text
    assert float(adjusted.json()["data"]["quantity"]) == 12

    from app.models.warehouse import Warehouse
    destination = Warehouse(
        company_id=test_company.id,
        code="WMS-WH-B-DEST",
        name="WMS Destination",
        is_default=False,
        is_active=True,
    )
    db_session.add(destination)
    await db_session.commit()
    transferred = await client.post(
        f"/api/v1/wms/batches/{batch['id']}/transfer",
        json={"destination_warehouse_id": str(destination.id)},
        headers=auth_headers,
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["data"]["warehouse_id"] == str(destination.id)

    product_id = product.id
    company_id = test_company.id
    db_session.expire_all()
    balances = (
        await db_session.execute(
            select(InventoryBalance).where(
                InventoryBalance.company_id == company_id,
                InventoryBalance.product_id == product_id,
            ).order_by(InventoryBalance.warehouse_id)
        )
    ).scalars().all()
    assert sorted(float(row.quantity) for row in balances) == [0, 12]
    await db_session.refresh(product)
    assert float(product.current_stock) == 12


@pytest.mark.asyncio
async def test_serial_register_and_status_flow(client, auth_headers, test_company, db_session):
    product, warehouse = await create_wms_ctx(
        client, auth_headers, test_company, db_session, "S"
    )
    batch = await client.post(
        "/api/v1/wms/batches",
        json={
            "warehouse_id": str(warehouse.id),
            "product_id": str(product.id),
            "batch_number": "LOT-SER-001",
            "quantity": 1,
        },
        headers=auth_headers,
    )
    batch_id = batch.json()["data"]["id"]

    reg = await client.post(
        "/api/v1/wms/serials",
        json={
            "product_id": str(product.id),
            "serial_number": "SN-100001",
            "batch_id": batch_id,
            "warehouse_id": str(warehouse.id),
        },
        headers=auth_headers,
    )
    assert reg.status_code == 201, reg.text
    serial = reg.json()["data"]
    assert serial["status"] == "in_stock"

    # Duplicate -> 409
    dup = await client.post(
        "/api/v1/wms/serials",
        json={"product_id": str(product.id), "serial_number": "SN-100001"},
        headers=auth_headers,
    )
    assert dup.status_code == 409, dup.text

    # Mark sold
    sold = await client.patch(
        f"/api/v1/wms/serials/{serial['id']}/status?status=sold",
        headers=auth_headers,
    )
    assert sold.status_code == 200, sold.text
    assert sold.json()["data"]["status"] == "sold"
    assert sold.json()["data"]["sold_at"] is not None

    batch_row = await db_session.get(ProductBatch, batch_id)
    balance = (
        await db_session.execute(
            select(InventoryBalance).where(
                InventoryBalance.warehouse_id == warehouse.id,
                InventoryBalance.product_id == product.id,
            )
        )
    ).scalar_one()
    await db_session.refresh(batch_row)
    await db_session.refresh(balance)
    assert float(batch_row.quantity) == 0
    assert float(balance.quantity) == 0

    returned = await client.patch(
        f"/api/v1/wms/serials/{serial['id']}/status?status=returned",
        headers=auth_headers,
    )
    assert returned.status_code == 200, returned.text
    await db_session.refresh(batch_row)
    await db_session.refresh(balance)
    assert float(batch_row.quantity) == 1
    assert float(balance.quantity) == 1

    # Filter by status
    listing = await client.get(
        f"/api/v1/wms/serials?status=returned",
        headers=auth_headers,
    )
    assert listing.status_code == 200, listing.text
    assert len(listing.json()["data"]) == 1


@pytest.mark.asyncio
async def test_wms_tenant_isolation(client, auth_headers, test_company, db_session):
    from app.models.company import Company
    from app.models.product import Product
    from app.models.warehouse import Warehouse
    from tests.test_supplier_credit_reversals import create_user_headers

    other = Company(name="WMS Other", identification_code="WMS-OTH-1")
    db_session.add(other)
    await db_session.commit()
    other_product = Product(
        company_id=other.id, sku="WMS-OTHER-P", name="Other Product",
        sale_price=10, purchase_price=5, unit="ცალი", min_stock=0,
        current_stock=0, is_active=True,
    )
    other_warehouse = Warehouse(
        company_id=other.id, code="WMS-OTHER-W", name="Other Warehouse",
        is_default=True, is_active=True,
    )
    db_session.add_all([other_product, other_warehouse])
    await db_session.commit()

    injected = await client.post(
        "/api/v1/wms/batches",
        json={
            "warehouse_id": str(other_warehouse.id),
            "product_id": str(other_product.id),
            "batch_number": "CROSS-TENANT-LOT",
            "quantity": 1,
        },
        headers=auth_headers,
    )
    assert injected.status_code == 404, injected.text

    other_headers = await create_user_headers(
        client, db_session, other.id, "wms-other@test.ge", "admin"
    )

    # Other company lists batches -> empty (RLS + scoping)
    listing = await client.get("/api/v1/wms/batches", headers=other_headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["data"] == []
