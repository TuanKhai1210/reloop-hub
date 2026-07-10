from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import PointSourceType


class PointLedger(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "point_ledger"

    __table_args__ = (
        CheckConstraint(
            "points_change <> 0",
            name="ck_point_ledger_points_change_non_zero",
        ),
        CheckConstraint(
            "balance_after >= 0",
            name="ck_point_ledger_balance_after_non_negative",
        ),
        UniqueConstraint(
            "source_type",
            "source_id",
            name="uq_point_ledger_source",
        ),
        Index(
            "ix_point_ledger_user_created_at",
            "user_id",
            "created_at",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    source_type: Mapped[PointSourceType] = mapped_column(
        SqlEnum(
            PointSourceType,
            name="point_source_type_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    source_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )

    points_change: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    balance_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
