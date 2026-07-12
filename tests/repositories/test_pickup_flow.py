from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Hub,
    HubStatus,
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
    Pickup,
    PickupStatus,
    User,
    UserRole,
)
from app.repositories import (
    HubRepository,
    MaterialBatchRepository,
    PickupRepository,
    UserRepository,
)
from app.services import (
    AssignBatchCommand,
    CreatePickupCommand,
    PickupService,
)


pytestmark = pytest.mark.integration


def create_test_driver(
    db_session: Session,
) -> User:
    token = uuid4().hex[:12].upper()

    return UserRepository(db_session).add(
        User(
            name="Pickup Flow Test Driver",
            phone=None,
            student_code=f"DRIVER-{token}",
            role=UserRole.DRIVER,
            points_balance=0,
            total_bottles_returned=0,
        )
    )


def create_test_hub(
    db_session: Session,
    *,
    name_suffix: str = "",
) -> Hub:
    token = uuid4().hex[:12].upper()

    return HubRepository(db_session).add(
        Hub(
            code=f"PICKUP-HUB-{token}",
            name=f"Pickup Flow Hub{name_suffix}",
            location_name="Test Canteen",
            latitude=None,
            longitude=None,
            status=HubStatus.ACTIVE,
            pet_capacity=100,
            hdpe_capacity=100,
            pet_current=0,
            hdpe_current=0,
            pickup_threshold_percent=80,
        )
    )


def create_test_pickup(
    db_session: Session,
    *,
    hub: Hub,
    driver: User,
    status: PickupStatus = PickupStatus.PLANNED,
    code: str | None = None,
) -> Pickup:
    token = uuid4().hex[:12].upper()

    return PickupRepository(db_session).add(
        Pickup(
            code=code or f"PICKUP-{token}",
            hub_id=hub.id,
            driver_id=driver.id,
            status=status,
            total_batches=0,
            total_bottles=0,
            estimated_weight_kg=Decimal("0"),
            notes="Pickup flow integration test",
        )
    )


def create_test_batch(
    db_session: Session,
    *,
    hub: Hub,
    material_type: MaterialType = MaterialType.PET,
    bottle_count: int = 20,
    estimated_weight_kg: Decimal = Decimal("0.500"),
    status: MaterialBatchStatus = (
        MaterialBatchStatus.READY_FOR_PICKUP
    ),
    code: str | None = None,
) -> MaterialBatch:
    token = uuid4().hex[:12].upper()

    return MaterialBatchRepository(db_session).add(
        MaterialBatch(
            code=code or f"PICKUP-BATCH-{token}",
            hub_id=hub.id,
            pickup_id=None,
            material_type=material_type,
            bottle_count=bottle_count,
            estimated_weight_kg=estimated_weight_kg,
            status=status,
        )
    )


def assign_batch_to_pickup_contract(
    db_session: Session,
    *,
    pickup: Pickup,
    batch: MaterialBatch,
) -> None:
    if pickup.status not in {
        PickupStatus.PLANNED,
        PickupStatus.IN_PROGRESS,
    }:
        raise ValueError("pickup is not active")

    if batch.status != MaterialBatchStatus.READY_FOR_PICKUP:
        raise ValueError("batch is not ready for pickup")

    if batch.pickup_id is not None:
        raise ValueError("batch is already assigned")

    if batch.hub_id != pickup.hub_id:
        raise ValueError("batch and pickup belong to different hubs")

    now = datetime.now(timezone.utc)

    batch.pickup_id = pickup.id

    pickup.status = PickupStatus.IN_PROGRESS

    if pickup.started_at is None:
        pickup.started_at = now

    pickup.total_batches += 1
    pickup.total_bottles += batch.bottle_count
    pickup.estimated_weight_kg += batch.estimated_weight_kg

    db_session.flush()


def complete_pickup_contract(
    db_session: Session,
    *,
    pickup: Pickup,
) -> list[MaterialBatch]:
    if pickup.status != PickupStatus.IN_PROGRESS:
        raise ValueError("pickup is not in progress")

    batch_repository = MaterialBatchRepository(db_session)
    batches = list(
        batch_repository.list_by_pickup(
            pickup.id,
            limit=1000,
        )
    )

    if not batches:
        raise ValueError("pickup has no assigned batches")

    for batch in batches:
        if (
            batch.status
            != MaterialBatchStatus.READY_FOR_PICKUP
        ):
            raise ValueError(
                "pickup contains a batch with invalid status"
            )

    pickup.status = PickupStatus.COMPLETED
    pickup.completed_at = datetime.now(timezone.utc)

    for batch in batches:
        batch.status = MaterialBatchStatus.PICKED_UP

    db_session.flush()

    return batches


def test_complete_batch_pickup_flow(
    db_session: Session,
) -> None:
    driver = create_test_driver(db_session)
    hub = create_test_hub(db_session)

    pickup = create_test_pickup(
        db_session,
        hub=hub,
        driver=driver,
    )

    pet_batch = create_test_batch(
        db_session,
        hub=hub,
        material_type=MaterialType.PET,
        bottle_count=20,
        estimated_weight_kg=Decimal("0.500"),
    )

    hdpe_batch = create_test_batch(
        db_session,
        hub=hub,
        material_type=MaterialType.HDPE,
        bottle_count=10,
        estimated_weight_kg=Decimal("0.750"),
    )

    batch_repository = MaterialBatchRepository(db_session)
    pickup_repository = PickupRepository(db_session)

    ready_before = batch_repository.list_ready_for_pickup(
        hub_id=hub.id,
        limit=1000,
    )

    assert {batch.id for batch in ready_before} == {
        pet_batch.id,
        hdpe_batch.id,
    }

    assign_batch_to_pickup_contract(
        db_session,
        pickup=pickup,
        batch=pet_batch,
    )

    assign_batch_to_pickup_contract(
        db_session,
        pickup=pickup,
        batch=hdpe_batch,
    )

    assert pickup.status == PickupStatus.IN_PROGRESS
    assert pickup.started_at is not None
    assert pickup.total_batches == 2
    assert pickup.total_bottles == 30
    assert pickup.estimated_weight_kg == Decimal("1.250")

    assigned_batches = batch_repository.list_by_pickup(
        pickup.id,
        limit=1000,
    )

    assert {batch.id for batch in assigned_batches} == {
        pet_batch.id,
        hdpe_batch.id,
    }

    active_pickups = pickup_repository.list_active(
        hub_id=hub.id,
        limit=1000,
    )

    assert any(
        item.id == pickup.id
        for item in active_pickups
    )

    completed_batches = complete_pickup_contract(
        db_session,
        pickup=pickup,
    )

    pickup_id = pickup.id
    pet_batch_id = pet_batch.id
    hdpe_batch_id = hdpe_batch.id

    db_session.expire_all()

    stored_pickup = pickup_repository.get_by_id(pickup_id)
    stored_pet_batch = batch_repository.get_by_id(
        pet_batch_id
    )
    stored_hdpe_batch = batch_repository.get_by_id(
        hdpe_batch_id
    )

    assert stored_pickup is not None
    assert stored_pickup.status == PickupStatus.COMPLETED
    assert stored_pickup.started_at is not None
    assert stored_pickup.completed_at is not None
    assert (
        stored_pickup.completed_at
        >= stored_pickup.started_at
    )
    assert stored_pickup.total_batches == 2
    assert stored_pickup.total_bottles == 30
    assert stored_pickup.estimated_weight_kg == (
        Decimal("1.250")
    )

    assert len(completed_batches) == 2

    assert stored_pet_batch is not None
    assert stored_pet_batch.pickup_id == pickup_id
    assert stored_pet_batch.status == (
        MaterialBatchStatus.PICKED_UP
    )

    assert stored_hdpe_batch is not None
    assert stored_hdpe_batch.pickup_id == pickup_id
    assert stored_hdpe_batch.status == (
        MaterialBatchStatus.PICKED_UP
    )

    ready_after = batch_repository.list_ready_for_pickup(
        hub_id=hub.id,
        limit=1000,
    )

    active_after = pickup_repository.list_active(
        hub_id=hub.id,
        limit=1000,
    )

    completed_for_driver = (
        pickup_repository.list_by_driver(
            driver.id,
            status=PickupStatus.COMPLETED,
            limit=1000,
        )
    )

    assert pet_batch_id not in {
        batch.id for batch in ready_after
    }
    assert hdpe_batch_id not in {
        batch.id for batch in ready_after
    }
    assert pickup_id not in {
        item.id for item in active_after
    }
    assert any(
        item.id == pickup_id
        for item in completed_for_driver
    )


def test_batch_from_different_hub_is_rejected(
    db_session: Session,
) -> None:
    driver = create_test_driver(db_session)
    pickup_hub = create_test_hub(
        db_session,
        name_suffix=" A",
    )
    batch_hub = create_test_hub(
        db_session,
        name_suffix=" B",
    )

    pickup = create_test_pickup(
        db_session,
        hub=pickup_hub,
        driver=driver,
    )

    batch = create_test_batch(
        db_session,
        hub=batch_hub,
    )

    with pytest.raises(
        ValueError,
        match="different hubs",
    ):
        assign_batch_to_pickup_contract(
            db_session,
            pickup=pickup,
            batch=batch,
        )

    assert pickup.status == PickupStatus.PLANNED
    assert pickup.started_at is None
    assert pickup.total_batches == 0
    assert pickup.total_bottles == 0
    assert pickup.estimated_weight_kg == Decimal("0")
    assert batch.pickup_id is None
    assert batch.status == (
        MaterialBatchStatus.READY_FOR_PICKUP
    )


def test_cancelled_pickup_rejects_batch_assignment(
    db_session: Session,
) -> None:
    driver = create_test_driver(db_session)
    hub = create_test_hub(db_session)

    pickup = create_test_pickup(
        db_session,
        hub=hub,
        driver=driver,
        status=PickupStatus.CANCELLED,
    )

    batch = create_test_batch(
        db_session,
        hub=hub,
    )

    with pytest.raises(
        ValueError,
        match="pickup is not active",
    ):
        assign_batch_to_pickup_contract(
            db_session,
            pickup=pickup,
            batch=batch,
        )

    assert pickup.status == PickupStatus.CANCELLED
    assert pickup.total_batches == 0
    assert batch.pickup_id is None


def test_batch_cannot_be_assigned_twice(
    db_session: Session,
) -> None:
    driver = create_test_driver(db_session)
    hub = create_test_hub(db_session)

    pickup = create_test_pickup(
        db_session,
        hub=hub,
        driver=driver,
    )

    batch = create_test_batch(
        db_session,
        hub=hub,
    )

    assign_batch_to_pickup_contract(
        db_session,
        pickup=pickup,
        batch=batch,
    )

    with pytest.raises(
        ValueError,
        match="already assigned",
    ):
        assign_batch_to_pickup_contract(
            db_session,
            pickup=pickup,
            batch=batch,
        )

    assert pickup.total_batches == 1
    assert pickup.total_bottles == batch.bottle_count
    assert pickup.estimated_weight_kg == (
        batch.estimated_weight_kg
    )


def test_duplicate_pickup_code_is_rejected(
    db_session: Session,
) -> None:
    driver = create_test_driver(db_session)
    hub = create_test_hub(db_session)
    code = f"DUPLICATE-PICKUP-{uuid4().hex[:12].upper()}"

    first_pickup = create_test_pickup(
        db_session,
        hub=hub,
        driver=driver,
        code=code,
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            create_test_pickup(
                db_session,
                hub=hub,
                driver=driver,
                code=code,
            )

    stored_pickup = PickupRepository(
        db_session
    ).get_by_code(code)

    assert stored_pickup is not None
    assert stored_pickup.id == first_pickup.id


def test_duplicate_batch_code_is_rejected(
    db_session: Session,
) -> None:
    hub = create_test_hub(db_session)
    code = f"DUPLICATE-BATCH-{uuid4().hex[:12].upper()}"

    first_batch = create_test_batch(
        db_session,
        hub=hub,
        code=code,
    )

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            create_test_batch(
                db_session,
                hub=hub,
                code=code,
            )

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_code(code)

    assert stored_batch is not None
    assert stored_batch.id == first_batch.id


@pytest.mark.parametrize(
    (
        "bottle_count",
        "estimated_weight_kg",
    ),
    [
        (-1, Decimal("0.100")),
        (1, Decimal("-0.100")),
    ],
)
def test_invalid_batch_quantities_are_rejected(
    db_session: Session,
    bottle_count: int,
    estimated_weight_kg: Decimal,
) -> None:
    hub = create_test_hub(db_session)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            create_test_batch(
                db_session,
                hub=hub,
                bottle_count=bottle_count,
                estimated_weight_kg=estimated_weight_kg,
            )


@pytest.mark.parametrize(
    (
        "total_batches",
        "total_bottles",
        "estimated_weight_kg",
    ),
    [
        (-1, 0, Decimal("0")),
        (0, -1, Decimal("0")),
        (0, 0, Decimal("-0.100")),
    ],
)
def test_invalid_pickup_totals_are_rejected(
    db_session: Session,
    total_batches: int,
    total_bottles: int,
    estimated_weight_kg: Decimal,
) -> None:
    driver = create_test_driver(db_session)
    hub = create_test_hub(db_session)

    token = uuid4().hex[:12].upper()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            PickupRepository(db_session).add(
                Pickup(
                    code=f"INVALID-PICKUP-{token}",
                    hub_id=hub.id,
                    driver_id=driver.id,
                    status=PickupStatus.PLANNED,
                    total_batches=total_batches,
                    total_bottles=total_bottles,
                    estimated_weight_kg=(
                        estimated_weight_kg
                    ),
                    notes=None,
                )
            )


def test_batch_with_unknown_hub_is_rejected(
    db_session: Session,
) -> None:
    token = uuid4().hex[:12].upper()

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            MaterialBatchRepository(db_session).add(
                MaterialBatch(
                    code=f"UNKNOWN-HUB-BATCH-{token}",
                    hub_id=uuid4(),
                    pickup_id=None,
                    material_type=MaterialType.PET,
                    bottle_count=1,
                    estimated_weight_kg=Decimal("0.025"),
                    status=(
                        MaterialBatchStatus.READY_FOR_PICKUP
                    ),
                )
            )


def test_partial_pickup_failure_rolls_back_all_changes(
    db_session: Session,
) -> None:
    driver = create_test_driver(db_session)
    hub = create_test_hub(db_session)

    pickup = create_test_pickup(
        db_session,
        hub=hub,
        driver=driver,
    )

    batch = create_test_batch(
        db_session,
        hub=hub,
        bottle_count=15,
        estimated_weight_kg=Decimal("0.375"),
    )

    pickup_id: UUID = pickup.id
    batch_id: UUID = batch.id

    with pytest.raises(
        RuntimeError,
        match="simulated pickup failure",
    ):
        with db_session.begin_nested():
            assign_batch_to_pickup_contract(
                db_session,
                pickup=pickup,
                batch=batch,
            )

            assert pickup.status == (
                PickupStatus.IN_PROGRESS
            )
            assert batch.pickup_id == pickup.id

            raise RuntimeError(
                "simulated pickup failure"
            )

    db_session.expire_all()

    stored_pickup = PickupRepository(
        db_session
    ).get_by_id(pickup_id)

    stored_batch = MaterialBatchRepository(
        db_session
    ).get_by_id(batch_id)

    assert stored_pickup is not None
    assert stored_pickup.status == PickupStatus.PLANNED
    assert stored_pickup.started_at is None
    assert stored_pickup.completed_at is None
    assert stored_pickup.total_batches == 0
    assert stored_pickup.total_bottles == 0
    assert stored_pickup.estimated_weight_kg == Decimal("0")

    assert stored_batch is not None
    assert stored_batch.pickup_id is None
    assert stored_batch.status == (
        MaterialBatchStatus.READY_FOR_PICKUP
    )


def test_pickup_service_completes_flow_and_releases_hub_capacity(
    db_session: Session,
) -> None:
    driver = create_test_driver(db_session)
    hub = create_test_hub(db_session)
    hub.pet_current = 20
    hub.status = HubStatus.NEAR_FULL
    batch = create_test_batch(
        db_session,
        hub=hub,
        material_type=MaterialType.PET,
        bottle_count=20,
        estimated_weight_kg=Decimal("0.500"),
    )
    code = f"SERVICE-PICKUP-{uuid4().hex[:12].upper()}"
    service = PickupService(db_session)

    pickup = service.create_pickup(
        CreatePickupCommand(
            code=f"  {code}  ",
            hub_id=hub.id,
            driver_id=driver.id,
        )
    )
    service.assign_batch(
        AssignBatchCommand(
            pickup_id=pickup.id,
            batch_id=batch.id,
        )
    )
    service.complete_pickup(pickup.id)

    db_session.expire_all()

    stored_pickup = PickupRepository(db_session).get_by_id(
        pickup.id
    )
    stored_batch = MaterialBatchRepository(db_session).get_by_id(
        batch.id
    )
    stored_hub = HubRepository(db_session).get_by_id(hub.id)

    assert stored_pickup is not None
    assert stored_pickup.code == code
    assert stored_pickup.status == PickupStatus.COMPLETED
    assert stored_pickup.total_batches == 1
    assert stored_pickup.total_bottles == 20
    assert stored_batch is not None
    assert stored_batch.status == MaterialBatchStatus.PICKED_UP
    assert stored_batch.pickup_id == pickup.id
    assert stored_hub is not None
    assert stored_hub.pet_current == 0
    assert stored_hub.status == HubStatus.ACTIVE
