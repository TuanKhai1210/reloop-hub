from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import VerificationLevel, VerificationResult


class VerificationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "verification_events"

    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR "
            "(confidence >= 0 AND confidence <= 1)",
            name="ck_verification_events_confidence_valid",
        ),
        CheckConstraint(
            "processing_time_ms IS NULL OR processing_time_ms >= 0",
            name="ck_verification_events_processing_time_non_negative",
        ),
        Index(
            "ix_verification_events_transaction_created_at",
            "transaction_id",
            "created_at",
        ),
    )

    transaction_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("bottle_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )

    verification_level: Mapped[VerificationLevel] = mapped_column(
        SqlEnum(
            VerificationLevel,
            name="verification_level_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    result: Mapped[VerificationResult] = mapped_column(
        SqlEnum(
            VerificationResult,
            name="verification_result_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    verifier_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    verifier_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    rule_code: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    input_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    output_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    processing_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
