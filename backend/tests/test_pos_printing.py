"""POS network printing — device IP, direct send (raw 9100)."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_print_to_unreachable_printer(client, auth_headers, test_company, db_session):
    # device with an unreachable IP (RFC 5737 TEST-NET)
    resp = await client.post("/api/v1/pos/fiscal-devices", params={
        "name": "Printer 1", "device_type": "fiscal_printer",
        "serial_number": "SN-001", "ip_address": "192.0.2.1", "port": 9100,
    }, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    device_id = resp.json()["data"]["id"]

    resp = await client.post("/api/v1/pos/sessions", json={"name": "Print Shift"}, headers=auth_headers)
    session_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/products/", json={
        "name": "Net Product", "sku": "NET-1", "sale_price": 40,
    }, headers=auth_headers)
    product_id = resp.json()["data"]["id"]
    resp = await client.post("/api/v1/pos/orders", json={
        "session_id": session_id,
        "items": [{"product_id": product_id, "quantity": 1, "unit_price": 40}],
        "payment_method": "cash",
    }, headers=auth_headers)
    order = resp.json()["data"]

    # unreachable printer → 502 with clear detail
    resp = await client.post(
        f"/api/v1/pos/orders/{order['id']}/print",
        params={"device_id": device_id},
        headers=auth_headers,
    )
    assert resp.status_code == 502, resp.text
    assert "მიუწვდომელია" in resp.json()["detail"]

    # device without IP → 404
    resp = await client.post("/api/v1/pos/fiscal-devices", params={
        "name": "No IP", "device_type": "fiscal_printer", "serial_number": "SN-002",
    }, headers=auth_headers)
    device2 = resp.json()["data"]["id"]
    resp = await client.post(
        f"/api/v1/pos/orders/{order['id']}/print",
        params={"device_id": device2},
        headers=auth_headers,
    )
    assert resp.status_code == 404, resp.text
