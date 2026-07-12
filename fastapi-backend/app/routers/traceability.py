from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import Deposit, TraceEvent, TraceStage, User, UserRole
from app.schemas import TraceabilityRead, TraceEventCreate, TraceEventRead


router = APIRouter(prefix="/traceability", tags=["Material traceability"])
STAGE_ORDER = list(TraceStage)


@router.get("/{trace_code}", response_model=TraceabilityRead)
def get_trace(
    trace_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TraceabilityRead:
    deposit = db.scalar(select(Deposit).where(Deposit.trace_code == trace_code))
    if not deposit:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã truy xuất")
    events = list(
        db.scalars(select(TraceEvent).where(TraceEvent.trace_code == trace_code).order_by(TraceEvent.occurred_at))
    )
    if not events:
        raise HTTPException(status_code=404, detail="Giao dịch không có hành trình vật liệu do đã bị từ chối")
    return TraceabilityRead(
        trace_code=trace_code,
        material_type=deposit.material_type,
        weight_g=deposit.weight_g,
        quality_status=deposit.status,
        current_stage=events[-1].stage,
        events=[TraceEventRead.model_validate(event) for event in events],
    )


@router.post("/events", response_model=TraceEventRead, status_code=201)
def add_trace_event(
    payload: TraceEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.DRIVER, UserRole.RECYCLER)),
) -> TraceEvent:
    deposit = db.scalar(select(Deposit).where(Deposit.trace_code == payload.trace_code))
    if not deposit:
        raise HTTPException(status_code=404, detail="Không tìm thấy mã truy xuất")
    latest = db.scalar(
        select(TraceEvent)
        .where(TraceEvent.trace_code == payload.trace_code)
        .order_by(TraceEvent.occurred_at.desc())
        .limit(1)
    )
    if latest and STAGE_ORDER.index(payload.stage) < STAGE_ORDER.index(latest.stage):
        raise HTTPException(status_code=409, detail="Không thể ghi sự kiện lùi về giai đoạn trước")
    event = TraceEvent(**payload.model_dump(), actor_user_id=user.id)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

