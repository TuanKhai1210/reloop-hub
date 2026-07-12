from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

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
    UserRole,
)
from app.repositories import (
    HubRepository,
    MaterialBatchRepository,
    PickupRepository,
    UserRepository,
)
from app.services.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
)
from app.services.pickup_commands import (
    AssignBatchCommand,
    CreatePickupCommand,
)


class PickupService:
    PICKUP_CODE_UNIQUE_CONSTRAINT = "uq_pickups_code"

    def __init__(self, session: Session) -> None:
        self.session = session
        self.user_repository = UserRepository(session)
        self.hub_repository = HubRepository(session)
        self.pickup_repository = PickupRepository(session)
        self.batch_repository = MaterialBatchRepository(session)

    def create_pickup(
        self,
        command: CreatePickupCommand,
    ) -> Pickup:
        return self._run(
            lambda: self._create_with_conflict_mapping(command)
        )

    def assign_batch(
        self,
        command: AssignBatchCommand,
    ) -> Pickup:
        return self._run(lambda: self._assign_batch(command))

    def complete_pickup(self, pickup_id: UUID) -> Pickup:
        return self._run(lambda: self._complete_pickup(pickup_id))

    def cancel_pickup(self, pickup_id: UUID) -> Pickup:
        return self._run(lambda: self._cancel_pickup(pickup_id))

    def _run(self, operation):
        if self.session.in_transaction():
            return operation()

        with self.session.begin():
            return operation()

    def _create_with_conflict_mapping(
        self,
        command: CreatePickupCommand,
    ) -> Pickup:
        try:
            with self.session.begin_nested():
                return self._create_pickup(command)
        except IntegrityError as error:
            diagnostic = getattr(error.orig, "diag", None)
            constraint_name = getattr(
                diagnostic,
                "constraint_name",
                None,
            )
            sqlstate = getattr(error.orig, "sqlstate", None)

            if (
                sqlstate == "23505"
                and constraint_name
                == self.PICKUP_CODE_UNIQUE_CONSTRAINT
            ):
                raise ConflictError(
                    "pickup code already exists"
                ) from error

            raise

    def _create_pickup(
        self,
        command: CreatePickupCommand,
    ) -> Pickup:
        code = command.code.strip()

        if not code:
            raise InvalidStateError(
                "pickup code must not be empty"
            )

        if self.pickup_repository.get_by_code(code) is not None:
            raise ConflictError("pickup code already exists")

        hub = self.hub_repository.get_by_id(command.hub_id)

        if hub is None:
            raise EntityNotFoundError("hub not found")

        driver = self.user_repository.get_by_id(
            command.driver_id
        )

        if driver is None:
            raise EntityNotFoundError("driver not found")

        if driver.role != UserRole.DRIVER:
            raise InvalidStateError(
                "assigned user is not a driver"
            )

        values = {
            "code": code,
            "hub_id": hub.id,
            "driver_id": driver.id,
            "status": PickupStatus.PLANNED,
            "total_batches": 0,
            "total_bottles": 0,
            "estimated_weight_kg": Decimal("0"),
            "notes": command.notes.strip()
            if command.notes is not None
            else None,
        }

        if command.scheduled_at is not None:
            values["scheduled_at"] = command.scheduled_at

        return self.pickup_repository.add(Pickup(**values))

    def _assign_batch(
        self,
        command: AssignBatchCommand,
    ) -> Pickup:
        pickup = self.pickup_repository.get_by_id_for_update(
            command.pickup_id
        )

        if pickup is None:
            raise EntityNotFoundError("pickup not found")

        if pickup.status not in {
            PickupStatus.PLANNED,
            PickupStatus.IN_PROGRESS,
        }:
            raise InvalidStateError("pickup is not active")

        batch = self.batch_repository.get_by_id_for_update(
            command.batch_id
        )

        if batch is None:
            raise EntityNotFoundError("material batch not found")

        if batch.status != MaterialBatchStatus.READY_FOR_PICKUP:
            raise InvalidStateError(
                "material batch is not ready for pickup"
            )

        if batch.pickup_id is not None:
            raise ConflictError(
                "material batch is already assigned"
            )

        if batch.hub_id != pickup.hub_id:
            raise InvalidStateError(
                "material batch belongs to another hub"
            )

        batch.pickup_id = pickup.id
        pickup.status = PickupStatus.IN_PROGRESS

        if pickup.started_at is None:
            pickup.started_at = datetime.now(UTC)

        pickup.total_batches += 1
        pickup.total_bottles += batch.bottle_count
        pickup.estimated_weight_kg += batch.estimated_weight_kg
        self.session.flush()

        return pickup

    def _complete_pickup(self, pickup_id: UUID) -> Pickup:
        pickup = self.pickup_repository.get_by_id_for_update(
            pickup_id
        )

        if pickup is None:
            raise EntityNotFoundError("pickup not found")

        if pickup.status != PickupStatus.IN_PROGRESS:
            raise InvalidStateError("pickup is not in progress")

        hub = self.hub_repository.get_by_id_for_update(
            pickup.hub_id
        )

        if hub is None:
            raise EntityNotFoundError("hub not found")

        batches = self.batch_repository.list_by_pickup_for_update(
            pickup.id
        )

        if not batches:
            raise InvalidStateError(
                "pickup has no assigned material batches"
            )

        pet_bottles = 0
        hdpe_bottles = 0
        total_bottles = 0
        total_weight = Decimal("0")

        for batch in batches:
            if batch.status != MaterialBatchStatus.READY_FOR_PICKUP:
                raise InvalidStateError(
                    "pickup contains an invalid material batch"
                )

            if batch.material_type == MaterialType.PET:
                pet_bottles += batch.bottle_count
            elif batch.material_type == MaterialType.HDPE:
                hdpe_bottles += batch.bottle_count

            total_bottles += batch.bottle_count
            total_weight += batch.estimated_weight_kg

        if (
            pickup.total_batches != len(batches)
            or pickup.total_bottles != total_bottles
            or pickup.estimated_weight_kg != total_weight
        ):
            raise InvalidStateError(
                "pickup totals do not match assigned batches"
            )

        if pet_bottles > hub.pet_current:
            raise InvalidStateError(
                "pickup PET total exceeds hub inventory"
            )

        if hdpe_bottles > hub.hdpe_current:
            raise InvalidStateError(
                "pickup HDPE total exceeds hub inventory"
            )

        for batch in batches:
            batch.status = MaterialBatchStatus.PICKED_UP

        hub.pet_current -= pet_bottles
        hub.hdpe_current -= hdpe_bottles
        collected_weight = sum(
            (batch.estimated_weight_kg for batch in batches),
            start=Decimal("0"),
        )
        hub.current_load_kg = max(
            Decimal("0"),
            hub.current_load_kg - collected_weight,
        )
        hub.fill_level = (
            hub.current_load_kg
            / hub.capacity_kg
            * Decimal("100")
        ).quantize(Decimal("0.01"))
        self._refresh_hub_status(hub)

        pickup.status = PickupStatus.COMPLETED
        pickup.completed_at = datetime.now(UTC)
        self.session.flush()

        return pickup

    def _cancel_pickup(self, pickup_id: UUID) -> Pickup:
        pickup = self.pickup_repository.get_by_id_for_update(
            pickup_id
        )

        if pickup is None:
            raise EntityNotFoundError("pickup not found")

        if pickup.status != PickupStatus.PLANNED:
            raise InvalidStateError(
                "only planned pickups can be cancelled"
            )

        pickup.status = PickupStatus.CANCELLED
        self.session.flush()

        return pickup

    @staticmethod
    def _refresh_hub_status(hub: Hub) -> None:
        both_full = (
            hub.pet_current >= hub.pet_capacity
            and hub.hdpe_current >= hub.hdpe_capacity
        )
        any_threshold_reached = (
            hub.pet_current * 100
            >= hub.pet_capacity * hub.pickup_threshold_percent
            or hub.hdpe_current * 100
            >= hub.hdpe_capacity * hub.pickup_threshold_percent
        )

        if both_full:
            hub.status = HubStatus.FULL
        elif any_threshold_reached:
            hub.status = HubStatus.NEAR_FULL
        else:
            hub.status = HubStatus.ACTIVE
