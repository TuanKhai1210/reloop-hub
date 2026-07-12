from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import PointLedger, User, UserRole
from app.schemas import UserRead


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserRead])
def list_users(
    role: UserRole | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.OPERATOR)
    ),
) -> list[User]:
    query = select(User).order_by(User.name, User.id).limit(limit)
    if role is not None:
        query = query.where(User.role == role)
    return list(db.scalars(query))


@router.get("/me/points")
def my_points(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    entries = db.scalars(
        select(PointLedger)
        .where(PointLedger.user_id == user.id)
        .order_by(PointLedger.created_at.desc(), PointLedger.id.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(entry.id),
            "points_change": entry.points_change,
            "balance_after": entry.balance_after,
            "source_type": entry.source_type.value,
            "description": entry.description,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
