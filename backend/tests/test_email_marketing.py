async def test_email_campaign_crud(client, auth_headers):
    # create
    r = await client.post(
        "/api/v1/email-campaigns/",
        headers=auth_headers,
        json={
            "name": "Summer Promo",
            "subject": "Exclusive summer deals",
            "audience": {"segments": ["all"], "exclude": ["vip"]},
            "status": "draft",
        },
    )
    assert r.status_code == 200, r.text
    campaign = r.json()["data"]
    assert campaign["name"] == "Summer Promo"
    assert campaign["subject"] == "Exclusive summer deals"
    assert campaign["audience"] == {"segments": ["all"], "exclude": ["vip"]}
    assert campaign["status"] == "draft"
    cid = campaign["id"]

    # get
    r = await client.get(f"/api/v1/email-campaigns/{cid}", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["id"] == cid

    # list
    r = await client.get(
        "/api/v1/email-campaigns/", headers=auth_headers, params={"status": "draft"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["total"] == 1

    # update
    r = await client.patch(
        f"/api/v1/email-campaigns/{cid}",
        headers=auth_headers,
        json={"status": "scheduled"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "scheduled"

    # invalid status rejected
    r = await client.patch(
        f"/api/v1/email-campaigns/{cid}",
        headers=auth_headers,
        json={"status": "bogus"},
    )
    assert r.status_code == 422, r.text

    # delete
    r = await client.delete(f"/api/v1/email-campaigns/{cid}", headers=auth_headers)
    assert r.status_code == 200, r.text

    # gone
    r = await client.get(f"/api/v1/email-campaigns/{cid}", headers=auth_headers)
    assert r.status_code == 404, r.text
