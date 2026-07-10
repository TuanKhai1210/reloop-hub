from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def get_by_phone(self, phone: str) -> User | None:
        statement = select(User).where(User.phone == phone)

        return self.session.scalars(statement).one_or_none()

    def get_by_student_code(
        self,
        student_code: str,
    ) -> User | None:
        statement = select(User).where(
            User.student_code == student_code
        )

        return self.session.scalars(statement).one_or_none()

    def list_by_role(
        self,
        role: UserRole,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[User]:
        if offset < 0:
            raise ValueError("offset must be non-negative")

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = (
            select(User)
            .where(User.role == role)
            .order_by(User.name)
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()
