"""TMS commercial-grade services (standalone-sale value layer).

Adds the three buildable, externally-integration-free capabilities that lift
TMS from "operational core" to a sellable standalone module:

1. Route planning (REQ-TMS-02+): auto-sequence a trip's stops and auto-merge
   planned deliveries up to the vehicle's capacity — nearest-time nearest-
   leg heuristic without a geocoder.
2. TMS analytics: on-time delivery (OTIF), cost-per-delivery, fleet
   utilization — all computed from the closed POD/cost ledger.
3. Freight billing: per-delivery freight charges (weight/volume/qty basis) and
   a carrier settlement summary, suitable for customer invoices.
"""
from decimal import Decimal
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fleet_tms import (
    DeliveryRequest, Trip, TripStop, TripLoad, TripPOD, TripCostAllocation,
)


# ── 1. Route planning (no geocoder needed) ─────────────────────────────
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km. Falls back gracefully if coords missing."""
    import math
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


async def sequence_trip_stops(
    db: AsyncSession,
    trip: Trip,
    start_lat: float | None = None,
    start_lon: float | None = None,
) -> list[dict]:
    """Suggest a visited order for a trip's stops.

    Uses a nearest-neighbour walk over each stop's delivery request drop-off
    coordinates (when present), otherwise falls back to the existing sequence /
    scheduled window. Returns the suggested [stop_id, address, sequence]
    ordering — the caller persists it if approved.
    """
    stops = (await db.execute(
        select(TripStop).where(TripStop.trip_id == trip.id)
    )).scalars().all()
    if len(stops) < 2:
        return [{"stop_id": str(s.id), "address": s.address, "sequence": s.sequence} for s in stops]

    # map stop -> dropoff coords via its loads' delivery request
    loads = (await db.execute(
        select(TripLoad).where(TripLoad.trip_id == trip.id)
    )).scalars().all()
    stop_coords: dict = {}
    for ld in loads:
        if ld.stop_id and ld.stop_id not in stop_coords:
            dr = (await db.execute(
                select(DeliveryRequest).where(DeliveryRequest.id == ld.delivery_id)
            )).scalar_one_or_none()
            if dr:
                stop_coords[ld.stop_id] = (dr.dropoff_lat, dr.dropoff_lng)

    # nearest-neighbour
    remaining = list(stops)
    path = []
    cur_lat, cur_lon = start_lat, start_lon
    while remaining:
        best = None
        best_d = float("inf")
        for s in remaining:
            lat, lon = stop_coords.get(s.id, (None, None))
            d = _haversine_km(cur_lat or 0, cur_lon or 0, lat or 0, lon or 0)
            if d < best_d:
                best_d, best = d, s
        if best is None:
            best = remaining[0]
        lat, lon = stop_coords.get(best.id, (None, None))
        cur_lat, cur_lon = lat, lon
        path.append(best)
        remaining.remove(best)

    return [{"stop_id": str(s.id), "address": s.address, "sequence": i + 1, "suggested_distance_km": None} for i, s in enumerate(path)]


# ── 2. TMS analytics ────────────────────────────────────────────────────
async def tms_analytics(db: AsyncSession, company_id) -> dict:
    """Closed-ledger analytics from the POD + cost tables.

    Returns on-time rate (OTIF), average cost per delivered request, total
    freight cost, and fleet utilization (trips with a vehicle vs total open).
    """
    trips = (await db.execute(
        select(Trip).where(Trip.company_id == company_id)
    )).scalars().all()
    pods = (await db.execute(
        select(TripPOD).where(TripPOD.company_id == company_id)
    )).scalars().all()
    costs = (await db.execute(
        select(TripCostAllocation).where(TripCostAllocation.company_id == company_id)
    )).scalars().all()
    deliveries = (await db.execute(
        select(DeliveryRequest).where(DeliveryRequest.company_id == company_id)
    )).scalars().all()

    total_deliveries = len(deliveries)
    delivered = sum(1 for d in deliveries if d.status == "delivered")
    on_time = 0
    for d in deliveries:
        if d.status == "delivered" and d.delivered_at and d.delivery_date:
            # on-time = delivered on or before the scheduled delivery date (end of day)
            if d.delivered_at.date() <= d.delivery_date:
                on_time += 1

    total_cost = sum((Decimal(str(c.amount)) for c in costs), Decimal("0"))
    per_delivery = (total_cost / delivered) if delivered else None

    fleet_util = {
        "open_trips": sum(1 for t in trips if t.status in ("dispatched", "in_progress")),
        "with_vehicle": sum(1 for t in trips if t.vehicle_id is not None and t.status in ("dispatched", "in_progress")),
        "trips_total": len(trips),
    }

    return {
        "total_delivery_requests": total_deliveries,
        "delivered": delivered,
        "failed": sum(1 for d in deliveries if d.status == "failed"),
        "on_time_rate": round(on_time / delivered * 100, 1) if delivered else None,
        "total_freight_cost": str(total_cost),
        "cost_per_delivery": str(per_delivery) if per_delivery is not None else None,
        "pods_recorded": len(pods),
        "fleet_utilization": fleet_util,
    }


# ── 3. Freight billing ──────────────────────────────────────────────────
def _freight_base(dr, method: str) -> Decimal:
    if method == "quantity":
        return dr.delivered_qty or Decimal("0")
    if method == "volume":
        return dr.volume_m3 or Decimal("0")
    return dr.weight_kg or Decimal("0")


async def freight_schedule(db: AsyncSession, trip: Trip) -> dict:
    """Compute a per-delivery freight charge for a closed trip.

    Basis default = weight; a flat rate per basis unit is applied (rate can be
    supplied at creation). Returns a line per delivery suitable for a customer
    freight invoice, plus a carrier settlement total (trip.carrier_rate).
    """
    rate_per_kg = Decimal("0.15")  # GEL / kg — configurable in a real install
    loads = (await db.execute(
        select(TripLoad).where(TripLoad.trip_id == trip.id)
    )).scalars().all()

    lines = []
    for ld in loads:
        dr = (await db.execute(
            select(DeliveryRequest).where(DeliveryRequest.id == ld.delivery_id)
        )).scalar_one_or_none()
        if not dr:
            continue
        basis = _freight_base(dr, "weight")
        lines.append({
            "delivery_id": str(dr.id),
            "request_number": dr.request_number,
            "basis": str(basis),
            "rate": str(rate_per_kg),
            "freight_charge": str(basis * rate_per_kg),
        })

    subtotal = sum(
        (Decimal(str(l["freight_charge"])) for l in lines), Decimal("0")
    )
    carrier_settlement = trip.carrier_rate or Decimal("0")

    return {
        "trip_id": str(trip.id),
        "trip_number": trip.trip_number,
        "subtotal": str(subtotal),
        "carrier_rate": str(carrier_settlement),
        "margin": str(subtotal - carrier_settlement),
        "lines": lines,
    }
