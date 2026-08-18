"""Tenders lifecycle and vendor analytics aggregation."""
import uuid
from datetime import date

import pytest
from sqlalchemy import select

from app.models.purchase import Supplier
from app.models.tender import Tender, TenderBid
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_supplier(client, auth_headers, test_company, suffix: str):
    resp = await client.post("/api/v1/suppliers/", json={
        "name": f"Tender Supplier {suffix}", "code": f"TS-{suffix}",
        "identification_code": f"ID-{suffix}", "is_vat_payer": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_product(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/products/", json={
        "sku": f"TND-{suffix}", "name": f"Tender Product {suffix}", "sale_price": 10,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def _create_warehouse(client, auth_headers, suffix: str):
    resp = await client.post("/api/v1/warehouses/", json={
        "code": f"WH-{suffix}", "name": f"Tender Warehouse {suffix}", "is_default": True,
    }, headers=auth_headers)
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["data"]


async def test_tender_lifecycle_and_vendor_analytics(client, auth_headers, test_company, db_session):
    supplier = await _create_supplier(client, auth_headers, test_company, "A")
    product = await _create_product(client, auth_headers, "A")
    warehouse = await _create_warehouse(client, auth_headers, "A")

    created = await client.post("/api/v1/procurement/tenders", json={
        "title": "Tender Test", "budget_amount": 1000, "warehouse_id": warehouse["id"],
        "lines": [{"product_id": product["id"], "quantity": 10, "expected_price": 50}],
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    tender_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    published = await client.post(f"/api/v1/procurement/tenders/{tender_id}/publish", headers=auth_headers)
    assert published.status_code == 200, published.text
    assert published.json()["data"]["status"] == "bidding"

    # Bid with unit price 40 -> total 400
    async with TestSessionLocal() as s:
        from app.models.tender import TenderLine
        line = (await s.execute(select(TenderLine).where(TenderLine.tender_id == uuid.UUID(tender_id)))).scalar_one()
        line_id = str(line.id)
    bid = await client.post(f"/api/v1/procurement/tenders/{tender_id}/bids", json={
        "supplier_id": supplier["id"], "delivery_days": 5,
        "lines": [{"tender_line_id": line_id, "product_id": product["id"], "unit_price": 40}],
    }, headers=auth_headers)
    assert bid.status_code == 201, bid.text
    assert bid.json()["data"]["total_amount"] == 400.0

    comparison = await client.get(f"/api/v1/procurement/tenders/{tender_id}/comparison", headers=auth_headers)
    assert comparison.status_code == 200, comparison.text
    assert len(comparison.json()["data"]) == 1

    awarded = await client.post(f"/api/v1/procurement/tenders/{tender_id}/award", params={"supplier_id": supplier["id"]}, headers=auth_headers)
    assert awarded.status_code == 200, awarded.text
    assert awarded.json()["data"]["status"] == "awarded"
    assert awarded.json()["data"]["purchase_order_id"], "expected auto-generated PO on award"
    assert awarded.json()["data"]["purchase_order_number"].startswith("PO-")

    # The auto-generated PO is a draft with the accepted bid's line.
    po_id = awarded.json()["data"]["purchase_order_id"]
    po = await client.get(f"/api/v1/purchase-orders/{po_id}", headers=auth_headers)
    assert po.status_code == 200, po.text
    po_data = po.json()["data"]
    assert po_data["status"] == "draft"
    assert po_data["supplier_id"] == supplier["id"]
    assert len(po_data["items"]) == 1
    assert float(po_data["items"][0]["unit_price"]) == 40.0

    analytics = await client.get("/api/v1/procurement/vendor-analytics", headers=auth_headers)
    assert analytics.status_code == 200, analytics.text
    rows = analytics.json()["data"]
    assert any(r["supplier_id"] == supplier["id"] for r in rows)
