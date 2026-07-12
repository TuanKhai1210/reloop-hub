import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    DRIVER = "driver"
    RECYCLER = "recycler"
    RESIDENT = "resident"


class HubStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    FULL = "full"


class MaterialType(str, enum.Enum):
    PET = "PET"
    HDPE = "HDPE"


class DepositStatus(str, enum.Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RouteStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TraceStage(str, enum.Enum):
    DEPOSITED = "deposited"
    HUB_STORED = "hub_stored"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    RECYCLED = "recycled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.RESIDENT, index=True)
    points_balance: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Hub(Base):
    __tablename__ = "hubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(String(500))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    capacity_kg: Mapped[float] = mapped_column(Float, default=200)
    current_load_kg: Mapped[float] = mapped_column(Float, default=0)
    fill_level: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[HubStatus] = mapped_column(Enum(HubStatus), default=HubStatus.OFFLINE, index=True)
    camera_online: Mapped[bool] = mapped_column(Boolean, default=False)
    sensor_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    hub_id: Mapped[int] = mapped_column(ForeignKey("hubs.id"), index=True)
    fill_level: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    camera_online: Mapped[bool] = mapped_column(Boolean)
    sensor_online: Mapped[bool] = mapped_column(Boolean)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    hub: Mapped[Hub] = relationship()


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_code: Mapped[str] = mapped_column(String(40), unique=True, index=True, default=lambda: f"RL-{uuid.uuid4().hex[:12].upper()}")
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    hub_id: Mapped[int] = mapped_column(ForeignKey("hubs.id"), index=True)
    material_type: Mapped[MaterialType | None] = mapped_column(Enum(MaterialType), nullable=True, index=True)
    weight_g: Mapped[float] = mapped_column(Float)
    ai_confidence: Mapped[float] = mapped_column(Float)
    cleanliness_score: Mapped[float] = mapped_column(Float)
    liquid_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    foreign_object_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[DepositStatus] = mapped_column(Enum(DepositStatus), index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user: Mapped[User | None] = relationship()
    hub: Mapped[Hub] = relationship()


class PointsLedger(Base):
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    deposit_id: Mapped[int | None] = mapped_column(ForeignKey("deposits.id"), nullable=True)
    points: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(30), default="earn")
    description: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    capacity_kg: Mapped[float] = mapped_column(Float)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CollectionRoute(Base):
    __tablename__ = "collection_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    status: Mapped[RouteStatus] = mapped_column(Enum(RouteStatus), default=RouteStatus.PLANNED, index=True)
    threshold_percent: Mapped[float] = mapped_column(Float)
    total_distance_km: Mapped[float] = mapped_column(Float, default=0)
    baseline_distance_km: Mapped[float] = mapped_column(Float, default=0)
    distance_saved_percent: Mapped[float] = mapped_column(Float, default=0)
    estimated_load_kg: Mapped[float] = mapped_column(Float, default=0)
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vehicle: Mapped[Vehicle] = relationship()
    stops: Mapped[list["RouteStop"]] = relationship(back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.sequence")


class RouteStop(Base):
    __tablename__ = "route_stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("collection_routes.id"), index=True)
    hub_id: Mapped[int] = mapped_column(ForeignKey("hubs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    distance_from_previous_km: Mapped[float] = mapped_column(Float)
    expected_load_kg: Mapped[float] = mapped_column(Float)
    collected_load_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    route: Mapped[CollectionRoute] = relationship(back_populates="stops")
    hub: Mapped[Hub] = relationship()


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_code: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[TraceStage] = mapped_column(Enum(TraceStage), index=True)
    location_type: Mapped[str] = mapped_column(String(40))
    location_ref: Mapped[str] = mapped_column(String(100))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
