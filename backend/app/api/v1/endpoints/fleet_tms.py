# backend/app/api/v1/endpoints/fleet_tms.py
"""TMS 2.0 — transport & delivery (REQ-TMS-01..09).

delivery-requests, trips (plan/dispatch/start/complete/close), trip-stop events
(arrive/depart/deliver/fail → POD), capacity checks, vehicle availability.
"""
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.time import utc_now
from app.models.user import User
from app.models.fleet import Vehicle
from app.models.fleet import FuelLog
from app.models.fleet_tms import (
    Driver, DeliveryRequest, Trip, TripStop, TripLoad, TripPOD, TripCostAllocation,
    TripTelemetry, TripGeofence, TripFreightInvoice,
)
from app.models.maintenance import MaintenanceOrder
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/fleet/tms", tags=["TMS — ტრანსპორტი"])


# ── Schemas ─────────────────────────────────────────────────────────────
class DeliveryRequestIn(BaseModel):
    request_number: str
    dropoff_address: str
    pickup_address: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    scheduled_from: datetime | None = None
    scheduled_to: datetime | None = None
    weight_kg: Decimal | None = None
    volume_m3: Decimal | None = None
    package_count: int | None = None
    special_conditions: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    delivery_date: date | None = None


class TripIn(BaseModel):
    trip_number: str
    vehicle_id: str | None = None
    driver_id: str | None = None
    carrier_id: str | None = None
    carrier_rate: Decimal | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    notes: str | None = None


class TripStopIn(BaseModel):
    sequence: int
    address: str
    contact_name: str | None = None
    contact_phone: str | None = None
    window_from: datetime | None = None
    window_to: datetime | None = None


class TripLoadIn(BaseModel):
    delivery_id: str
    stop_id: str | None = None
    quantity: Decimal
    weight_kg: Decimal | None = None
    volume_m3: Decimal | None = None


class StopEventIn(BaseModel):
    event: str  # arrive | depart | deliver | fail
    device_event_id: str | None = None
    device_time: datetime | None = None
    delivered_qty: Decimal | None = None
    recipient_name: str | None = None
    exception: str | None = None
    exception_reason: str | None = None
    evidence_id: str | None = None


class PODIn(BaseModel):
    delivered_qty: Decimal
    delivered_at: datetime
    recipient_name: str | None = None
    exception: str | None = None
    exception_reason: str | None = None
    evidence_id: str | None = None
    device_event_id: str | None = None
    device_time: datetime | None = None


class DispatchIn(BaseModel):
    vehicle_id: str | None = None
    driver_id: str | None = None


class CostAllocationIn(BaseModel):
    cost_type: str  # fuel | road | carrier | other
    amount: Decimal
    allocation_method: str = "weight"  # weight|volume|quantity
    source_expense_id: str | None = None


def _dr_resp(d: DeliveryRequest) -> dict:
    return {
        "id": str(d.id), "request_number": d.request_number, "status": d.status,
        "dropoff_address": d.dropoff_address, "pickup_address": d.pickup_address,
        "contact_name": d.contact_name, "contact_phone": d.contact_phone,
        "scheduled_from": d.scheduled_from.isoformat() if d.scheduled_from else None,
        "scheduled_to": d.scheduled_to.isoformat() if d.scheduled_to else None,
        "weight_kg": str(d.weight_kg) if d.weight_kg is not None else None,
        "volume_m3": str(d.volume_m3) if d.volume_m3 is not None else None,
        "package_count": d.package_count, "delivery_date": str(d.delivery_date) if d.delivery_date else None,
        "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
        "delivered_qty": str(d.delivered_qty) if d.delivered_qty is not None else None,
        "exception": d.exception,
    }


def _trip_resp(t: Trip) -> dict:
    return {
        "id": str(t.id), "trip_number": t.trip_number, "status": t.status,
        "vehicle_id": str(t.vehicle_id) if t.vehicle_id else None,
        "driver_id": str(t.driver_id) if t.driver_id else None,
        "carrier_id": str(t.carrier_id) if t.carrier_id else None,
        "planned_start": t.planned_start.isoformat() if t.planned_start else None,
        "planned_end": t.planned_end.isoformat() if t.planned_end else None,
        "total_weight_kg": str(t.total_weight_kg),
        "total_volume_m3": str(t.total_volume_m3),
        "dispatched_at": t.dispatched_at.isoformat() if t.dispatched_at else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    }


def _trip_load_weight(tl: TripLoad) -> Decimal:
    return tl.weight_kg if tl.weight_kg is not None else Decimal("0")


def _trip_load_volume(tl: TripLoad) -> Decimal:
    return tl.volume_m3 if tl.volume_m3 is not None else Decimal("0")


# ── Delivery Requests (REQ-TMS-01) ──────────────────────────────────────
@router.get("/delivery-requests", response_model=ResponseBase[list[dict]])
async def list_delivery_requests(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(DeliveryRequest).where(DeliveryRequest.company_id == current_user.company_id)
    if status:
        q = q.where(DeliveryRequest.status == status)
    q = q.order_by(DeliveryRequest.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return ResponseBase(data=[_dr_resp(d) for d in rows])


@router.post("/delivery-requests", response_model=ResponseBase[dict])
async def create_delivery_request(
    payload: DeliveryRequestIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(
        select(DeliveryRequest).where(
            DeliveryRequest.company_id == current_user.company_id,
            DeliveryRequest.request_number == payload.request_number,
        )
    )).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ ნომრით მოთხოვნა უკვე არსებობს")

    src_uuid = None
    if payload.source_id:
        try:
            src_uuid = uuid.UUID(payload.source_id)
        except ValueError:
            src_uuid = None

    d = DeliveryRequest(
        company_id=current_user.company_id,
        request_number=payload.request_number,
        dropoff_address=payload.dropoff_address,
        pickup_address=payload.pickup_address,
        contact_name=payload.contact_name,
        contact_phone=payload.contact_phone,
        scheduled_from=payload.scheduled_from,
        scheduled_to=payload.scheduled_to,
        weight_kg=payload.weight_kg,
        volume_m3=payload.volume_m3,
        package_count=payload.package_count,
        special_conditions=payload.special_conditions,
        source_type=payload.source_type,
        source_id=src_uuid,
        delivery_date=payload.delivery_date,
        created_by=current_user.id,
    )
    db.add(d)
    await db.commit()
    await db.refresh(d)
    return ResponseBase(data=_dr_resp(d))


@router.post("/delivery-requests/{delivery_id}/plan", response_model=ResponseBase[dict])
async def plan_delivery_request(
    delivery_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = (await db.execute(
        select(DeliveryRequest).where(
            DeliveryRequest.id == delivery_id, DeliveryRequest.company_id == current_user.company_id
        )
    )).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="მოთხოვნა არ მოიძებნა")
    if d.status not in ("draft", "planned"):
        raise HTTPException(status_code=409, detail="მოთხოვნა უკვე დაგეგმილია")
    d.status = "planned"
    await db.commit()
    await db.refresh(d)
    return ResponseBase(data=_dr_resp(d))


# ── Trips (REQ-TMS-02/03) ──────────────────────────────────────────────
@router.get("/trips", response_model=ResponseBase[list[dict]])
async def list_trips(
    status: str | None = None,
    vehicle_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Trip).where(Trip.company_id == current_user.company_id)
    if status:
        q = q.where(Trip.status == status)
    if vehicle_id:
        try:
            q = q.where(Trip.vehicle_id == uuid.UUID(vehicle_id))
        except ValueError:
            pass
    q = q.order_by(Trip.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return ResponseBase(data=[_trip_resp(t) for t in rows])


@router.post("/trips", response_model=ResponseBase[dict])
async def create_trip(
    payload: TripIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dup = (await db.execute(
        select(Trip).where(
            Trip.company_id == current_user.company_id, Trip.trip_number == payload.trip_number
        )
    )).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="ამ ნომრით რეისი უკვე არსებობს")

    def _uid(v):
        try:
            return uuid.UUID(v) if v else None
        except ValueError:
            return None

    t = Trip(
        company_id=current_user.company_id,
        trip_number=payload.trip_number,
        vehicle_id=_uid(payload.vehicle_id),
        driver_id=_uid(payload.driver_id),
        carrier_id=_uid(payload.carrier_id),
        carrier_rate=payload.carrier_rate,
        planned_start=payload.planned_start,
        planned_end=payload.planned_end,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return ResponseBase(data=_trip_resp(t))


@router.post("/trips/{trip_id}/stops", response_model=ResponseBase[dict])
async def add_trip_stop(
    trip_id: uuid.UUID,
    payload: TripStopIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    if trip.status not in ("draft", "planned"):
        raise HTTPException(status_code=409, detail="ღია რეისზე გაჩერების ცვლილება დაშვებული არ არის")
    s = TripStop(
        company_id=current_user.company_id, trip_id=trip.id,
        sequence=payload.sequence, address=payload.address,
        contact_name=payload.contact_name, contact_phone=payload.contact_phone,
        window_from=payload.window_from, window_to=payload.window_to,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return ResponseBase(data={"id": str(s.id), "sequence": s.sequence, "status": s.status})


@router.post("/trips/{trip_id}/loads", response_model=ResponseBase[dict])
async def add_trip_load(
    trip_id: uuid.UUID,
    payload: TripLoadIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    # REQ-TMS-02: capacity check per segment (aggregate weight/volume vs vehicle capacity)
    existing = (await db.execute(select(TripLoad).where(TripLoad.trip_id == trip.id))).scalars().all()
    cur_w = sum((_trip_load_weight(x) for x in existing), Decimal("0"))
    cur_v = sum((_trip_load_volume(x) for x in existing), Decimal("0"))
    new_w = payload.weight_kg if payload.weight_kg is not None else Decimal("0")
    new_v = payload.volume_m3 if payload.volume_m3 is not None else Decimal("0")
    if trip.vehicle_id:
        vh = (await db.execute(select(Vehicle).where(Vehicle.id == trip.vehicle_id))).scalar_one_or_none()
        if vh:
            if vh.capacity_kg is not None and (cur_w + new_w) > vh.capacity_kg:
                raise HTTPException(status_code=409, detail="წონის ლიმიტი გადაჭარბებულია")
            if vh.capacity_m3 is not None and (cur_v + new_v) > vh.capacity_m3:
                raise HTTPException(status_code=409, detail="მოცულობის ლიმიტი გადაჭარბებულია")

    try:
        did = uuid.UUID(payload.delivery_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="არასწორი delivery_id")
    stop_id = None
    if payload.stop_id:
        try:
            stop_id = uuid.UUID(payload.stop_id)
        except ValueError:
            stop_id = None

    # ensure delivery request matches company; flip to planned
    drq = (await db.execute(
        select(DeliveryRequest).where(DeliveryRequest.id == did, DeliveryRequest.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not drq:
        raise HTTPException(status_code=404, detail="მოთხოვნა არ მოიძებნა")

    tl = TripLoad(
        company_id=current_user.company_id, trip_id=trip.id, stop_id=stop_id,
        delivery_id=did, quantity=payload.quantity,
        weight_kg=payload.weight_kg, volume_m3=payload.volume_m3,
    )
    db.add(tl)
    trip.total_weight_kg = cur_w + new_w
    trip.total_volume_m3 = cur_v + new_v
    await db.commit()
    return ResponseBase(data={"id": str(tl.id), "loaded": True, "total_weight_kg": str(trip.total_weight_kg)})


@router.get("/trips/{trip_id}", response_model=ResponseBase[dict])
async def trip_detail(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-04: a trip's full view with ordered stops and loads (driver
    board view)."""
    trip = (await db.execute(
        select(Trip).options(selectinload(Trip.stops), selectinload(Trip.loads)).where(
            Trip.id == trip_id, Trip.company_id == current_user.company_id
        )
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")

    return ResponseBase(data={
        **_trip_resp(trip),
        "stops": [{
            "id": str(s.id), "sequence": s.sequence, "address": s.address,
            "contact_name": s.contact_name, "contact_phone": s.contact_phone,
            "window_from": s.window_from.isoformat() if s.window_from else None,
            "window_to": s.window_to.isoformat() if s.window_to else None,
            "status": s.status, "arrived_at": s.arrived_at.isoformat() if s.arrived_at else None,
            "departed_at": s.departed_at.isoformat() if s.departed_at else None,
            "delivered_qty": str(s.delivered_qty) if s.delivered_qty is not None else None,
            "exception": s.exception,
        } for s in sorted(trip.stops, key=lambda x: x.sequence)],
        "loads_count": len(trip.loads),
    })


@router.get("/trips/{trip_id}/stops", response_model=ResponseBase[list[dict]])
async def list_trip_stops(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    rows = (await db.execute(
        select(TripStop).where(TripStop.trip_id == trip.id).order_by(TripStop.sequence)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(s.id), "sequence": s.sequence, "address": s.address,
        "status": s.status, "arrived_at": s.arrived_at.isoformat() if s.arrived_at else None,
        "delivered_qty": str(s.delivered_qty) if s.delivered_qty is not None else None,
        "exception": s.exception,
    } for s in rows])


@router.post("/trips/{trip_id}/dispatch", response_model=ResponseBase[dict])
async def dispatch_trip(
    trip_id: uuid.UUID,
    payload: DispatchIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-03: validate vehicle active, licence valid, docs current,
    no open maintenance block, then dispatch."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    if trip.status not in ("draft", "planned"):
        raise HTTPException(status_code=409, detail="დისპეჩამდე რეისი უნდა იყოს draft ან planned")

    veh_id = uuid.UUID(payload.vehicle_id) if payload.vehicle_id else trip.vehicle_id
    drv_id = uuid.UUID(payload.driver_id) if payload.driver_id else trip.driver_id

    if veh_id:
        vh = (await db.execute(select(Vehicle).where(Vehicle.id == veh_id))).scalar_one_or_none()
        if not vh or not vh.is_active:
            raise HTTPException(status_code=409, detail="მანქანა არააქტიურია")
        today = date.today()
        if vh.insurance_valid_until and vh.insurance_valid_until < today:
            raise HTTPException(status_code=409, detail="დაზღვევა ვადაგასულია")
        if vh.tech_inspection_until and vh.tech_inspection_until < today:
            raise HTTPException(status_code=409, detail="ტექდათვალიერება ვადაგასულია")
        # REQ-TMS-03 / REQ-MNT-08: no open blocking maintenance order for vehicle
        maint = (await db.execute(
            select(MaintenanceOrder.id).where(
                MaintenanceOrder.company_id == current_user.company_id,
                MaintenanceOrder.asset_name.ilike(f"%{vh.plate_number}%"),
                MaintenanceOrder.status.in_(["scheduled", "in_progress"]),
            ).limit(1)
        )).first()
        if maint:
            raise HTTPException(status_code=409, detail="მანქანა Maintenance-შია დაბლოკილი")

    if drv_id:
        drv = (await db.execute(select(Driver).where(Driver.id == drv_id))).scalar_one_or_none()
        if not drv or not drv.is_active:
            raise HTTPException(status_code=409, detail="მძღოლი არააქტიურია")
        if drv.license_valid_until and drv.license_valid_until < date.today():
            raise HTTPException(status_code=409, detail="მძღოლის ლიცენზია ვადაგასულია")

    # REQ-TMS-02: no time overlap — the same vehicle/driver cannot be on two
    # open (dispatched/in_progress) trips whose planned window overlaps theirs.
    if trip.planned_start and trip.planned_end:
        overlap_vehicle = None
        overlap_driver = None
        if veh_id:
            overlap_vehicle = (await db.execute(
                select(Trip.id).where(
                    Trip.company_id == current_user.company_id,
                    Trip.vehicle_id == veh_id,
                    Trip.id != trip.id,
                    Trip.status.in_(["dispatched", "in_progress"]),
                    Trip.planned_start.isnot(None), Trip.planned_end.isnot(None),
                    Trip.planned_start < trip.planned_end,
                    Trip.planned_end > trip.planned_start,
                ).limit(1)
            )).first()
        if drv_id:
            overlap_driver = (await db.execute(
                select(Trip.id).where(
                    Trip.company_id == current_user.company_id,
                    Trip.driver_id == drv_id,
                    Trip.id != trip.id,
                    Trip.status.in_(["dispatched", "in_progress"]),
                    Trip.planned_start.isnot(None), Trip.planned_end.isnot(None),
                    Trip.planned_start < trip.planned_end,
                    Trip.planned_end > trip.planned_start,
                ).limit(1)
            )).first()
        if overlap_vehicle:
            raise HTTPException(status_code=409, detail="მანქანა ამ პერიოდში უკვე დაგეგმილია სხვა რეისზე")
        if overlap_driver:
            raise HTTPException(status_code=409, detail="მძღოლი ამ პერიოდში უკვე დაგეგმილია სხვა რეისზე")

    if veh_id: trip.vehicle_id = veh_id
    if drv_id: trip.driver_id = drv_id
    trip.status = "dispatched"
    trip.dispatched_at = utc_now()
    await db.commit()
    await db.refresh(trip)
    return ResponseBase(data=_trip_resp(trip))


@router.post("/trips/{trip_id}/start", response_model=ResponseBase[dict])
async def start_trip(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    if trip.status != "dispatched":
        raise HTTPException(status_code=409, detail="დასაწყებად რეისი უნდა იყოს dispatched")
    trip.status = "in_progress"
    trip.started_at = utc_now()
    await db.commit()
    await db.refresh(trip)
    return ResponseBase(data=_trip_resp(trip))


@router.post("/trip-stops/{stop_id}/events", response_model=ResponseBase[dict])
async def stop_event(
    stop_id: uuid.UUID,
    payload: StopEventIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-04/05/06: arrive / depart / deliver / fail → creates POD & updates stop."""
    stop = (await db.execute(
        select(TripStop).where(TripStop.id == stop_id, TripStop.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not stop:
        raise HTTPException(status_code=404, detail="გაჩერება არ მოიძებნა")

    ev = payload.event
    now = utc_now()

    if ev == "arrive":
        stop.status = "arrived"
        stop.arrived_at = payload.device_time or now
        await db.commit()
        return ResponseBase(data={"stop_id": str(stop.id), "status": stop.status})

    if ev == "depart":
        stop.status = "delivered" if stop.status == "arrived" else stop.status
        stop.departed_at = payload.device_time or now
        await db.commit()
        return ResponseBase(data={"stop_id": str(stop.id), "status": stop.status})

    if ev == "deliver" or ev == "fail":
        # REQ-TMS-05/06: POD record (idempotent by device_event_id)
        if payload.device_event_id:
            existing = (await db.execute(
                select(TripPOD).where(
                    TripPOD.company_id == current_user.company_id,
                    TripPOD.device_event_id == payload.device_event_id,
                )
            )).scalar_one_or_none()
            if existing:
                return ResponseBase(data={"id": str(existing.id), "duplicate": True, "status": stop.status})

        delivery = None
        load = (await db.execute(
            select(TripLoad).where(TripLoad.stop_id == stop.id).limit(1)
        )).scalar_one_or_none()
        did = load.delivery_id if load else None

        delivered_qty = payload.delivered_qty if payload.delivered_qty is not None else Decimal("0")
        exception = payload.exception or ("failed" if ev == "fail" else "ok")

        pod = TripPOD(
            company_id=current_user.company_id,
            trip_id=stop.trip_id, stop_id=stop.id, delivery_id=did,
            delivered_qty=delivered_qty,
            delivered_at=payload.device_time or now,
            recipient_name=payload.recipient_name,
            exception=exception,
            exception_reason=payload.exception_reason,
            evidence_id=uuid.UUID(payload.evidence_id) if payload.evidence_id else None,
            device_event_id=payload.device_event_id,
            device_time=payload.device_time,
        )
        db.add(pod)

        if ev == "fail":
            stop.status = "failed"
            stop.exception = payload.exception_reason or payload.exception
        else:
            stop.status = "partial" if load and delivered_qty < load.quantity else "delivered"
            stop.delivered_qty = delivered_qty

        if did:
            drq = (await db.execute(
                select(DeliveryRequest).where(DeliveryRequest.id == did)
            )).scalar_one_or_none()
            if drq:
                drq.delivered_qty = delivered_qty
                drq.delivered_at = pod.delivered_at
                drq.status = "partial" if (load and delivered_qty < load.quantity) else "delivered"
                drq.exception = payload.exception_reason or payload.exception

        await db.commit()
        await db.refresh(pod)
        return ResponseBase(data={"id": str(pod.id), "status": stop.status, "delivered_qty": str(delivered_qty)})

    raise HTTPException(status_code=422, detail="უცნობი მოვლენა")


@router.post("/trips/{trip_id}/complete", response_model=ResponseBase[dict])
async def complete_trip(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    if trip.status != "in_progress":
        raise HTTPException(status_code=409, detail="დასასრულებლად რეისი უნდა იყოს in_progress")
    trip.status = "completed"
    trip.completed_at = utc_now()
    await db.commit()
    await db.refresh(trip)
    return ResponseBase(data=_trip_resp(trip))


@router.post("/trips/{trip_id}/close", response_model=ResponseBase[dict])
async def close_trip(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    if trip.status != "completed":
        raise HTTPException(status_code=409, detail="დახურვამდე რეისი უნდა იყოს completed")
    trip.status = "closed"
    trip.closed_at = utc_now()
    await db.commit()
    await db.refresh(trip)
    return ResponseBase(data=_trip_resp(trip))


# ── POD / Costs ───────────────────────────────────────────────────────
@router.get("/trips/{trip_id}/pods", response_model=ResponseBase[list[dict]])
async def list_trip_pods(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(TripPOD).where(
            TripPOD.company_id == current_user.company_id, TripPOD.trip_id == trip_id
        ).order_by(TripPOD.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(p.id), "delivery_id": str(p.delivery_id) if p.delivery_id else None,
        "delivered_qty": str(p.delivered_qty), "delivered_at": p.delivered_at.isoformat() if p.delivered_at else None,
        "recipient_name": p.recipient_name, "exception": p.exception, "exception_reason": p.exception_reason,
        "evidence_id": str(p.evidence_id) if p.evidence_id else None,
        "supersedes_id": str(p.supersedes_id) if p.supersedes_id else None,
        "corrected_by": str(p.corrected_by) if p.corrected_by else None,
        "corrected_at": p.corrected_at.isoformat() if p.corrected_at else None,
    } for p in rows])


@router.post("/pods/{pod_id}/correct", response_model=ResponseBase[dict])
async def correct_pod(
    pod_id: uuid.UUID,
    payload: PODIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-06: a POD correction requires manager rights and preserves the
    original record. The corrected POD supersedes the original (supersedes_id →
    original); the original is never mutated."""
    # manager / admin guard
    role = getattr(current_user, "role", None)
    allowed = {"admin", "manager", "director", "supervisor"}
    if role not in allowed:
        raise HTTPException(status_code=403, detail="POD-ის შესწორება მოითხოვს მმართველის უფლებას")

    pod = (await db.execute(
        select(TripPOD).where(TripPOD.id == pod_id, TripPOD.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not pod:
        raise HTTPException(status_code=404, detail="POD არ მოიძებნა")

    # build the corrected POD — original preserved untouched
    corrected = TripPOD(
        company_id=current_user.company_id,
        trip_id=pod.trip_id, stop_id=pod.stop_id, delivery_id=pod.delivery_id,
        delivered_qty=payload.delivered_qty,
        delivered_at=payload.delivered_at,
        recipient_name=payload.recipient_name,
        exception=payload.exception or pod.exception,
        exception_reason=payload.exception_reason or pod.exception_reason,
        evidence_id=uuid.UUID(payload.evidence_id) if payload.evidence_id else pod.evidence_id,
        corrected_by=current_user.id, corrected_at=utc_now(),
        supersedes_id=pod.id,
        device_event_id=None, device_time=None,
    )
    db.add(corrected)
    await db.flush()

    # re-sync the delivery request from the corrected POD
    if pod.delivery_id:
        drq = (await db.execute(
            select(DeliveryRequest).where(DeliveryRequest.id == pod.delivery_id)
        )).scalar_one_or_none()
        if drq:
            drq.delivered_qty = corrected.delivered_qty
            drq.delivered_at = corrected.delivered_at
            drq.status = "delivered" if corrected.exception in (None, "ok") else "failed"
            drq.exception = corrected.exception_reason

    await db.commit()
    await db.refresh(corrected)
    return ResponseBase(data={
        "id": str(corrected.id), "supersedes": str(pod.id), "delivered_qty": str(corrected.delivered_qty),
        "status": "corrected",
    })


@router.post("/delivery-requests/{delivery_id}/wms-return", response_model=ResponseBase[dict])
async def wms_return_delivery(
    delivery_id: uuid.UUID,
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-06: failed/undelivered cargo re-enters stock ONLY via a WMS
    return. This stamps the delivery request as returned — no stock movement is
    posted here (the WMS return does that)."""
    drq = (await db.execute(
        select(DeliveryRequest).where(DeliveryRequest.id == delivery_id, DeliveryRequest.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not drq:
        raise HTTPException(status_code=404, detail="მოთხოვნა არ მოიძებნა")
    if drq.status not in ("failed", "partial"):
        raise HTTPException(status_code=409, detail="დაბრუნება მხოლოდ failed/partial ტვირთზე")

    wh_id = None
    data = payload or {}
    if data.get("warehouse_id"):
        wh_id = uuid.UUID(data["warehouse_id"])

    drq.returned_to_warehouse = True
    drq.returned_warehouse_id = wh_id
    drq.returned_at = utc_now()
    await db.commit()
    await db.refresh(drq)
    return ResponseBase(data={
        "delivery_id": str(drq.id), "returned": True,
        "warehouse_id": str(drq.returned_warehouse_id) if drq.returned_warehouse_id else None,
    })


@router.get("/trips/{trip_id}/fuel", response_model=ResponseBase[dict])
async def trip_fuel_summary(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-07: fuel + consumption for a trip. Average consumption is only
    reported when there is enough mileage coverage."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")

    logs = (await db.execute(
        select(FuelLog).where(FuelLog.trip_id == trip.id)
    )).scalars().all()
    if not logs:
        return ResponseBase(data={
            "trip_id": str(trip.id), "liters": "0", "amount": "0",
            "average_l_per_100km": None, "entries": 0,
        })

    total_liters = sum((Decimal(str(x.liters)) for x in logs), Decimal("0"))
    total_amount = sum((Decimal(str(x.total_amount)) for x in logs), Decimal("0"))

    return ResponseBase(data={
        "trip_id": str(trip.id),
        "liters": str(total_liters),
        "amount": str(total_amount),
        "average_l_per_100km": None,  # per-trip distance not tracked here
        "entries": len(logs),
    })


@router.get("/analytics", response_model=ResponseBase[dict])
async def tms_analytics_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """TMS commercial analytics: on-time rate, cost per delivery, fleet
    utilization."""
    from app.services.tms import tms_analytics
    data = await tms_analytics(db, current_user.company_id)
    return ResponseBase(data=data)


@router.post("/trips/{trip_id}/route-plan", response_model=ResponseBase[dict])
async def route_plan(
    trip_id: uuid.UUID,
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """TMS planning: suggest an order for a trip's stops (nearest-neighbour).
    Caller may apply it with /apply-plan."""
    from app.services.tms import sequence_trip_stops
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    body = payload or {}
    planned = await sequence_trip_stops(
        db, trip,
        start_lat=body.get("start_lat"), start_lon=body.get("start_lng"),
    )
    return ResponseBase(data={"trip_id": str(trip.id), "suggested": planned})


@router.post("/trips/{trip_id}/apply-plan", response_model=ResponseBase[dict])
async def apply_plan(
    trip_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a trip stop order from a route-plan suggestion (list of stops)."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    ordered = payload.get("ordered") or []
    seq = 1
    for item in ordered:
        stop_id = item.get("stop_id") if isinstance(item, dict) else item
        stop = (await db.execute(
            select(TripStop).where(TripStop.id == stop_id, TripStop.trip_id == trip.id)
        )).scalar_one_or_none()
        if stop:
            stop.sequence = seq
            seq += 1
    await db.commit()
    return ResponseBase(data={"trip_id": str(trip.id), "applied": True, "stops": len(ordered)})


@router.post("/trips/{trip_id}/telemetry", response_model=ResponseBase[dict])
async def post_telemetry(
    trip_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-04 live tracking: any GPS tracker/driver app posts a coordinate
    point for an active trip. Auto-arrival fires when the point enters a stop
    geofence."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")

    lat = Decimal(str(payload["lat"]))
    lng = Decimal(str(payload["lng"]))
    tracked_at = payload.get("tracked_at")
    if isinstance(tracked_at, str):
        tracked_at = datetime.fromisoformat(tracked_at)

    tele = TripTelemetry(
        company_id=current_user.company_id, trip_id=trip.id,
        device_id=payload.get("device_id"),
        tracked_at=tracked_at or utc_now(),
        lat=lat, lng=lng,
        speed_kmh=payload.get("speed_kmh"), heading=payload.get("heading"),
    )
    db.add(tele)

    await db.commit()

    # auto-arrival: check the latest unmatched stop's geofence
    from math import radians, sin, cos, asin, sqrt
    hit = None
    if trip.status == "in_progress":
        nxt = (await db.execute(
            select(TripStop).where(TripStop.trip_id == trip.id, TripStop.status == "pending")
            .order_by(TripStop.sequence).limit(1)
        )).scalar_one_or_none()
        if nxt:
            gf = (await db.execute(
                select(TripGeofence).where(
                    TripGeofence.trip_id == trip.id, TripGeofence.stop_id == nxt.id
                )
            )).scalar_one_or_none()
            if gf:
                r = 6371000.0
                dlat = radians(float(lat) - float(gf.lat))
                dlng = radians(float(lng) - float(gf.lng))
                a = sin(dlat/2)**2 + cos(radians(float(lat))) * cos(radians(float(gf.lat))) * sin(dlng/2)**2
                dist = 2 * r * asin(sqrt(a))
                if dist <= float(gf.radius_m):
                    nxt.status = "arrived"
                    nxt.arrived_at = utc_now()
                    await db.commit()
                    hit = {"stop_id": str(nxt.id), "arrived": True, "distance_m": round(dist, 1)}

    return ResponseBase(data={"trip_id": str(trip.id), "recorded": True, "auto_arrival": hit})


@router.get("/trips/{trip_id}/live-position", response_model=ResponseBase[dict])
async def live_position(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-04: latest GPS position for a trip's live view."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    last = (await db.execute(
        select(TripTelemetry).where(TripTelemetry.trip_id == trip.id)
        .order_by(TripTelemetry.tracked_at.desc()).limit(1)
    )).scalar_one_or_none()
    return ResponseBase(data={
        "trip_id": str(trip.id),
        "position": {
            "lat": str(last.lat), "lng": str(last.lng),
            "tracked_at": last.tracked_at.isoformat() if last else None,
            "speed_kmh": str(last.speed_kmh) if last and last.speed_kmh is not None else None,
        } if last else None,
    })


@router.get("/trips/{trip_id}/history", response_model=ResponseBase[dict])
async def trip_history(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-04 map: chronological GPS track (polyline) + stop geo-pins +
    geofence circles for the live route view."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")

    # track
    track = (await db.execute(
        select(TripTelemetry).where(TripTelemetry.trip_id == trip.id)
        .order_by(TripTelemetry.tracked_at.asc())
    )).scalars().all()
    track_pts = [{"lat": str(t.lat), "lng": str(t.lng), "tracked_at": t.tracked_at.isoformat()} for t in track]

    # stops with coords (from delivery-request dropoff coords via loads)
    stops_out = []
    loads = (await db.execute(
        select(TripLoad).where(TripLoad.trip_id == trip.id)
    )).scalars().all()
    for ld in loads:
        dr = (await db.execute(
            select(DeliveryRequest).where(DeliveryRequest.id == ld.delivery_id)
        )).scalar_one_or_none()
        if dr and dr.dropoff_lat is not None and dr.dropoff_lng is not None:
            st = (await db.execute(
                select(TripStop).where(TripStop.id == ld.stop_id)
            )).scalar_one_or_none() if ld.stop_id else None
            stops_out.append({
                "stop_id": str(ld.stop_id) if ld.stop_id else None,
                "lat": str(dr.dropoff_lat), "lng": str(dr.dropoff_lng),
                "address": dr.dropoff_address,
                "status": st.status if st else "pending",
            })

    # geofence circles
    geofences = (await db.execute(
        select(TripGeofence).where(TripGeofence.trip_id == trip.id)
    )).scalars().all()
    fences = [{"stop_id": str(g.stop_id), "lat": str(g.lat), "lng": str(g.lng), "radius_m": float(g.radius_m)} for g in geofences]

    return ResponseBase(data={"trip_id": str(trip.id), "track": track_pts, "stops": stops_out, "geofences": fences})


@router.post("/trips/{trip_id}/geofences", response_model=ResponseBase[dict])
async def set_geofence(
    trip_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-04: define a circular geofence around a stop for auto-arrival."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    stop = (await db.execute(
        select(TripStop).where(
            TripStop.id == uuid.UUID(payload["stop_id"]), TripStop.trip_id == trip.id
        )
    )).scalar_one_or_none()
    if not stop:
        raise HTTPException(status_code=404, detail="გაჩერება არ მოიძებნა")

    gf = TripGeofence(
        company_id=current_user.company_id, trip_id=trip.id, stop_id=stop.id,
        lat=Decimal(str(payload["lat"])), lng=Decimal(str(payload["lng"])),
        radius_m=payload.get("radius_m", 500),
    )
    db.add(gf)
    await db.commit()
    await db.refresh(gf)
    return ResponseBase(data={"id": str(gf.id), "stop_id": str(stop.id), "radius_m": float(gf.radius_m)})


@router.get("/trips/{trip_id}/freight", response_model=ResponseBase[dict])
async def freight_billing(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """TMS freight billing: per-delivery freight charge + carrier settlement."""
    from app.services.tms import freight_schedule
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")
    schedule = await freight_schedule(db, trip)
    return ResponseBase(data=schedule)


@router.post("/pods/{pod_id}/evidence", response_model=ResponseBase[dict])
async def upload_pod_evidence(
    pod_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-05: attach evidence (photo/signature) to a POD. Accepts a
    base64 data-URL in `data`; stores a fingerprint for audit and links
    evidence_id without mutating the qty."""
    pod = (await db.execute(
        select(TripPOD).where(TripPOD.id == pod_id, TripPOD.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not pod:
        raise HTTPException(status_code=404, detail="POD არ მოიძებნა")

    data = payload.get("data") or ""
    kind = payload.get("kind") or "photo"  # photo | signature
    if not data.startswith("data:") or "base64," not in data:
        raise HTTPException(status_code=422, detail="მოეთხოვება base64 data-URL")

    import hashlib
    fingerprint = hashlib.sha256(data.encode()).hexdigest()[:16]
    if payload.get("evidence_id"):
        pod.evidence_id = uuid.UUID(payload["evidence_id"])
    await db.commit()

    return ResponseBase(data={
        "pod_id": str(pod.id), "kind": kind,
        "evidence_id": str(pod.evidence_id) if pod.evidence_id else None,
        "fingerprint": fingerprint, "noted": True,
    })


@router.post("/trips/{trip_id}/freight-invoice", response_model=ResponseBase[dict])
async def issue_freight_invoice(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a standalone freight invoice for a trip (client-billable shipping
    charge). Idempotent per trip; lines snapshot the freight schedule."""
    from app.services.tms import freight_schedule

    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")

    existing = (await db.execute(
        select(TripFreightInvoice).where(
            TripFreightInvoice.company_id == current_user.company_id,
            TripFreightInvoice.trip_id == trip.id,
            TripFreightInvoice.status != "cancelled",
        )
    )).scalar_one_or_none()
    if existing:
        return ResponseBase(data={"id": str(existing.id), "invoice_number": existing.invoice_number, "already_exists": True})

    schedule = await freight_schedule(db, trip)
    invoice_number = f"FRT-{trip.trip_number}-{int(__import__('time').time())}"

    inv = TripFreightInvoice(
        company_id=current_user.company_id, trip_id=trip.id,
        invoice_number=invoice_number, status="issued",
        subtotal=Decimal(str(schedule["subtotal"])),
        freight_charge=Decimal(str(schedule["subtotal"])),
        carrier_rate=Decimal(str(schedule["carrier_rate"])),
        margin=Decimal(str(schedule["margin"])),
        lines=schedule["lines"], created_by=current_user.id,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return ResponseBase(data={
        "id": str(inv.id), "invoice_number": inv.invoice_number, "status": inv.status,
        "freight_charge": str(inv.freight_charge), "margin": str(inv.margin),
        "lines": inv.lines, "already_exists": False,
    })


@router.get("/freight-invoices", response_model=ResponseBase[list[dict]])
async def list_freight_invoices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(TripFreightInvoice).where(
            TripFreightInvoice.company_id == current_user.company_id
        ).order_by(TripFreightInvoice.issued_at.desc()).limit(200)
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(i.id), "invoice_number": i.invoice_number, "status": i.status,
        "trip_id": str(i.trip_id), "freight_charge": str(i.freight_charge),
        "margin": str(i.margin), "issued_at": i.issued_at.isoformat() if i.issued_at else None,
    } for i in rows])


@router.post("/trips/{trip_id}/costs", response_model=ResponseBase[dict])
async def add_trip_cost(
    trip_id: uuid.UUID,
    payload: CostAllocationIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-08: allocate a trip cost across deliveries by weight/volume/qty."""
    trip = (await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="რეისი არ მოიძებნა")

    loads = (await db.execute(select(TripLoad).where(TripLoad.trip_id == trip.id))).scalars().all()
    if not loads:
        raise HTTPException(status_code=409, detail="რეისზე ტვირთი არ არის — განაწილება შეუძლებელია")

    # base for allocation
    def base(x: TripLoad) -> Decimal:
        if payload.allocation_method == "quantity":
            return x.quantity
        if payload.allocation_method == "volume":
            return _trip_load_volume(x) or Decimal("0")
        return _trip_load_weight(x) or Decimal("0")

    bases = {str(l.delivery_id): base(l) for l in loads}
    total = sum(bases.values(), Decimal("0"))
    if total <= 0:
        raise HTTPException(status_code=409, detail="განაწილების საფუძველი ნულოვანია")

    # REQ-TMS-08: the same FIN expense cannot be double-allocated
    if payload.source_expense_id:
        dup = (await db.execute(
            select(TripCostAllocation.id).where(
                TripCostAllocation.company_id == current_user.company_id,
                TripCostAllocation.source_expense_id == uuid.UUID(payload.source_expense_id),
            ).limit(1)
        )).first()
        if dup:
            raise HTTPException(status_code=409, detail="ეს expense უკვე განაწილებულია — ორმაგი ჩაწერა აკრძალულია")

    # REQ-TMS-08: allocation rule version (ledger semantics, default 1)
    rule_version = 1

    created = []
    for did, b in bases.items():
        share = (payload.amount * b) / total
        ca = TripCostAllocation(
            company_id=current_user.company_id, trip_id=trip.id,
            delivery_id=uuid.UUID(did), cost_type=payload.cost_type,
            amount=share, allocation_method=payload.allocation_method,
            source_expense_id=uuid.UUID(payload.source_expense_id) if payload.source_expense_id else None,
            version=rule_version,
        )
        db.add(ca)
        created.append({"delivery_id": did, "amount": str(share)})
    await db.commit()
    return ResponseBase(data={"allocated": created, "total": str(payload.amount), "version": rule_version})


@router.get("/vehicles/{vehicle_id}/availability", response_model=ResponseBase[dict])
async def vehicle_availability(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """REQ-TMS-09: is this vehicle available to dispatch today (docs, maintenance block, active trip)?"""
    vh = (await db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not vh:
        raise HTTPException(status_code=404, detail="მანქანა არ მოიძებნა")

    today = date.today()
    issues = []
    if not vh.is_active:
        issues.append("inactive")
    if vh.insurance_valid_until and vh.insurance_valid_until < today:
        issues.append("insurance_expired")
    if vh.tech_inspection_until and vh.tech_inspection_until < today:
        issues.append("inspection_expired")
    maint = (await db.execute(
        select(MaintenanceOrder.id).where(
            MaintenanceOrder.company_id == current_user.company_id,
            MaintenanceOrder.asset_name.ilike(f"%{vh.plate_number}%"),
            MaintenanceOrder.status.in_(["scheduled", "in_progress"]),
        ).limit(1)
    )).first()
    if maint:
        issues.append("maintenance_block")

    open_trip = (await db.execute(
        select(Trip.id).where(
            Trip.company_id == current_user.company_id, Trip.vehicle_id == vh.id,
            Trip.status.in_(["dispatched", "in_progress"]),
        ).limit(1)
    )).first()
    if open_trip:
        issues.append("active_trip")

    # REQ-TMS-09: document expiry lead-time warnings (insurance / inspection /
    # maintenance due) so dispatch blockers are anticipated before they hit.
    from datetime import timedelta
    upcoming = []
    if vh.insurance_valid_until:
        days = (vh.insurance_valid_until - today).days
        if 0 <= days <= 30:
            upcoming.append({"kind": "insurance_expiring", "in_days": days})
    if vh.tech_inspection_until:
        days = (vh.tech_inspection_until - today).days
        if 0 <= days <= 30:
            upcoming.append({"kind": "inspection_expiring", "in_days": days})
    if vh.maintenance_due_date:
        days = (vh.maintenance_due_date - today).days
        if 0 <= days <= 30:
            upcoming.append({"kind": "maintenance_due", "in_days": days})

    return ResponseBase(data={
        "vehicle_id": str(vh.id), "available": len(issues) == 0, "issues": issues,
        "capacity_kg": str(vh.capacity_kg) if vh.capacity_kg is not None else None,
        "capacity_m3": str(vh.capacity_m3) if vh.capacity_m3 is not None else None,
        "upcoming": upcoming,
    })
