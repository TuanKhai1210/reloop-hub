from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReturnSession, ReturnSessionStatus
from app.repositories.base import BaseRepository


class ReturnSessionRepository(BaseRepository[ReturnSession]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ReturnSession)

    def get_latest_open_by_user(
        self,
        user_id: UUID,
    ) -> ReturnSession | None:
        statement = (
            select(ReturnSession)
            .where(
                ReturnSession.user_id == user_id,
                ReturnSession.status == ReturnSessionStatus.OPEN,
            )
            .order_by(
                ReturnSession.created_at.desc(),
                ReturnSession.id.desc(),
            )
            .limit(1)
        )

        return self.session.scalars(statement).first()

    def list_by_user(
        self,
        user_id: UUID,
        *,
        status: ReturnSessionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ReturnSession]:
        self._validate_pagination(offset, limit)

        statement = select(ReturnSession).where(
            ReturnSession.user_id == user_id
        )

        if status is not None:
            statement = statement.where(
                ReturnSession.status == status
            )

        statement = (
            statement
            .order_by(
                ReturnSession.created_at.desc(),
                ReturnSession.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_by_hub(
        self,
        hub_id: UUID,
        *,
        status: ReturnSessionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ReturnSession]:
        self._validate_pagination(offset, limit)

        statement = select(ReturnSession).where(
            ReturnSession.hub_id == hub_id
        )

        if status is not None:
            statement = statement.where(
                ReturnSession.status == status
            )

        statement = (
            statement
            .order_by(
                ReturnSession.created_at.desc(),
                ReturnSession.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    @staticmethod
    def _validate_pagination(
        offset: int,
        limit: int,
    ) -> None:
        if offset < 0:
            raise ValueError("offset must be non-negative")

        if limit <= 0:
            raise ValueError("limit must be positive")

        if limit > BaseRepository.MAX_PAGE_SIZE:
            raise ValueError("limit must not exceed 1000")
