from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import PointsLedger, User, UserRole
from app.schemas import PointsTransactionRead, RewardRedeem, UserAdminUpdate, UserRead


router = APIRouter(prefix="/users", tags=["User & rewards management"])


@router.get("", response_model=list[UserRead])
def list_users(
    role: UserRole | None = None,
    active: bool | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> list[User]:
    query = select(User).order_by(User.created_at.desc()).limit(limit)
    if role:
        query = query.where(User.role == role)
    if active is not None:
        query = query.where(User.is_active == active)
    return list(db.scalars(query))


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(UserRole.ADMIN)),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == actor.id and changes.get("is_active") is False:
        raise HTTPException(status_code=409, detail="Admin không thể tự khóa tài khoản đang đăng nhập")
    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/rewards/redeem", response_model=PointsTransactionRead, status_code=201)
def redeem_reward(
    payload: RewardRedeem,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PointsLedger:
    if user.points_balance < payload.points:
        raise HTTPException(status_code=409, detail="Số dư điểm không đủ")
    user.points_balance -= payload.points
    transaction = PointsLedger(
        user_id=user.id,
        points=-payload.points,
        transaction_type="redeem",
        description=(
            f"Đổi thưởng: {payload.reward_name}"
            + (f" qua {payload.payout_channel}" if payload.payout_channel and payload.payout_channel != "none" else "")
        ),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction
