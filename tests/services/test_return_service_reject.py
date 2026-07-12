from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import (
    BottleTransactionStatus,
    CleanlinessStatus,
    Hub,
    HubStatus,
    MaterialType,
    PointSourceType,
    RejectReason,
    ReturnSessionStatus,
    User,
    UserRole,
    VerificationLevel,
    VerificationResult,
)
from app.repositories import (
    BottleTransactionRepository,
    HubRepository,
    PointLedgerRepository,
    ReturnSessionRepository,
    UserRepository,
    VerificationEventRepository,
)
from app.services import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
    RejectBottleCommand,
    ReturnService,
)


pytestmark = pytest.mark.integration


def create_user(db_session: Session) -> User:
    token = uuid4().hex[:12].upper()

    return UserRepository(db_session).add(
        User(
            name="Reject Bottle Test User",
            phone=None,
            student_code=f"REJECT-{token}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )


def create_hub(db_session: Session) -> Hub:
    token = uuid4().hex[:12].upper()

    return HubRepository(db_session).add(
        Hub(
            code=f"REJECT-HUB-{token}",
            name="Reject Bottle Test Hub",
            location_name="Test Canteen",
            latitude=None,
            longitude=None,
            status=HubStatus.ACTIVE,
            pet_capacity=50,
            hdpe_capacity=30,
            pet_current=0,
            hdpe_current=0,
            pickup_threshold_percent=80,
        )
    )


def test_reject_bottle_records_rejection_without_rewards(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    command = RejectBottleCommand(
        session_id=return_session.id,
        transaction_code=(
            f"REJECT-TX-{uuid4().hex.upper()}"
        ),
        material_type=MaterialType.UNKNOWN,
        reject_reason=RejectReason.UNSUPPORTED_MATERIAL,
        verification_level=VerificationLevel.LEVEL_2,
        verifier_name="sensor_rule_engine",
        verified_material_type=MaterialType.UNKNOWN,
        cleanliness_status=CleanlinessStatus.UNKNOWN,
        weight_gram=None,
        verifier_version="1.0.0",
        rule_code="UNSUPPORTED_MATERIAL",
        input_payload={
            "selected_slot": "PET",
            "detected_material": "UNKNOWN",
        },
        output_payload={
            "accepted": False,
            "reason": "UNSUPPORTED_MATERIAL",
        },
        confidence=Decimal("0.4200"),
        processing_time_ms=11,
        failure_reason="unsupported material",
    )

    created_transaction = ReturnService(
        db_session
    ).reject_bottle(command)

    transaction_id = created_transaction.id

    db_session.flush()
    db_session.expire_all()

    stored_user = UserRepository(
        db_session
    ).get_by_id(user.id)

    stored_hub = HubRepository(
        db_session
    ).get_by_id(hub.id)

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(return_session.id)

    stored_transaction = BottleTransactionRepository(
        db_session
    ).get_by_code(command.transaction_code)

    stored_verification = VerificationEventRepository(
        db_session
    ).get_latest_by_transaction(transaction_id)

    stored_ledger = PointLedgerRepository(
        db_session
    ).get_by_source(
        PointSourceType.BOTTLE_RETURN,
        transaction_id,
    )

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_hub is not None
    assert stored_hub.pet_current == 0
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.OPEN
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 1
    assert stored_session.total_points == 0

    assert stored_transaction is not None
    assert stored_transaction.id == transaction_id
    assert (
        stored_transaction.status
        == BottleTransactionStatus.REJECTED
    )
    assert stored_transaction.batch_id is None
    assert (
        stored_transaction.material_type
        == MaterialType.UNKNOWN
    )
    assert (
        stored_transaction.verified_material_type
        == MaterialType.UNKNOWN
    )
    assert (
        stored_transaction.reject_reason
        == RejectReason.UNSUPPORTED_MATERIAL
    )
    assert stored_transaction.points_awarded == 0
    assert stored_transaction.weight_gram is None

    assert stored_verification is not None
    assert (
        stored_verification.result
        == VerificationResult.FAIL
    )
    assert (
        stored_verification.failure_reason
        == "unsupported material"
    )
    assert stored_verification.output_payload == {
        "accepted": False,
        "reason": "UNSUPPORTED_MATERIAL",
    }

    assert stored_ledger is None


@pytest.mark.parametrize(
    "closed_status",
    [
        ReturnSessionStatus.COMPLETED,
        ReturnSessionStatus.CANCELLED,
    ],
)
def test_reject_bottle_rejects_closed_session_without_changes(
    db_session: Session,
    closed_status: ReturnSessionStatus,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    return_session.status = closed_status
    return_session.finished_at = datetime.now(UTC)
    db_session.flush()

    command = RejectBottleCommand(
        session_id=return_session.id,
        transaction_code=(
            f"CLOSED-REJECT-TX-{uuid4().hex.upper()}"
        ),
        material_type=MaterialType.UNKNOWN,
        reject_reason=RejectReason.UNSUPPORTED_MATERIAL,
        verification_level=VerificationLevel.LEVEL_2,
        verifier_name="sensor_rule_engine",
        verified_material_type=MaterialType.UNKNOWN,
        cleanliness_status=CleanlinessStatus.UNKNOWN,
    )

    with pytest.raises(
        InvalidStateError,
        match="return session is not open",
    ):
        ReturnService(db_session).reject_bottle(command)

    db_session.expire_all()

    stored_user = UserRepository(
        db_session
    ).get_by_id(user.id)

    stored_hub = HubRepository(
        db_session
    ).get_by_id(hub.id)

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(return_session.id)

    stored_transactions = (
        BottleTransactionRepository(db_session)
        .list_by_session(return_session.id)
    )

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_hub is not None
    assert stored_hub.pet_current == 0
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == closed_status
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 0

    assert stored_transactions == []


@pytest.mark.parametrize(
    "command_overrides,expected_message",
    [
        (
            {
                "transaction_code": "   ",
            },
            "transaction code must not be empty",
        ),
        (
            {
                "verifier_name": "   ",
            },
            "verifier name must not be empty",
        ),
        (
            {
                "weight_gram": Decimal("-1.00"),
            },
            "rejected bottle weight must be non-negative",
        ),
    ],
)
def test_reject_bottle_rejects_invalid_metadata_without_changes(
    db_session: Session,
    command_overrides: dict[str, object],
    expected_message: str,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    command_data = {
        "session_id": return_session.id,
        "transaction_code": (
            f"INVALID-REJECT-TX-{uuid4().hex.upper()}"
        ),
        "material_type": MaterialType.UNKNOWN,
        "reject_reason": RejectReason.UNSUPPORTED_MATERIAL,
        "verification_level": VerificationLevel.LEVEL_2,
        "verifier_name": "sensor_rule_engine",
        "verified_material_type": MaterialType.UNKNOWN,
        "cleanliness_status": CleanlinessStatus.UNKNOWN,
        "weight_gram": None,
    }

    command_data.update(command_overrides)

    command = RejectBottleCommand(**command_data)

    with pytest.raises(
        InvalidStateError,
        match=expected_message,
    ):
        ReturnService(db_session).reject_bottle(command)

    db_session.expire_all()

    stored_user = UserRepository(
        db_session
    ).get_by_id(user.id)

    stored_hub = HubRepository(
        db_session
    ).get_by_id(hub.id)

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(return_session.id)

    stored_transactions = (
        BottleTransactionRepository(db_session)
        .list_by_session(return_session.id)
    )

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_hub is not None
    assert stored_hub.pet_current == 0
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.OPEN
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 0

    assert stored_transactions == []


def test_reject_bottle_rejects_duplicate_transaction_code(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    transaction_code = (
        f"DUPLICATE-REJECT-TX-{uuid4().hex.upper()}"
    )

    first_command = RejectBottleCommand(
        session_id=return_session.id,
        transaction_code=transaction_code,
        material_type=MaterialType.UNKNOWN,
        reject_reason=RejectReason.UNSUPPORTED_MATERIAL,
        verification_level=VerificationLevel.LEVEL_2,
        verifier_name="sensor_rule_engine",
        verified_material_type=MaterialType.UNKNOWN,
        cleanliness_status=CleanlinessStatus.UNKNOWN,
        failure_reason="unsupported material",
    )

    service = ReturnService(db_session)

    first_transaction = service.reject_bottle(
        first_command
    )

    duplicate_command = RejectBottleCommand(
        session_id=return_session.id,
        transaction_code=transaction_code,
        material_type=MaterialType.PET,
        reject_reason=RejectReason.DIRTY_BOTTLE,
        verification_level=VerificationLevel.LEVEL_3,
        verifier_name="duplicate_verifier",
        verified_material_type=MaterialType.PET,
        cleanliness_status=CleanlinessStatus.DIRTY,
        weight_gram=Decimal("30.00"),
        failure_reason="duplicate request",
    )

    with pytest.raises(
        ConflictError,
        match="transaction code already exists",
    ):
        service.reject_bottle(duplicate_command)

    db_session.expire_all()

    stored_user = UserRepository(
        db_session
    ).get_by_id(user.id)

    stored_hub = HubRepository(
        db_session
    ).get_by_id(hub.id)

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(return_session.id)

    stored_transactions = (
        BottleTransactionRepository(db_session)
        .list_by_session(return_session.id)
    )

    stored_verification = VerificationEventRepository(
        db_session
    ).get_latest_by_transaction(
        first_transaction.id
    )

    stored_ledger = PointLedgerRepository(
        db_session
    ).get_by_source(
        PointSourceType.BOTTLE_RETURN,
        first_transaction.id,
    )

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_hub is not None
    assert stored_hub.pet_current == 0
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.OPEN
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 1
    assert stored_session.total_points == 0

    assert len(stored_transactions) == 1
    assert stored_transactions[0].id == first_transaction.id
    assert (
        stored_transactions[0].status
        == BottleTransactionStatus.REJECTED
    )
    assert (
        stored_transactions[0].reject_reason
        == RejectReason.UNSUPPORTED_MATERIAL
    )
    assert stored_transactions[0].points_awarded == 0

    assert stored_verification is not None
    assert (
        stored_verification.result
        == VerificationResult.FAIL
    )
    assert (
        stored_verification.failure_reason
        == "unsupported material"
    )

    assert stored_ledger is None


def test_reject_bottle_rejects_unknown_session_without_changes(
    db_session: Session,
) -> None:
    transaction_code = (
        f"UNKNOWN-REJECT-SESSION-{uuid4().hex.upper()}"
    )

    command = RejectBottleCommand(
        session_id=uuid4(),
        transaction_code=transaction_code,
        material_type=MaterialType.UNKNOWN,
        reject_reason=RejectReason.UNSUPPORTED_MATERIAL,
        verification_level=VerificationLevel.LEVEL_2,
        verifier_name="sensor_rule_engine",
        verified_material_type=MaterialType.UNKNOWN,
        cleanliness_status=CleanlinessStatus.UNKNOWN,
    )

    with pytest.raises(
        EntityNotFoundError,
        match="return session not found",
    ):
        ReturnService(db_session).reject_bottle(command)

    stored_transaction = BottleTransactionRepository(
        db_session
    ).get_by_code(transaction_code)

    assert stored_transaction is None
