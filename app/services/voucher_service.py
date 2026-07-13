from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    PointLedger,
    PointSourceType,
    VoucherRedemption,
    VoucherRedemptionStatus,
    VoucherStatus,
)
from app.repositories import (
    PointLedgerRepository,
    UserRepository,
    VoucherRedemptionRepository,
    VoucherRepository,
)
from app.services.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
)
from app.services.voucher_commands import (
    RedeemVoucherCommand,
)


class VoucherService:
    REDEMPTION_VALIDITY = timedelta(days=1)

    REDEMPTION_CODE_UNIQUE_CONSTRAINT = (
        "uq_voucher_redemptions_redemption_code"
    )

    def __init__(self, session: Session) -> None:
        self.session = session

        self.user_repository = UserRepository(session)
        self.voucher_repository = VoucherRepository(session)

        self.voucher_redemption_repository = (
            VoucherRedemptionRepository(session)
        )

        self.point_ledger_repository = (
            PointLedgerRepository(session)
        )

    def redeem_voucher(
        self,
        command: RedeemVoucherCommand,
    ) -> VoucherRedemption:
        if self.session.in_transaction():
            return (
                self._redeem_voucher_with_conflict_mapping(
                    command
                )
            )

        with self.session.begin():
            return (
                self._redeem_voucher_with_conflict_mapping(
                    command
                )
            )

    def use_redemption(self, redemption_code: str) -> VoucherRedemption:
        if self.session.in_transaction():
            return self._use_redemption(redemption_code)
        with self.session.begin():
            return self._use_redemption(redemption_code)

    def _use_redemption(self, redemption_code: str) -> VoucherRedemption:
        normalized_code = redemption_code.strip()
        if not normalized_code:
            raise InvalidStateError("redemption code must not be empty")
        redemption = self.session.scalar(
            select(VoucherRedemption)
            .where(
                VoucherRedemption.redemption_code == normalized_code
            )
            .with_for_update()
        )
        if redemption is None:
            raise EntityNotFoundError("voucher redemption not found")
        if redemption.status != VoucherRedemptionStatus.ISSUED:
            raise InvalidStateError("voucher redemption is not usable")
        now = datetime.now(UTC)
        if (
            redemption.expires_at is not None
            and redemption.expires_at <= now
        ):
            raise InvalidStateError("voucher redemption has expired")
        redemption.status = VoucherRedemptionStatus.USED
        redemption.used_at = now
        self.session.flush()
        return redemption

    def _redeem_voucher_with_conflict_mapping(
        self,
        command: RedeemVoucherCommand,
    ) -> VoucherRedemption:
        try:
            with self.session.begin_nested():
                return self._redeem_voucher(command)
        except IntegrityError as error:
            if self._is_redemption_code_conflict(error):
                raise ConflictError(
                    "redemption code already exists"
                ) from error

            raise

    @classmethod
    def _is_redemption_code_conflict(
        cls,
        error: IntegrityError,
    ) -> bool:
        diagnostic = getattr(
            error.orig,
            "diag",
            None,
        )

        constraint_name = getattr(
            diagnostic,
            "constraint_name",
            None,
        )

        sqlstate = getattr(
            error.orig,
            "sqlstate",
            None,
        )

        return (
            sqlstate == "23505"
            and constraint_name
            == cls.REDEMPTION_CODE_UNIQUE_CONSTRAINT
        )

    def _redeem_voucher(
        self,
        command: RedeemVoucherCommand,
    ) -> VoucherRedemption:
        redemption_code = command.redemption_code.strip()

        if not redemption_code:
            raise InvalidStateError(
                "redemption code must not be empty"
            )

        existing_redemption = (
            self.voucher_redemption_repository
            .get_by_code(redemption_code)
        )

        if existing_redemption is not None:
            raise ConflictError(
                "redemption code already exists"
            )

        user = self.user_repository.get_by_id_for_update(
            command.user_id
        )

        if user is None:
            raise EntityNotFoundError("user not found")

        voucher = (
            self.voucher_repository
            .get_by_id_for_update(command.voucher_id)
        )

        if voucher is None:
            raise EntityNotFoundError("voucher not found")

        now = datetime.now(UTC)

        if voucher.status != VoucherStatus.ACTIVE:
            raise InvalidStateError(
                "voucher is not active"
            )

        if voucher.quantity_available <= 0:
            raise InvalidStateError(
                "voucher is out of stock"
            )

        if (
            voucher.valid_from is not None
            and voucher.valid_from > now
        ):
            raise InvalidStateError(
                "voucher is not valid yet"
            )

        if (
            voucher.expires_at is not None
            and voucher.expires_at <= now
        ):
            raise InvalidStateError(
                "voucher has expired"
            )

        if user.points_balance < voucher.required_points:
            raise InvalidStateError(
                "insufficient points"
            )

        redemption = (
            self.voucher_redemption_repository.add(
                VoucherRedemption(
                    user_id=user.id,
                    voucher_id=voucher.id,
                    redemption_code=redemption_code,
                    points_spent=voucher.required_points,
                    status=(
                        VoucherRedemptionStatus.ISSUED
                    ),
                    used_at=None,
                    expires_at=(
                        now + self.REDEMPTION_VALIDITY
                    ),
                )
            )
        )

        user.points_balance -= voucher.required_points
        voucher.quantity_available -= 1

        self.point_ledger_repository.add(
            PointLedger(
                user_id=user.id,
                source_type=(
                    PointSourceType.VOUCHER_REDEMPTION
                ),
                source_id=redemption.id,
                points_change=-voucher.required_points,
                balance_after=user.points_balance,
                description=(
                    f"Redeemed voucher {voucher.code}"
                ),
            )
        )

        self.session.flush()

        return redemption
