import pytest


@pytest.mark.asyncio
async def test_vehicle_location_is_saved_and_updated(client, auth_headers, test_company):
    created = await client.post(
        "/api/v1/fleet/vehicles",
        headers=auth_headers,
        json={
            "plate_number": "MAP-001",
            "brand": "Toyota",
            "model": "RAV4",
            "location_name": "თბილისი, საქართველო",
            "latitude": 41.7151,
            "longitude": 44.8271,
        },
    )
    assert created.status_code == 201
    vehicle = created.json()["data"]
    assert vehicle["location_name"] == "თბილისი, საქართველო"
    assert vehicle["latitude"] == pytest.approx(41.7151)
    assert vehicle["longitude"] == pytest.approx(44.8271)

    updated = await client.put(
        f"/api/v1/fleet/vehicles/{vehicle['id']}",
        headers=auth_headers,
        json={
            "location_name": "ბათუმი, საქართველო",
            "latitude": 41.6168,
            "longitude": 41.6367,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["location_name"] == "ბათუმი, საქართველო"

    listed = await client.get("/api/v1/fleet/vehicles", headers=auth_headers)
    assert listed.status_code == 200
    listed_vehicle = next(item for item in listed.json()["data"] if item["id"] == vehicle["id"])
    assert listed_vehicle["latitude"] == pytest.approx(41.6168)
    assert listed_vehicle["longitude"] == pytest.approx(41.6367)


@pytest.mark.asyncio
async def test_vehicle_location_rejects_invalid_coordinates(client, auth_headers, test_company):
    response = await client.post(
        "/api/v1/fleet/vehicles",
        headers=auth_headers,
        json={
            "plate_number": "MAP-002",
            "brand": "Ford",
            "model": "Transit",
            "latitude": 95,
            "longitude": 44.8,
        },
    )
    assert response.status_code == 422
