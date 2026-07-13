from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import (
    BottleTransaction,
    CleanlinessStatus,
    HubStatus,
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
    RejectReason,
    TraceEvent,
    TraceStage,
    VerificationLevel,
)
from app.repositories import (
    HubRepository,
    MaterialBatchRepository,
    ReturnSessionRepository,
    UserRepository,
)
from app.services.errors import EntityNotFoundError, InvalidStateError
from app.services.return_commands import (
    AcceptBottleCommand,
    RejectBottleCommand,
)
from app.services.return_service import ReturnService


MIN_AI_CONFIDENCE = Decimal("0.80")
MIN_CLEANLINESS_SCORE = Decimal("0.70")


@dataclass(frozen=True, slots=True)
class InspectBottleCommand:
    user_id: UUID
    hub_code: str
    material_type: MaterialType
    weight_gram: Decimal
    ai_confidence: Decimal
    cleanliness_score: Decimal
    liquid_detected: bool
    foreign_object_detected: bool


class DepositService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.user_repository = UserRepository(session)
        self.hub_repository = HubRepository(session)
        self.session_repository = ReturnSessionRepository(session)
        self.batch_repository = MaterialBatchRepository(session)
        self.return_service = ReturnService(session)

    def inspect_bottle(
        self,
        command: InspectBottleCommand,
    ) -> BottleTransaction:
        user = self.user_repository.get_by_id(command.user_id)
        if user is None:
            raise EntityNotFoundError("user not found")

        hub = self.hub_repository.get_by_code(
            command.hub_code.strip()
        )
        if hub is None:
            raise EntityNotFoundError("hub not found")

        if hub.status in {
            HubStatus.MAINTENANCE,
            HubStatus.OFFLINE,
            HubStatus.FULL,
        }:
            raise InvalidStateError(
                "hub is not available for bottle returns"
            )

        return_session = self.session_repository.get_latest_open_by_user(
            user.id
        )
        if return_session is None:
            return_session = self.return_service.start_session(
                user_id=user.id,
                hub_id=hub.id,
            )
        elif return_session.hub_id != hub.id:
            raise InvalidStateError(
                "user has an open session at another hub"
            )

        transaction_code = f"RL-{uuid4().hex[:16].upper()}"
        reject_reason = self._get_reject_reason(command)

        if reject_reason is not None:
            transaction = self.return_service.reject_bottle(
                RejectBottleCommand(
                    session_id=return_session.id,
                    transaction_code=transaction_code,
                    material_type=command.material_type,
                    verified_material_type=command.material_type,
                    reject_reason=reject_reason,
                    verification_level=VerificationLevel.LEVEL_2,
                    verifier_name="hub_rule_engine",
                    verifier_version="1.0.0",
                    cleanliness_status=(
                        CleanlinessStatus.DIRTY
                        if command.cleanliness_score
                        < MIN_CLEANLINESS_SCORE
                        else CleanlinessStatus.UNKNOWN
                    ),
                    weight_gram=command.weight_gram,
                    confidence=command.ai_confidence,
                    cleanliness_score=command.cleanliness_score,
                    input_payload=self._payload(command),
                    output_payload={"accepted": False},
                    failure_reason=reject_reason.value,
                )
            )
            self._add_trace(
                transaction=transaction,
                stage=TraceStage.REJECTED,
                hub_code=hub.code,
                user_id=user.id,
                metadata={"reason": reject_reason.value},
            )
            return transaction

        added_kg = command.weight_gram / Decimal("1000")
        if hub.current_load_kg + added_kg > hub.capacity_kg:
            transaction = self.return_service.reject_bottle(
                RejectBottleCommand(
                    session_id=return_session.id,
                    transaction_code=transaction_code,
                    material_type=command.material_type,
                    verified_material_type=command.material_type,
                    reject_reason=RejectReason.HUB_FULL,
                    verification_level=VerificationLevel.LEVEL_2,
                    verifier_name="hub_capacity_rule",
                    weight_gram=command.weight_gram,
                    confidence=command.ai_confidence,
                    cleanliness_score=command.cleanliness_score,
                    input_payload=self._payload(command),
                    output_payload={"accepted": False},
                )
            )
            self._add_trace(
                transaction=transaction,
                stage=TraceStage.REJECTED,
                hub_code=hub.code,
                user_id=user.id,
                metadata={"reason": RejectReason.HUB_FULL.value},
            )
            return transaction

        batch = self._get_or_create_batch(
            hub_id=hub.id,
            material_type=command.material_type,
        )
        transaction = self.return_service.accept_bottle(
            AcceptBottleCommand(
                session_id=return_session.id,
                batch_id=batch.id,
                transaction_code=transaction_code,
                material_type=command.material_type,
                verified_material_type=command.material_type,
                verification_level=VerificationLevel.LEVEL_2,
                cleanliness_status=CleanlinessStatus.CLEAN,
                weight_gram=command.weight_gram,
                points_awarded=0,
                verifier_name="hub_rule_engine",
                verifier_version="1.0.0",
                rule_code="MATERIAL_CLEAN_WEIGHT_VALID",
                input_payload=self._payload(command),
                output_payload={
                    "accepted": True,
                    "material_type": command.material_type.value,
                },
                confidence=command.ai_confidence,
                cleanliness_score=command.cleanliness_score,
            )
        )

        hub.current_load_kg += added_kg
        hub.fill_level = (
            hub.current_load_kg / hub.capacity_kg * Decimal("100")
        ).quantize(Decimal("0.01"))
        if hub.fill_level >= Decimal("100"):
            hub.status = HubStatus.FULL
        elif hub.fill_level >= hub.pickup_threshold_percent:
            hub.status = HubStatus.NEAR_FULL

        self._add_trace(
            transaction=transaction,
            stage=TraceStage.DEPOSITED,
            hub_code=hub.code,
            user_id=user.id,
            metadata={
                "weight_gram": str(command.weight_gram),
                "material": command.material_type.value,
            },
        )
        self._add_trace(
            transaction=transaction,
            stage=TraceStage.HUB_STORED,
            hub_code=hub.code,
            user_id=None,
            metadata={"batch_id": str(batch.id)},
        )
        self.session.flush()
        return transaction

    def _get_or_create_batch(
        self,
        *,
        hub_id: UUID,
        material_type: MaterialType,
    ) -> MaterialBatch:
        batches = self.batch_repository.list_by_hub(
            hub_id,
            material_type=material_type,
            status=MaterialBatchStatus.STORING,
            limit=1,
        )
        if batches:
            batch = self.batch_repository.get_by_id_for_update(
                batches[0].id
            )
            if batch is not None:
                return batch

        return self.batch_repository.add(
            MaterialBatch(
                code=f"BATCH-{uuid4().hex[:16].upper()}",
                hub_id=hub_id,
                pickup_id=None,
                material_type=material_type,
                bottle_count=0,
                estimated_weight_kg=Decimal("0"),
                status=MaterialBatchStatus.STORING,
            )
        )

    def _add_trace(
        self,
        *,
        transaction: BottleTransaction,
        stage: TraceStage,
        hub_code: str,
        user_id: UUID | None,
        metadata: dict,
    ) -> None:
        self.session.add(
            TraceEvent(
                trace_code=transaction.code,
                transaction_id=transaction.id,
                stage=stage,
                location_type="hub",
                location_ref=hub_code,
                actor_user_id=user_id,
                notes=None,
                event_metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _get_reject_reason(
        command: InspectBottleCommand,
    ) -> RejectReason | None:
        if command.material_type not in {
            MaterialType.PET,
            MaterialType.HDPE,
        }:
            return RejectReason.UNSUPPORTED_MATERIAL
        if command.ai_confidence < MIN_AI_CONFIDENCE:
            return RejectReason.LOW_CONFIDENCE
        if command.liquid_detected:
            return RejectReason.BOTTLE_HAS_LIQUID
        if command.foreign_object_detected:
            return RejectReason.INVALID_SAMPLE_CODE
        if command.cleanliness_score < MIN_CLEANLINESS_SCORE:
            return RejectReason.DIRTY_BOTTLE
        return None

    @staticmethod
    def _payload(command: InspectBottleCommand) -> dict:
        return {
            "material_type": command.material_type.value,
            "weight_gram": str(command.weight_gram),
            "ai_confidence": str(command.ai_confidence),
            "cleanliness_score": str(command.cleanliness_score),
            "liquid_detected": command.liquid_detected,
            "foreign_object_detected": command.foreign_object_detected,
        }
