from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    VerificationEvent,
    VerificationLevel,
    VerificationResult,
)
from app.repositories.base import BaseRepository


class VerificationEventRepository(
    BaseRepository[VerificationEvent]
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, VerificationEvent)

    def get_latest_by_transaction(
        self,
        transaction_id: UUID,
    ) -> VerificationEvent | None:
        statement = (
            select(VerificationEvent)
            .where(
                VerificationEvent.transaction_id
                == transaction_id
            )
            .order_by(
                VerificationEvent.created_at.desc(),
                VerificationEvent.id.desc(),
            )
            .limit(1)
        )

        return self.session.scalars(statement).first()

    def list_by_transaction(
        self,
        transaction_id: UUID,
        *,
        verification_level: VerificationLevel | None = None,
        result: VerificationResult | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[VerificationEvent]:
        self._validate_pagination(offset, limit)

        statement = select(VerificationEvent).where(
            VerificationEvent.transaction_id == transaction_id
        )

        if verification_level is not None:
            statement = statement.where(
                VerificationEvent.verification_level
                == verification_level
            )

        if result is not None:
            statement = statement.where(
                VerificationEvent.result == result
            )

        statement = (
            statement
            .order_by(
                VerificationEvent.created_at.desc(),
                VerificationEvent.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_by_result(
        self,
        result: VerificationResult,
        *,
        verification_level: VerificationLevel | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[VerificationEvent]:
        self._validate_pagination(offset, limit)

        statement = select(VerificationEvent).where(
            VerificationEvent.result == result
        )

        if verification_level is not None:
            statement = statement.where(
                VerificationEvent.verification_level
                == verification_level
            )

        statement = (
            statement
            .order_by(
                VerificationEvent.created_at.desc(),
                VerificationEvent.id.desc(),
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
