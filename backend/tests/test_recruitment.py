import pytest


async def test_recruitment_crud(client, auth_headers):
    # create
    r = await client.post(
        "/api/v1/recruitment/",
        headers=auth_headers,
        json={
            "title": "Backend Engineer",
            "department": "Engineering",
            "location": "Tbilisi",
            "employment_type": "full_time",
            "salary_min": 3000,
            "salary_max": 5000,
            "description": "Build APIs",
            "status": "open",
        },
    )
    assert r.status_code == 200, r.text
    posting = r.json()["data"]
    assert posting["title"] == "Backend Engineer"
    assert posting["status"] == "open"
    pid = posting["id"]

    # list
    r = await client.get("/api/v1/recruitment/", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["total"] == 1

    # list filtered by status
    r = await client.get(
        "/api/v1/recruitment/?status=open", headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 1

    # get
    r = await client.get(f"/api/v1/recruitment/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["id"] == pid

    # update
    r = await client.patch(
        f"/api/v1/recruitment/{pid}",
        headers=auth_headers,
        json={"status": "closed", "location": "Remote"},
    )
    assert r.status_code == 200, r.text
    updated = r.json()["data"]
    assert updated["status"] == "closed"
    assert updated["location"] == "Remote"

    # delete
    r = await client.delete(f"/api/v1/recruitment/{pid}", headers=auth_headers)
    assert r.status_code == 200
    r = await client.get(f"/api/v1/recruitment/{pid}", headers=auth_headers)
    assert r.status_code == 404


async def test_recruitment_requires_auth(client):
    r = await client.get("/api/v1/recruitment/")
    assert r.status_code == 401


async def test_recruitment_invalid_status_rejected(client, auth_headers):
    r = await client.post(
        "/api/v1/recruitment/",
        headers=auth_headers,
        json={"title": "Bad", "status": "nonsense"},
    )
    assert r.status_code == 422
