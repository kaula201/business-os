"""Quotation 2.0: versions, approval workflow, e-signature, portal, configurator."""
import pytest
from datetime import date, timedelta

from app.models.quotation import QuotationVersion


async def _create_quotation(client, auth_headers, discount=0, total_price=1000, optional=False):
    items = [{
        "description": "სტანდარტული პროდუქტი", "quantity": 1, "unit_price": total_price,
        "discount_percent": 0,
    }]
    if optional:
        items.append({
            "description": "ოფციონალური დანამატი", "quantity": 1, "unit_price": 200,
            "discount_percent": 0, "is_optional": True, "config": {"color": "წითელი"},
        })
    r = await client.post("/api/v1/quotations/", json={
        "client_id": None,  # filled below
        "quotation_date": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=14)).isoformat(),
        "discount_percent": discount,
        "items": items,
    }, headers=auth_headers)
    return r


async def _make_client(client, auth_headers):
    r = await client.post("/api/v1/clients/", json={
        "client_type": "legal", "name": "შეთავაზების კლიენტი", "identification_code": f"QT-{__import__('uuid').uuid4().hex[:6]}",
    }, headers=auth_headers)
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_versions_and_revision(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    r = await client.post("/api/v1/quotations/", json={
        "client_id": cid,
        "quotation_date": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=14)).isoformat(),
        "discount_percent": 0,
        "items": [{"description": "პროდუქტი A", "quantity": 2, "unit_price": 500}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    qid = r.json()["data"]["id"]
    assert r.json()["data"]["version_number"] == 1

    # revise → version 2
    r = await client.put(f"/api/v1/quotations/{qid}", json={
        "discount_percent": 5,
        "items": [{"description": "პროდუქტი A", "quantity": 3, "unit_price": 500}],
        "change_reason": "ფასის გადახედვა",
    }, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["version_number"] == 2
    assert r.json()["data"]["status"] == "draft"

    # versions list → 1 snapshot (v1 state, captured on first revision)
    r = await client.get(f"/api/v1/quotations/{qid}/versions", headers=auth_headers)
    assert r.status_code == 200
    versions = r.json()["data"]
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1  # snapshot of v1
    assert versions[0]["items_snapshot"][0]["quantity"] == 2.0


@pytest.mark.asyncio
async def test_approval_workflow(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    # small quotation → no approval needed
    r = await client.post("/api/v1/quotations/", json={
        "client_id": cid,
        "quotation_date": date.today().isoformat(),
        "discount_percent": 0,
        "items": [{"description": "პროდუქტი", "quantity": 1, "unit_price": 100}],
    }, headers=auth_headers)
    qid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/quotations/{qid}/approval", headers=auth_headers)
    assert r.status_code == 400  # not needed

    # big discount → approval required
    r = await client.post("/api/v1/quotations/", json={
        "client_id": cid,
        "quotation_date": date.today().isoformat(),
        "discount_percent": 15,
        "items": [{"description": "პროდუქტი", "quantity": 1, "unit_price": 1000}],
    }, headers=auth_headers)
    qid = r.json()["data"]["id"]
    r = await client.post(f"/api/v1/quotations/{qid}/approval", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["approval_required"] is True
    assert r.json()["data"]["approval_request_id"] is not None

    # duplicate request → 400
    r = await client.post(f"/api/v1/quotations/{qid}/approval", headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_electronic_signature(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    r = await client.post("/api/v1/quotations/", json={
        "client_id": cid,
        "quotation_date": date.today().isoformat(),
        "discount_percent": 0,
        "items": [{"description": "პროდუქტი", "quantity": 1, "unit_price": 1000}],
    }, headers=auth_headers)
    qid = r.json()["data"]["id"]

    # sign on draft → 400
    r = await client.post(f"/api/v1/quotations/{qid}/sign", json={"signer_name": "გიორგი"}, headers=auth_headers)
    assert r.status_code == 400

    # send → sign → accepted + hash
    r = await client.patch(f"/api/v1/quotations/{qid}/status", json={"status": "sent"}, headers=auth_headers)
    assert r.status_code == 200
    r = await client.post(f"/api/v1/quotations/{qid}/sign", json={"signer_name": "გიორგი", "method": "manual"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "accepted"
    assert d["signed_by"] == "გიორგი"
    assert d["signature_hash"] and len(d["signature_hash"]) == 64

    # double sign → 400
    r = await client.post(f"/api/v1/quotations/{qid}/sign", json={"signer_name": "გიორგი"}, headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_portal_accept_reject(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    r = await client.post("/api/v1/quotations/", json={
        "client_id": cid,
        "quotation_date": date.today().isoformat(),
        "discount_percent": 0,
        "items": [{"description": "პროდუქტი", "quantity": 1, "unit_price": 1000}],
    }, headers=auth_headers)
    qid = r.json()["data"]["id"]
    await client.patch(f"/api/v1/quotations/{qid}/status", json={"status": "sent"}, headers=auth_headers)

    # generate token
    r = await client.post(f"/api/v1/quotations/{qid}/portal-token", headers=auth_headers)
    assert r.status_code == 200
    token = r.json()["data"]["portal_token"]
    assert token

    # portal accept (no auth!)
    r = await client.post(f"/api/v1/quotations/portal/{token}", json={"action": "accept", "signer_name": "კლიენტი ივანე"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "accepted"

    # second response → 400 (already responded)
    r = await client.post(f"/api/v1/quotations/portal/{token}", json={"action": "reject"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_optional_lines_and_config(client, auth_headers):
    cid = await _make_client(client, auth_headers)
    r = await client.post("/api/v1/quotations/", json={
        "client_id": cid,
        "quotation_date": date.today().isoformat(),
        "discount_percent": 0,
        "items": [
            {"description": "ბაზური პროდუქტი", "quantity": 1, "unit_price": 1000},
            {"description": "ოფციონალური დანამატი", "quantity": 1, "unit_price": 200,
             "is_optional": True, "config": {"color": "წითელი", "size": "L"}},
        ],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 2
    opt = [i for i in items if i["is_optional"]]
    assert len(opt) == 1
    assert opt[0]["config"] == {"color": "წითელი", "size": "L"}
    # optional line included in total
    assert r.json()["data"]["total"] == 1416.0  # (1000+200)*1.18
