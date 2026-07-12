from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import TraceStage


class TraceEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "trace_events"

    __table_args__ = (
        Index("ix_trace_events_code_time", "trace_code", "occurred_at"),
    )

    trace_code: Mapped[str] = mapped_column(String(80), nullable=False)
    transaction_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("bottle_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    stage: Mapped[TraceStage] = mapped_column(
        SqlEnum(TraceStage, name="trace_stage_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    location_type: Mapped[str] = mapped_column(String(40), nullable=False)
    location_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
