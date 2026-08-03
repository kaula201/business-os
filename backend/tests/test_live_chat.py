# backend/tests/test_live_chat.py
"""Live Chat module endpoint tests."""
import uuid


async def test_live_chat_crud(client, auth_headers, test_company):
    # create
    resp = await client.post(
        "/api/v1/live-chat/",
        headers=auth_headers,
        json={
            "sender_type": "customer",
            "sender_id": str(uuid.uuid4()),
            "message": "Hello, is my order shipped?",
            "channel": "web",
            "status": "delivered",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    msg_id = data["id"]
    assert data["company_id"] == str(test_company.id)
    assert data["sender_type"] == "customer"
    assert data["message"] == "Hello, is my order shipped?"

    # list
    resp = await client.get("/api/v1/live-chat/", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert any(i["id"] == msg_id for i in items)

    # get
    resp = await client.get(f"/api/v1/live-chat/{msg_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == msg_id

    # delete
    resp = await client.delete(f"/api/v1/live-chat/{msg_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.get(f"/api/v1/live-chat/{msg_id}", headers=auth_headers)
    assert resp.status_code == 404


async def test_live_chat_tenant_isolation(client, auth_headers, other_auth_headers, test_company):
    resp = await client.post(
        "/api/v1/live-chat/",
        headers=auth_headers,
        json={
            "sender_type": "user",
            "sender_id": str(uuid.uuid4()),
            "message": "company A msg",
            "channel": "mobile",
            "status": "read",
        },
    )
    msg_id = resp.json()["data"]["id"]

    # other company cannot read it
    resp = await client.get(f"/api/v1/live-chat/{msg_id}", headers=other_auth_headers)
    assert resp.status_code == 404

    # other company cannot delete it
    resp = await client.delete(f"/api/v1/live-chat/{msg_id}", headers=other_auth_headers)
    assert resp.status_code == 404
