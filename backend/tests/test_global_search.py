# backend/tests/test_global_search.py
"""Global search: transliteration (Georgian/Latin) and grouping."""

import pytest_asyncio


@pytest_asyncio.fixture
async def seeded_client(client, auth_headers):
    """Create a client with a Georgian name for search tests."""
    res = await client.post(
        "/api/v1/clients/",
        json={
            "name": "შპს ივერია",
            "client_type": "legal",
            "identification_code": "404010101",
            "status": "active",
            "address": "თბილისი",
        },
        headers=auth_headers,
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["data"]


async def test_search_georgian_input(client, auth_headers, seeded_client):
    """Georgian query finds the client."""
    res = await client.get("/api/v1/search", params={"q": "ივერია"}, headers=auth_headers)
    assert res.status_code == 200
    names = [c["name"] for c in res.json()["data"]["clients"]]
    assert "შპს ივერია" in names


async def test_search_latin_input(client, auth_headers, seeded_client):
    """Latin transliteration finds the Georgian client name."""
    res = await client.get("/api/v1/search", params={"q": "iveria"}, headers=auth_headers)
    assert res.status_code == 200
    names = [c["name"] for c in res.json()["data"]["clients"]]
    assert "შპს ივერია" in names


async def test_search_latin_company_prefix(client, auth_headers, seeded_client):
    """'shps' (Latin) resolves to 'შპს' and matches."""
    res = await client.get("/api/v1/search", params={"q": "shps"}, headers=auth_headers)
    assert res.status_code == 200
    names = [c["name"] for c in res.json()["data"]["clients"]]
    assert "შპს ივერია" in names


async def test_search_no_results(client, auth_headers):
    """Gibberish query returns empty groups (200, not error)."""
    res = await client.get("/api/v1/search", params={"q": "zzzqqqyyy"}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["clients"] == []
    assert data["products"] == []
    assert data["orders"] == []
    assert data["invoices"] == []
    assert data["suppliers"] == []
