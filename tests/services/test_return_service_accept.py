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
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
    PointSourceType,
    ReturnSessionStatus,
    User,
    UserRole,
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
from app.services import (
    AcceptBottleCommand,
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
    ReturnService,
)


pytestmark = pytest.mark.integration


def create_user(db_session: Session) -> User:
    token = uuid4().hex[:12].upper()

    return UserRepository(db_session).add(
        User(
            name="Accept Bottle Test User",
            phone=None,
            student_code=f"ACCEPT-{token}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )


def create_hub(db_session: Session) -> Hub:
    token = uuid4().hex[:12].upper()

    return HubRepository(db_session).add(
        Hub(
            code=f"ACCEPT-HUB-{token}",
            name="Accept Bottle Test Hub",
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


def create_batch(
    db_session: Session,
    hub: Hub,
    *,
    material_type: MaterialType = MaterialType.PET,
) -> MaterialBatch:
    token = uuid4().hex[:12].upper()

    return MaterialBatchRepository(db_session).add(
        MaterialBatch(
            code=f"ACCEPT-BATCH-{token}",
            hub_id=hub.id,
            pickup_id=None,
            material_type=material_type,
            bottle_count=0,
            estimated_weight_kg=Decimal("0"),
            status=MaterialBatchStatus.STORING,
        )
    )


def test_accept_bottle_updates_all_return_records(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    batch = create_batch(db_session, hub)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    command = AcceptBottleCommand(
        session_id=return_session.id,
        batch_id=batch.id,
        transaction_code=f"ACCEPT-TX-{uuid4().hex.upper()}",
        material_type=MaterialType.PET,
        verified_material_type=MaterialType.PET,
        verification_level=VerificationLevel.LEVEL_2,
        cleanliness_status=CleanlinessStatus.CLEAN,
        weight_gram=Decimal("25.00"),
        points_awarded=10,
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
    )

    created_transaction = ReturnService(
        db_session
    ).accept_bottle(command)

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

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

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
    assert stored_user.points_balance == 10
    assert stored_user.total_bottles_returned == 1

    assert stored_hub is not None
    assert stored_hub.pet_current == 1
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.OPEN
    assert stored_session.total_accepted == 1
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 10
    assert stored_session.finished_at is None

    assert stored_batch is not None
    assert stored_batch.bottle_count == 1
    assert stored_batch.estimated_weight_kg == Decimal("0.025")
    assert stored_batch.status == MaterialBatchStatus.STORING

    assert stored_transaction is not None
    assert stored_transaction.status == (
        BottleTransactionStatus.ACCEPTED
    )
    assert stored_transaction.session_id == return_session.id
    assert stored_transaction.batch_id == batch.id
    assert stored_transaction.material_type == MaterialType.PET
    assert stored_transaction.verified_material_type == (
        MaterialType.PET
    )
    assert stored_transaction.points_awarded == 10
    assert stored_transaction.weight_gram == Decimal("25.00")

    assert stored_verification is not None
    assert stored_verification.result == VerificationResult.PASS
    assert stored_verification.rule_code == (
        "PET_CLEAN_WEIGHT_VALID"
    )
    assert stored_verification.output_payload == {
        "accepted": True,
        "material_type": "PET",
    }

    assert stored_ledger is not None
    assert stored_ledger.user_id == user.id
    assert stored_ledger.points_change == 10
    assert stored_ledger.balance_after == 10


def test_accept_bottle_uses_server_reward_and_normalizes_metadata(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    hub.pet_capacity = 1
    hub.pickup_threshold_percent = 100
    batch = create_batch(db_session, hub)

    return_session = ReturnService(db_session).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )
    raw_code = f"  NORMALIZED-{uuid4().hex.upper()}  "

    created = ReturnService(db_session).accept_bottle(
        AcceptBottleCommand(
            session_id=return_session.id,
            batch_id=batch.id,
            transaction_code=raw_code,
            material_type=MaterialType.PET,
            verified_material_type=MaterialType.PET,
            verification_level=VerificationLevel.LEVEL_2,
            cleanliness_status=CleanlinessStatus.CLEAN,
            weight_gram=Decimal("25.00"),
            points_awarded=999,
            verifier_name="  sensor_rule_engine  ",
        )
    )

    db_session.expire_all()

    stored_user = UserRepository(db_session).get_by_id(user.id)
    stored_hub = HubRepository(db_session).get_by_id(hub.id)
    stored_batch = MaterialBatchRepository(db_session).get_by_id(
        batch.id
    )
    stored_transaction = BottleTransactionRepository(
        db_session
    ).get_by_id(created.id)
    stored_verification = VerificationEventRepository(
        db_session
    ).get_latest_by_transaction(created.id)

    assert stored_user is not None
    assert stored_user.points_balance == 10
    assert stored_hub is not None
    assert stored_hub.status == HubStatus.NEAR_FULL
    assert stored_batch is not None
    assert stored_batch.status == MaterialBatchStatus.READY_FOR_PICKUP
    assert stored_transaction is not None
    assert stored_transaction.code == raw_code.strip()
    assert stored_transaction.points_awarded == 10
    assert stored_verification is not None
    assert stored_verification.verifier_name == "sensor_rule_engine"


@pytest.mark.parametrize(
    "closed_status",
    [
        ReturnSessionStatus.COMPLETED,
        ReturnSessionStatus.CANCELLED,
    ],
)
def test_accept_bottle_rejects_closed_session_without_changes(
    db_session: Session,
    closed_status: ReturnSessionStatus,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    batch = create_batch(db_session, hub)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    return_session.status = closed_status
    return_session.finished_at = datetime.now(UTC)
    db_session.flush()

    command = AcceptBottleCommand(
        session_id=return_session.id,
        batch_id=batch.id,
        transaction_code=(
            f"CLOSED-TX-{uuid4().hex.upper()}"
        ),
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

    with pytest.raises(
        InvalidStateError,
        match="return session is not open",
    ):
        ReturnService(db_session).accept_bottle(
            command
        )

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

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

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

    assert stored_batch is not None
    assert stored_batch.bottle_count == 0
    assert stored_batch.estimated_weight_kg == Decimal("0.000")

    assert stored_transactions == []


@pytest.mark.parametrize(
    "invalid_batch_case,expected_message",
    [
        (
            "different_hub",
            "material batch belongs to another hub",
        ),
        (
            "not_storing",
            "material batch is not storing bottles",
        ),
    ],
)
def test_accept_bottle_rejects_invalid_batch_without_changes(
    db_session: Session,
    invalid_batch_case: str,
    expected_message: str,
) -> None:
    user = create_user(db_session)
    session_hub = create_hub(db_session)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=session_hub.id,
    )

    if invalid_batch_case == "different_hub":
        batch_hub = create_hub(db_session)
        batch = create_batch(db_session, batch_hub)
    else:
        batch = create_batch(db_session, session_hub)
        batch.status = MaterialBatchStatus.READY_FOR_PICKUP
        db_session.flush()

    command = AcceptBottleCommand(
        session_id=return_session.id,
        batch_id=batch.id,
        transaction_code=(
            f"INVALID-BATCH-TX-{uuid4().hex.upper()}"
        ),
        material_type=MaterialType.PET,
        verified_material_type=MaterialType.PET,
        verification_level=VerificationLevel.LEVEL_2,
        cleanliness_status=CleanlinessStatus.CLEAN,
        weight_gram=Decimal("25.00"),
        points_awarded=10,
        verifier_name="sensor_rule_engine",
    )

    with pytest.raises(
        InvalidStateError,
        match=expected_message,
    ):
        ReturnService(db_session).accept_bottle(command)

    db_session.expire_all()

    stored_user = UserRepository(
        db_session
    ).get_by_id(user.id)

    stored_session_hub = HubRepository(
        db_session
    ).get_by_id(session_hub.id)

    stored_session = ReturnSessionRepository(
        db_session
    ).get_by_id(return_session.id)

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

    stored_transactions = (
        BottleTransactionRepository(db_session)
        .list_by_session(return_session.id)
    )

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_session_hub is not None
    assert stored_session_hub.pet_current == 0
    assert stored_session_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.OPEN
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 0

    assert stored_batch is not None
    assert stored_batch.bottle_count == 0
    assert stored_batch.estimated_weight_kg == Decimal("0.000")

    assert stored_transactions == []


@pytest.mark.parametrize(
    "command_overrides,expected_message",
    [
        (
            {
                "material_type": MaterialType.UNKNOWN,
                "verified_material_type": MaterialType.UNKNOWN,
            },
            "unsupported material type",
        ),
        (
            {
                "verified_material_type": MaterialType.HDPE,
            },
            "verified material type does not match",
        ),
        (
            {
                "material_type": MaterialType.HDPE,
                "verified_material_type": MaterialType.HDPE,
            },
            "material batch type does not match",
        ),
        (
            {
                "cleanliness_status": CleanlinessStatus.DIRTY,
            },
            "accepted bottle must be clean",
        ),
        (
            {
                "weight_gram": Decimal("0"),
            },
            "accepted bottle weight must be positive",
        ),
        (
            {
                "weight_gram": Decimal("-1.00"),
            },
            "accepted bottle weight must be positive",
        ),
    ],
)
def test_accept_bottle_rejects_invalid_bottle_without_changes(
    db_session: Session,
    command_overrides: dict[str, object],
    expected_message: str,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    batch = create_batch(db_session, hub)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    command_data = {
        "session_id": return_session.id,
        "batch_id": batch.id,
        "transaction_code": (
            f"INVALID-BOTTLE-TX-{uuid4().hex.upper()}"
        ),
        "material_type": MaterialType.PET,
        "verified_material_type": MaterialType.PET,
        "verification_level": VerificationLevel.LEVEL_2,
        "cleanliness_status": CleanlinessStatus.CLEAN,
        "weight_gram": Decimal("25.00"),
        "points_awarded": 10,
        "verifier_name": "sensor_rule_engine",
    }

    command_data.update(command_overrides)

    command = AcceptBottleCommand(**command_data)

    with pytest.raises(
        InvalidStateError,
        match=expected_message,
    ):
        ReturnService(db_session).accept_bottle(command)

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

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

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

    assert stored_batch is not None
    assert stored_batch.bottle_count == 0
    assert stored_batch.estimated_weight_kg == Decimal("0.000")

    assert stored_transactions == []


@pytest.mark.parametrize(
    "material_type,expected_message",
    [
        (
            MaterialType.PET,
            "hub PET compartment is full",
        ),
        (
            MaterialType.HDPE,
            "hub HDPE compartment is full",
        ),
    ],
)
def test_accept_bottle_rejects_full_compartment_without_changes(
    db_session: Session,
    material_type: MaterialType,
    expected_message: str,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)

    batch = create_batch(
        db_session,
        hub,
        material_type=material_type,
    )

    if material_type == MaterialType.PET:
        hub.pet_current = hub.pet_capacity
    else:
        hub.hdpe_current = hub.hdpe_capacity

    db_session.flush()

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    command = AcceptBottleCommand(
        session_id=return_session.id,
        batch_id=batch.id,
        transaction_code=(
            f"FULL-HUB-TX-{uuid4().hex.upper()}"
        ),
        material_type=material_type,
        verified_material_type=material_type,
        verification_level=VerificationLevel.LEVEL_2,
        cleanliness_status=CleanlinessStatus.CLEAN,
        weight_gram=Decimal("25.00"),
        points_awarded=10,
        verifier_name="sensor_rule_engine",
    )

    with pytest.raises(
        InvalidStateError,
        match=expected_message,
    ):
        ReturnService(db_session).accept_bottle(command)

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

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

    stored_transactions = (
        BottleTransactionRepository(db_session)
        .list_by_session(return_session.id)
    )

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_hub is not None

    if material_type == MaterialType.PET:
        assert stored_hub.pet_current == stored_hub.pet_capacity
        assert stored_hub.hdpe_current == 0
    else:
        assert stored_hub.pet_current == 0
        assert stored_hub.hdpe_current == stored_hub.hdpe_capacity

    assert stored_session is not None
    assert stored_session.status == ReturnSessionStatus.OPEN
    assert stored_session.total_accepted == 0
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 0

    assert stored_batch is not None
    assert stored_batch.bottle_count == 0
    assert stored_batch.estimated_weight_kg == Decimal("0.000")

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
                "points_awarded": -1,
            },
            "awarded points must be non-negative",
        ),
        (
            {
                "verifier_name": "   ",
            },
            "verifier name must not be empty",
        ),
    ],
)
def test_accept_bottle_rejects_invalid_metadata_without_changes(
    db_session: Session,
    command_overrides: dict[str, object],
    expected_message: str,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    batch = create_batch(db_session, hub)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    command_data = {
        "session_id": return_session.id,
        "batch_id": batch.id,
        "transaction_code": (
            f"INVALID-METADATA-TX-{uuid4().hex.upper()}"
        ),
        "material_type": MaterialType.PET,
        "verified_material_type": MaterialType.PET,
        "verification_level": VerificationLevel.LEVEL_2,
        "cleanliness_status": CleanlinessStatus.CLEAN,
        "weight_gram": Decimal("25.00"),
        "points_awarded": 10,
        "verifier_name": "sensor_rule_engine",
    }

    command_data.update(command_overrides)

    command = AcceptBottleCommand(**command_data)

    with pytest.raises(
        InvalidStateError,
        match=expected_message,
    ):
        ReturnService(db_session).accept_bottle(command)

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

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

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

    assert stored_batch is not None
    assert stored_batch.bottle_count == 0
    assert stored_batch.estimated_weight_kg == Decimal("0.000")

    assert stored_transactions == []


def test_accept_bottle_rejects_duplicate_transaction_code(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    batch = create_batch(db_session, hub)

    return_session = ReturnService(
        db_session
    ).start_session(
        user_id=user.id,
        hub_id=hub.id,
    )

    transaction_code = (
        f"DUPLICATE-TX-{uuid4().hex.upper()}"
    )

    first_command = AcceptBottleCommand(
        session_id=return_session.id,
        batch_id=batch.id,
        transaction_code=transaction_code,
        material_type=MaterialType.PET,
        verified_material_type=MaterialType.PET,
        verification_level=VerificationLevel.LEVEL_2,
        cleanliness_status=CleanlinessStatus.CLEAN,
        weight_gram=Decimal("25.00"),
        points_awarded=10,
        verifier_name="sensor_rule_engine",
    )

    service = ReturnService(db_session)

    first_transaction = service.accept_bottle(
        first_command
    )

    first_transaction_id = first_transaction.id

    duplicate_command = AcceptBottleCommand(
        session_id=return_session.id,
        batch_id=batch.id,
        transaction_code=transaction_code,
        material_type=MaterialType.PET,
        verified_material_type=MaterialType.PET,
        verification_level=VerificationLevel.LEVEL_2,
        cleanliness_status=CleanlinessStatus.CLEAN,
        weight_gram=Decimal("30.00"),
        points_awarded=99,
        verifier_name="sensor_rule_engine",
    )

    with pytest.raises(
        ConflictError,
        match="transaction code already exists",
    ):
        service.accept_bottle(duplicate_command)

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

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

    stored_transactions = (
        BottleTransactionRepository(db_session)
        .list_by_session(return_session.id)
    )

    stored_verification = VerificationEventRepository(
        db_session
    ).get_latest_by_transaction(
        first_transaction_id
    )

    stored_ledger = PointLedgerRepository(
        db_session
    ).get_by_source(
        PointSourceType.BOTTLE_RETURN,
        first_transaction_id,
    )

    assert stored_user is not None
    assert stored_user.points_balance == 10
    assert stored_user.total_bottles_returned == 1

    assert stored_hub is not None
    assert stored_hub.pet_current == 1
    assert stored_hub.hdpe_current == 0

    assert stored_session is not None
    assert stored_session.total_accepted == 1
    assert stored_session.total_rejected == 0
    assert stored_session.total_points == 10

    assert stored_batch is not None
    assert stored_batch.bottle_count == 1
    assert stored_batch.estimated_weight_kg == Decimal("0.025")

    assert len(stored_transactions) == 1
    assert stored_transactions[0].id == first_transaction_id
    assert stored_transactions[0].points_awarded == 10
    assert stored_transactions[0].weight_gram == Decimal("25.00")

    assert stored_verification is not None
    assert stored_verification.result == VerificationResult.PASS

    assert stored_ledger is not None
    assert stored_ledger.points_change == 10
    assert stored_ledger.balance_after == 10


def test_accept_bottle_rejects_unknown_session_without_changes(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    hub = create_hub(db_session)
    batch = create_batch(db_session, hub)

    transaction_code = (
        f"UNKNOWN-SESSION-TX-{uuid4().hex.upper()}"
    )

    command = AcceptBottleCommand(
        session_id=uuid4(),
        batch_id=batch.id,
        transaction_code=transaction_code,
        material_type=MaterialType.PET,
        verified_material_type=MaterialType.PET,
        verification_level=VerificationLevel.LEVEL_2,
        cleanliness_status=CleanlinessStatus.CLEAN,
        weight_gram=Decimal("25.00"),
        points_awarded=10,
        verifier_name="sensor_rule_engine",
    )

    with pytest.raises(
        EntityNotFoundError,
        match="return session not found",
    ):
        ReturnService(db_session).accept_bottle(command)

    db_session.expire_all()

    stored_user = UserRepository(
        db_session
    ).get_by_id(user.id)

    stored_hub = HubRepository(
        db_session
    ).get_by_id(hub.id)

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch.id)

    stored_transaction = BottleTransactionRepository(
        db_session
    ).get_by_code(transaction_code)

    assert stored_user is not None
    assert stored_user.points_balance == 0
    assert stored_user.total_bottles_returned == 0

    assert stored_hub is not None
    assert stored_hub.pet_current == 0
    assert stored_hub.hdpe_current == 0

    assert stored_batch is not None
    assert stored_batch.bottle_count == 0
    assert (
        stored_batch.estimated_weight_kg
        == Decimal("0.000")
    )

    assert stored_transaction is None


def test_accept_bottle_rejects_unknown_batch_without_changes(
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
        f"UNKNOWN-BATCH-TX-{uuid4().hex.upper()}"
    )

    command = AcceptBottleCommand(
        session_id=return_session.id,
        batch_id=uuid4(),
        transaction_code=transaction_code,
        material_type=MaterialType.PET,
        verified_material_type=MaterialType.PET,
        verification_level=VerificationLevel.LEVEL_2,
        cleanliness_status=CleanlinessStatus.CLEAN,
        weight_gram=Decimal("25.00"),
        points_awarded=10,
        verifier_name="sensor_rule_engine",
    )

    with pytest.raises(
        EntityNotFoundError,
        match="material batch not found",
    ):
        ReturnService(db_session).accept_bottle(command)

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
    ).get_by_code(transaction_code)

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

    assert stored_transaction is None
