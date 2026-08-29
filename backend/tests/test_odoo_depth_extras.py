"""Odoo-depth extras: barcode scan, marketplace billing, visual signature."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_product(client, auth_headers, barcode: str) -> str:
    p = await client.post("/api/v1/products/", json={
        "name": f"BC-{uuid.uuid4().hex[:6]}", "sku": f"SKU-{uuid.uuid4().hex[:6]}",
        "barcode": barcode, "sale_price": 10, "purchase_price": 5,
    }, headers=auth_headers)
    assert p.status_code in (200, 201), p.text
    return p.json()["data"]["id"]


async def test_barcode_scan_creates_check(client, auth_headers):
    barcode = f"480{uuid.uuid4().hex[:10]}"
    pid = await _seed_product(client, auth_headers, barcode)

    scan = await client.post("/api/v1/quality-control/scan", json={"barcode": barcode}, headers=auth_headers)
    assert scan.status_code == 200, scan.text
    data = scan.json()["data"]
    assert data["product_id"] == pid
    assert data["status"] == "pending"
    assert data["barcode"] == barcode

    # unknown barcode → 404
    bad = await client.post("/api/v1/quality-control/scan", json={"barcode": "999999999"}, headers=auth_headers)
    assert bad.status_code == 404


async def test_marketplace_purchase_and_trial(client, auth_headers):
    # publish a paid app
    app = await client.post("/api/v1/marketplace/apps", json={
        "name": f"PaidApp-{uuid.uuid4().hex[:4]}", "price": 49.99, "category": "sales",
    }, headers=auth_headers)
    assert app.status_code == 201, app.text
    app_id = app.json()["data"]["id"]

    # purchase (sandbox → paid + license)
    buy = await client.post(f"/api/v1/marketplace/apps/{app_id}/purchase", json={"billing_mode": "one_time"}, headers=auth_headers)
    assert buy.status_code == 200, buy.text
    data = buy.json()["data"]
    assert data["status"] == "paid"
    assert data["invoice_number"].startswith("INV-MP")
    assert data["license_key"].startswith("LIC-")
    assert data["gateway"] == "sandbox"

    # purchases history
    hist = await client.get("/api/v1/marketplace/purchases", headers=auth_headers)
    assert hist.status_code == 200
    assert len(hist.json()["data"]) == 1
    assert float(hist.json()["data"][0]["amount"]) == 49.99

    # trial on another app
    app2 = await client.post("/api/v1/marketplace/apps", json={
        "name": f"TrialApp-{uuid.uuid4().hex[:4]}", "price": 99, "category": "finance",
    }, headers=auth_headers)
    app2_id = app2.json()["data"]["id"]
    tr = await client.post(f"/api/v1/marketplace/apps/{app2_id}/trial", headers=auth_headers)
    assert tr.status_code == 200, tr.text
    assert tr.json()["data"]["status"] == "trial"
    assert tr.json()["data"]["trial_ends_at"] is not None


async def test_visual_signature_saved(client, auth_headers):
    created = await client.post("/api/v1/signature-requests/", json={
        "document_name": "ვიზუალური ხელმოწერა", "signer_name": "თამარი", "signer_email": "tamari@client.ge",
    }, headers=auth_headers)
    assert created.status_code == 201, created.text
    req_id = created.json()["data"]["id"]

    from app.models.signature import SignatureRequest
    from sqlalchemy import select
    from tests.conftest import TestSessionLocal
    async with TestSessionLocal() as session:
        db_req = (await session.execute(select(SignatureRequest).where(
            SignatureRequest.id == uuid.UUID(req_id),
        ))).scalar_one()
        token = db_req.signing_token

    # sign with a canvas drawing (data URL)
    sig_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    ok = await client.post("/api/v1/signature-requests/sign", json={
        "token": token, "signer_email": "tamari@client.ge", "decision": "sign",
        "signature_data": sig_data,
    })
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["status"] == "signed"
    assert ok.json()["data"]["signature_data"] == sig_data
