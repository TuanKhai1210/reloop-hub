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
    CleanlinessStatus,
    Hub,
    HubStatus,
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
    PointLedger,
    ReturnSession,
    User,
    UserRole,
    VerificationEvent,
    VerificationLevel,
)
from app.repositories import (
    BottleTransactionRepository,
    HubRepository,
    MaterialBatchRepository,
    UserRepository,
)
from app.services import (
    AcceptBottleCommand,
    ConflictError,
    ReturnService,
)


pytestmark = pytest.mark.integration


def create_return_context(
    session: Session,
    *,
    token: str,
    index: int,
) -> tuple[UUID, UUID, UUID, UUID]:
    suffix = f"{token[:10]}-{index}"

    user = UserRepository(session).add(
        User(
            name=f"Concurrency User {index}",
            phone=None,
            student_code=f"RACE-{suffix}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )

    hub = HubRepository(session).add(
        Hub(
            code=f"RACE-HUB-{suffix}",
            name=f"Concurrency Hub {index}",
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

    batch = MaterialBatchRepository(session).add(
        MaterialBatch(
            code=f"RACE-BATCH-{suffix}",
            hub_id=hub.id,
            pickup_id=None,
            material_type=MaterialType.PET,
            bottle_count=0,
            estimated_weight_kg=Decimal("0"),
            status=MaterialBatchStatus.STORING,
        )
    )

    return_session = ReturnService(
        session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    return (
        user.id,
        hub.id,
        batch.id,
        return_session.id,
    )


def test_concurrent_duplicate_transaction_code_returns_conflict(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()
    transaction_code = f"RACE-TX-{token}"

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
                    (
                        user_id,
                        hub_id,
                        batch_id,
                        return_session_id,
                    ) = create_return_context(
                        setup_session,
                        token=token,
                        index=index,
                    )

                    user_ids.append(user_id)
                    hub_ids.append(hub_id)
                    batch_ids.append(batch_id)
                    return_session_ids.append(
                        return_session_id
                    )

        commands = [
            AcceptBottleCommand(
                session_id=return_session_ids[index],
                batch_id=batch_ids[index],
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
                        VerificationEvent.transaction_id.in_(
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
            assert len(stored_verifications) == 1
            assert len(stored_ledgers) == 1

            assert sum(
                user.points_balance
                for user in stored_users
            ) == 10

            assert sum(
                user.total_bottles_returned
                for user in stored_users
            ) == 1

            assert sum(
                hub.pet_current
                for hub in stored_hubs
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
        with Session(
            bind=database_engine
        ) as cleanup_session:
            with cleanup_session.begin():
                transaction_ids = list(
                    cleanup_session.scalars(
                        select(BottleTransaction.id).where(
                            BottleTransaction.code
                            == transaction_code
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

                if return_session_ids:
                    cleanup_session.execute(
                        delete(ReturnSession).where(
                            ReturnSession.id.in_(
                                return_session_ids
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
