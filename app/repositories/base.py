from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(
        self,
        session: Session,
        model: type[ModelT],
    ) -> None:
        self.session = session
        self.model = model

    def get_by_id(self, record_id: UUID) -> ModelT | None:
        return self.session.get(self.model, record_id)

    def list_all(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ModelT]:
        if offset < 0:
            raise ValueError("offset must be non-negative")

        if limit <= 0:
            raise ValueError("limit must be positive")

        statement = (
            select(self.model)
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
