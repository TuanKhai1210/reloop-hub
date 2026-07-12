from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    BottleTransactionStatus,
    CleanlinessStatus,
    MaterialType,
    RejectReason,
    VerificationLevel,
)


class BottleTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bottle_transactions"

    __table_args__ = (
        CheckConstraint(
            "points_awarded >= 0",
            name="ck_bottle_transactions_points_non_negative",
        ),
        CheckConstraint(
            "weight_gram IS NULL OR weight_gram >= 0",
            name="ck_bottle_transactions_weight_non_negative",
        ),
        CheckConstraint(
            "ai_confidence IS NULL OR "
            "(ai_confidence >= 0 AND ai_confidence <= 1)",
            name="ck_bottle_transactions_ai_confidence_valid",
        ),
        CheckConstraint(
            "(status = 'ACCEPTED' AND batch_id IS NOT NULL "
            "AND reject_reason IS NULL) OR "
            "(status = 'REJECTED' AND batch_id IS NULL "
            "AND reject_reason IS NOT NULL AND points_awarded = 0)",
            name="ck_bottle_transactions_outcome_consistent",
        ),
    )

    code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
    )

    session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("return_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    batch_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("material_batches.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    material_type: Mapped[MaterialType] = mapped_column(
        SqlEnum(
            MaterialType,
            name="material_type_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    verified_material_type: Mapped[MaterialType | None] = mapped_column(
        SqlEnum(
            MaterialType,
            name="verified_material_type_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=True,
    )

    status: Mapped[BottleTransactionStatus] = mapped_column(
        SqlEnum(
            BottleTransactionStatus,
            name="bottle_transaction_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    reject_reason: Mapped[RejectReason | None] = mapped_column(
        SqlEnum(
            RejectReason,
            name="reject_reason_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=True,
    )

    verification_level: Mapped[VerificationLevel] = mapped_column(
        SqlEnum(
            VerificationLevel,
            name="verification_level_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=VerificationLevel.LEVEL_1,
        server_default=VerificationLevel.LEVEL_1.value,
    )

    cleanliness_status: Mapped[CleanlinessStatus | None] = mapped_column(
        SqlEnum(
            CleanlinessStatus,
            name="cleanliness_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=True,
    )

    weight_gram: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    ai_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    points_awarded: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
