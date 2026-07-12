from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    PointLedger,
    PointSourceType,
    User,
    UserRole,
    Voucher,
    VoucherRedemption,
    VoucherRedemptionStatus,
    VoucherStatus,
)
from app.repositories import (
    UserRepository,
    VoucherRedemptionRepository,
    VoucherRepository,
)
from app.services import (
    ConflictError,
    RedeemVoucherCommand,
    VoucherService,
)


pytestmark = pytest.mark.integration


def create_user(
    session: Session,
    *,
    token: str,
    index: int,
) -> User:
    return UserRepository(session).add(
        User(
            name=f"Voucher Race User {index}",
            phone=None,
            student_code=(
                f"VOUCHER-RACE-{token[:8]}-{index}"
            ),
            role=UserRole.USER,
            points_balance=100,
            total_bottles_returned=0,
        )
    )


def create_voucher(
    session: Session,
    *,
    token: str,
    index: int,
) -> Voucher:
    return VoucherRepository(session).add(
        Voucher(
            code=(
                f"VOUCHER-RACE-{token[:8]}-{index}"
            ),
            name=f"Voucher Race Test {index}",
            partner_name="Test Canteen",
            description="Concurrent voucher redemption.",
            required_points=50,
            value_text="2,000 VND discount",
            quantity_available=1,
            status=VoucherStatus.ACTIVE,
            valid_from=None,
            expires_at=None,
        )
    )


def test_concurrent_duplicate_redemption_code_returns_conflict(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()
    redemption_code = f"REDEMPTION-RACE-{token}"

    user_ids: list[UUID] = []
    voucher_ids: list[UUID] = []

    try:
        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as setup_session:
            with setup_session.begin():
                for index in range(2):
                    user = create_user(
                        setup_session,
                        token=token,
                        index=index,
                    )

                    voucher = create_voucher(
                        setup_session,
                        token=token,
                        index=index,
                    )

                    user_ids.append(user.id)
                    voucher_ids.append(voucher.id)

        commands = [
            RedeemVoucherCommand(
                user_id=user_ids[index],
                voucher_id=voucher_ids[index],
                redemption_code=redemption_code,
            )
            for index in range(2)
        ]

        lookup_barrier = Barrier(2)

        original_get_by_code = (
            VoucherRedemptionRepository.get_by_code
        )

        def synchronized_get_by_code(
            repository: VoucherRedemptionRepository,
            code: str,
        ) -> VoucherRedemption | None:
            redemption = original_get_by_code(
                repository,
                code,
            )

            if code == redemption_code:
                lookup_barrier.wait(timeout=10)

            return redemption

        monkeypatch.setattr(
            VoucherRedemptionRepository,
            "get_by_code",
            synchronized_get_by_code,
        )

        def run_redemption(
            command: RedeemVoucherCommand,
        ) -> str:
            with Session(
                bind=database_engine,
                expire_on_commit=False,
            ) as worker_session:
                try:
                    VoucherService(
                        worker_session
                    ).redeem_voucher(command)
                except ConflictError:
                    return "conflict"
                except IntegrityError:
                    return "integrity_error"

                return "success"

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:
            futures = [
                executor.submit(
                    run_redemption,
                    command,
                )
                for command in commands
            ]

            statuses = [
                future.result(timeout=20)
                for future in futures
            ]

        assert sorted(statuses) == [
            "conflict",
            "success",
        ]

        with Session(
            bind=database_engine
        ) as verification_session:
            stored_redemptions = list(
                verification_session.scalars(
                    select(VoucherRedemption).where(
                        VoucherRedemption.redemption_code
                        == redemption_code
                    )
                )
            )

            stored_users = list(
                verification_session.scalars(
                    select(User).where(
                        User.id.in_(user_ids)
                    )
                )
            )

            stored_vouchers = list(
                verification_session.scalars(
                    select(Voucher).where(
                        Voucher.id.in_(voucher_ids)
                    )
                )
            )

            redemption_ids = [
                redemption.id
                for redemption in stored_redemptions
            ]

            stored_ledgers = list(
                verification_session.scalars(
                    select(PointLedger).where(
                        PointLedger.source_type
                        == PointSourceType.VOUCHER_REDEMPTION,
                        PointLedger.source_id.in_(
                            redemption_ids
                        ),
                    )
                )
            )

            assert len(stored_redemptions) == 1

            stored_redemption = stored_redemptions[0]

            assert (
                stored_redemption.status
                == VoucherRedemptionStatus.ISSUED
            )
            assert stored_redemption.points_spent == 50

            assert len(stored_ledgers) == 1
            assert stored_ledgers[0].points_change == -50
            assert stored_ledgers[0].balance_after == 50

            assert sorted(
                user.points_balance
                for user in stored_users
            ) == [50, 100]

            assert sorted(
                voucher.quantity_available
                for voucher in stored_vouchers
            ) == [0, 1]

    finally:
        with Session(
            bind=database_engine
        ) as cleanup_session:
            with cleanup_session.begin():
                redemption_ids = list(
                    cleanup_session.scalars(
                        select(VoucherRedemption.id).where(
                            VoucherRedemption.redemption_code
                            == redemption_code
                        )
                    )
                )

                if redemption_ids:
                    cleanup_session.execute(
                        delete(PointLedger).where(
                            PointLedger.source_type
                            == (
                                PointSourceType
                                .VOUCHER_REDEMPTION
                            ),
                            PointLedger.source_id.in_(
                                redemption_ids
                            ),
                        )
                    )

                    cleanup_session.execute(
                        delete(VoucherRedemption).where(
                            VoucherRedemption.id.in_(
                                redemption_ids
                            )
                        )
                    )

                if user_ids:
                    cleanup_session.execute(
                        delete(User).where(
                            User.id.in_(user_ids)
                        )
                    )

                if voucher_ids:
                    cleanup_session.execute(
                        delete(Voucher).where(
                            Voucher.id.in_(voucher_ids)
                        )
                    )
