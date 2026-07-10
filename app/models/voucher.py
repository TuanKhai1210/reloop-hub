from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import VoucherStatus


class Voucher(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vouchers"

    __table_args__ = (
        CheckConstraint(
            "required_points > 0",
            name="ck_vouchers_required_points_positive",
        ),
        CheckConstraint(
            "quantity_available >= 0",
            name="ck_vouchers_quantity_available_non_negative",
        ),
        CheckConstraint(
            "expires_at IS NULL OR valid_from IS NULL "
            "OR expires_at > valid_from",
            name="ck_vouchers_valid_period",
        ),
        Index(
            "ix_vouchers_status",
            "status",
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

    partner_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    required_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    value_text: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    quantity_available: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default="100",
    )

    status: Mapped[VoucherStatus] = mapped_column(
        SqlEnum(
            VoucherStatus,
            name="voucher_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=VoucherStatus.ACTIVE,
        server_default=VoucherStatus.ACTIVE.value,
    )

    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
