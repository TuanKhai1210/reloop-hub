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
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
    ReturnService,
)


pytestmark = pytest.mark.integration


def create_user(
    db_session: Session,
) -> User:
    token = uuid4().hex[:12].upper()

    return UserRepository(db_session).add(
        User(
            name="Return Service Test User",
            phone=None,
            student_code=f"SERVICE-{token}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )


def create_hub(
    db_session: Session,
    *,
    status: HubStatus = HubStatus.ACTIVE,
) -> Hub:
    token = uuid4().hex[:12].upper()

    return HubRepository(db_session).add(
        Hub(
            code=f"SERVICE-HUB-{token}",
            name="Return Service Test Hub",
            location_name="Test Canteen",
            latitude=None,
            longitude=None,
            status=status,
            pet_capacity=50,
            hdpe_capacity=30,
            pet_current=0,
            hdpe_current=0,
            pickup_threshold_percent=80,
        )
    )


def test_start_session_creates_open_session(
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

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(return_session.id)

    assert stored_session is not None
    assert stored_session.user_id == user.id
    assert stored_session.hub_id == hub.id
    assert stored_session.status == ReturnSessionStatus.OPEN
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 0
    assert stored_session.finished_at is None


def test_start_session_rejects_duplicate_open_session(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    service = ReturnService(db_session)

    first_session = service.start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    with pytest.raises(
        ConflictError,
        match="already has an open return session",
    ):
        service.start_session(
            user_id=user.id,
            hub_id=hub.id,
        )

    sessions = ReturnSessionRepository(
        db_session
    ).list_by_user(
        user.id,
        status=ReturnSessionStatus.OPEN,
    )

    assert len(sessions) == 1
    assert sessions[0].id == first_session.id


@pytest.mark.parametrize(
    "hub_status",
    [
        HubStatus.FULL,
        HubStatus.MAINTENANCE,
        HubStatus.OFFLINE,
    ],
)
def test_start_session_rejects_unavailable_hub(
    db_session: Session,
    hub_status: HubStatus,
) -> None:
    user = create_user(db_session)
    hub = create_hub(
        db_session,
        status=hub_status,
    )

    with pytest.raises(
        InvalidStateError,
        match="hub is not available",
    ):
        ReturnService(db_session).start_session(
            user_id=user.id,
            hub_id=hub.id,
        )

    assert (
        ReturnSessionRepository(
            db_session
        ).get_latest_open_by_user(user.id)
        is None
    )


def test_start_session_rejects_unknown_user(
    db_session: Session,
) -> None:
    hub = create_hub(db_session)

    with pytest.raises(
        EntityNotFoundError,
        match="user not found",
    ):
        ReturnService(db_session).start_session(
            user_id=uuid4(),
            hub_id=hub.id,
        )


def test_start_session_rejects_unknown_hub(
    db_session: Session,
) -> None:
    user = create_user(db_session)

    with pytest.raises(
        EntityNotFoundError,
        match="hub not found",
    ):
        ReturnService(db_session).start_session(
            user_id=user.id,
            hub_id=uuid4(),
        )
