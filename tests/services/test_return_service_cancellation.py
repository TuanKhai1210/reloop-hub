from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import (
    BottleTransactionStatus,
    CleanlinessStatus,
    Hub,
    HubStatus,
    MaterialType,
    RejectReason,
    ReturnSessionStatus,
    User,
    UserRole,
    VerificationLevel,
)
from app.repositories import (
    BottleTransactionRepository,
    HubRepository,
    ReturnSessionRepository,
    UserRepository,
)
from app.services import (
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
            name="Cancellation Test User",
            phone=None,
            student_code=f"CANCEL-{token}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )


def create_hub(db_session: Session) -> Hub:
    token = uuid4().hex[:12].upper()

    return HubRepository(db_session).add(
        Hub(
            code=f"CANCEL-HUB-{token}",
            name="Cancellation Test Hub",
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


def test_cancel_session_preserves_records_and_allows_new_session(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    service = ReturnService(db_session)

    first_session = service.start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    transaction_code = (
        f"CANCEL-REJECT-TX-{uuid4().hex.upper()}"
    )

    rejected_transaction = service.reject_bottle(
        RejectBottleCommand(
            session_id=first_session.id,
            transaction_code=transaction_code,
            material_type=MaterialType.UNKNOWN,
            reject_reason=(
                RejectReason.UNSUPPORTED_MATERIAL
            ),
            verification_level=(
                VerificationLevel.LEVEL_2
            ),
            verifier_name="sensor_rule_engine",
            verified_material_type=(
                MaterialType.UNKNOWN
            ),
            cleanliness_status=(
                CleanlinessStatus.UNKNOWN
            ),
            failure_reason="unsupported material",
        )
    )

    before_cancellation = datetime.now(UTC)

    with patch.object(
        service.return_session_repository,
        "get_by_id_for_update",
        wraps=(
            service.return_session_repository
            .get_by_id_for_update
        ),
    ) as locked_get:
        cancelled_session = service.cancel_session(
            session_id=first_session.id
        )

    after_cancellation = datetime.now(UTC)

    locked_get.assert_called_once_with(first_session.id)

    assert (
        cancelled_session.status
        == ReturnSessionStatus.CANCELLED
    )
    assert cancelled_session.finished_at is not None

    db_session.expire_all()

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(first_session.id)

    stored_transaction = BottleTransactionRepository(
        db_session
    ).get_by_code(transaction_code)

    assert stored_session is not None
    assert (
        stored_session.status
        == ReturnSessionStatus.CANCELLED
    )
    assert stored_session.finished_at is not None
    assert stored_session.finished_at.tzinfo is not None
    assert (
        before_cancellation
        <= stored_session.finished_at
        <= after_cancellation
    )

    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 1
    assert stored_session.total_points == 0

    assert stored_transaction is not None
    assert stored_transaction.id == rejected_transaction.id
    assert (
        stored_transaction.status
        == BottleTransactionStatus.REJECTED
    )
    assert stored_transaction.points_awarded == 0

    second_session = service.start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    assert second_session.id != first_session.id
    assert second_session.status == ReturnSessionStatus.OPEN
    assert second_session.finished_at is None


def test_cancel_session_rejects_unknown_session(
    db_session: Session,
) -> None:
    with pytest.raises(
        EntityNotFoundError,
        match="return session not found",
    ):
        ReturnService(db_session).cancel_session(
            session_id=uuid4()
        )


@pytest.mark.parametrize(
    "terminal_status",
    [
        ReturnSessionStatus.COMPLETED,
        ReturnSessionStatus.CANCELLED,
    ],
)
def test_cancel_session_rejects_terminal_session(
    db_session: Session,
    terminal_status: ReturnSessionStatus,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    service = ReturnService(db_session)

    return_session = service.start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    original_finished_at = datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
    )

    return_session.status = terminal_status
    return_session.finished_at = original_finished_at

    db_session.flush()

    with pytest.raises(
        InvalidStateError,
        match="return session is not open",
    ):
        service.cancel_session(
            session_id=return_session.id
        )

    db_session.expire_all()

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(return_session.id)

    assert stored_session is not None
    assert stored_session.status == terminal_status
    assert (
        stored_session.finished_at
        == original_finished_at
    )
