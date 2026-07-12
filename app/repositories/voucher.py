from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Voucher, VoucherStatus
from app.repositories.base import BaseRepository


class VoucherRepository(BaseRepository[Voucher]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Voucher)

    def get_by_code(
        self,
        code: str,
    ) -> Voucher | None:
        statement = select(Voucher).where(
            Voucher.code == code
        )

        return self.session.scalars(statement).one_or_none()

    def list_by_status(
        self,
        status: VoucherStatus,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Voucher]:
        self._validate_pagination(offset, limit)

        statement = (
            select(Voucher)
            .where(Voucher.status == status)
            .order_by(
                Voucher.required_points,
                Voucher.code,
            )
            .offset(offset)
            .limit(limit)
        )

        return self.session.scalars(statement).all()

    def list_available(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[Voucher]:
        self._validate_pagination(offset, limit)

        statement = (
            select(Voucher)
            .where(
                Voucher.status == VoucherStatus.ACTIVE,
                Voucher.quantity_available > 0,
                or_(
                    Voucher.valid_from.is_(None),
                    Voucher.valid_from <= func.now(),
                ),
                or_(
                    Voucher.expires_at.is_(None),
                    Voucher.expires_at > func.now(),
                ),
            )
            .order_by(
                Voucher.required_points,
                Voucher.code,
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
