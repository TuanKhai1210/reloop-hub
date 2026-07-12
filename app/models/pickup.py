from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PickupStatus


class Pickup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pickups"

    __table_args__ = (
        CheckConstraint(
            "total_batches >= 0",
            name="ck_pickups_total_batches_non_negative",
        ),
        CheckConstraint(
            "total_bottles >= 0",
            name="ck_pickups_total_bottles_non_negative",
        ),
        CheckConstraint(
            "estimated_weight_kg >= 0",
            name="ck_pickups_estimated_weight_non_negative",
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL "
            "OR completed_at >= started_at",
            name="ck_pickups_completion_time_valid",
        ),
        CheckConstraint(
            "(status = 'PLANNED' AND started_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'IN_PROGRESS' AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'COMPLETED' AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'CANCELLED' AND completed_at IS NULL)",
            name="ck_pickups_status_time_consistent",
        ),
    )

    code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
    )

    hub_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    driver_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    status: Mapped[PickupStatus] = mapped_column(
        SqlEnum(
            PickupStatus,
            name="pickup_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=PickupStatus.PLANNED,
        server_default=PickupStatus.PLANNED.value,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    total_batches: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    total_bottles: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    estimated_weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
