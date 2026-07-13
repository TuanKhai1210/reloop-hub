from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    BottleTransaction,
    BottleTransactionStatus,
    CleanlinessStatus,
    Hub,
    HubStatus,
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
    PointLedger,
    PointSourceType,
    ReturnSession,
    ReturnSessionStatus,
    VerificationEvent,
    VerificationResult,
)
from app.repositories import (
    BottleTransactionRepository,
    HubRepository,
    MaterialBatchRepository,
    PointLedgerRepository,
    ReturnSessionRepository,
    UserRepository,
    VerificationEventRepository,
)
from app.services.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
)
from app.services.return_commands import (
    AcceptBottleCommand,
    RejectBottleCommand,
)
from app.services.reward_policy import (
    FixedBottleRewardPolicy,
    RewardPolicy,
)


class ReturnService:
    AVAILABLE_HUB_STATUSES = frozenset(
        {
            HubStatus.ACTIVE,
            HubStatus.NEAR_FULL,
        }
    )

    SUPPORTED_MATERIAL_TYPES = frozenset(
        {
            MaterialType.PET,
            MaterialType.HDPE,
        }
    )

    GRAMS_PER_KILOGRAM = Decimal("1000")

    TRANSACTION_CODE_UNIQUE_CONSTRAINT = (
        "uq_bottle_transactions_code"
    )

    def __init__(
        self,
        session: Session,
        *,
        reward_policy: RewardPolicy | None = None,
    ) -> None:
        self.session = session
        self.reward_policy = (
            reward_policy or FixedBottleRewardPolicy()
        )

        self.user_repository = UserRepository(session)
        self.hub_repository = HubRepository(session)

        self.return_session_repository = (
            ReturnSessionRepository(session)
        )

        self.bottle_transaction_repository = (
            BottleTransactionRepository(session)
        )

        self.material_batch_repository = (
            MaterialBatchRepository(session)
        )

        self.verification_event_repository = (
            VerificationEventRepository(session)
        )

        self.point_ledger_repository = (
            PointLedgerRepository(session)
        )

    def start_session(
        self,
        *,
        user_id: UUID,
        hub_id: UUID,
    ) -> ReturnSession:
        if self.session.in_transaction():
            return self._start_session(
                user_id=user_id,
                hub_id=hub_id,
            )

        with self.session.begin():
            return self._start_session(
                user_id=user_id,
                hub_id=hub_id,
            )

    def _start_session(
        self,
        *,
        user_id: UUID,
        hub_id: UUID,
    ) -> ReturnSession:
        user = self.user_repository.get_by_id_for_update(
            user_id
        )

        if user is None:
            raise EntityNotFoundError("user not found")

        hub = self.hub_repository.get_by_id(hub_id)

        if hub is None:
            raise EntityNotFoundError("hub not found")

        if hub.status not in self.AVAILABLE_HUB_STATUSES:
            raise InvalidStateError(
                "hub is not available for return sessions"
            )

        existing_session = (
            self.return_session_repository
            .get_latest_open_by_user(user_id)
        )

        if existing_session is not None:
            raise ConflictError(
                "user already has an open return session"
            )

        return self.return_session_repository.add(
            ReturnSession(
                user_id=user.id,
                hub_id=hub.id,
                status=ReturnSessionStatus.OPEN,
                total_accepted=0,
                total_rejected=0,
                total_points=0,
                finished_at=None,
            )
        )

    def complete_session(
        self,
        *,
        session_id: UUID,
    ) -> ReturnSession:
        if self.session.in_transaction():
            return self._complete_session(
                session_id=session_id
            )

        with self.session.begin():
            return self._complete_session(
                session_id=session_id
            )

    def _complete_session(
        self,
        *,
        session_id: UUID,
    ) -> ReturnSession:
        return_session = (
            self.return_session_repository
            .get_by_id_for_update(session_id)
        )

        if return_session is None:
            raise EntityNotFoundError(
                "return session not found"
            )

        if return_session.status != ReturnSessionStatus.OPEN:
            raise InvalidStateError(
                "return session is not open"
            )

        return_session.status = (
            ReturnSessionStatus.COMPLETED
        )
        return_session.finished_at = datetime.now(UTC)

        self.session.flush()

        return return_session

    def cancel_session(
        self,
        *,
        session_id: UUID,
    ) -> ReturnSession:
        if self.session.in_transaction():
            return self._cancel_session(
                session_id=session_id
            )

        with self.session.begin():
            return self._cancel_session(
                session_id=session_id
            )

    def _cancel_session(
        self,
        *,
        session_id: UUID,
    ) -> ReturnSession:
        return_session = (
            self.return_session_repository
            .get_by_id_for_update(session_id)
        )

        if return_session is None:
            raise EntityNotFoundError(
                "return session not found"
            )

        if return_session.status != ReturnSessionStatus.OPEN:
            raise InvalidStateError(
                "return session is not open"
            )

        return_session.status = (
            ReturnSessionStatus.CANCELLED
        )
        return_session.finished_at = datetime.now(UTC)

        self.session.flush()

        return return_session

    def accept_bottle(
        self,
        command: AcceptBottleCommand,
    ) -> BottleTransaction:
        if self.session.in_transaction():
            return (
                self._accept_bottle_with_conflict_mapping(
                    command
                )
            )

        with self.session.begin():
            return (
                self._accept_bottle_with_conflict_mapping(
                    command
                )
            )

    def _accept_bottle_with_conflict_mapping(
        self,
        command: AcceptBottleCommand,
    ) -> BottleTransaction:
        try:
            with self.session.begin_nested():
                return self._accept_bottle(command)
        except IntegrityError as error:
            if self._is_transaction_code_conflict(error):
                raise ConflictError(
                    "transaction code already exists"
                ) from error

            raise

    def reject_bottle(
        self,
        command: RejectBottleCommand,
    ) -> BottleTransaction:
        if self.session.in_transaction():
            return (
                self._reject_bottle_with_conflict_mapping(
                    command
                )
            )

        with self.session.begin():
            return (
                self._reject_bottle_with_conflict_mapping(
                    command
                )
            )

    def _reject_bottle_with_conflict_mapping(
        self,
        command: RejectBottleCommand,
    ) -> BottleTransaction:
        try:
            with self.session.begin_nested():
                return self._reject_bottle(command)
        except IntegrityError as error:
            if self._is_transaction_code_conflict(error):
                raise ConflictError(
                    "transaction code already exists"
                ) from error

            raise

    @classmethod
    def _is_transaction_code_conflict(
        cls,
        error: IntegrityError,
    ) -> bool:
        diagnostic = getattr(
            error.orig,
            "diag",
            None,
        )

        constraint_name = getattr(
            diagnostic,
            "constraint_name",
            None,
        )

        sqlstate = getattr(
            error.orig,
            "sqlstate",
            None,
        )

        return (
            sqlstate == "23505"
            and constraint_name
            == cls.TRANSACTION_CODE_UNIQUE_CONSTRAINT
        )

    def _accept_bottle(
        self,
        command: AcceptBottleCommand,
    ) -> BottleTransaction:
        return_session = (
            self.return_session_repository
            .get_by_id_for_update(command.session_id)
        )

        if return_session is None:
            raise EntityNotFoundError(
                "return session not found"
            )

        if return_session.status != ReturnSessionStatus.OPEN:
            raise InvalidStateError(
                "return session is not open"
            )

        transaction_code = command.transaction_code.strip()
        verifier_name = command.verifier_name.strip()

        existing_transaction = (
            self.bottle_transaction_repository
            .get_by_code(transaction_code)
        )

        if existing_transaction is not None:
            raise ConflictError(
                "transaction code already exists"
            )

        user = self.user_repository.get_by_id_for_update(
            return_session.user_id
        )

        if user is None:
            raise EntityNotFoundError("user not found")

        hub = self.hub_repository.get_by_id_for_update(
            return_session.hub_id
        )

        if hub is None:
            raise EntityNotFoundError("hub not found")

        if hub.status not in self.AVAILABLE_HUB_STATUSES:
            raise InvalidStateError(
                "hub is not available for bottle returns"
            )

        if (
            command.material_type == MaterialType.PET
            and hub.pet_current >= hub.pet_capacity
        ):
            raise InvalidStateError(
                "hub PET compartment is full"
            )

        if (
            command.material_type == MaterialType.HDPE
            and hub.hdpe_current >= hub.hdpe_capacity
        ):
            raise InvalidStateError(
                "hub HDPE compartment is full"
            )

        batch = (
            self.material_batch_repository
            .get_by_id_for_update(command.batch_id)
        )

        if batch is None:
            raise EntityNotFoundError(
                "material batch not found"
            )

        if batch.hub_id != return_session.hub_id:
            raise InvalidStateError(
                "material batch belongs to another hub"
            )

        if batch.status != MaterialBatchStatus.STORING:
            raise InvalidStateError(
                "material batch is not storing bottles"
            )

        if (
            command.material_type
            not in self.SUPPORTED_MATERIAL_TYPES
        ):
            raise InvalidStateError(
                "unsupported material type"
            )

        if (
            command.verified_material_type
            != command.material_type
        ):
            raise InvalidStateError(
                "verified material type does not match"
            )

        if batch.material_type != command.material_type:
            raise InvalidStateError(
                "material batch type does not match"
            )

        if (
            command.cleanliness_status
            != CleanlinessStatus.CLEAN
        ):
            raise InvalidStateError(
                "accepted bottle must be clean"
            )

        if command.weight_gram <= 0:
            raise InvalidStateError(
                "accepted bottle weight must be positive"
            )

        if command.points_awarded < 0:
            raise InvalidStateError(
                "awarded points must be non-negative"
            )

        if not transaction_code:
            raise InvalidStateError(
                "transaction code must not be empty"
            )

        if not verifier_name:
            raise InvalidStateError(
                "verifier name must not be empty"
            )

        if command.material_type == MaterialType.PET:
            if hub.pet_current >= hub.pet_capacity:
                raise InvalidStateError(
                    "hub PET compartment is full"
                )

            hub.pet_current += 1

        elif command.material_type == MaterialType.HDPE:
            if hub.hdpe_current >= hub.hdpe_capacity:
                raise InvalidStateError(
                    "hub HDPE compartment is full"
                )

            hub.hdpe_current += 1

        points_awarded = self.reward_policy.points_for_bottle(
            material_type=command.material_type,
            verification_level=command.verification_level,
        )

        if points_awarded < 0:
            raise InvalidStateError(
                "reward policy returned negative points"
            )

        weight_kg = (
            command.weight_gram
            / self.GRAMS_PER_KILOGRAM
        )

        batch.bottle_count += 1
        batch.estimated_weight_kg += weight_kg

        self._update_collection_state(
            hub=hub,
            batch=batch,
            material_type=command.material_type,
        )

        return_session.total_accepted += 1
        return_session.total_points += (
            points_awarded
        )

        new_balance = (
            user.points_balance
            + points_awarded
        )

        user.points_balance = new_balance
        user.total_bottles_returned += 1

        bottle_transaction = (
            self.bottle_transaction_repository.add(
                BottleTransaction(
                    code=transaction_code,
                    session_id=return_session.id,
                    batch_id=batch.id,
                    material_type=command.material_type,
                    verified_material_type=(
                        command.verified_material_type
                    ),
                    status=(
                        BottleTransactionStatus.ACCEPTED
                    ),
                    reject_reason=None,
                    verification_level=(
                        command.verification_level
                    ),
                    cleanliness_status=(
                        command.cleanliness_status
                    ),
                    weight_gram=command.weight_gram,
                    ai_confidence=command.confidence,
                    cleanliness_score=command.cleanliness_score,
                    points_awarded=(
                        points_awarded
                    ),
                )
            )
        )

        self.verification_event_repository.add(
            VerificationEvent(
                transaction_id=bottle_transaction.id,
                verification_level=(
                    command.verification_level
                ),
                result=VerificationResult.PASS,
                verifier_name=verifier_name,
                verifier_version=(
                    command.verifier_version
                ),
                rule_code=command.rule_code,
                input_payload=dict(
                    command.input_payload
                ),
                output_payload=(
                    dict(command.output_payload)
                    if command.output_payload is not None
                    else None
                ),
                confidence=command.confidence,
                processing_time_ms=(
                    command.processing_time_ms
                ),
                failure_reason=None,
            )
        )

        if points_awarded > 0:
            self.point_ledger_repository.add(
                PointLedger(
                    user_id=user.id,
                    source_type=(
                        PointSourceType.BOTTLE_RETURN
                    ),
                    source_id=bottle_transaction.id,
                    points_change=(
                        points_awarded
                    ),
                    balance_after=new_balance,
                    description=(
                        "Accepted bottle return"
                    ),
                )
            )

        self.session.flush()

        return bottle_transaction

    def _reject_bottle(
        self,
        command: RejectBottleCommand,
    ) -> BottleTransaction:
        return_session = (
            self.return_session_repository
            .get_by_id_for_update(command.session_id)
        )

        if return_session is None:
            raise EntityNotFoundError(
                "return session not found"
            )

        if return_session.status != ReturnSessionStatus.OPEN:
            raise InvalidStateError(
                "return session is not open"
            )

        transaction_code = command.transaction_code.strip()
        verifier_name = command.verifier_name.strip()

        existing_transaction = (
            self.bottle_transaction_repository
            .get_by_code(transaction_code)
        )

        if existing_transaction is not None:
            raise ConflictError(
                "transaction code already exists"
            )

        if not transaction_code:
            raise InvalidStateError(
                "transaction code must not be empty"
            )

        if not verifier_name:
            raise InvalidStateError(
                "verifier name must not be empty"
            )

        if (
            command.weight_gram is not None
            and command.weight_gram < 0
        ):
            raise InvalidStateError(
                "rejected bottle weight must be non-negative"
            )

        return_session.total_rejected += 1

        bottle_transaction = (
            self.bottle_transaction_repository.add(
                BottleTransaction(
                    code=transaction_code,
                    session_id=return_session.id,
                    batch_id=None,
                    material_type=command.material_type,
                    verified_material_type=(
                        command.verified_material_type
                    ),
                    status=(
                        BottleTransactionStatus.REJECTED
                    ),
                    reject_reason=command.reject_reason,
                    verification_level=(
                        command.verification_level
                    ),
                    cleanliness_status=(
                        command.cleanliness_status
                    ),
                    weight_gram=command.weight_gram,
                    ai_confidence=command.confidence,
                    cleanliness_score=command.cleanliness_score,
                    points_awarded=0,
                )
            )
        )

        failure_reason = (
            command.failure_reason
            if command.failure_reason is not None
            else command.reject_reason.value
        )

        self.verification_event_repository.add(
            VerificationEvent(
                transaction_id=bottle_transaction.id,
                verification_level=(
                    command.verification_level
                ),
                result=VerificationResult.FAIL,
                verifier_name=verifier_name,
                verifier_version=(
                    command.verifier_version
                ),
                rule_code=command.rule_code,
                input_payload=dict(
                    command.input_payload
                ),
                output_payload=(
                    dict(command.output_payload)
                    if command.output_payload is not None
                    else None
                ),
                confidence=command.confidence,
                processing_time_ms=(
                    command.processing_time_ms
                ),
                failure_reason=failure_reason,
            )
        )

        self.session.flush()

        return bottle_transaction

    @staticmethod
    def _update_collection_state(
        *,
        hub: Hub,
        batch: MaterialBatch,
        material_type: MaterialType,
    ) -> None:
        if material_type == MaterialType.PET:
            current = hub.pet_current
            capacity = hub.pet_capacity
        else:
            current = hub.hdpe_current
            capacity = hub.hdpe_capacity

        threshold_reached = (
            current * 100
            >= capacity * hub.pickup_threshold_percent
        )

        if threshold_reached:
            batch.status = MaterialBatchStatus.READY_FOR_PICKUP

        both_full = (
            hub.pet_current >= hub.pet_capacity
            and hub.hdpe_current >= hub.hdpe_capacity
        )
        any_threshold_reached = (
            hub.pet_current * 100
            >= hub.pet_capacity * hub.pickup_threshold_percent
            or hub.hdpe_current * 100
            >= hub.hdpe_capacity * hub.pickup_threshold_percent
        )

        if both_full:
            hub.status = HubStatus.FULL
        elif any_threshold_reached:
            hub.status = HubStatus.NEAR_FULL
        else:
            hub.status = HubStatus.ACTIVE
