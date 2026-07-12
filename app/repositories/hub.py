from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Hub, HubStatus
from app.repositories.base import BaseRepository


class HubRepository(BaseRepository[Hub]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Hub)

    def get_by_code(self, code: str) -> Hub | None:
        statement = select(Hub).where(Hub.code == code)

        return self.session.scalars(statement).one_or_none()

    def get_by_code_for_update(self, code: str) -> Hub | None:
        statement = (
            select(Hub)
            .where(Hub.code == code)
            .with_for_update()
        )
        return self.session.scalars(statement).one_or_none()

    def list_by_status(
        self,
        status: HubStatus,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Hub]:
        if offset < 0:
            raise ValueError("offset must be non-negative")

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = (
            select(Hub)
            .where(Hub.status == status)
            .order_by(Hub.code)
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()
