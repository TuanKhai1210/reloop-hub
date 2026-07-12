from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_errors import service_http_error
from app.core.database import get_db
from app.dependencies import get_current_user, verify_device_key
from app.models import BottleTransaction, BottleTransactionStatus, User
from app.realtime import hub_manager
from app.schemas import DepositInspection, DepositRead, DepositResult
from app.services import DepositService, InspectBottleCommand, ServiceError


router = APIRouter(prefix="/deposits", tags=["Bottle returns"])


@router.post("/inspect", response_model=DepositResult, status_code=201)
async def inspect_deposit(
    payload: DepositInspection,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
) -> DepositResult:
    try:
        transaction = DepositService(db).inspect_bottle(
            InspectBottleCommand(
                user_id=payload.user_id,
                hub_code=payload.hub_code,
                material_type=payload.material_type,
                weight_gram=payload.weight_g,
                ai_confidence=payload.ai_confidence,
                cleanliness_score=payload.cleanliness_score,
                liquid_detected=payload.liquid_detected,
                foreign_object_detected=(
                    payload.foreign_object_detected
                ),
            )
        )
    except ServiceError as error:
        raise service_http_error(error) from error

    accepted = (
        transaction.status == BottleTransactionStatus.ACCEPTED
    )
    await hub_manager.broadcast(
        {
            "event": "deposit.inspected",
            "data": {
                "hub_code": payload.hub_code,
                "trace_code": transaction.code,
                "status": transaction.status.value,
            },
        }
    )
    return DepositResult(
        deposit=DepositRead.model_validate(transaction),
        machine_action=(
            "accept_and_store" if accepted else "reject_and_return"
        ),
        user_message=(
            f"Bottle accepted, +{transaction.points_awarded} points"
            if accepted
            else f"Bottle rejected: {transaction.reject_reason.value}"
        ),
    )


@router.get("", response_model=list[DepositRead])
def list_deposits(
    status: BottleTransactionStatus | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BottleTransaction]:
    query = (
        select(BottleTransaction)
        .order_by(BottleTransaction.created_at.desc())
        .limit(limit)
    )
    if user.role.value == "USER":
        from app.models import ReturnSession

        query = query.join(ReturnSession).where(
            ReturnSession.user_id == user.id
        )
    if status is not None:
        query = query.where(BottleTransaction.status == status)
    return list(db.scalars(query))
