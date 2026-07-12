from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreatePickupCommand:
    code: str
    hub_id: UUID
    driver_id: UUID
    scheduled_at: datetime | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class AssignBatchCommand:
    pickup_id: UUID
    batch_id: UUID
