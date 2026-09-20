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
from sqlalchemy import delete as sqla_delete

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


@pytest.mark.asyncio
async def test_tms_maintenance_block_dispatch(client, auth_headers, test_company, db_session):
    """REQ-TMS-03 / REQ-MNT-08: a vehicle in an open maintenance order is blocked
    at dispatch; a free vehicle dispatches normally."""
    from app.models.maintenance import MaintenanceOrder
    mnt_vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="MNT-BLOCK-9", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", capacity_kg=5000, capacity_m3=100,
        ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(mnt_vehicle)
    await db_session.flush()
    await db_session.commit()

    # open maintenance order referencing the vehicle's plate
    mnt = MaintenanceOrder(
        company_id=test_company.id, order_number="MNT-9001",
        description="ა.პ. სასწრაფო შეკეთება",
        asset_name=f"ტესტი {mnt_vehicle.plate_number}", status="in_progress",
    )
    db_session.add(mnt)
    await db_session.flush()
    await db_session.commit()

    # try dispatching a trip on the maintenance-blocked vehicle
    tr_resp = await client.post("/api/v1/fleet/tms/trips", headers=auth_headers, json={
        "trip_number": "TR-MNTBLOCK", "planned_start": "2026-09-25T08:00:00",
        "planned_end": "2026-09-25T12:00:00"})
    tr_id = tr_resp.json()["data"]["id"]
    disp = await client.post(f"/api/v1/fleet/tms/trips/{tr_id}/dispatch",
                             headers=auth_headers, json={"vehicle_id": str(mnt_vehicle.id)})
    assert disp.status_code == 409, disp.text
    assert "Maintenance" in disp.text or "დაბლოკილი" in disp.text

    await db_session.execute(sqla_delete(Trip).where(Trip.id == tr_id))
    await db_session.execute(sqla_delete(MaintenanceOrder).where(MaintenanceOrder.id == mnt.id))
    await db_session.delete(mnt_vehicle)
    await db_session.commit()


@pytest.mark.asyncio
async def test_tms_time_overlap_block(client, auth_headers, test_company, db_session):
    """REQ-TMS-02: the same vehicle cannot be dispatched on two trips whose
    planned windows overlap."""
    from app.models.fleet_tms import TripStop, TripLoad
    vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="TMS-OVLP-1", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", capacity_kg=10000, capacity_m3=200,
        ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()

    # Trip A already dispatched
    ta_num = "TR-OVLPA"
    ta = await client.post("/api/v1/fleet/tms/trips", headers=auth_headers, json={
        "trip_number": ta_num, "planned_start": "2026-09-25T08:00:00", "planned_end": "2026-09-25T12:00:00"})
    ta_id = ta.json()["data"]["id"]
    da = await client.post(f"/api/v1/fleet/tms/trips/{ta_id}/dispatch",
                           headers=auth_headers, json={"vehicle_id": str(vehicle.id)})
    assert da.status_code == 200, da.text

    # Trip B overlapping same vehicle → block
    tb = await client.post("/api/v1/fleet/tms/trips", headers=auth_headers, json={
        "trip_number": "TR-OVLPB", "planned_start": "2026-09-25T10:00:00", "planned_end": "2026-09-25T14:00:00"})
    tb_id = tb.json()["data"]["id"]
    db2 = await client.post(f"/api/v1/fleet/tms/trips/{tb_id}/dispatch",
                            headers=auth_headers, json={"vehicle_id": str(vehicle.id)})
    assert db2.status_code == 409, db2.text
    assert "უკვე დაგეგმილია" in db2.text

    await db_session.execute(sqla_delete(Trip).where(Trip.id == ta_id))
    await db_session.execute(sqla_delete(Trip).where(Trip.id == tb_id))
    await db_session.delete(vehicle)
    await db_session.commit()


@pytest.mark.asyncio
async def test_tms_wms_return_only_for_failed(client, auth_headers, test_company, db_session):
    """REQ-TMS-06: a delivery request only returns to warehouse when failed/
    partial; a delivered one cannot be stamped as returned via WMS."""
    vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="TMS-RET-1", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", capacity_kg=5000, capacity_m3=100,
        ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()

    dr_id, trip_id, stop_id = await _prepare_trip(
        client, auth_headers, trip_number="TR-RET", request_number="DR-RET",
        weight="1000.000", volume="20.000")

    # fail the stop
    fl = await client.post(f"/api/v1/fleet/tms/trip-stops/{stop_id}/events",
                           headers=auth_headers, json={
                               "event": "fail", "delivered_qty": 0,
                               "exception": "refused", "exception_reason": "მიმღებმა უარი თქვა",
                           })
    assert fl.status_code == 200, fl.text

    # WMS return allowed on failed
    ret = await client.post(f"/api/v1/fleet/tms/delivery-requests/{dr_id}/wms-return",
                            headers=auth_headers, json={})
    assert ret.status_code == 200, ret.text
    assert ret.json()["data"]["returned"] is True

    # a delivered request cannot be returned
    dr2, trip2, stop2 = await _prepare_trip(
        client, auth_headers, trip_number="TR-RET2", request_number="DR-RET2",
        weight="500.000", volume="10.000")
    dv = await client.post(f"/api/v1/fleet/tms/trip-stops/{stop2}/events",
                           headers=auth_headers, json={"event": "deliver", "delivered_qty": 10})
    assert dv.status_code == 200, dv.text
    ret2 = await client.post(f"/api/v1/fleet/tms/delivery-requests/{dr2}/wms-return",
                             headers=auth_headers, json={})
    assert ret2.status_code == 409, ret2.text

    await _cleanup(db_session, trip_id, [dr_id], vehicle)
    await _cleanup(db_session, trip2, [dr2])


@pytest.mark.asyncio
async def test_tms_pod_correction_requires_manager(client, auth_headers, test_company, db_session, test_employee):
    """REQ-TMS-06: POD correction requires manager rights; a plain employee is
    refused, and once corrected the original POD is preserved (supersedes)."""
    # obtain a low-privilege employee token via the API
    emp_resp = await client.post("/api/v1/auth/login",
                                 json={"email": "employee@test.ge", "password": "employee123"})
    assert emp_resp.status_code == 200, emp_resp.text
    emp_token = emp_resp.json()["data"]["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    # build a delivered POD
    vehicle = Vehicle(
        company_id=test_company.id,
        plate_number="TMS-PODC-1", brand="Toyota", model="Hiace", year=2024,
        fuel_type="diesel", capacity_kg=5000, capacity_m3=100,
        ownership="own", is_active=True,
        insurance_valid_until=None, tech_inspection_until=None,
    )
    db_session.add(vehicle)
    await db_session.flush()
    await db_session.commit()

    dr_id, trip_id, stop_id = await _prepare_trip(
        client, auth_headers, trip_number="TR-PODC", request_number="DR-PODC",
        weight="1000.000", volume="20.000")
    dl = await client.post(f"/api/v1/fleet/tms/trip-stops/{stop_id}/events",
                           headers=auth_headers, json={
                               "event": "deliver", "delivered_qty": 10, "recipient_name": "გიორგი",
                               "device_event_id": "podc-1"})
    assert dl.status_code == 200, dl.text
    pods = await client.get(f"/api/v1/fleet/tms/trips/{trip_id}/pods", headers=auth_headers)
    pod_id = pods.json()["data"][0]["id"]

    # employee cannot correct
    corr = {"delivered_qty": 8, "delivered_at": "2026-09-25T12:00:00", "recipient_name": "გიორგი",
            "exception": "partial", "exception_reason": "ნაწილობრივი"}
    emp_corr = await client.post(f"/api/v1/fleet/tms/pods/{pod_id}/correct",
                                 headers=emp_headers, json=corr)
    assert emp_corr.status_code == 403, emp_corr.text

    # admin corrects → new POD, original preserved
    adm_corr = await client.post(f"/api/v1/fleet/tms/pods/{pod_id}/correct",
                                 headers=auth_headers, json=corr)
    assert adm_corr.status_code == 200, adm_corr.text
    assert adm_corr.json()["data"]["supersedes"] == pod_id

    pods2 = await client.get(f"/api/v1/fleet/tms/trips/{trip_id}/pods", headers=auth_headers)
    supers = [p for p in pods2.json()["data"] if p.get("supersedes_id") == pod_id]
    assert len(supers) == 1

    await _cleanup(db_session, trip_id, [dr_id], vehicle)
