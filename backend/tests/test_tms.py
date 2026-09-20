"""TMS 2.0 acceptance tests (REQ-TMS-01..09; AC-TMS-01..03).

Uses the same conventions as test_dashboard_operational.py: authenticated
HTTP client (client + auth_headers of test_admin) + db_session for setup.

Covers the operational transport/delivery chain via the public API:
- create delivery request → trip → stop → load
- dispatch guards (REQ-TMS-03) and stop events (REQ-TMS-04/05/06)
- AC-TMS-01 capacity block, AC-TMS-02 offline POD idempotency
- full chain: dispatch → start → arrive → deliver → POD → complete → close
"""
import pytest
from sqlalchemy import select

from app.models.fleet import Vehicle
from app.models.fleet_tms import (
    DeliveryRequest, Trip, TripStop, TripLoad, TripPOD,
)


async def _prepare_trip(client, auth_headers, trip_number="TR-9001",
                        request_number="DR-9001", weight="1000.000", volume="25.000"):
    """Create delivery request + trip + stop + load via the API; return ids."""
    r = await client.post("/api/v1/fleet/tms/delivery-requests", headers=auth_headers, json={
        "request_number": request_number,
        "dropoff_address": "თბილისი, ტესტის ქუჩა 5",
        "weight_kg": weight, "volume_m3": volume,
        "package_count": 4, "delivery_date": "2026-09-25",
    })
    assert r.status_code == 200, r.text
    dr_id = r.json()["data"]["id"]

    t = await client.post("/api/v1/fleet/tms/trips", headers=auth_headers, json={
        "trip_number": trip_number, "planned_start": "2026-09-25T08:00:00",
    })
    assert t.status_code == 200, t.text
    trip_id = t.json()["data"]["id"]

    s = await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/stops", headers=auth_headers, json={
        "sequence": 1, "address": "თბილისი, ტესტის ქუჩა 5",
    })
    assert s.status_code == 200, s.text
    stop_id = s.json()["data"]["id"]

    l = await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/loads", headers=auth_headers, json={
        "delivery_id": dr_id, "stop_id": stop_id, "quantity": 10,
        "weight_kg": weight, "volume_m3": volume,
    })
    assert l.status_code == 200, l.text

    return dr_id, trip_id, stop_id


async def _cleanup(db_session, trip_id, dr_ids, vehicle=None):
    rows = (await db_session.execute(
        select(TripPOD).where(TripPOD.trip_id == trip_id))).scalars().all()
    for r in rows:
        await db_session.delete(r)
    loads = (await db_session.execute(
        select(TripLoad).where(TripLoad.trip_id == trip_id))).scalars().all()
    for l in loads:
        await db_session.delete(l)
    stops = (await db_session.execute(
        select(TripStop).where(TripStop.trip_id == trip_id))).scalars().all()
    for s in stops:
        await db_session.delete(s)
    trip = (await db_session.execute(
        select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
    if trip:
        await db_session.delete(trip)
    for did in dr_ids:
        d = (await db_session.execute(
            select(DeliveryRequest).where(DeliveryRequest.id == did))).scalar_one_or_none()
        if d:
            await db_session.delete(d)
    if vehicle:
        await db_session.delete(vehicle)
    await db_session.commit()


@pytest.mark.asyncio
async def test_tms_end_to_end_chain(client, auth_headers, test_company, db_session):
    """REQ-TMS-01..06: full chain through the public API.

    Create a vehicle directly, then delivery request → trip → stop → load,
    dispatch (vehicle validations), start, arrive, deliver → POD, complete,
    close; the delivery request flips to delivered."""
    vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="TMS-E2E-1", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", initial_mileage=100, current_mileage=100,
        capacity_kg=5000, capacity_m3=100, ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()

    dr_id, trip_id, stop_id = await _prepare_trip(
        client, auth_headers, trip_number="TR-9001", request_number="DR-9001")

    # dispatch with explicit vehicle
    d = await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/dispatch",
                          headers=auth_headers, json={"vehicle_id": str(vehicle.id)})
    assert d.status_code == 200, d.text
    assert d.json()["data"]["status"] == "dispatched"

    st = await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/start",
                          headers=auth_headers, json={})
    assert st.json()["data"]["status"] == "in_progress"

    ar = await client.post(f"/api/v1/fleet/tms/trip-stops/{stop_id}/events",
                           headers=auth_headers, json={"event": "arrive"})
    assert ar.json()["data"]["status"] == "arrived"

    dl = await client.post(f"/api/v1/fleet/tms/trip-stops/{stop_id}/events",
                           headers=auth_headers, json={
                               "event": "deliver", "delivered_qty": 10,
                               "recipient_name": "გიორგი", "device_event_id": "dev-2001",
                           })
    assert dl.status_code == 200, dl.text
    assert dl.json()["data"]["status"] == "delivered"

    pods = await client.get(f"/api/v1/fleet/tms/trips/{trip_id}/pods", headers=auth_headers)
    assert len(pods.json()["data"]) == 1
    assert pods.json()["data"][0]["delivered_qty"] == "10.000"
    assert pods.json()["data"][0]["recipient_name"] == "გიორგი"

    dr_list = await client.get("/api/v1/fleet/tms/delivery-requests", headers=auth_headers)
    status = [x["status"] for x in dr_list.json()["data"] if x["request_number"] == "DR-9001"][0]
    assert status == "delivered"

    co = await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/complete",
                           headers=auth_headers, json={})
    assert co.json()["data"]["status"] == "completed"
    cl = await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/close",
                           headers=auth_headers, json={})
    assert cl.json()["data"]["status"] == "closed"

    await _cleanup(db_session, trip_id, [dr_id], vehicle)


@pytest.mark.asyncio
async def test_tms_offline_pod_idempotency(client, auth_headers, test_company, db_session):
    """AC-TMS-02: the same offline device_event_id is recorded as a single POD."""
    vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="TMS-ID-1", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", capacity_kg=5000, capacity_m3=100,
        ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()

    dr_id, trip_id, stop_id = await _prepare_trip(
        client, auth_headers, trip_number="TR-9002", request_number="DR-9002")

    await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/dispatch",
                      headers=auth_headers, json={"vehicle_id": str(vehicle.id)})
    await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/start",
                      headers=auth_headers, json={})

    ev = {"event": "deliver", "delivered_qty": 10, "recipient_name": "უილი",
          "device_event_id": "offline-1"}
    a1 = await client.post(f"/api/v1/fleet/tms/trip-stops/{stop_id}/events",
                           headers=auth_headers, json=ev)
    a2 = await client.post(f"/api/v1/fleet/tms/trip-stops/{stop_id}/events",
                           headers=auth_headers, json=ev)
    assert a1.status_code == 200, a1.text
    assert a2.json()["data"].get("duplicate") is True

    rows = (await db_session.execute(
        select(TripPOD).where(TripPOD.device_event_id == "offline-1"))).scalars().all()
    assert len(rows) == 1

    await _cleanup(db_session, trip_id, [dr_id], vehicle)


@pytest.mark.asyncio
async def test_tms_capacity_block(client, auth_headers, test_company, db_session):
    """AC-TMS-01: a load that pushes the vehicle past its cargo weight capacity
    is rejected with 409."""
    vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="TMS-CAP-1", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", capacity_kg=5000, capacity_m3=100,
        ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()

    # first load 4000kg
    dr_id, trip_id, stop_id = await _prepare_trip(
        client, auth_headers, trip_number="TR-CAP1", request_number="DR-CAP1",
        weight="4000.000", volume="30.000")

    # attach vehicle to trip
    t = (await db_session.execute(select(Trip).where(Trip.id == trip_id))).scalar_one()
    t.vehicle_id = vehicle.id
    t.status = "planned"
    await db_session.commit()

    # second load of 4000kg → 8000 > 5000 → rejected
    r2 = await client.post("/api/v1/fleet/tms/delivery-requests", headers=auth_headers, json={
        "request_number": "DR-CAP1B", "dropoff_address": "მთავარი 2",
        "weight_kg": "4000.000", "volume_m3": "30.000", "delivery_date": "2026-09-25",
    })
    dr2_id = r2.json()["data"]["id"]
    l2 = await client.post(f"/api/v1/fleet/tms/trips/{trip_id}/loads", headers=auth_headers, json={
        "delivery_id": dr2_id, "stop_id": stop_id, "quantity": 10,
        "weight_kg": "4000.000", "volume_m3": "30.000",
    })
    assert l2.status_code == 409, l2.text
    assert "ლიმიტი" in l2.text or "გადაჭარბებული" in l2.text

    await _cleanup(db_session, trip_id, [dr_id, dr2_id], vehicle)


@pytest.mark.asyncio
async def test_tms_vehicle_availability(client, auth_headers, test_company, db_session):
    """REQ-TMS-09: availability endpoint reports a valid idle vehicle as free
    and lists its cargo capacity."""
    vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="TMS-AVAIL-1", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", capacity_kg=5000, capacity_m3=100,
        ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()

    av = await client.get(f"/api/v1/fleet/tms/vehicles/{vehicle.id}/availability",
                          headers=auth_headers)
    assert av.status_code == 200, av.text
    data = av.json()["data"]
    assert data["available"] is True
    assert data["capacity_kg"].startswith("5000")

    await db_session.delete(vehicle)
    await db_session.commit()
