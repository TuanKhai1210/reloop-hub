from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PointLedger, PointSourceType
from app.repositories.base import BaseRepository


class PointLedgerRepository(BaseRepository[PointLedger]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PointLedger)

    def get_by_source(
        self,
        source_type: PointSourceType,
        source_id: UUID,
    ) -> PointLedger | None:
        statement = select(PointLedger).where(
            PointLedger.source_type == source_type,
            PointLedger.source_id == source_id,
        )

        return self.session.scalars(statement).one_or_none()

    def get_latest_by_user(
        self,
        user_id: UUID,
    ) -> PointLedger | None:
        statement = (
            select(PointLedger)
            .where(PointLedger.user_id == user_id)
            .order_by(
                PointLedger.created_at.desc(),
                PointLedger.id.desc(),
            )
            .limit(1)
        )

        return self.session.scalars(statement).first()

    def list_by_user(
        self,
        user_id: UUID,
        *,
        source_type: PointSourceType | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[PointLedger]:
        self._validate_pagination(offset, limit)

        statement = select(PointLedger).where(
            PointLedger.user_id == user_id
        )

        if source_type is not None:
            statement = statement.where(
                PointLedger.source_type == source_type
            )

        statement = (
            statement
            .order_by(
                PointLedger.created_at.desc(),
                PointLedger.id.desc(),
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
