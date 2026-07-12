from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RouteStatus


class CollectionRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "collection_routes"

    __table_args__ = (
        CheckConstraint(
            "threshold_percent BETWEEN 1 AND 100",
            name="ck_collection_routes_threshold_valid",
        ),
        CheckConstraint(
            "total_distance_km >= 0 AND baseline_distance_km >= 0",
            name="ck_collection_routes_distance_non_negative",
        ),
        CheckConstraint(
            "estimated_load_kg >= 0",
            name="ck_collection_routes_load_non_negative",
        ),
        CheckConstraint(
            "(status = 'PLANNED' AND started_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'IN_PROGRESS' AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'COMPLETED' AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'CANCELLED' AND completed_at IS NULL)",
            name="ck_collection_routes_status_time_consistent",
        ),
    )

    code: Mapped[str] = mapped_column(
        String(80), nullable=False, unique=True
    )
    vehicle_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[RouteStatus] = mapped_column(
        SqlEnum(RouteStatus, name="route_status_enum", native_enum=True),
        nullable=False,
        default=RouteStatus.PLANNED,
        server_default=RouteStatus.PLANNED.value,
        index=True,
    )
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    total_distance_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0, server_default="0"
    )
    baseline_distance_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=0, server_default="0"
    )
    distance_saved_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0, server_default="0"
    )
    estimated_load_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=0, server_default="0"
    )
    planned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RouteStop(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "route_stops"

    __table_args__ = (
        CheckConstraint(
            "sequence > 0", name="ck_route_stops_sequence_positive"
        ),
        CheckConstraint(
            "distance_from_previous_km >= 0",
            name="ck_route_stops_distance_non_negative",
        ),
        CheckConstraint(
            "expected_load_kg >= 0 AND "
            "(collected_load_kg IS NULL OR collected_load_kg >= 0)",
            name="ck_route_stops_load_non_negative",
        ),
        UniqueConstraint(
            "route_id",
            "sequence",
            name="uq_route_stops_route_sequence",
        ),
    )

    route_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("collection_routes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    hub_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pickup_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("pickups.id", ondelete="RESTRICT"),
        nullable=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_from_previous_km: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    expected_load_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    collected_load_kg: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
