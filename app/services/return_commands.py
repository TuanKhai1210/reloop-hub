from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping
from uuid import UUID

from app.models import (
    CleanlinessStatus,
    MaterialType,
    VerificationLevel,
)


@dataclass(frozen=True, slots=True)
class AcceptBottleCommand:
    session_id: UUID
    batch_id: UUID
    transaction_code: str
    material_type: MaterialType
    verified_material_type: MaterialType
    verification_level: VerificationLevel
    cleanliness_status: CleanlinessStatus
    weight_gram: Decimal
    points_awarded: int
    verifier_name: str
    verifier_version: str | None = None
    rule_code: str | None = None
    input_payload: Mapping[str, object] = field(
        default_factory=dict
    )
    output_payload: Mapping[str, object] | None = None
    confidence: Decimal | None = None
    processing_time_ms: int | None = None
