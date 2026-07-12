from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ReturnSessionStatus


class ReturnSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "return_sessions"

    __table_args__ = (
        CheckConstraint(
            "total_accepted >= 0",
            name="ck_return_sessions_total_accepted_non_negative",
        ),
        CheckConstraint(
            "total_rejected >= 0",
            name="ck_return_sessions_total_rejected_non_negative",
        ),
        CheckConstraint(
            "total_points >= 0",
            name="ck_return_sessions_total_points_non_negative",
        ),
        CheckConstraint(
            "(status = 'OPEN' AND finished_at IS NULL) OR "
            "(status IN ('COMPLETED', 'CANCELLED') "
            "AND finished_at IS NOT NULL)",
            name="ck_return_sessions_status_time_consistent",
        ),
        Index(
            "uq_return_sessions_user_open",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    hub_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[ReturnSessionStatus] = mapped_column(
        SqlEnum(
            ReturnSessionStatus,
            name="return_session_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=ReturnSessionStatus.OPEN,
        server_default=ReturnSessionStatus.OPEN.value,
    )

    total_accepted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    total_rejected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    total_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
