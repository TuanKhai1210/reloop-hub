from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MaterialBatchStatus, MaterialType


class MaterialBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "material_batches"

    __table_args__ = (
        CheckConstraint(
            "bottle_count >= 0",
            name="ck_material_batches_bottle_count_non_negative",
        ),
        CheckConstraint(
            "estimated_weight_kg >= 0",
            name="ck_material_batches_weight_non_negative",
        ),
        CheckConstraint(
            "material_type IN ('PET', 'HDPE')",
            name="ck_material_batches_supported_material",
        ),
    )

    code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
    )

    hub_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("hubs.id", ondelete="RESTRICT"),
        nullable=False,
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

    bottle_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    estimated_weight_kg: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )

    status: Mapped[MaterialBatchStatus] = mapped_column(
        SqlEnum(
            MaterialBatchStatus,
            name="material_batch_status_enum",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=MaterialBatchStatus.STORING,
        server_default=MaterialBatchStatus.STORING.value,
    )
