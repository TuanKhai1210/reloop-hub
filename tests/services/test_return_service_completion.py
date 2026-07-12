from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Hub,
    HubStatus,
    ReturnSessionStatus,
    User,
    UserRole,
)
from app.repositories import (
    HubRepository,
    ReturnSessionRepository,
    UserRepository,
)
from app.services import (
    EntityNotFoundError,
    InvalidStateError,
    ReturnService,
)


pytestmark = pytest.mark.integration


def create_user(db_session: Session) -> User:
    token = uuid4().hex[:12].upper()

    return UserRepository(db_session).add(
        User(
            name="Completion Test User",
            phone=None,
            student_code=f"COMPLETE-{token}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )


def create_hub(db_session: Session) -> Hub:
    token = uuid4().hex[:12].upper()

    return HubRepository(db_session).add(
        Hub(
            code=f"COMPLETE-HUB-{token}",
            name="Completion Test Hub",
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


def test_complete_session_marks_finished_and_allows_new_session(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    service = ReturnService(db_session)

    first_session = service.start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    before_completion = datetime.now(UTC)

    with patch.object(
        service.return_session_repository,
        "get_by_id_for_update",
        wraps=(
            service.return_session_repository
            .get_by_id_for_update
        ),
    ) as locked_get:
        completed_session = service.complete_session(
            session_id=first_session.id
        )

    after_completion = datetime.now(UTC)

    locked_get.assert_called_once_with(first_session.id)

    assert (
        completed_session.status
        == ReturnSessionStatus.COMPLETED
    )
    assert completed_session.finished_at is not None

    db_session.expire_all()

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(first_session.id)

    assert stored_session is not None
    assert (
        stored_session.status
        == ReturnSessionStatus.COMPLETED
    )
    assert stored_session.finished_at is not None
    assert stored_session.finished_at.tzinfo is not None
    assert (
        before_completion
        <= stored_session.finished_at
        <= after_completion
    )
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 0

    second_session = service.start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    assert second_session.id != first_session.id
    assert second_session.status == ReturnSessionStatus.OPEN
    assert second_session.finished_at is None

    latest_open_session = ReturnSessionRepository(
        db_session
    ).get_latest_open_by_user(user.id)

    assert latest_open_session is not None
    assert latest_open_session.id == second_session.id


def test_complete_session_rejects_unknown_session(
    db_session: Session,
) -> None:
    with pytest.raises(
        EntityNotFoundError,
        match="return session not found",
    ):
        ReturnService(db_session).complete_session(
            session_id=uuid4()
        )


@pytest.mark.parametrize(
    "terminal_status",
    [
        ReturnSessionStatus.COMPLETED,
        ReturnSessionStatus.CANCELLED,
    ],
)
def test_complete_session_rejects_terminal_session(
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
        service.complete_session(
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
