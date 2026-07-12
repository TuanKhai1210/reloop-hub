from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import TraceEvent, User
from app.schemas import (
    TraceabilityRead,
    TraceEventRead,
)


router = APIRouter(prefix="/traceability", tags=["Traceability"])


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
