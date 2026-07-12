from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
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
    RejectReason,
    ReturnSession,
    ReturnSessionStatus,
    User,
    UserRole,
    VerificationEvent,
    VerificationLevel,
    VerificationResult,
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
    ConflictError,
    InvalidStateError,
    RejectBottleCommand,
    ReturnService,
)


pytestmark = pytest.mark.integration


def create_user(
    session: Session,
    *,
    token: str,
    index: int,
) -> User:
    return UserRepository(session).add(
        User(
            name=f"Hardening User {index}",
            phone=None,
            student_code=(
                f"HARD-{token[:8]}-{index}"
            ),
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )


def create_hub(
    session: Session,
    *,
    token: str,
    index: int,
    pet_capacity: int = 50,
) -> Hub:
    return HubRepository(session).add(
        Hub(
            code=f"HARD-HUB-{token[:8]}-{index}",
            name=f"Hardening Hub {index}",
            location_name="Test Canteen",
            latitude=None,
            longitude=None,
            status=HubStatus.ACTIVE,
            pet_capacity=pet_capacity,
            hdpe_capacity=30,
            pet_current=0,
            hdpe_current=0,
            pickup_threshold_percent=80,
        )
    )


def create_batch(
    session: Session,
    *,
    hub_id: UUID,
    token: str,
    index: int,
) -> MaterialBatch:
    return MaterialBatchRepository(session).add(
        MaterialBatch(
            code=f"HARD-BATCH-{token[:8]}-{index}",
            hub_id=hub_id,
            pickup_id=None,
            material_type=MaterialType.PET,
            bottle_count=0,
            estimated_weight_kg=Decimal("0"),
            status=MaterialBatchStatus.STORING,
        )
    )


def create_context(
    session: Session,
    *,
    hub: Hub,
    token: str,
    index: int,
) -> tuple[UUID, UUID, UUID]:
    user = create_user(
        session,
        token=token,
        index=index,
    )

    batch = create_batch(
        session,
        hub_id=hub.id,
        token=token,
        index=index,
    )

    return_session = ReturnService(
        session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    return (
        user.id,
        batch.id,
        return_session.id,
    )


def cleanup_return_data(
    database_engine: Engine,
    *,
    transaction_codes: list[str],
    session_ids: list[UUID],
    batch_ids: list[UUID],
    user_ids: list[UUID],
    hub_ids: list[UUID],
) -> None:
    with Session(
        bind=database_engine
    ) as cleanup_session:
        with cleanup_session.begin():
            transaction_ids = list(
                cleanup_session.scalars(
                    select(BottleTransaction.id).where(
                        BottleTransaction.code.in_(
                            transaction_codes
                        )
                    )
                )
            )

            if transaction_ids:
                cleanup_session.execute(
                    delete(VerificationEvent).where(
                        VerificationEvent
                        .transaction_id.in_(
                            transaction_ids
                        )
                    )
                )

                cleanup_session.execute(
                    delete(PointLedger).where(
                        PointLedger.source_id.in_(
                            transaction_ids
                        )
                    )
                )

                cleanup_session.execute(
                    delete(BottleTransaction).where(
                        BottleTransaction.id.in_(
                            transaction_ids
                        )
                    )
                )

            if session_ids:
                cleanup_session.execute(
                    delete(ReturnSession).where(
                        ReturnSession.id.in_(
                            session_ids
                        )
                    )
                )

            if batch_ids:
                cleanup_session.execute(
                    delete(MaterialBatch).where(
                        MaterialBatch.id.in_(
                            batch_ids
                        )
                    )
                )

            if user_ids:
                cleanup_session.execute(
                    delete(User).where(
                        User.id.in_(user_ids)
                    )
                )

            if hub_ids:
                cleanup_session.execute(
                    delete(Hub).where(
                        Hub.id.in_(hub_ids)
                    )
                )


def test_concurrent_accepts_do_not_exceed_hub_capacity(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()

    transaction_codes = [
        f"CAPACITY-RACE-{token}-{index}"
        for index in range(2)
    ]

    user_ids: list[UUID] = []
    batch_ids: list[UUID] = []
    return_session_ids: list[UUID] = []
    hub_ids: list[UUID] = []

    try:
        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as setup_session:
            with setup_session.begin():
                hub = create_hub(
                    setup_session,
                    token=token,
                    index=0,
                    pet_capacity=1,
                )

                hub_id = hub.id
                hub_ids.append(hub_id)

                for index in range(2):
                    (
                        user_id,
                        batch_id,
                        return_session_id,
                    ) = create_context(
                        setup_session,
                        hub=hub,
                        token=token,
                        index=index,
                    )

                    user_ids.append(user_id)
                    batch_ids.append(batch_id)
                    return_session_ids.append(
                        return_session_id
                    )

        commands = [
            AcceptBottleCommand(
                session_id=return_session_ids[index],
                batch_id=batch_ids[index],
                transaction_code=(
                    transaction_codes[index]
                ),
                material_type=MaterialType.PET,
                verified_material_type=(
                    MaterialType.PET
                ),
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
            for index in range(2)
        ]

        lock_barrier = Barrier(2)

        original_hub_lock = (
            HubRepository.get_by_id_for_update
        )

        def synchronized_hub_lock(
            repository: HubRepository,
            record_id: UUID,
        ) -> Hub | None:
            if record_id == hub_id:
                lock_barrier.wait(timeout=10)

            return original_hub_lock(
                repository,
                record_id,
            )

        monkeypatch.setattr(
            HubRepository,
            "get_by_id_for_update",
            synchronized_hub_lock,
        )

        def run_accept(
            command: AcceptBottleCommand,
        ) -> str:
            with Session(
                bind=database_engine,
                expire_on_commit=False,
            ) as worker_session:
                try:
                    ReturnService(
                        worker_session
                    ).accept_bottle(command)
                except InvalidStateError as error:
                    if (
                        str(error)
                        == "hub PET compartment is full"
                    ):
                        return "capacity"

                    raise

                return "success"

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    run_accept,
                    command,
                )
                for command in commands
            ]

            statuses = [
                future.result(timeout=20)
                for future in futures
            ]

        assert sorted(statuses) == [
            "capacity",
            "success",
        ]

        with Session(
            bind=database_engine
        ) as verification_session:
            stored_transactions = list(
                verification_session.scalars(
                    select(BottleTransaction).where(
                        BottleTransaction.code.in_(
                            transaction_codes
                        )
                    )
                )
            )

            stored_users = list(
                verification_session.scalars(
                    select(User).where(
                        User.id.in_(user_ids)
                    )
                )
            )

            stored_hub = HubRepository(
                verification_session
            ).get_by_id(hub_id)

            stored_sessions = list(
                verification_session.scalars(
                    select(ReturnSession).where(
                        ReturnSession.id.in_(
                            return_session_ids
                        )
                    )
                )
            )

            stored_batches = list(
                verification_session.scalars(
                    select(MaterialBatch).where(
                        MaterialBatch.id.in_(
                            batch_ids
                        )
                    )
                )
            )

            transaction_ids = [
                transaction.id
                for transaction in stored_transactions
            ]

            stored_verifications = list(
                verification_session.scalars(
                    select(VerificationEvent).where(
                        VerificationEvent
                        .transaction_id.in_(
                            transaction_ids
                        )
                    )
                )
            )

            stored_ledgers = list(
                verification_session.scalars(
                    select(PointLedger).where(
                        PointLedger.source_id.in_(
                            transaction_ids
                        )
                    )
                )
            )

            assert len(stored_transactions) == 1
            assert (
                stored_transactions[0].status
                == BottleTransactionStatus.ACCEPTED
            )

            assert len(stored_verifications) == 1
            assert (
                stored_verifications[0].result
                == VerificationResult.PASS
            )

            assert len(stored_ledgers) == 1

            assert stored_hub is not None
            assert stored_hub.pet_current == 1

            assert sum(
                user.points_balance
                for user in stored_users
            ) == 10

            assert sum(
                user.total_bottles_returned
                for user in stored_users
            ) == 1

            assert sum(
                return_session.total_accepted
                for return_session in stored_sessions
            ) == 1

            assert sum(
                return_session.total_points
                for return_session in stored_sessions
            ) == 10

            assert sum(
                batch.bottle_count
                for batch in stored_batches
            ) == 1

            assert sum(
                (
                    batch.estimated_weight_kg
                    for batch in stored_batches
                ),
                Decimal("0"),
            ) == Decimal("0.025")

    finally:
        cleanup_return_data(
            database_engine,
            transaction_codes=transaction_codes,
            session_ids=return_session_ids,
            batch_ids=batch_ids,
            user_ids=user_ids,
            hub_ids=hub_ids,
        )


def test_concurrent_rejects_with_duplicate_code_return_conflict(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()
    transaction_code = f"REJECT-RACE-{token}"

    user_ids: list[UUID] = []
    hub_ids: list[UUID] = []
    batch_ids: list[UUID] = []
    return_session_ids: list[UUID] = []

    try:
        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as setup_session:
            with setup_session.begin():
                for index in range(2):
                    hub = create_hub(
                        setup_session,
                        token=token,
                        index=index,
                    )

                    (
                        user_id,
                        batch_id,
                        return_session_id,
                    ) = create_context(
                        setup_session,
                        hub=hub,
                        token=token,
                        index=index,
                    )

                    user_ids.append(user_id)
                    hub_ids.append(hub.id)
                    batch_ids.append(batch_id)
                    return_session_ids.append(
                        return_session_id
                    )

        commands = [
            RejectBottleCommand(
                session_id=return_session_ids[index],
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
            for index in range(2)
        ]

        lookup_barrier = Barrier(2)

        original_get_by_code = (
            BottleTransactionRepository.get_by_code
        )

        def synchronized_get_by_code(
            repository: BottleTransactionRepository,
            code: str,
        ) -> BottleTransaction | None:
            transaction = original_get_by_code(
                repository,
                code,
            )

            if code == transaction_code:
                lookup_barrier.wait(timeout=10)

            return transaction

        monkeypatch.setattr(
            BottleTransactionRepository,
            "get_by_code",
            synchronized_get_by_code,
        )

        def run_reject(
            command: RejectBottleCommand,
        ) -> str:
            with Session(
                bind=database_engine,
                expire_on_commit=False,
            ) as worker_session:
                try:
                    ReturnService(
                        worker_session
                    ).reject_bottle(command)
                except ConflictError:
                    return "conflict"
                except IntegrityError:
                    return "integrity_error"

                return "success"

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    run_reject,
                    command,
                )
                for command in commands
            ]

            statuses = [
                future.result(timeout=20)
                for future in futures
            ]

        assert sorted(statuses) == [
            "conflict",
            "success",
        ]

        with Session(
            bind=database_engine
        ) as verification_session:
            stored_transactions = list(
                verification_session.scalars(
                    select(BottleTransaction).where(
                        BottleTransaction.code
                        == transaction_code
                    )
                )
            )

            stored_sessions = list(
                verification_session.scalars(
                    select(ReturnSession).where(
                        ReturnSession.id.in_(
                            return_session_ids
                        )
                    )
                )
            )

            stored_users = list(
                verification_session.scalars(
                    select(User).where(
                        User.id.in_(user_ids)
                    )
                )
            )

            stored_hubs = list(
                verification_session.scalars(
                    select(Hub).where(
                        Hub.id.in_(hub_ids)
                    )
                )
            )

            transaction_ids = [
                transaction.id
                for transaction in stored_transactions
            ]

            stored_verifications = list(
                verification_session.scalars(
                    select(VerificationEvent).where(
                        VerificationEvent
                        .transaction_id.in_(
                            transaction_ids
                        )
                    )
                )
            )

            stored_ledgers = list(
                verification_session.scalars(
                    select(PointLedger).where(
                        PointLedger.source_id.in_(
                            transaction_ids
                        )
                    )
                )
            )

            assert len(stored_transactions) == 1
            assert (
                stored_transactions[0].status
                == BottleTransactionStatus.REJECTED
            )

            assert len(stored_verifications) == 1
            assert (
                stored_verifications[0].result
                == VerificationResult.FAIL
            )

            assert stored_ledgers == []

            assert sum(
                return_session.total_rejected
                for return_session in stored_sessions
            ) == 1

            assert sum(
                user.points_balance
                for user in stored_users
            ) == 0

            assert sum(
                user.total_bottles_returned
                for user in stored_users
            ) == 0

            assert sum(
                hub.pet_current
                for hub in stored_hubs
            ) == 0

    finally:
        cleanup_return_data(
            database_engine,
            transaction_codes=[transaction_code],
            session_ids=return_session_ids,
            batch_ids=batch_ids,
            user_ids=user_ids,
            hub_ids=hub_ids,
        )


def test_accept_and_complete_session_are_serialized(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()
    transaction_code = f"CLOSE-RACE-{token}"

    user_ids: list[UUID] = []
    hub_ids: list[UUID] = []
    batch_ids: list[UUID] = []
    return_session_ids: list[UUID] = []

    try:
        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as setup_session:
            with setup_session.begin():
                hub = create_hub(
                    setup_session,
                    token=token,
                    index=0,
                )

                (
                    user_id,
                    batch_id,
                    return_session_id,
                ) = create_context(
                    setup_session,
                    hub=hub,
                    token=token,
                    index=0,
                )

                user_ids.append(user_id)
                hub_ids.append(hub.id)
                batch_ids.append(batch_id)
                return_session_ids.append(
                    return_session_id
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
            cleanliness_status=CleanlinessStatus.CLEAN,
            weight_gram=Decimal("25.00"),
            points_awarded=10,
            verifier_name="sensor_rule_engine",
        )

        lock_barrier = Barrier(2)

        original_session_lock = (
            ReturnSessionRepository.get_by_id_for_update
        )

        def synchronized_session_lock(
            repository: ReturnSessionRepository,
            record_id: UUID,
        ) -> ReturnSession | None:
            if record_id == return_session_id:
                lock_barrier.wait(timeout=10)

            return original_session_lock(
                repository,
                record_id,
            )

        monkeypatch.setattr(
            ReturnSessionRepository,
            "get_by_id_for_update",
            synchronized_session_lock,
        )

        def run_accept() -> str:
            with Session(
                bind=database_engine,
                expire_on_commit=False,
            ) as worker_session:
                try:
                    ReturnService(
                        worker_session
                    ).accept_bottle(command)
                except InvalidStateError:
                    return "accept_invalid_state"

                return "accept_success"

        def run_complete() -> str:
            with Session(
                bind=database_engine,
                expire_on_commit=False,
            ) as worker_session:
                try:
                    ReturnService(
                        worker_session
                    ).complete_session(
                        session_id=return_session_id
                    )
                except InvalidStateError:
                    return "complete_invalid_state"

                return "complete_success"

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            accept_future = executor.submit(run_accept)
            complete_future = executor.submit(run_complete)

            statuses = [
                accept_future.result(timeout=20),
                complete_future.result(timeout=20),
            ]

        assert "complete_success" in statuses
        assert (
            "accept_success" in statuses
            or "accept_invalid_state" in statuses
        )

        with Session(
            bind=database_engine
        ) as verification_session:
            stored_user = UserRepository(
                verification_session
            ).get_by_id(user_id)

            stored_hub = HubRepository(
                verification_session
            ).get_by_id(hub.id)

            stored_batch = MaterialBatchRepository(
                verification_session
            ).get_by_id(batch_id)

            stored_session = ReturnSessionRepository(
                verification_session
            ).get_by_id(return_session_id)

            stored_transactions = list(
                verification_session.scalars(
                    select(BottleTransaction).where(
                        BottleTransaction.code
                        == transaction_code
                    )
                )
            )

            transaction_ids = [
                transaction.id
                for transaction in stored_transactions
            ]

            stored_verifications = list(
                verification_session.scalars(
                    select(VerificationEvent).where(
                        VerificationEvent
                        .transaction_id.in_(
                            transaction_ids
                        )
                    )
                )
            )

            stored_ledgers = list(
                verification_session.scalars(
                    select(PointLedger).where(
                        PointLedger.source_id.in_(
                            transaction_ids
                        )
                    )
                )
            )

            assert stored_user is not None
            assert stored_hub is not None
            assert stored_batch is not None
            assert stored_session is not None

            assert (
                stored_session.status
                == ReturnSessionStatus.COMPLETED
            )
            assert stored_session.finished_at is not None

            if "accept_success" in statuses:
                assert len(stored_transactions) == 1
                assert len(stored_verifications) == 1
                assert len(stored_ledgers) == 1

                assert stored_user.points_balance == 10
                assert (
                    stored_user.total_bottles_returned
                    == 1
                )

                assert stored_hub.pet_current == 1
                assert stored_batch.bottle_count == 1
                assert (
                    stored_batch.estimated_weight_kg
                    == Decimal("0.025")
                )

                assert stored_session.total_accepted == 1
                assert stored_session.total_points == 10
            else:
                assert stored_transactions == []
                assert stored_verifications == []
                assert stored_ledgers == []

                assert stored_user.points_balance == 0
                assert (
                    stored_user.total_bottles_returned
                    == 0
                )

                assert stored_hub.pet_current == 0
                assert stored_batch.bottle_count == 0
                assert (
                    stored_batch.estimated_weight_kg
                    == Decimal("0.000")
                )

                assert stored_session.total_accepted == 0
                assert stored_session.total_points == 0

    finally:
        cleanup_return_data(
            database_engine,
            transaction_codes=[transaction_code],
            session_ids=return_session_ids,
            batch_ids=batch_ids,
            user_ids=user_ids,
            hub_ids=hub_ids,
        )
