"""TMS — transport & delivery models (REQ-TMS-01..09).

Built on the shared Asset/Vehicle identity (fleet.py). A Trip bundles delivery
requests into a planned route with stops, load and POD. Driver is a light
reference to the employee who drives (license validity enforced at dispatch).
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Driver(Base):
    """A driver tied to a fleet vehicle (light ref; full HR lives elsewhere)."""
    __tablename__ = "tms_drivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_categories: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class DeliveryRequest(Base):
    """REQ-TMS-01: a delivery to fulfil from SAL/WMS or an external source."""
    __tablename__ = "tms_delivery_requests"
    __table_args__ = (
        UniqueConstraint("company_id", "request_number", name="uq_tms_delivery_request_number"),
        CheckConstraint("source_type IS NULL OR length(source_type) >= 1", name="ck_tms_delivery_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    request_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # sales_order_line | shipment | external
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    # draft | planned | assigned | in_progress | delivered | partial | failed | cancelled

    pickup_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dropoff_address: Mapped[str] = mapped_column(String(500), nullable=False)
    # REQ-TMS-02 planning: dropoff coordinates (optional, used for route
    # sequencing when recorded — no geocoder required)
    dropoff_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    dropoff_lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scheduled_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # time window
    scheduled_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    package_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    special_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    exception: Mapped[str | None] = mapped_column(String(255), nullable=True)  # undelivered reason
    # REQ-TMS-06: returned (undelivered/failed) cargo re-enters stock ONLY via a
    # WMS return. These stamps record that the return was processed by WMS.
    returned_to_warehouse: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    returned_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    loads = relationship("TripLoad", back_populates="delivery", cascade="all, delete-orphan")


class Trip(Base):
    """REQ-TMS-02: a planned route bundling delivery requests with a vehicle+driver."""
    __tablename__ = "tms_trips"
    __table_args__ = (
        UniqueConstraint("company_id", "trip_number", name="uq_tms_trip_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    trip_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    # draft → planned → dispatched → in_progress → completed → closed; cancelled

    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=True, index=True)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_drivers.id"), nullable=True, index=True)
    carrier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)  # hired carrier
    carrier_rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    planned_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    total_weight_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"), nullable=False)
    total_volume_m3: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    vehicle = relationship("Vehicle")
    driver = relationship("Driver")
    stops = relationship("TripStop", back_populates="trip", order_by="TripStop.sequence", cascade="all, delete-orphan")
    loads = relationship("TripLoad", back_populates="trip", cascade="all, delete-orphan")


class TripStop(Base):
    """REQ-TMS-02/04: one stop in a trip sequence with planned window + arrival state."""
    __tablename__ = "tms_trip_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_trips.id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    window_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    window_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending → arrived → delivered / partial / failed

    arrived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    departed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    exception: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    trip = relationship("Trip", back_populates="stops")
    loads = relationship("TripLoad", back_populates="stop", cascade="all, delete-orphan")


class TripLoad(Base):
    """REQ-TMS-02: a delivery request assigned to a trip stop with its qty/weight/volume."""
    __tablename__ = "tms_trip_loads"
    __table_args__ = (
        UniqueConstraint("company_id", "trip_id", "delivery_id", name="uq_tms_trip_load_delivery"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_trips.id"), nullable=False, index=True)
    stop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_trip_stops.id"), nullable=True, index=True)
    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_delivery_requests.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)

    trip = relationship("Trip", back_populates="loads")
    stop = relationship("TripStop", back_populates="loads")
    delivery = relationship("DeliveryRequest", back_populates="loads")


class TripPOD(Base):
    """REQ-TMS-05/06: proof of delivery — actual result + evidence."""
    __tablename__ = "tms_pods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_trips.id"), nullable=False, index=True)
    stop_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_trip_stops.id"), nullable=False, index=True)
    delivery_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_delivery_requests.id"), nullable=True)

    delivered_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    delivered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    exception: Mapped[str | None] = mapped_column(String(100), nullable=True)  # ok | not_at_place | refused | damaged | wrong_address | other
    exception_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # photo/signature doc id
    corrected_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # REQ-TMS-06 POD correction: original record is preserved; a corrected POD
    # supersedes it (supersedes_id → original). Original is never mutated.
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_pods.id"), nullable=True, index=True)

    device_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # offline idempotency
    device_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    server_received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class TripCostAllocation(Base):
    """REQ-TMS-08: trip costs split across deliveries by weight/volume/qty."""
    __tablename__ = "tms_trip_cost_allocations"
    __table_args__ = (
        UniqueConstraint("company_id", "trip_id", "delivery_id", "cost_type", name="uq_tms_trip_cost_alloc"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_trips.id"), nullable=False, index=True)
    delivery_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tms_delivery_requests.id"), nullable=False, index=True)
    cost_type: Mapped[str] = mapped_column(String(30), nullable=False)  # fuel | road | carrier | other
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    allocation_method: Mapped[str] = mapped_column(String(20), default="weight", nullable=False)  # weight|volume|quantity
    # REQ-TMS-08: rule version used for this allocation (immutable ledger semantics)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_expense_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)  # FIN expense ref
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
