from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api_errors import service_http_error
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.repositories import VoucherRepository
from app.schemas import (
    VoucherRead,
    VoucherRedeemRequest,
    VoucherRedemptionRead,
)
from app.services import (
    RedeemVoucherCommand,
    ServiceError,
    VoucherService,
)


router = APIRouter(prefix="/vouchers", tags=["Green Points"])


@router.get("", response_model=list[VoucherRead])
def list_vouchers(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list:
    return list(VoucherRepository(db).list_available(limit=1000))


@router.post(
    "/redeem",
    response_model=VoucherRedemptionRead,
    status_code=201,
)
def redeem_voucher(
    payload: VoucherRedeemRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return VoucherService(db).redeem_voucher(
            RedeemVoucherCommand(
                user_id=user.id,
                voucher_id=payload.voucher_id,
                redemption_code=(
                    f"REDEEM-{uuid4().hex[:16].upper()}"
                ),
            )
        )
    except ServiceError as error:
        raise service_http_error(error) from error
