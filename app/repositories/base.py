from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    MAX_PAGE_SIZE = 1000

    def __init__(
        self,
        session: Session,
        model: type[ModelT],
    ) -> None:
        self.session = session
        self.model = model

    def get_by_id(self, record_id: UUID) -> ModelT | None:
        return self.session.get(self.model, record_id)

    def get_by_id_for_update(
        self,
        record_id: UUID,
    ) -> ModelT | None:
        primary_key = next(
            iter(self.model.__table__.primary_key.columns)
        )

        statement = (
            select(self.model)
            .where(primary_key == record_id)
            .with_for_update()
        )

        return self.session.scalars(
            statement
        ).one_or_none()

    def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelT]:
        self._validate_pagination(offset, limit)

        primary_key = next(
            iter(self.model.__table__.primary_key.columns)
        )

        statement = (
            select(self.model)
            .order_by(primary_key)
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)

        return entity

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)
        self.session.flush()

    @classmethod
    def _validate_pagination(
        cls,
        offset: int,
        limit: int,
    ) -> None:
        if offset < 0:
            raise ValueError("offset must be non-negative")

        if limit <= 0:
            raise ValueError("limit must be positive")

        if limit > cls.MAX_PAGE_SIZE:
            raise ValueError(
                f"limit must not exceed {cls.MAX_PAGE_SIZE}"
            )
