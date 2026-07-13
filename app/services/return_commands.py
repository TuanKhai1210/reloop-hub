from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping
from uuid import UUID

from app.models import (
    CleanlinessStatus,
    MaterialType,
    RejectReason,
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
    cleanliness_score: Decimal | None = None



@dataclass(frozen=True, slots=True)
class RejectBottleCommand:
    session_id: UUID
    transaction_code: str
    material_type: MaterialType
    reject_reason: RejectReason
    verification_level: VerificationLevel
    verifier_name: str
    verified_material_type: MaterialType | None = None
    cleanliness_status: CleanlinessStatus | None = None
    weight_gram: Decimal | None = None
    verifier_version: str | None = None
    rule_code: str | None = None
    input_payload: Mapping[str, object] = field(
        default_factory=dict
    )
    output_payload: Mapping[str, object] | None = None
    confidence: Decimal | None = None
    processing_time_ms: int | None = None
    failure_reason: str | None = None
    cleanliness_score: Decimal | None = None
