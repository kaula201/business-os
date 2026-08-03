"""Fleet management API: vehicles, fuel logs, service records, driver assignments."""
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_module
from app.models.audit import AuditLog
from app.models.fleet import DriverAssignment, FuelLog, OdometerReading, ServiceRecord, Vehicle
from app.models.user import User
from app.schemas.common import ResponseBase
from app.schemas.fleet import (
    DriverAssignmentCreate,
    DriverAssignmentResponse,
    DriverAssignmentUpdate,
    FuelLogCreate,
    FuelLogResponse,
    OdometerReadingCreate,
    OdometerReadingResponse,
    ServiceRecordCreate,
    ServiceRecordResponse,
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)

router = APIRouter(prefix="/fleet", tags=["ავტოპარკი"])


# ── Helpers ──────────────────────────────────────────────────────────

def add_fleet_audit(
    db: AsyncSession,
    current_user: User,
    action: str,
    entity_type: str,
    entity_id: UUID,
    details: dict,
) -> None:
    db.add(
        AuditLog(
            company_id=current_user.company_id,
            user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details, ensure_ascii=False, default=str),
        )
    )


async def get_company_vehicle(
    db: AsyncSession, vehicle_id: UUID, company_id: UUID
) -> Vehicle:
    vehicle = (
        await db.execute(
            select(Vehicle).where(
                Vehicle.id == vehicle_id,
                Vehicle.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="ავტომობილი არ მოიძებნა")
    return vehicle


async def record_odometer(
    db: AsyncSession,
    company_id: UUID,
    vehicle_id: UUID,
    reading_date,
    mileage_km,
    source: str = "manual",
    notes: str | None = None,
) -> None:
    """Insert an odometer reading and advance the vehicle's current mileage."""
    if mileage_km is None:
        return
    # Only advance if this reading is newer than what we already have.
    vehicle = (
        await db.execute(
            select(Vehicle).where(
                Vehicle.id == vehicle_id,
                Vehicle.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if vehicle is None:
        return
    if vehicle.current_mileage is None or mileage_km > vehicle.current_mileage:
        vehicle.current_mileage = mileage_km
    # Avoid duplicate readings for the exact same mileage on the same day/source.
    existing = (
        await db.execute(
            select(OdometerReading).where(
                OdometerReading.vehicle_id == vehicle_id,
                OdometerReading.mileage_km == mileage_km,
                OdometerReading.reading_date == reading_date,
                OdometerReading.source == source,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        OdometerReading(
            company_id=company_id,
            vehicle_id=vehicle_id,
            reading_date=reading_date,
            mileage_km=mileage_km,
            source=source,
            notes=notes,
        )
    )
    await db.flush()


# ── Vehicles ─────────────────────────────────────────────────────────

@router.get("/vehicles", response_model=ResponseBase[list[VehicleResponse]])
async def list_vehicles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vehicle)
        .where(Vehicle.company_id == current_user.company_id)
        .order_by(Vehicle.created_at.desc())
    )
    vehicles = result.scalars().all()
    return ResponseBase(data=vehicles)


@router.get("/vehicles/{vehicle_id}", response_model=ResponseBase[VehicleResponse])
async def get_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle = await get_company_vehicle(db, vehicle_id, current_user.company_id)
    return ResponseBase(data=vehicle)


@router.post("/vehicles", response_model=ResponseBase[VehicleResponse], status_code=201)
async def create_vehicle(
    payload: VehicleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle = Vehicle(
        company_id=current_user.company_id,
        **payload.model_dump(),
    )
    db.add(vehicle)
    await db.flush()
    add_fleet_audit(
        db, current_user, "create", "vehicle", vehicle.id,
        {"plate_number": vehicle.plate_number, "brand": vehicle.brand, "model": vehicle.model},
    )
    await db.refresh(vehicle)
    return ResponseBase(data=vehicle, message="ავტომობილი დამატებულია")


@router.put("/vehicles/{vehicle_id}", response_model=ResponseBase[VehicleResponse])
async def update_vehicle(
    vehicle_id: UUID,
    payload: VehicleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    vehicle = await get_company_vehicle(db, vehicle_id, current_user.company_id)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="განახლების მონაცემები არ არის მოწოდებული")
    for key, value in update_data.items():
        setattr(vehicle, key, value)
    await db.flush()
    add_fleet_audit(
        db, current_user, "update", "vehicle", vehicle.id,
        {"updated_fields": list(update_data.keys())},
    )
    await db.refresh(vehicle)
    return ResponseBase(data=vehicle, message="ავტომობილი განახლებულია")


@router.delete("/vehicles/{vehicle_id}", response_model=ResponseBase)
async def delete_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(require_module("fleet", "can_delete")),
    db: AsyncSession = Depends(get_db),
):
    vehicle = await get_company_vehicle(db, vehicle_id, current_user.company_id)
    await db.delete(vehicle)
    add_fleet_audit(
        db, current_user, "delete", "vehicle", vehicle_id,
        {"plate_number": vehicle.plate_number},
    )
    return ResponseBase(message="ავტომობილი წაშლილია")


# ── Fuel Logs ────────────────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/fuel-logs", response_model=ResponseBase[list[FuelLogResponse]])
async def list_fuel_logs(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    result = await db.execute(
        select(FuelLog)
        .where(
            FuelLog.vehicle_id == vehicle_id,
            FuelLog.company_id == current_user.company_id,
        )
        .order_by(FuelLog.refuel_date.desc())
    )
    logs = result.scalars().all()
    return ResponseBase(data=logs)


@router.post("/vehicles/{vehicle_id}/fuel-logs", response_model=ResponseBase[FuelLogResponse], status_code=201)
async def create_fuel_log(
    vehicle_id: UUID,
    payload: FuelLogCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    log = FuelLog(
        company_id=current_user.company_id,
        vehicle_id=vehicle_id,
        **payload.model_dump(exclude={"vehicle_id"}),
    )
    db.add(log)
    await db.flush()
    # Record odometer reading + advance vehicle mileage
    await record_odometer(
        db,
        company_id=current_user.company_id,
        vehicle_id=vehicle_id,
        reading_date=log.refuel_date,
        mileage_km=log.mileage_at_refuel,
        source="fuel",
    )
    add_fleet_audit(
        db, current_user, "create", "fuel_log", log.id,
        {"vehicle_id": str(vehicle_id), "liters": str(log.liters), "total_amount": str(log.total_amount)},
    )
    await db.refresh(log)
    return ResponseBase(data=log, message="საწვავის ჩანაწერი დამატებულია")


@router.delete("/fuel-logs/{log_id}", response_model=ResponseBase)
async def delete_fuel_log(
    log_id: UUID,
    current_user: User = Depends(require_module("fleet", "can_delete")),
    db: AsyncSession = Depends(get_db),
):
    log = (
        await db.execute(
            select(FuelLog).where(
                FuelLog.id == log_id,
                FuelLog.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="საწვავის ჩანაწერი არ მოიძებნა")
    await db.delete(log)
    add_fleet_audit(
        db, current_user, "delete", "fuel_log", log_id,
        {"vehicle_id": str(log.vehicle_id)},
    )
    return ResponseBase(message="საწვავის ჩანაწერი წაშლილია")


# ── Service Records ──────────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/services", response_model=ResponseBase[list[ServiceRecordResponse]])
async def list_service_records(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    result = await db.execute(
        select(ServiceRecord)
        .where(
            ServiceRecord.vehicle_id == vehicle_id,
            ServiceRecord.company_id == current_user.company_id,
        )
        .order_by(ServiceRecord.service_date.desc())
    )
    records = result.scalars().all()
    return ResponseBase(data=records)


@router.post("/vehicles/{vehicle_id}/services", response_model=ResponseBase[ServiceRecordResponse], status_code=201)
async def create_service_record(
    vehicle_id: UUID,
    payload: ServiceRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    record = ServiceRecord(
        company_id=current_user.company_id,
        vehicle_id=vehicle_id,
        **payload.model_dump(exclude={"vehicle_id"}),
    )
    db.add(record)
    await db.flush()
    # Record odometer reading + advance vehicle mileage
    await record_odometer(
        db,
        company_id=current_user.company_id,
        vehicle_id=vehicle_id,
        reading_date=record.service_date,
        mileage_km=record.mileage_at_service,
        source="service",
    )
    add_fleet_audit(
        db, current_user, "create", "service_record", record.id,
        {"vehicle_id": str(vehicle_id), "service_type": record.service_type, "cost": str(record.cost)},
    )
    await db.refresh(record)
    return ResponseBase(data=record, message="მომსახურების ჩანაწერი დამატებულია")


@router.delete("/services/{record_id}", response_model=ResponseBase)
async def delete_service_record(
    record_id: UUID,
    current_user: User = Depends(require_module("fleet", "can_delete")),
    db: AsyncSession = Depends(get_db),
):
    record = (
        await db.execute(
            select(ServiceRecord).where(
                ServiceRecord.id == record_id,
                ServiceRecord.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="მომსახურების ჩანაწერი არ მოიძებნა")
    await db.delete(record)
    add_fleet_audit(
        db, current_user, "delete", "service_record", record_id,
        {"vehicle_id": str(record.vehicle_id)},
    )
    return ResponseBase(message="მომსახურების ჩანაწერი წაშლილია")


# ── Driver Assignments ────────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/drivers", response_model=ResponseBase[list[DriverAssignmentResponse]])
async def list_driver_assignments(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    result = await db.execute(
        select(DriverAssignment)
        .where(
            DriverAssignment.vehicle_id == vehicle_id,
            DriverAssignment.company_id == current_user.company_id,
        )
        .order_by(DriverAssignment.assigned_from.desc())
    )
    assignments = result.scalars().all()
    return ResponseBase(data=assignments)


@router.post("/vehicles/{vehicle_id}/drivers", response_model=ResponseBase[DriverAssignmentResponse], status_code=201)
async def create_driver_assignment(
    vehicle_id: UUID,
    payload: DriverAssignmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    assignment = DriverAssignment(
        company_id=current_user.company_id,
        vehicle_id=vehicle_id,
        **payload.model_dump(exclude={"vehicle_id"}),
    )
    db.add(assignment)
    await db.flush()
    add_fleet_audit(
        db, current_user, "create", "driver_assignment", assignment.id,
        {"vehicle_id": str(vehicle_id), "driver_name": assignment.driver_name},
    )
    await db.refresh(assignment)
    return ResponseBase(data=assignment, message="მძღოლი მინიჭებულია")


@router.put("/drivers/{assignment_id}", response_model=ResponseBase[DriverAssignmentResponse])
async def update_driver_assignment(
    assignment_id: UUID,
    payload: DriverAssignmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assignment = (
        await db.execute(
            select(DriverAssignment).where(
                DriverAssignment.id == assignment_id,
                DriverAssignment.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="მძღოლის მინიჭება არ მოიძებნა")
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="განახლების მონაცემები არ არის მოწოდებული")
    for key, value in update_data.items():
        setattr(assignment, key, value)
    await db.flush()
    add_fleet_audit(
        db, current_user, "update", "driver_assignment", assignment.id,
        {"updated_fields": list(update_data.keys())},
    )
    await db.refresh(assignment)
    return ResponseBase(data=assignment, message="მძღოლის მინიჭება განახლებულია")


@router.delete("/drivers/{assignment_id}", response_model=ResponseBase)
async def delete_driver_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_module("fleet", "can_delete")),
    db: AsyncSession = Depends(get_db),
):
    assignment = (
        await db.execute(
            select(DriverAssignment).where(
                DriverAssignment.id == assignment_id,
                DriverAssignment.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="მძღოლის მინიჭება არ მოიძებნა")
    await db.delete(assignment)
    add_fleet_audit(
        db, current_user, "delete", "driver_assignment", assignment_id,
        {"vehicle_id": str(assignment.vehicle_id)},
    )
    return ResponseBase(message="მძღოლის მინიჭება წაშლილია")


# ── Odometer Readings ─────────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/odometer", response_model=ResponseBase[list[OdometerReadingResponse]])
async def list_odometer_readings(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    result = await db.execute(
        select(OdometerReading)
        .where(
            OdometerReading.vehicle_id == vehicle_id,
            OdometerReading.company_id == current_user.company_id,
        )
        .order_by(OdometerReading.reading_date.desc())
    )
    readings = result.scalars().all()
    return ResponseBase(data=readings)


@router.post("/vehicles/{vehicle_id}/odometer", response_model=ResponseBase[OdometerReadingResponse], status_code=201)
async def create_odometer_reading(
    vehicle_id: UUID,
    payload: OdometerReadingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_company_vehicle(db, vehicle_id, current_user.company_id)
    reading = OdometerReading(
        company_id=current_user.company_id,
        vehicle_id=vehicle_id,
        **payload.model_dump(exclude={"vehicle_id"}),
    )
    db.add(reading)
    await db.flush()
    vehicle = await get_company_vehicle(db, vehicle_id, current_user.company_id)
    if reading.mileage_km > (vehicle.current_mileage or 0):
        vehicle.current_mileage = reading.mileage_km
    add_fleet_audit(
        db, current_user, "create", "odometer_reading", reading.id,
        {"vehicle_id": str(vehicle_id), "mileage_km": str(reading.mileage_km)},
    )
    await db.refresh(reading)
    return ResponseBase(data=reading, message="ოდომეტრის ჩანაწერი დამატებულია")


@router.delete("/odometer/{reading_id}", response_model=ResponseBase)
async def delete_odometer_reading(
    reading_id: UUID,
    current_user: User = Depends(require_module("fleet", "can_delete")),
    db: AsyncSession = Depends(get_db),
):
    reading = (
        await db.execute(
            select(OdometerReading).where(
                OdometerReading.id == reading_id,
                OdometerReading.company_id == current_user.company_id,
            )
        )
    ).scalar_one_or_none()
    if not reading:
        raise HTTPException(status_code=404, detail="ოდომეტრის ჩანაწერი არ მოიძებნა")
    await db.delete(reading)
    add_fleet_audit(
        db, current_user, "delete", "odometer_reading", reading_id,
        {"vehicle_id": str(reading.vehicle_id)},
    )
    return ResponseBase(message="ოდომეტრის ჩანაწერი წაშლილია")
