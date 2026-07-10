from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import Hub, HubStatus, User, UserRole
pytestmark = pytest.mark.integration


from app.repositories import (
    BaseRepository,
    HubRepository,
    UserRepository,
)


def test_base_repository_add_get_list_and_delete(
    db_session: Session,
) -> None:
    repository = BaseRepository(db_session, User)
    token = uuid4().hex[:12].upper()

    user = repository.add(
        User(
            name="Base Repository Test User",
            phone=None,
            student_code=f"BASE-{token}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )

    assert user.id is not None
    assert repository.get_by_id(user.id) is not None
    assert any(
        item.id == user.id
        for item in repository.list_all(limit=1000)
    )

    repository.delete(user)

    assert repository.get_by_id(user.id) is None


def test_user_repository_queries(
    db_session: Session,
) -> None:
    repository = UserRepository(db_session)
    token = uuid4().hex[:12].upper()
    phone = f"TEST-{token}"
    student_code = f"STUDENT-{token}"

    user = repository.add(
        User(
            name="User Repository Test",
            phone=phone,
            student_code=student_code,
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )

    phone_result = repository.get_by_phone(phone)
    student_result = repository.get_by_student_code(
        student_code
    )
    users = repository.list_by_role(
        UserRole.USER,
        limit=1000,
    )

    assert phone_result is not None
    assert phone_result.id == user.id
    assert student_result is not None
    assert student_result.id == user.id
    assert any(item.id == user.id for item in users)


def test_hub_repository_queries(
    db_session: Session,
) -> None:
    repository = HubRepository(db_session)
    token = uuid4().hex[:12].upper()
    hub_code = f"TEST-HUB-{token}"

    hub = repository.add(
        Hub(
            code=hub_code,
            name="Repository Test Hub",
            location_name="Test Canteen",
            latitude=None,
            longitude=None,
            status=HubStatus.MAINTENANCE,
            pet_capacity=50,
            hdpe_capacity=30,
            pet_current=0,
            hdpe_current=0,
            pickup_threshold_percent=80,
        )
    )

    code_result = repository.get_by_code(hub_code)
    hubs = repository.list_by_status(
        HubStatus.MAINTENANCE,
        limit=1000,
    )

    assert code_result is not None
    assert code_result.id == hub.id
    assert any(item.id == hub.id for item in hubs)
