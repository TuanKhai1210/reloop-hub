from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class SensorReading(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sensor_readings"

    __table_args__ = (
        CheckConstraint(
            "fill_level >= 0 AND fill_level <= 100",
            name="ck_sensor_readings_fill_level_valid",
        ),
        CheckConstraint(
            "weight_kg >= 0",
            name="ck_sensor_readings_weight_non_negative",
        ),
    )

    hub_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fill_level: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    camera_online: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sensor_online: Mapped[bool] = mapped_column(Boolean, nullable=False)
    temperature_c: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
