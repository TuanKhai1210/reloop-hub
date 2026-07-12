from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Pickup, PickupStatus
from app.repositories.base import BaseRepository


class PickupRepository(BaseRepository[Pickup]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Pickup)

    def get_by_code(
        self,
        code: str,
    ) -> Pickup | None:
        statement = select(Pickup).where(
            Pickup.code == code
        )

        return self.session.scalars(statement).one_or_none()

    def list_by_hub(
        self,
        hub_id: UUID,
        *,
        status: PickupStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Pickup]:
        self._validate_pagination(offset, limit)

        statement = select(Pickup).where(
            Pickup.hub_id == hub_id
        )

        if status is not None:
            statement = statement.where(
                Pickup.status == status
            )

        statement = (
            statement
            .order_by(
                Pickup.scheduled_at.desc(),
                Pickup.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_by_driver(
        self,
        driver_id: UUID,
        *,
        status: PickupStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Pickup]:
        self._validate_pagination(offset, limit)

        statement = select(Pickup).where(
            Pickup.driver_id == driver_id
        )

        if status is not None:
            statement = statement.where(
                Pickup.status == status
            )

        statement = (
            statement
            .order_by(
                Pickup.scheduled_at.desc(),
                Pickup.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_active(
        self,
        *,
        hub_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Pickup]:
        self._validate_pagination(offset, limit)

        statement = select(Pickup).where(
            Pickup.status.in_(
                [
                    PickupStatus.PLANNED,
                    PickupStatus.IN_PROGRESS,
                ]
            )
        )

        if hub_id is not None:
            statement = statement.where(
                Pickup.hub_id == hub_id
            )

        statement = (
            statement
            .order_by(
                Pickup.scheduled_at,
                Pickup.id,
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
