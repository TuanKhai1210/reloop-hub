from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import (
    CleanlinessStatus,
    Hub,
    HubStatus,
    MaterialBatch,
    MaterialBatchStatus,
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
    MaterialBatchRepository,
    ReturnSessionRepository,
    UserRepository,
)
from app.services import (
    AcceptBottleCommand,
    RejectBottleCommand,
    ReturnService,
)


pytestmark = pytest.mark.integration


def test_accept_bottle_rolls_back_when_verification_insert_fails(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()
    transaction_code = f"ROLLBACK-TX-{token}"

    with database_engine.connect() as connection:
        outer_transaction = connection.begin()

        try:
            with Session(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as setup_session:
                user = UserRepository(setup_session).add(
                    User(
                        name="Rollback Test User",
                        phone=None,
                        student_code=f"ROLLBACK-{token[:12]}",
                        role=UserRole.USER,
                        points_balance=0,
                        total_bottles_returned=0,
                    )
                )

                hub = HubRepository(setup_session).add(
                    Hub(
                        code=f"ROLLBACK-HUB-{token[:12]}",
                        name="Rollback Test Hub",
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

                batch = MaterialBatchRepository(
                    setup_session
                ).add(
                    MaterialBatch(
                        code=f"ROLLBACK-BATCH-{token[:12]}",
                        hub_id=hub.id,
                        pickup_id=None,
                        material_type=MaterialType.PET,
                        bottle_count=0,
                        estimated_weight_kg=Decimal("0"),
                        status=MaterialBatchStatus.STORING,
                    )
                )

                return_session = ReturnService(
                    setup_session
                ).start_session(
                    user_id=user.id,
                    hub_id=hub.id,
                )

                user_id = user.id
                hub_id = hub.id
                batch_id = batch.id
                return_session_id = return_session.id

                setup_session.commit()

            with Session(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as service_session:
                service = ReturnService(service_session)

                def raise_verification_failure(
                    _event: object,
                ) -> None:
                    raise RuntimeError(
                        "forced verification failure"
                    )

                monkeypatch.setattr(
                    service.verification_event_repository,
                    "add",
                    raise_verification_failure,
                )

                command = AcceptBottleCommand(
                    session_id=return_session_id,
                    batch_id=batch_id,
                    transaction_code=transaction_code,
                    material_type=MaterialType.PET,
                    verified_material_type=MaterialType.PET,
                    verification_level=(
                        VerificationLevel.LEVEL_2
                    ),
                    cleanliness_status=(
                        CleanlinessStatus.CLEAN
                    ),
                    weight_gram=Decimal("25.00"),
                    points_awarded=10,
                    verifier_name="sensor_rule_engine",
                )

                with pytest.raises(
                    RuntimeError,
                    match="forced verification failure",
                ):
                    service.accept_bottle(command)

                assert not service_session.in_transaction()

            with Session(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as verification_session:
                stored_user = UserRepository(
                    verification_session
                ).get_by_id(user_id)

                stored_hub = HubRepository(
                    verification_session
                ).get_by_id(hub_id)

                stored_session = ReturnSessionRepository(
                    verification_session
                ).get_by_id(return_session_id)

                stored_batch = MaterialBatchRepository(
                    verification_session
                ).get_by_id(batch_id)

                stored_transaction = (
                    BottleTransactionRepository(
                        verification_session
                    ).get_by_code(transaction_code)
                )

                assert stored_user is not None
                assert stored_user.points_balance == 0
                assert stored_user.total_bottles_returned == 0

                assert stored_hub is not None
                assert stored_hub.pet_current == 0
                assert stored_hub.hdpe_current == 0

                assert stored_session is not None
                assert (
                    stored_session.status
                    == ReturnSessionStatus.OPEN
                )
                assert stored_session.total_accepted == 0
                assert stored_session.total_rejected == 0
                assert stored_session.total_points == 0

                assert stored_batch is not None
                assert stored_batch.bottle_count == 0
                assert (
                    stored_batch.estimated_weight_kg
                    == Decimal("0.000")
                )

                assert stored_transaction is None

        finally:
            if outer_transaction.is_active:
                outer_transaction.rollback()


def test_reject_bottle_rolls_back_when_verification_insert_fails(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()
    transaction_code = f"REJECT-ROLLBACK-TX-{token}"

    with database_engine.connect() as connection:
        outer_transaction = connection.begin()

        try:
            with Session(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as setup_session:
                user = UserRepository(setup_session).add(
                    User(
                        name="Reject Rollback Test User",
                        phone=None,
                        student_code=(
                            f"REJECT-RB-{token[:12]}"
                        ),
                        role=UserRole.USER,
                        points_balance=0,
                        total_bottles_returned=0,
                    )
                )

                hub = HubRepository(setup_session).add(
                    Hub(
                        code=f"REJECT-RB-HUB-{token[:12]}",
                        name="Reject Rollback Test Hub",
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

                return_session = ReturnService(
                    setup_session
                ).start_session(
                    user_id=user.id,
                    hub_id=hub.id,
                )

                user_id = user.id
                hub_id = hub.id
                return_session_id = return_session.id

                setup_session.commit()

            with Session(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as service_session:
                service = ReturnService(service_session)

                def raise_verification_failure(
                    _event: object,
                ) -> None:
                    raise RuntimeError(
                        "forced reject verification failure"
                    )

                monkeypatch.setattr(
                    service.verification_event_repository,
                    "add",
                    raise_verification_failure,
                )

                command = RejectBottleCommand(
                    session_id=return_session_id,
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

                with pytest.raises(
                    RuntimeError,
                    match=(
                        "forced reject verification failure"
                    ),
                ):
                    service.reject_bottle(command)

                assert not service_session.in_transaction()

            with Session(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as verification_session:
                stored_user = UserRepository(
                    verification_session
                ).get_by_id(user_id)

                stored_hub = HubRepository(
                    verification_session
                ).get_by_id(hub_id)

                stored_session = ReturnSessionRepository(
                    verification_session
                ).get_by_id(return_session_id)

                stored_transaction = (
                    BottleTransactionRepository(
                        verification_session
                    ).get_by_code(transaction_code)
                )

                assert stored_user is not None
                assert stored_user.points_balance == 0
                assert (
                    stored_user.total_bottles_returned
                    == 0
                )

                assert stored_hub is not None
                assert stored_hub.pet_current == 0
                assert stored_hub.hdpe_current == 0

                assert stored_session is not None
                assert (
                    stored_session.status
                    == ReturnSessionStatus.OPEN
                )
                assert stored_session.total_accepted == 0
                assert stored_session.total_rejected == 0
                assert stored_session.total_points == 0

                assert stored_transaction is None

        finally:
            if outer_transaction.is_active:
                outer_transaction.rollback()
