"""Fleet management: vehicles, fuel logs, service records, drivers."""
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import CheckConstraint, String, Boolean, DateTime, ForeignKey, Text, Numeric, Date, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Vehicle(Base):
    """Company vehicle registry."""
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_vehicle_latitude"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_vehicle_longitude"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_vehicle_coordinate_pair",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    plate_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int | None] = mapped_column(Numeric(4, 0), nullable=True)
    vin: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fuel_type: Mapped[str] = mapped_column(String(20), default="petrol")  # petrol, diesel, gas, electric, hybrid
    engine_capacity: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    tank_capacity_liters: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    # TMS 2.0 (REQ-TMS-02/09): cargo capacity + ownership for dispatch capacity checks
    capacity_kg: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    capacity_m3: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    ownership: Mapped[str] = mapped_column(String(20), default="own", nullable=False)  # own | leased | hired
    maintenance_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    initial_mileage: Mapped[float] = mapped_column(Numeric(10, 1), default=0)
    current_mileage: Mapped[float] = mapped_column(Numeric(10, 1), default=0)
    service_interval_km: Mapped[float | None] = mapped_column(Numeric(10, 1), nullable=True)
    service_interval_days: Mapped[int | None] = mapped_column(Numeric(5, 0), nullable=True)
    insurance_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_policy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insurance_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    tech_inspection_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    fuel_logs = relationship("FuelLog", back_populates="vehicle", cascade="all, delete-orphan")
    service_records = relationship("ServiceRecord", back_populates="vehicle", cascade="all, delete-orphan")
    assignments = relationship("DriverAssignment", back_populates="vehicle", cascade="all, delete-orphan")
    odometer_readings = relationship("OdometerReading", back_populates="vehicle", cascade="all, delete-orphan")


class FuelLog(Base):
    """Fuel refueling records."""
    __tablename__ = "fuel_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    refuel_date: Mapped[date] = mapped_column(Date, nullable=False)
    liters: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_liter: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    mileage_at_refuel: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    fuel_card: Mapped[str | None] = mapped_column(String(100), nullable=True)
    station: Mapped[str | None] = mapped_column(String(255), nullable=True)
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # REQ-TMS-07: a fuel log can be linked to an optional trip for per-trip cost/
    # consumption reporting. trip optional by design.
    trip_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_trips.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="fuel_logs")


class ServiceRecord(Base):
    """Vehicle maintenance and repair records."""
    __tablename__ = "service_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_type: Mapped[str] = mapped_column(String(50), nullable=False)  # oil_change, repair, tire, inspection, other
    description: Mapped[str] = mapped_column(Text, nullable=False)
    mileage_at_service: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    service_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    next_service_mileage: Mapped[float | None] = mapped_column(Numeric(10, 1), nullable=True)
    next_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="service_records")


class DriverAssignment(Base):
    """Driver-to-vehicle assignment tracking."""
    __tablename__ = "driver_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    driver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    driver_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    driver_license: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assigned_from: Mapped[date] = mapped_column(Date, nullable=False)
    assigned_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="assignments")


class OdometerReading(Base):
    """Recorded odometer readings for a vehicle (drives km tracking + fuel economy)."""
    __tablename__ = "odometer_readings"
    __table_args__ = (
        CheckConstraint("mileage_km >= 0", name="ck_odometer_mileage_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    reading_date: Mapped[date] = mapped_column(Date, nullable=False)
    mileage_km: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    source: Mapped[str | None] = mapped_column(String(30), default="manual")  # manual, fuel, service, gps
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vehicle = relationship("Vehicle", back_populates="odometer_readings")
