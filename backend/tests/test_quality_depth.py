"""Quality Control — Odoo-depth: control points, tests, results, alerts."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_product(client, auth_headers) -> str:
    p = await client.post("/api/v1/products/", json={
        "name": f"Q-{uuid.uuid4().hex[:6]}", "sku": f"QSKU-{uuid.uuid4().hex[:6]}",
        "sale_price": 10, "purchase_price": 5,
    }, headers=auth_headers)
    assert p.status_code in (200, 201), p.text
    return p.json()["data"]["id"]


async def test_control_point_and_tests(client, auth_headers):
    pid = await _seed_product(client, auth_headers)

    cp = await client.post("/api/v1/quality-control/control-points", json={
        "name": "მიღება — ნედლეული", "point_type": "receipt", "product_id": pid,
    }, headers=auth_headers)
    assert cp.status_code == 201, cp.text
    cp_id = cp.json()["data"]["id"]

    t = await client.post(f"/api/v1/quality-control/control-points/{cp_id}/tests", json={
        "name": "წონა", "test_type": "measure", "unit": "kg",
        "min_value": 9.5, "max_value": 10.5,
    }, headers=auth_headers)
    assert t.status_code == 201, t.text
    test_id = t.json()["data"]["id"]

    lst = await client.get(f"/api/v1/quality-control/control-points/{cp_id}/tests", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1
    assert lst.json()["data"][0]["test_type"] == "measure"


async def test_measure_result_pass_and_fail(client, auth_headers, test_admin):
    pid = await _seed_product(client, auth_headers)
    cp = await client.post("/api/v1/quality-control/control-points", json={
        "name": "წარმოება", "point_type": "production", "product_id": pid,
    }, headers=auth_headers)
    cp_id = cp.json()["data"]["id"]
    t = await client.post(f"/api/v1/quality-control/control-points/{cp_id}/tests", json={
        "name": "სიგრძე", "test_type": "measure", "unit": "cm", "min_value": 90, "max_value": 110,
    }, headers=auth_headers)
    test_id = t.json()["data"]["id"]

    # create a check
    ch = await client.post("/api/v1/quality-control/", json={
        "product_id": pid, "status": "pending", "checked_by": str(test_admin.id),
    }, headers=auth_headers)
    assert ch.status_code in (200, 201), ch.text
    check_id = ch.json()["data"]["id"]

    # pass: 100 within [90, 110]
    ok = await client.post(f"/api/v1/quality-control/checks/{check_id}/results", json={
        "test_id": test_id, "measured_value": 100,
    }, headers=auth_headers)
    assert ok.status_code == 201, ok.text
    assert ok.json()["data"]["passed"] is True

    # fail: 150 out of range → check auto-fails
    bad = await client.post(f"/api/v1/quality-control/checks/{check_id}/results", json={
        "test_id": test_id, "measured_value": 150,
    }, headers=auth_headers)
    assert bad.status_code == 201, bad.text
    assert bad.json()["data"]["passed"] is False

    got = await client.get(f"/api/v1/quality-control/{check_id}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["data"]["status"] == "fail"


async def test_quality_alert_flow(client, auth_headers):
    pid = await _seed_product(client, auth_headers)

    a = await client.post("/api/v1/quality-control/alerts", json={
        "title": "მომწოდებლის პარტია უარყოფილია", "source": "supplier",
        "product_id": pid, "priority": "high", "description": "ტენიანობა ნორმაზე მაღალი",
    }, headers=auth_headers)
    assert a.status_code == 201, a.text
    alert_id = a.json()["data"]["id"]

    lst = await client.get("/api/v1/quality-control/alerts", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1
    assert lst.json()["data"][0]["status"] == "open"

    res = await client.post(f"/api/v1/quality-control/alerts/{alert_id}/resolve", json={
        "resolution": "მომწოდებელს დაუბრუნდა პარტია",
    }, headers=auth_headers)
    assert res.status_code == 200, res.text

    lst2 = await client.get("/api/v1/quality-control/alerts?status=done", headers=auth_headers)
    assert len(lst2.json()["data"]) == 1
    assert lst2.json()["data"][0]["resolution"] == "მომწოდებელს დაუბრუნდა პარტია"
