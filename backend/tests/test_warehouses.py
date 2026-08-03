# backend/tests/test_warehouses.py
import pytest
from sqlalchemy import select

from app.models.audit import AuditLog


async def create_product(client, auth_headers, sku: str = "WH-TEST-001"):
    response = await client.post(
        "/api/v1/products/",
        json={"sku": sku, "name": "საწყობის სატესტო პროდუქტი", "sale_price": 25},
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()["data"]


async def create_warehouse(client, auth_headers, code: str, name: str, is_default=False):
    response = await client.post(
        "/api/v1/warehouses/",
        json={"code": code, "name": name, "is_default": is_default},
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()["data"]


@pytest.mark.asyncio
async def test_create_and_list_warehouses(client, auth_headers):
    created = await create_warehouse(
        client, auth_headers, "MAIN", "მთავარი საწყობი", is_default=True
    )

    response = await client.get("/api/v1/warehouses/", headers=auth_headers)

    assert response.status_code == 200
    warehouses = response.json()["data"]
    assert len(warehouses) == 1
    assert warehouses[0]["id"] == created["id"]
    assert warehouses[0]["code"] == "MAIN"
    assert warehouses[0]["is_default"] is True


@pytest.mark.asyncio
async def test_receive_stock_creates_warehouse_balance(client, auth_headers):
    product = await create_product(client, auth_headers)
    warehouse = await create_warehouse(client, auth_headers, "MAIN", "მთავარი საწყობი")

    response = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": product["id"],
            "warehouse_id": warehouse["id"],
            "movement_type": "in",
            "quantity": 12.5,
            "reason": "initial_stock",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["balance_after"] == 12.5

    balances_response = await client.get(
        f"/api/v1/warehouses/balances?product_id={product['id']}",
        headers=auth_headers,
    )
    assert balances_response.status_code == 200
    balances = balances_response.json()["data"]
    assert len(balances) == 1
    assert balances[0]["quantity"] == 12.5
    assert balances[0]["warehouse_name"] == "მთავარი საწყობი"


@pytest.mark.asyncio
async def test_stock_issue_rejects_negative_balance(client, auth_headers):
    product = await create_product(client, auth_headers)
    warehouse = await create_warehouse(client, auth_headers, "MAIN", "მთავარი საწყობი")

    response = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": product["id"],
            "warehouse_id": warehouse["id"],
            "movement_type": "out",
            "quantity": 1,
            "reason": "sale",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "საწყობში არასაკმარისი ნაშთია"


@pytest.mark.asyncio
async def test_transfer_moves_stock_between_warehouses(client, auth_headers):
    product = await create_product(client, auth_headers)
    source = await create_warehouse(client, auth_headers, "MAIN", "მთავარი საწყობი")
    destination = await create_warehouse(client, auth_headers, "BR-01", "ფილიალი 1")

    receive_response = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": product["id"],
            "warehouse_id": source["id"],
            "movement_type": "in",
            "quantity": 20,
            "reason": "purchase",
        },
        headers=auth_headers,
    )
    assert receive_response.status_code == 200

    transfer_response = await client.post(
        "/api/v1/warehouses/transfers",
        json={
            "product_id": product["id"],
            "source_warehouse_id": source["id"],
            "destination_warehouse_id": destination["id"],
            "quantity": 7,
            "reason": "branch_replenishment",
        },
        headers=auth_headers,
    )

    assert transfer_response.status_code == 200
    transfer = transfer_response.json()["data"]
    assert transfer["source_balance_after"] == 13
    assert transfer["destination_balance_after"] == 7
    assert transfer["reference"]

    balances_response = await client.get(
        f"/api/v1/warehouses/balances?product_id={product['id']}",
        headers=auth_headers,
    )
    balances = {
        item["warehouse_id"]: item["quantity"]
        for item in balances_response.json()["data"]
    }
    assert balances[source["id"]] == 13
    assert balances[destination["id"]] == 7


@pytest.mark.asyncio
async def test_edit_warehouse_set_default_and_write_audit(
    client, auth_headers, db_session
):
    main = await create_warehouse(
        client, auth_headers, "MAIN", "მთავარი საწყობი", is_default=True
    )
    branch = await create_warehouse(client, auth_headers, "BR-01", "ფილიალი")

    update_response = await client.patch(
        f"/api/v1/warehouses/{branch['id']}",
        json={"code": "BR-02", "name": "ვაკის ფილიალი", "address": "ჭავჭავაძის გამზირი"},
        headers=auth_headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]
    assert updated["code"] == "BR-02"
    assert updated["name"] == "ვაკის ფილიალი"

    default_response = await client.post(
        f"/api/v1/warehouses/{branch['id']}/set-default",
        headers=auth_headers,
    )
    assert default_response.status_code == 200
    assert default_response.json()["data"]["is_default"] is True

    list_response = await client.get("/api/v1/warehouses/", headers=auth_headers)
    warehouses = {item["id"]: item for item in list_response.json()["data"]}
    assert warehouses[branch["id"]]["is_default"] is True
    assert warehouses[main["id"]]["is_default"] is False

    audit_actions = (
        await db_session.execute(
            select(AuditLog.action).where(
                AuditLog.entity_type == "warehouse",
                AuditLog.entity_id == branch["id"],
            )
        )
    ).scalars().all()
    assert "warehouse.updated" in audit_actions
    assert "warehouse.default_changed" in audit_actions


@pytest.mark.asyncio
async def test_safe_delete_allows_only_unused_non_default_warehouse(
    client, auth_headers, db_session
):
    main = await create_warehouse(
        client, auth_headers, "MAIN", "მთავარი საწყობი", is_default=True
    )
    unused = await create_warehouse(client, auth_headers, "TMP", "დროებითი")

    default_delete = await client.delete(
        f"/api/v1/warehouses/{main['id']}", headers=auth_headers
    )
    assert default_delete.status_code == 409

    delete_response = await client.delete(
        f"/api/v1/warehouses/{unused['id']}", headers=auth_headers
    )
    assert delete_response.status_code == 200

    warehouses = (
        await client.get("/api/v1/warehouses/?include_inactive=true", headers=auth_headers)
    ).json()["data"]
    assert unused["id"] not in {warehouse["id"] for warehouse in warehouses}

    deleted_audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "warehouse.deleted",
                AuditLog.entity_id == unused["id"],
            )
        )
    ).scalar_one_or_none()
    assert deleted_audit is not None


@pytest.mark.asyncio
async def test_used_warehouse_requires_zero_stock_and_is_archived(
    client, auth_headers
):
    product = await create_product(client, auth_headers, sku="WH-LIFECYCLE-001")
    await create_warehouse(
        client, auth_headers, "MAIN", "მთავარი საწყობი", is_default=True
    )
    branch = await create_warehouse(client, auth_headers, "USED", "გამოყენებული")

    receive = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": product["id"],
            "warehouse_id": branch["id"],
            "movement_type": "in",
            "quantity": 5,
            "reason": "purchase",
        },
        headers=auth_headers,
    )
    assert receive.status_code == 200

    archive_with_stock = await client.post(
        f"/api/v1/warehouses/{branch['id']}/archive", headers=auth_headers
    )
    assert archive_with_stock.status_code == 409

    issue = await client.post(
        "/api/v1/warehouses/adjust-stock",
        json={
            "product_id": product["id"],
            "warehouse_id": branch["id"],
            "movement_type": "out",
            "quantity": 5,
            "reason": "transfer_cleanup",
        },
        headers=auth_headers,
    )
    assert issue.status_code == 200

    hard_delete = await client.delete(
        f"/api/v1/warehouses/{branch['id']}", headers=auth_headers
    )
    assert hard_delete.status_code == 409

    archive_response = await client.post(
        f"/api/v1/warehouses/{branch['id']}/archive", headers=auth_headers
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["data"]["is_active"] is False

    active_warehouses = (
        await client.get("/api/v1/warehouses/", headers=auth_headers)
    ).json()["data"]
    assert branch["id"] not in {warehouse["id"] for warehouse in active_warehouses}

    all_warehouses = (
        await client.get("/api/v1/warehouses/?include_inactive=true", headers=auth_headers)
    ).json()["data"]
    archived = next(item for item in all_warehouses if item["id"] == branch["id"])
    assert archived["is_active"] is False
