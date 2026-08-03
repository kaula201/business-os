"""Fleet enhanced: fuel consumption reports, anomaly detection, service alerts,
expiry tracking, driver history, analytics, export, map privacy."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.user import User
from app.models.fleet import Vehicle, FuelLog, OdometerReading, ServiceRecord, DriverAssignment
from app.schemas.common import ResponseBase
from pydantic import BaseModel
from io import BytesIO
import openpyxl
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/fleet", tags=["ავტოპარკი — გაძლიერებული"])


# ── Fuel Consumption Report ────────────────────────────────────────────────────

class FuelConsumption(BaseModel):
    vehicle_id: UUID
    plate_number: str
    brand: str
    model: str
    total_liters: float
    total_cost: float
    avg_price_per_liter: float
    refuel_count: int
    last_refuel_date: str | None


@router.get("/fuel-report", response_model=ResponseBase[list[FuelConsumption]])
async def fuel_consumption_report(
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("fleet", "can_access")),
):
    company_id = current_user.company_id
    today = date.today()
    d_from = date.fromisoformat(date_from) if date_from else today - timedelta(days=90)
    d_to = date.fromisoformat(date_to) if date_to else today

    rows = (await db.execute(
        select(
            Vehicle.id, Vehicle.plate_number, Vehicle.brand, Vehicle.model,
            func.coalesce(func.sum(FuelLog.liters), 0),
            func.coalesce(func.sum(FuelLog.total_amount), 0),
            func.count(FuelLog.id),
            func.max(FuelLog.refuel_date),
        )
        .outerjoin(FuelLog, FuelLog.vehicle_id == Vehicle.id)
        .where(
            Vehicle.company_id == company_id,
            FuelLog.refuel_date.between(d_from, d_to),
        )
        .group_by(Vehicle.id, Vehicle.plate_number, Vehicle.brand, Vehicle.model)
        .order_by(Vehicle.plate_number)
    )).all()

    items = []
    for vid, plate, brand, model, liters, cost, count, last_date in rows:
        items.append(FuelConsumption(
            vehicle_id=vid, plate_number=plate, brand=brand, model=model,
            total_liters=float(liters), total_cost=float(cost),
            avg_price_per_liter=float(cost) / float(liters) if float(liters) > 0 else 0,
            refuel_count=count, last_refuel_date=str(last_date) if last_date else None,
        ))

    return ResponseBase(data=items)


# ── Service Alerts ────────────────────────────────────────────────────────────

class ServiceAlert(BaseModel):
    vehicle_id: UUID
    plate_number: str
    brand: str
    model: str
    last_service_date: str | None
    last_service_km: int | None
    days_since_service: int
    km_since_service: int | None
    alert_type: str  # "overdue" | "upcoming"


@router.get("/service-alerts", response_model=ResponseBase[list[ServiceAlert]])
async def service_alerts(
    upcoming_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("fleet", "can_access")),
):
    company_id = current_user.company_id
    today = date.today()

    vehicles = (await db.execute(
        select(Vehicle).where(Vehicle.company_id == company_id)
    )).scalars().all()

    alerts = []
    for v in vehicles:
        # Get last service
        last_service = (await db.execute(
        select(ServiceRecord)
        .where(ServiceRecord.vehicle_id == v.id, ServiceRecord.company_id == company_id)
        .order_by(ServiceRecord.service_date.desc())
        .limit(1)
        )).scalar_one_or_none()

        if last_service:
            days_since = (today - last_service.service_date).days
            alert_type = "overdue" if days_since > 90 else "upcoming" if days_since > 60 else ""
            if alert_type:
                alerts.append(ServiceAlert(
                    vehicle_id=v.id, plate_number=v.plate_number,
                    brand=v.brand, model=v.model,
                    last_service_date=str(last_service.service_date),
                    last_service_km=int(last_service.mileage_at_service or 0),
                    days_since_service=days_since,
                    km_since_service=int((v.current_mileage or 0) - (last_service.mileage_at_service or 0))
                    if v.current_mileage and last_service.mileage_at_service else None,
                    alert_type=alert_type,
                ))
        else:
            # No service record — alert if vehicle exists > 90 days
            if v.created_at and (today - v.created_at.date()).days > 90:
                alerts.append(ServiceAlert(
                    vehicle_id=v.id, plate_number=v.plate_number,
                    brand=v.brand, model=v.model,
                    last_service_date=None, last_service_km=None,
                    days_since_service=(today - v.created_at.date()).days,
                    km_since_service=None, alert_type="overdue",
                ))

    return ResponseBase(data=alerts)


# ── Fleet Analytics ──────────────────────────────────────────────────────────

class FleetAnalytics(BaseModel):
    total_vehicles: int
    active_vehicles: int
    total_fuel_cost: float
    total_service_cost: float
    total_fuel_liters: float
    avg_fuel_consumption: float  # liters per 100km


@router.get("/analytics", response_model=ResponseBase[FleetAnalytics])
async def fleet_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("fleet", "can_access")),
):
    company_id = current_user.company_id

    total = (await db.execute(select(func.count(Vehicle.id)).where(Vehicle.company_id == company_id))).scalar()
    active = (await db.execute(select(func.count(Vehicle.id)).where(Vehicle.company_id == company_id, Vehicle.is_active == True))).scalar()

    fuel_cost = (await db.execute(
        select(func.coalesce(func.sum(FuelLog.total_amount), 0))
        .join(Vehicle, Vehicle.id == FuelLog.vehicle_id)
        .where(Vehicle.company_id == company_id)
    )).scalar()

    fuel_liters = (await db.execute(
        select(func.coalesce(func.sum(FuelLog.liters), 0))
        .join(Vehicle, Vehicle.id == FuelLog.vehicle_id)
        .where(Vehicle.company_id == company_id)
    )).scalar()

    service_cost = (await db.execute(
        select(func.coalesce(func.sum(ServiceRecord.cost), 0))
        .join(Vehicle, Vehicle.id == ServiceRecord.vehicle_id)
        .where(Vehicle.company_id == company_id)
    )).scalar()

    # Average fuel consumption (liters / 100 km) across vehicles with odometer data.
    # Use the latest two odometer readings per vehicle and total fuel for that span.
    avg_consumption = await _avg_consumption_l_per_100km(db, company_id)

    return ResponseBase(data=FleetAnalytics(
        total_vehicles=total or 0, active_vehicles=active or 0,
        total_fuel_cost=float(fuel_cost or 0), total_service_cost=float(service_cost or 0),
        total_fuel_liters=float(fuel_liters or 0),
        avg_fuel_consumption=avg_consumption,
    ))


async def _avg_consumption_l_per_100km(db: AsyncSession, company_id: UUID) -> float:
    """Compute liters-per-100km across the fleet from odometer deltas and fuel totals.

    For each vehicle, take its earliest and latest odometer reading. The distance is the
    delta; the fuel used is the sum of fuel logs between those two readings. Returns 0
    when insufficient data exists.
    """
    vehicles = (await db.execute(
        select(Vehicle).where(Vehicle.company_id == company_id)
    )).scalars().all()
    totals_km = 0.0
    totals_liters = 0.0
    for v in vehicles:
        readings = (await db.execute(
            select(OdometerReading.mileage_km, OdometerReading.reading_date)
            .where(
                OdometerReading.vehicle_id == v.id,
                OdometerReading.company_id == company_id,
            )
            .order_by(OdometerReading.reading_date)
        )).all()
        if len(readings) < 2:
            continue
        km_start = float(readings[0][0])
        km_end = float(readings[-1][0])
        start_date = readings[0][1]
        end_date = readings[-1][1]
        if km_end <= km_start:
            continue
        fuel = (await db.execute(
            select(func.coalesce(func.sum(FuelLog.liters), 0))
            .where(
                FuelLog.vehicle_id == v.id,
                FuelLog.refuel_date >= start_date,
                FuelLog.refuel_date <= end_date,
            )
        )).scalar()
        totals_km += (km_end - km_start)
        totals_liters += float(fuel or 0)
    if totals_km <= 0:
        return 0.0
    return round(totals_liters / totals_km * 100, 2)


# ── Export ──────────────────────────────────────────────────────────────────────

@router.get("/export/vehicles")
async def export_vehicles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_module("fleet", "can_access")),
):
    rows = (await db.execute(
        select(Vehicle).where(Vehicle.company_id == current_user.company_id).order_by(Vehicle.plate_number)
    )).scalars().all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ავტოპარკი"
    ws.append(["ნომერი", "მარკა", "მოდელი", "წელი", "ფერი", "VIN", "სტატუსი",
               "მიმდინარე ოდომეტრი", "საწვავის ტიპი", "შექმნის თარიღი"])
    for v in rows:
        ws.append([v.plate_number, v.brand, v.model, v.year or "", v.color or "", v.vin or "",
                   v.is_active, v.current_mileage or 0, v.fuel_type or "", str(v.created_at)])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=fleet_vehicles.xlsx"})
