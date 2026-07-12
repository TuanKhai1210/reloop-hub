from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    VoucherRedemption,
    VoucherRedemptionStatus,
)
from app.repositories.base import BaseRepository


class VoucherRedemptionRepository(
    BaseRepository[VoucherRedemption]
):
    def __init__(self, session: Session) -> None:
        super().__init__(session, VoucherRedemption)

    def get_by_code(
        self,
        redemption_code: str,
    ) -> VoucherRedemption | None:
        statement = select(VoucherRedemption).where(
            VoucherRedemption.redemption_code == redemption_code
        )

        return self.session.scalars(statement).one_or_none()

    def get_usable_by_code(
        self,
        redemption_code: str,
    ) -> VoucherRedemption | None:
        statement = select(VoucherRedemption).where(
            VoucherRedemption.redemption_code == redemption_code,
            VoucherRedemption.status
            == VoucherRedemptionStatus.ISSUED,
            or_(
                VoucherRedemption.expires_at.is_(None),
                VoucherRedemption.expires_at > func.now(),
            ),
        )

        return self.session.scalars(statement).one_or_none()

    def list_by_user(
        self,
        user_id: UUID,
        *,
        status: VoucherRedemptionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[VoucherRedemption]:
        self._validate_pagination(offset, limit)

        statement = select(VoucherRedemption).where(
            VoucherRedemption.user_id == user_id
        )

        if status is not None:
            statement = statement.where(
                VoucherRedemption.status == status
            )

        statement = (
            statement
            .order_by(
                VoucherRedemption.created_at.desc(),
                VoucherRedemption.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_by_voucher(
        self,
        voucher_id: UUID,
        *,
        status: VoucherRedemptionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[VoucherRedemption]:
        self._validate_pagination(offset, limit)

        statement = select(VoucherRedemption).where(
            VoucherRedemption.voucher_id == voucher_id
        )

        if status is not None:
            statement = statement.where(
                VoucherRedemption.status == status
            )

        statement = (
            statement
            .order_by(
                VoucherRedemption.created_at.desc(),
                VoucherRedemption.id.desc(),
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
