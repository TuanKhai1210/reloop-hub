from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
)
from app.repositories.base import BaseRepository


class MaterialBatchRepository(BaseRepository[MaterialBatch]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, MaterialBatch)

    def get_by_code(
        self,
        code: str,
    ) -> MaterialBatch | None:
        statement = select(MaterialBatch).where(
            MaterialBatch.code == code
        )

        return self.session.scalars(statement).one_or_none()

    def list_by_hub(
        self,
        hub_id: UUID,
        *,
        material_type: MaterialType | None = None,
        status: MaterialBatchStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[MaterialBatch]:
        self._validate_pagination(offset, limit)

        statement = select(MaterialBatch).where(
            MaterialBatch.hub_id == hub_id
        )

        if material_type is not None:
            statement = statement.where(
                MaterialBatch.material_type == material_type
            )

        if status is not None:
            statement = statement.where(
                MaterialBatch.status == status
            )

        statement = (
            statement
            .order_by(
                MaterialBatch.created_at.desc(),
                MaterialBatch.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_by_pickup(
        self,
        pickup_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[MaterialBatch]:
        self._validate_pagination(offset, limit)

        statement = (
            select(MaterialBatch)
            .where(MaterialBatch.pickup_id == pickup_id)
            .order_by(
                MaterialBatch.created_at.desc(),
                MaterialBatch.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_by_pickup_for_update(
        self,
        pickup_id: UUID,
    ) -> Sequence[MaterialBatch]:
        statement = (
            select(MaterialBatch)
            .where(MaterialBatch.pickup_id == pickup_id)
            .order_by(MaterialBatch.id)
            .with_for_update()
        )

        return self.session.scalars(statement).all()

    def list_ready_for_pickup(
        self,
        *,
        hub_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[MaterialBatch]:
        self._validate_pagination(offset, limit)

        statement = select(MaterialBatch).where(
            MaterialBatch.status
            == MaterialBatchStatus.READY_FOR_PICKUP
        )

        if hub_id is not None:
            statement = statement.where(
                MaterialBatch.hub_id == hub_id
            )

        statement = (
            statement
            .order_by(
                MaterialBatch.created_at,
                MaterialBatch.id,
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
