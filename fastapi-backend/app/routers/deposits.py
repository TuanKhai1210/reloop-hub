from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, verify_device_key
from app.models import (
    Deposit,
    DepositStatus,
    Hub,
    HubStatus,
    PointsLedger,
    TraceEvent,
    TraceStage,
    User,
    UserRole,
)
from app.realtime import hub_manager
from app.schemas import DepositInspection, DepositRead, DepositResult, PointsTransactionRead


router = APIRouter(tags=["Quality & transactions"])

MIN_AI_CONFIDENCE = 0.80
MIN_CLEANLINESS = 0.70
POINTS_PER_100G = {"PET": 10, "HDPE": 12}


def rejection_reason(payload: DepositInspection) -> str | None:
    if payload.material_type is None:
        return "Không nhận diện được PET hoặc HDPE"
    if payload.ai_confidence < MIN_AI_CONFIDENCE:
        return "Độ tin cậy nhận diện thấp"
    if payload.liquid_detected:
        return "Chai còn chứa chất lỏng"
    if payload.foreign_object_detected:
        return "Phát hiện dị vật hoặc vật liệu không phù hợp"
    if payload.cleanliness_score < MIN_CLEANLINESS:
        return "Chai quá bẩn, vui lòng làm sạch"
    return None


@router.post("/deposits/inspect", response_model=DepositResult, status_code=201)
async def inspect_deposit(
    payload: DepositInspection,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
) -> DepositResult:
    hub = db.scalar(select(Hub).where(Hub.code == payload.hub_code))
    if not hub:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hub")
    if hub.status in (HubStatus.MAINTENANCE, HubStatus.OFFLINE):
        raise HTTPException(status_code=409, detail="Hub hiện không sẵn sàng tiếp nhận")
    if payload.user_id is not None and not db.get(User, payload.user_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")

    reason = rejection_reason(payload)
    accepted = reason is None and hub.fill_level < 95
    if reason is None and not accepted:
        reason = "Kho chứa gần đầy, vui lòng đến Hub khác"
    points = 0
    if accepted and payload.material_type:
        points = max(1, round(payload.weight_g / 100 * POINTS_PER_100G[payload.material_type.value]))

    deposit = Deposit(
        **payload.model_dump(exclude={"hub_code"}),
        hub_id=hub.id,
        status=DepositStatus.ACCEPTED if accepted else DepositStatus.REJECTED,
        rejection_reason=reason,
        points_earned=points,
    )
    db.add(deposit)
    db.flush()

    if accepted:
        added_kg = payload.weight_g / 1000
        hub.current_load_kg = min(hub.capacity_kg, hub.current_load_kg + added_kg)
        hub.fill_level = round(hub.current_load_kg / hub.capacity_kg * 100, 2)
        if hub.fill_level >= 90:
            hub.status = HubStatus.FULL
        if payload.user_id:
            user = db.get(User, payload.user_id)
            user.points_balance += points
            db.add(
                PointsLedger(
                    user_id=user.id,
                    deposit_id=deposit.id,
                    points=points,
                    description=f"Đổi {payload.weight_g:g}g {payload.material_type.value}",
                )
            )
        db.add_all(
            [
                TraceEvent(
                    trace_code=deposit.trace_code,
                    stage=TraceStage.DEPOSITED,
                    location_type="hub",
                    location_ref=hub.code,
                    actor_user_id=payload.user_id,
                    event_metadata={"weight_g": payload.weight_g, "material": payload.material_type.value},
                ),
                TraceEvent(
                    trace_code=deposit.trace_code,
                    stage=TraceStage.HUB_STORED,
                    location_type="hub",
                    location_ref=hub.code,
                    event_metadata={"quality_verified": True},
                ),
            ]
        )
    db.commit()
    db.refresh(deposit)
    db.refresh(hub)
    await hub_manager.broadcast(
        {
            "event": "deposit.inspected",
            "data": {
                "hub_code": hub.code,
                "trace_code": deposit.trace_code,
                "status": deposit.status.value,
                "fill_level": hub.fill_level,
            },
        }
    )
    return DepositResult(
        deposit=DepositRead.model_validate(deposit),
        machine_action="accept_and_store" if accepted else "reject_and_return",
        user_message=f"Đã nhận chai, cộng {points} điểm" if accepted else reason or "Không đạt tiêu chuẩn",
    )


@router.get("/deposits", response_model=list[DepositRead])
def list_deposits(
    status: DepositStatus | None = None,
    hub_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Deposit]:
    query = select(Deposit).order_by(Deposit.created_at.desc()).limit(limit)
    if user.role == UserRole.RESIDENT:
        query = query.where(Deposit.user_id == user.id)
    if status:
        query = query.where(Deposit.status == status)
    if hub_id:
        query = query.where(Deposit.hub_id == hub_id)
    return list(db.scalars(query))


@router.get("/users/me/points", response_model=list[PointsTransactionRead])
def my_points(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PointsLedger]:
    return list(
        db.scalars(
            select(PointsLedger)
            .where(PointsLedger.user_id == user.id)
            .order_by(PointsLedger.created_at.desc())
            .limit(limit)
        )
    )
