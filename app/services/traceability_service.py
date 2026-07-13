from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    BottleTransaction,
    MaterialBatch,
    MaterialBatchStatus,
    Pickup,
    PickupStatus,
    TraceEvent,
    TraceStage,
)
from app.services.errors import EntityNotFoundError, InvalidStateError


@dataclass(frozen=True, slots=True)
class BatchReceiptResult:
    batch: MaterialBatch
    facility_code: str
    received_weight_kg: Decimal
    trace_events_created: int
    received_at: datetime


class TraceabilityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def receive_batch(
        self,
        *,
        batch_id: UUID,
        facility_code: str,
        received_weight_kg: Decimal,
        actor_user_id: UUID,
        notes: str | None = None,
    ) -> BatchReceiptResult:
        arguments = {
            "batch_id": batch_id,
            "facility_code": facility_code,
            "received_weight_kg": received_weight_kg,
            "actor_user_id": actor_user_id,
            "notes": notes,
        }
        if self.session.in_transaction():
            return self._receive_batch(**arguments)
        with self.session.begin():
            return self._receive_batch(**arguments)

    def _receive_batch(
        self,
        *,
        batch_id: UUID,
        facility_code: str,
        received_weight_kg: Decimal,
        actor_user_id: UUID,
        notes: str | None,
    ) -> BatchReceiptResult:
        normalized_facility = facility_code.strip()
        if not normalized_facility:
            raise InvalidStateError("facility code must not be empty")
        if received_weight_kg < 0:
            raise InvalidStateError("received weight must be non-negative")

        batch = self.session.scalar(
            select(MaterialBatch)
            .where(MaterialBatch.id == batch_id)
            .with_for_update()
        )
        if batch is None:
            raise EntityNotFoundError("material batch not found")
        if batch.status != MaterialBatchStatus.PICKED_UP:
            raise InvalidStateError("material batch is not picked up")
        if batch.pickup_id is None:
            raise InvalidStateError("material batch has no pickup")
        pickup = self.session.get(Pickup, batch.pickup_id)
        if pickup is None or pickup.status != PickupStatus.COMPLETED:
            raise InvalidStateError("material batch pickup is not completed")

        transactions = list(
            self.session.scalars(
                select(BottleTransaction)
                .where(BottleTransaction.batch_id == batch.id)
                .order_by(BottleTransaction.created_at, BottleTransaction.id)
            )
        )
        if not transactions:
            raise InvalidStateError("material batch has no bottles")

        received_at = datetime.now(UTC)
        for transaction in transactions:
            self.session.add(
                TraceEvent(
                    trace_code=transaction.code,
                    transaction_id=transaction.id,
                    stage=TraceStage.RECEIVED,
                    location_type="recycler",
                    location_ref=normalized_facility,
                    actor_user_id=actor_user_id,
                    notes=notes,
                    event_metadata={
                        "batch_id": str(batch.id),
                        "pickup_id": str(batch.pickup_id),
                        "received_weight_kg": str(received_weight_kg),
                    },
                    occurred_at=received_at,
                )
            )

        batch.status = MaterialBatchStatus.RECEIVED
        self.session.flush()
        return BatchReceiptResult(
            batch=batch,
            facility_code=normalized_facility,
            received_weight_kg=received_weight_kg,
            trace_events_created=len(transactions),
            received_at=received_at,
        )
