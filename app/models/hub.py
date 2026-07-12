from decimal import Decimal

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import HubStatus


class Hub(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hubs"

    __table_args__ = (
        CheckConstraint(
            "pet_capacity > 0",
            name="ck_hubs_pet_capacity_positive",
        ),
        CheckConstraint(
            "hdpe_capacity > 0",
            name="ck_hubs_hdpe_capacity_positive",
        ),
        CheckConstraint(
            "pet_current >= 0 AND pet_current <= pet_capacity",
            name="ck_hubs_pet_current_valid",
        ),
        CheckConstraint(
            "hdpe_current >= 0 AND hdpe_current <= hdpe_capacity",
            name="ck_hubs_hdpe_current_valid",
        ),
        CheckConstraint(
            "pickup_threshold_percent BETWEEN 1 AND 100",
            name="ck_hubs_pickup_threshold_valid",
        ),
        CheckConstraint(
            "capacity_kg > 0",
            name="ck_hubs_capacity_kg_positive",
        ),
        CheckConstraint(
            "current_load_kg >= 0 AND current_load_kg <= capacity_kg",
            name="ck_hubs_current_load_valid",
        ),
        CheckConstraint(
            "fill_level >= 0 AND fill_level <= 100",
            name="ck_hubs_fill_level_valid",
        ),
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    location_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )

    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )

    status: Mapped[HubStatus] = mapped_column(
        SqlEnum(
            HubStatus,
            name="hub_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=HubStatus.ACTIVE,
        server_default=HubStatus.ACTIVE.value,
    )

    pet_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        server_default="50",
    )

    hdpe_capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        server_default="30",
    )

    pet_current: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    hdpe_current: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    pickup_threshold_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=80,
        server_default="80",
    )

    capacity_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("200"),
        server_default="200",
    )

    current_load_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    fill_level: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    camera_online: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    sensor_online: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
