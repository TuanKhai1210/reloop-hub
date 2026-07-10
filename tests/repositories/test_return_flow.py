from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
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
    PointLedgerRepository,
    ReturnSessionRepository,
    UserRepository,
    VerificationEventRepository,
)


pytestmark = pytest.mark.integration


def create_test_user_and_hub(
    db_session: Session,
) -> tuple[User, Hub]:
    token = uuid4().hex[:12].upper()

    user = UserRepository(db_session).add(
        User(
            name="Return Flow Test User",
            phone=None,
            student_code=f"FLOW-{token}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )

    hub = HubRepository(db_session).add(
        Hub(
            code=f"FLOW-HUB-{token}",
            name="Return Flow Test Hub",
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

    return user, hub


def create_open_return_session(
    db_session: Session,
    user: User,
    hub: Hub,
) -> ReturnSession:
    return ReturnSessionRepository(db_session).add(
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


def test_accepted_bottle_return_flow(
    db_session: Session,
) -> None:
    user, hub = create_test_user_and_hub(db_session)
    return_session = create_open_return_session(
        db_session,
        user,
        hub,
    )

    token = uuid4().hex[:12].upper()

    batch_repository = MaterialBatchRepository(db_session)
    transaction_repository = BottleTransactionRepository(
        db_session
    )
    verification_repository = VerificationEventRepository(
        db_session
    )
    ledger_repository = PointLedgerRepository(db_session)

    batch = batch_repository.add(
        MaterialBatch(
            code=f"FLOW-BATCH-{token}",
            hub_id=hub.id,
            pickup_id=None,
            material_type=MaterialType.PET,
            bottle_count=0,
            estimated_weight_kg=Decimal("0"),
            status=MaterialBatchStatus.STORING,
        )
    )

    bottle_transaction = transaction_repository.add(
        BottleTransaction(
            code=f"FLOW-TX-{token}",
            session_id=return_session.id,
            batch_id=batch.id,
            material_type=MaterialType.PET,
            verified_material_type=MaterialType.PET,
            status=BottleTransactionStatus.ACCEPTED,
            reject_reason=None,
            verification_level=VerificationLevel.LEVEL_2,
            cleanliness_status=CleanlinessStatus.CLEAN,
            weight_gram=Decimal("25.00"),
            ai_confidence=None,
            points_awarded=10,
        )
    )

    verification_repository.add(
        VerificationEvent(
            transaction_id=bottle_transaction.id,
            verification_level=VerificationLevel.LEVEL_2,
            result=VerificationResult.PASS,
            verifier_name="sensor_rule_engine",
            verifier_version="1.0.0",
            rule_code="PET_CLEAN_WEIGHT_VALID",
            input_payload={
                "selected_slot": "PET",
                "weight_gram": 25.0,
                "clean": True,
            },
            output_payload={
                "accepted": True,
                "material_type": "PET",
            },
            confidence=Decimal("1.0000"),
            processing_time_ms=8,
            failure_reason=None,
        )
    )

    ledger_repository.add(
        PointLedger(
            user_id=user.id,
            source_type=PointSourceType.BOTTLE_RETURN,
            source_id=bottle_transaction.id,
            points_change=10,
            balance_after=10,
            description="Accepted PET bottle return",
        )
    )

    user.points_balance = 10
    user.total_bottles_returned = 1

    hub.pet_current = 1

    batch.bottle_count = 1
    batch.estimated_weight_kg = Decimal("0.025")

    return_session.status = ReturnSessionStatus.COMPLETED
    return_session.total_accepted = 1
    return_session.total_rejected = 0
    return_session.total_points = 10
    return_session.finished_at = datetime.now(timezone.utc)

    db_session.flush()

    user_id = user.id
    hub_id = hub.id
    session_id = return_session.id
    batch_id = batch.id
    transaction_id = bottle_transaction.id
    transaction_code = bottle_transaction.code

    db_session.expire_all()

    stored_user = UserRepository(db_session).get_by_id(user_id)
    stored_hub = HubRepository(db_session).get_by_id(hub_id)
    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(session_id)
    stored_batch = batch_repository.get_by_id(batch_id)
    stored_transaction = transaction_repository.get_by_code(
        transaction_code
    )
    stored_verification = (
        verification_repository.get_latest_by_transaction(
            transaction_id
        )
    )
    stored_ledger = ledger_repository.get_by_source(
        PointSourceType.BOTTLE_RETURN,
        transaction_id,
    )

    accepted_transactions = (
        transaction_repository.list_by_session(
            session_id,
            status=BottleTransactionStatus.ACCEPTED,
        )
    )

    assert stored_user is not None
    assert stored_user.points_balance == 10
    assert stored_user.total_bottles_returned == 1

    assert stored_hub is not None
    assert stored_hub.pet_current == 1
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.COMPLETED
    assert stored_session.total_accepted == 1
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 10
    assert stored_session.finished_at is not None

    assert stored_batch is not None
    assert stored_batch.material_type == MaterialType.PET
    assert stored_batch.bottle_count == 1
    assert stored_batch.estimated_weight_kg == Decimal("0.025")
    assert stored_batch.status == MaterialBatchStatus.STORING

    assert stored_transaction is not None
    assert stored_transaction.status == (
        BottleTransactionStatus.ACCEPTED
    )
    assert stored_transaction.batch_id == batch_id
    assert stored_transaction.reject_reason is None
    assert stored_transaction.points_awarded == 10
    assert stored_transaction.weight_gram == Decimal("25.00")

    assert len(accepted_transactions) == 1
    assert accepted_transactions[0].id == transaction_id

    assert stored_verification is not None
    assert stored_verification.result == VerificationResult.PASS
    assert stored_verification.verification_level == (
        VerificationLevel.LEVEL_2
    )
    assert stored_verification.output_payload == {
        "accepted": True,
        "material_type": "PET",
    }
    assert stored_verification.failure_reason is None

    assert stored_ledger is not None
    assert stored_ledger.points_change == 10
    assert stored_ledger.balance_after == 10
    assert stored_ledger.user_id == user_id


def test_rejected_bottle_return_flow(
    db_session: Session,
) -> None:
    user, hub = create_test_user_and_hub(db_session)
    return_session = create_open_return_session(
        db_session,
        user,
        hub,
    )

    token = uuid4().hex[:12].upper()

    transaction_repository = BottleTransactionRepository(
        db_session
    )
    verification_repository = VerificationEventRepository(
        db_session
    )
    ledger_repository = PointLedgerRepository(db_session)

    bottle_transaction = transaction_repository.add(
        BottleTransaction(
            code=f"FLOW-TX-REJECTED-{token}",
            session_id=return_session.id,
            batch_id=None,
            material_type=MaterialType.PET,
            verified_material_type=MaterialType.PET,
            status=BottleTransactionStatus.REJECTED,
            reject_reason=RejectReason.DIRTY_BOTTLE,
            verification_level=VerificationLevel.LEVEL_2,
            cleanliness_status=CleanlinessStatus.DIRTY,
            weight_gram=Decimal("40.00"),
            ai_confidence=None,
            points_awarded=0,
        )
    )

    verification_repository.add(
        VerificationEvent(
            transaction_id=bottle_transaction.id,
            verification_level=VerificationLevel.LEVEL_2,
            result=VerificationResult.FAIL,
            verifier_name="sensor_rule_engine",
            verifier_version="1.0.0",
            rule_code="DIRTY_BOTTLE_REJECTED",
            input_payload={
                "selected_slot": "PET",
                "weight_gram": 40.0,
                "clean": False,
            },
            output_payload={
                "accepted": False,
                "material_type": "PET",
            },
            confidence=Decimal("1.0000"),
            processing_time_ms=6,
            failure_reason="Bottle cleanliness check failed",
        )
    )

    return_session.status = ReturnSessionStatus.COMPLETED
    return_session.total_accepted = 0
    return_session.total_rejected = 1
    return_session.total_points = 0
    return_session.finished_at = datetime.now(timezone.utc)

    db_session.flush()

    user_id = user.id
    hub_id = hub.id
    session_id = return_session.id
    transaction_id = bottle_transaction.id
    transaction_code = bottle_transaction.code

    db_session.expire_all()

    stored_user = UserRepository(db_session).get_by_id(user_id)
    stored_hub = HubRepository(db_session).get_by_id(hub_id)
    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(session_id)
    stored_transaction = transaction_repository.get_by_code(
        transaction_code
    )
    stored_verification = (
        verification_repository.get_latest_by_transaction(
            transaction_id
        )
    )
    stored_ledger = ledger_repository.get_by_source(
        PointSourceType.BOTTLE_RETURN,
        transaction_id,
    )

    rejected_transactions = (
        transaction_repository.list_by_session(
            session_id,
            status=BottleTransactionStatus.REJECTED,
        )
    )

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_hub is not None
    assert stored_hub.pet_current == 0
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.COMPLETED
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 1
    assert stored_session.total_points == 0

    assert stored_transaction is not None
    assert stored_transaction.status == (
        BottleTransactionStatus.REJECTED
    )
    assert stored_transaction.batch_id is None
    assert stored_transaction.reject_reason == (
        RejectReason.DIRTY_BOTTLE
    )
    assert stored_transaction.points_awarded == 0
    assert stored_transaction.cleanliness_status == (
        CleanlinessStatus.DIRTY
    )

    assert len(rejected_transactions) == 1
    assert rejected_transactions[0].id == transaction_id

    assert stored_verification is not None
    assert stored_verification.result == VerificationResult.FAIL
    assert stored_verification.failure_reason == (
        "Bottle cleanliness check failed"
    )
    assert stored_verification.output_payload == {
        "accepted": False,
        "material_type": "PET",
    }

    assert stored_ledger is None
