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
