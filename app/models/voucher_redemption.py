from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import VoucherRedemptionStatus


class VoucherRedemption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "voucher_redemptions"

    __table_args__ = (
        CheckConstraint(
            "points_spent > 0",
            name="ck_voucher_redemptions_points_spent_positive",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="ck_voucher_redemptions_expiration_valid",
        ),
        Index(
            "ix_voucher_redemptions_user_created_at",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_voucher_redemptions_voucher_status",
            "voucher_id",
            "status",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    voucher_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("vouchers.id", ondelete="RESTRICT"),
        nullable=False,
    )

    redemption_code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
    )

    points_spent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[VoucherRedemptionStatus] = mapped_column(
        SqlEnum(
            VoucherRedemptionStatus,
            name="voucher_redemption_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=VoucherRedemptionStatus.ISSUED,
        server_default=VoucherRedemptionStatus.ISSUED.value,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
