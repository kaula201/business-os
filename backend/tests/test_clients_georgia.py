"""API tests for Georgian identification-code validation and masking."""
import pytest


async def _create_client(client, headers, payload):
    return await client.post("/api/v1/clients/", headers=headers, json=payload)


@pytest.mark.asyncio
async def test_create_legal_rejects_invalid_identification_code(client, auth_headers):
    resp = await client.post(
        "/api/v1/clients/",
        headers=auth_headers,
        json={
            "name": "Invalid Legal",
            "client_type": "legal",
            "identification_code": "12345678",
            "is_vat_payer": True,
        },
    )
    assert resp.status_code == 422
    assert "9" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_individual_rejects_invalid_identification_code(client, auth_headers):
    resp = await client.post(
        "/api/v1/clients/",
        headers=auth_headers,
        json={
            "name": "Invalid Person",
            "client_type": "individual",
            "identification_code": "0123456789",
            "is_vat_payer": True,
        },
    )
    assert resp.status_code == 422
    assert "11" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_legal_accepts_valid_identification_code(client, auth_headers):
    resp = await client.post(
        "/api/v1/clients/",
        headers=auth_headers,
        json={
            "name": "Valid Legal",
            "client_type": "legal",
            "identification_code": "123456789",
            "is_vat_payer": True,
        },
    )
    assert resp.status_code in (200, 201), resp.text


@pytest.mark.asyncio
async def test_create_individual_accepts_valid_identification_code(client, auth_headers):
    resp = await client.post(
        "/api/v1/clients/",
        headers=auth_headers,
        json={
            "name": "Valid Person",
            "client_type": "individual",
            "identification_code": "01234567890",
            "is_vat_payer": True,
        },
    )
    assert resp.status_code in (200, 201), resp.text
