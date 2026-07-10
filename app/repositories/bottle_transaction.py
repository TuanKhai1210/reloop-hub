from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BottleTransaction, BottleTransactionStatus
from app.repositories.base import BaseRepository


class BottleTransactionRepository(
    BaseRepository[BottleTransaction]
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, BottleTransaction)

    def get_by_code(
        self,
        code: str,
    ) -> BottleTransaction | None:
        statement = select(BottleTransaction).where(
            BottleTransaction.code == code
        )

        return self.session.scalars(statement).one_or_none()

    def list_by_session(
        self,
        session_id: UUID,
        *,
        status: BottleTransactionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[BottleTransaction]:
        self._validate_pagination(offset, limit)

        statement = select(BottleTransaction).where(
            BottleTransaction.session_id == session_id
        )

        if status is not None:
            statement = statement.where(
                BottleTransaction.status == status
            )

        statement = (
            statement
            .order_by(
                BottleTransaction.created_at.desc(),
                BottleTransaction.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_by_batch(
        self,
        batch_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[BottleTransaction]:
        self._validate_pagination(offset, limit)

        statement = (
            select(BottleTransaction)
            .where(BottleTransaction.batch_id == batch_id)
            .order_by(
                BottleTransaction.created_at.desc(),
                BottleTransaction.id.desc(),
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
