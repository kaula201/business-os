import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, func, Numeric, Table, Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
import enum


class ClientType(str, enum.Enum):
    LEGAL = "legal"
    INDIVIDUAL = "individual"


class ClientStatus(str, enum.Enum):
    POTENTIAL = "potential"
    ACTIVE = "active"
    INACTIVE = "inactive"


# M2M: clients ↔ groups
client_groups = Table(
    "client_groups",
    Base.metadata,
    Column("client_id", UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", UUID(as_uuid=True), ForeignKey("client_group_defs.id", ondelete="CASCADE"), primary_key=True),
)


class ClientGroupDef(Base):
    """Client group / segment definition (e.g. VIP, Wholesale, Retail)."""
    __tablename__ = "client_group_defs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    clients = relationship("Client", secondary=client_groups, back_populates="groups")


class ClientAddress(Base):
    """Multiple addresses per client: legal / delivery / billing."""
    __tablename__ = "client_addresses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    address_type: Mapped[str] = mapped_column(String(20), default="legal", nullable=False)  # legal | delivery | billing
    address_line: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), default="საქართველო", nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="addresses")


class ClientRelation(Base):
    """Linked companies / branches (parent, subsidiary, branch, partner)."""
    __tablename__ = "client_relations"
    __table_args__ = (
        UniqueConstraint("company_id", "client_id", "related_client_id", name="uq_client_relation_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    related_client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(30), default="branch", nullable=False)  # parent | subsidiary | branch | partner
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client = relationship("Client", foreign_keys=[client_id], back_populates="relations")
    related_client = relationship("Client", foreign_keys=[related_client_id])


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_type: Mapped[str] = mapped_column(String(20), nullable=False)
    identification_code: Mapped[str] = mapped_column(String(50), nullable=False)
    vat_status: Mapped[bool] = mapped_column(Boolean, default=True)
    fiscal_position_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("fiscal_positions.id"), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="potential")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit_limit: Mapped[float | None] = mapped_column(Numeric(18, 2), default=0, nullable=True)
    balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="clients")
    orders = relationship("Order", back_populates="client")
    tasks = relationship("Task", back_populates="client")
    contacts = relationship("Contact", back_populates="client", cascade="all, delete-orphan")
    interactions = relationship("Interaction", back_populates="client", cascade="all, delete-orphan")
    addresses = relationship("ClientAddress", back_populates="client", cascade="all, delete-orphan")
    groups = relationship("ClientGroupDef", secondary=client_groups, back_populates="clients")
    relations = relationship("ClientRelation", foreign_keys=[ClientRelation.client_id], back_populates="client", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="contacts")


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # note, call, meeting, email
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    client = relationship("Client", back_populates="interactions")
