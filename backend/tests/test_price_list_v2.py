"""PriceList 2.0: rule engine — quantity tiers, date validity, segment pricing, currency, margin floor, cost+markup, approval."""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.models.approval import ApprovalRequest
from app.models.client import ClientGroupDef
from app.models.pricing import PriceList, PriceListItem
from app.models.product import Product


async def _make_product(client, auth_headers, purchase_price=100):
    r = await client.post("/api/v1/products/", json={
        "sku": f"PL-{__import__('uuid').uuid4().hex[:6]}",
        "name": "ფასების სიის პროდუქტი",
        "sale_price": 200,
        "purchase_price": purchase_price,
        "unit": "ცალი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


async def _make_segment(client, auth_headers, name="VIP"):
    r = await client.post("/api/v1/clients/client-groups", json={
        "name": name, "description": "სეგმენტი",
    }, headers=auth_headers)
    assert r.status_code in (200, 201), r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_quantity_tiers(client, auth_headers):
    """რაოდენობრივი საფეხურები: 1 ცალი 100, 10+ ცალი 80."""
    pid = await _make_product(client, auth_headers)
    r = await client.post("/api/v1/price-lists/", json={
        "name": "საფეხურები", "currency": "GEL",
        "items": [
            {"product_id": pid, "price": 100, "min_quantity": 1},
            {"product_id": pid, "price": 80, "min_quantity": 10},
        ],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r1 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["data"]["price"] == 100.0

    r2 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=15", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["price"] == 80.0
    assert r2.json()["data"]["min_quantity"] == 10.0


@pytest.mark.asyncio
async def test_date_validity(client, auth_headers):
    """თარიღით მოქმედება: ვადაგასული სია არ გამოიყენება."""
    pid = await _make_product(client, auth_headers)
    past = (date.today() - timedelta(days=10)).isoformat()
    r = await client.post("/api/v1/price-lists/", json={
        "name": "ძველი სია", "currency": "GEL",
        "valid_from": (date.today() - timedelta(days=30)).isoformat(),
        "valid_until": past,
        "items": [{"product_id": pid, "price": 50}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r2 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1", headers=auth_headers)
    assert r2.status_code == 404  # expired → no price

    # future list also skipped
    r3 = await client.post("/api/v1/price-lists/", json={
        "name": "მომავალი სია", "currency": "GEL",
        "valid_from": (date.today() + timedelta(days=5)).isoformat(),
        "items": [{"product_id": pid, "price": 60}],
    }, headers=auth_headers)
    assert r3.status_code == 201, r3.text
    r4 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1", headers=auth_headers)
    assert r4.status_code == 404


@pytest.mark.asyncio
async def test_segment_pricing(client, auth_headers, db_session, test_company):
    """კლიენტის სეგმენტის ფასი: VIP კლიენტი იღებს VIP სიის ფასს."""
    pid = await _make_product(client, auth_headers)
    seg_id = await _make_segment(client, auth_headers, "VIP")

    # general list
    r = await client.post("/api/v1/price-lists/", json={
        "name": "ზოგადი", "currency": "GEL", "is_default": True,
        "items": [{"product_id": pid, "price": 100}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    # VIP list
    r = await client.post("/api/v1/price-lists/", json={
        "name": "VIP სია", "currency": "GEL", "segment_id": seg_id,
        "items": [{"product_id": pid, "price": 70}],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    # client in VIP segment
    cid = (await client.post("/api/v1/clients/", json={
        "client_type": "legal", "name": "VIP კლიენტი",
        "identification_code": f"VIP-{__import__('uuid').uuid4().hex[:6]}",
    }, headers=auth_headers)).json()["data"]["id"]
    from sqlalchemy import text
    await db_session.execute(text(
        "INSERT INTO client_groups (client_id, group_id) VALUES (:c, :g)"
    ), {"c": str(cid), "g": str(seg_id)})
    await db_session.commit()

    r2 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1&client_id={cid}", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["price"] == 70.0
    assert r2.json()["data"]["price_list_name"] == "VIP სია"

    # non-VIP client → general price
    cid2 = (await client.post("/api/v1/clients/", json={
        "client_type": "legal", "name": "ჩვეულებრივი კლიენტი",
        "identification_code": f"GEN-{__import__('uuid').uuid4().hex[:6]}",
    }, headers=auth_headers)).json()["data"]["id"]
    r3 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1&client_id={cid2}", headers=auth_headers)
    assert r3.status_code == 200, r3.text
    assert r3.json()["data"]["price"] == 100.0


@pytest.mark.asyncio
async def test_currency_pricing(client, auth_headers):
    """ვალუტის მიხედვით ფასი: USD override."""
    pid = await _make_product(client, auth_headers)
    r = await client.post("/api/v1/price-lists/", json={
        "name": "ვალუტა", "currency": "GEL",
        "items": [
            {"product_id": pid, "price": 100},
            {"product_id": pid, "price": 30, "currency": "USD"},
        ],
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    r1 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1&currency=USD", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["data"]["price"] == 30.0
    assert r1.json()["data"]["currency"] == "USD"

    r2 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1&currency=GEL", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["data"]["price"] == 100.0


@pytest.mark.asyncio
async def test_cost_plus_markup_and_margin_floor(client, auth_headers, db_session):
    """ფორმულა cost+markup და მარჟის მინიმალური ზღვარი."""
    pid = await _make_product(client, auth_headers, purchase_price=100)
    r = await client.post("/api/v1/price-lists/", json={
        "name": "cost+markup", "currency": "GEL",
        "pricing_method": "cost_plus_markup", "markup_percent": 30,
        "min_margin_percent": 20,
        "items": [{"product_id": pid, "price": 0}],  # price computed from cost
    }, headers=auth_headers)
    assert r.status_code == 201, r.text
    # cost 100 + 30% = 130
    assert float(r.json()["data"]["items"][0]["price"]) == 130.0

    r2 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["price"] == 130.0
    assert d["rule"] == "cost+30.0%"
    # margin floor: 130 >= 120 (100+20%) → not violated
    assert d["margin_floor_violated"] is False


@pytest.mark.asyncio
async def test_approval_when_below_min_margin(client, auth_headers, db_session, test_company):
    """approval, თუ ფასი მინიმუმზე დაბალია."""
    pid = await _make_product(client, auth_headers, purchase_price=100)
    r = await client.post("/api/v1/price-lists/", json={
        "name": "დაბალი ფასი", "currency": "GEL",
        "pricing_method": "fixed",
        "min_margin_percent": 30,  # min price = 130
        "approval_required": True,
        "items": [{"product_id": pid, "price": 110}],  # below 130 → approval
    }, headers=auth_headers)
    assert r.status_code == 201, r.text

    # approval request created
    from sqlalchemy import select
    reqs = (await db_session.execute(select(ApprovalRequest).where(
        ApprovalRequest.approval_type == "price_list",
    ))).scalars().all()
    assert len(reqs) == 1
    assert reqs[0].status == "pending"
    assert "110" in reqs[0].description

    # resolve flags the violation
    r2 = await client.get(f"/api/v1/price-lists/resolve?product_id={pid}&quantity=1", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    d = r2.json()["data"]
    assert d["margin_floor_violated"] is True
    assert d["min_allowed_price"] == 130.0
    assert d["approval_required"] is True
