from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api_errors import service_http_error
from app.dependencies import get_current_user, require_roles
from app.models import TraceEvent, User, UserRole
from app.schemas import (
    BatchReceiptRead,
    BatchReceiptRequest,
    TraceabilityRead,
    TraceEventRead,
)
from app.services import ServiceError, TraceabilityService


router = APIRouter(prefix="/traceability", tags=["Traceability"])


@router.post(
    "/batches/{batch_id}/receive",
    response_model=BatchReceiptRead,
)
def receive_batch_at_recycler(
    batch_id: UUID,
    payload: BatchReceiptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.OPERATOR,
            UserRole.RECYCLER,
        )
    ),
) -> BatchReceiptRead:
    try:
        result = TraceabilityService(db).receive_batch(
            batch_id=batch_id,
            facility_code=payload.facility_code,
            received_weight_kg=payload.received_weight_kg,
            actor_user_id=user.id,
            notes=payload.notes,
        )
    except ServiceError as error:
        raise service_http_error(error) from error
    return BatchReceiptRead(
        batch_id=result.batch.id,
        batch_code=result.batch.code,
        status=result.batch.status,
        facility_code=result.facility_code,
        received_weight_kg=result.received_weight_kg,
        bottle_count=result.batch.bottle_count,
        trace_events_created=result.trace_events_created,
        received_at=result.received_at,
    )


@router.get("/{trace_code}", response_model=TraceabilityRead)
def get_traceability(
    trace_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TraceabilityRead:
    events = list(
        db.scalars(
            select(TraceEvent)
            .where(TraceEvent.trace_code == trace_code.strip())
            .order_by(TraceEvent.occurred_at, TraceEvent.id)
        )
    )
    if not events:
        raise HTTPException(status_code=404, detail="Trace code not found")
    return TraceabilityRead(
        trace_code=trace_code.strip(),
        current_stage=events[-1].stage,
        events=[TraceEventRead.model_validate(event) for event in events],
    )
