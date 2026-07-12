from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    __table_args__ = (
        CheckConstraint(
            "capacity_kg > 0",
            name="ck_vehicles_capacity_positive",
        ),
    )

    code: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True
    )
    driver_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    capacity_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    latitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6), nullable=False
    )
    longitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
