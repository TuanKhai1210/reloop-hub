from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import (
    PointLedger,
    PointSourceType,
    User,
    UserRole,
    Voucher,
    VoucherRedemption,
    VoucherStatus,
)
from app.repositories import (
    UserRepository,
    VoucherRepository,
)
from app.services import (
    InvalidStateError,
    RedeemVoucherCommand,
    VoucherService,
)


pytestmark = pytest.mark.integration


def create_user(
    session: Session,
    *,
    token: str,
    index: int,
    points_balance: int,
) -> User:
    return UserRepository(session).add(
        User(
            name=f"Voucher Hardening User {index}",
            phone=None,
            student_code=(
                f"VOUCHER-HARD-{token[:8]}-{index}"
            ),
            role=UserRole.USER,
            points_balance=points_balance,
            total_bottles_returned=0,
        )
    )


def create_voucher(
    session: Session,
    *,
    token: str,
    index: int,
    required_points: int = 50,
    quantity_available: int = 1,
) -> Voucher:
    return VoucherRepository(session).add(
        Voucher(
            code=(
                f"VOUCHER-HARD-{token[:8]}-{index}"
            ),
            name=f"Voucher Hardening {index}",
            partner_name="Test Canteen",
            description="Voucher hardening test.",
            required_points=required_points,
            value_text="2,000 VND discount",
            quantity_available=quantity_available,
            status=VoucherStatus.ACTIVE,
            valid_from=None,
            expires_at=None,
        )
    )


def cleanup_voucher_data(
    database_engine: Engine,
    *,
    redemption_codes: list[str],
    user_ids: list[UUID],
    voucher_ids: list[UUID],
) -> None:
    with Session(
        bind=database_engine
    ) as cleanup_session:
        with cleanup_session.begin():
            redemption_ids = list(
                cleanup_session.scalars(
                    select(VoucherRedemption.id).where(
                        VoucherRedemption.redemption_code.in_(
                            redemption_codes
                        )
                    )
                )
            )

            if redemption_ids:
                cleanup_session.execute(
                    delete(PointLedger).where(
                        PointLedger.source_type
                        == PointSourceType.VOUCHER_REDEMPTION,
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


def test_concurrent_redemptions_do_not_exceed_stock(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()

    redemption_codes = [
        f"STOCK-RACE-{token}-{index}"
        for index in range(2)
    ]

    user_ids: list[UUID] = []
    voucher_ids: list[UUID] = []

    try:
        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as setup_session:
            with setup_session.begin():
                voucher = create_voucher(
                    setup_session,
                    token=token,
                    index=0,
                    quantity_available=1,
                )

                voucher_id = voucher.id
                voucher_ids.append(voucher_id)

                for index in range(2):
                    user = create_user(
                        setup_session,
                        token=token,
                        index=index,
                        points_balance=100,
                    )

                    user_ids.append(user.id)

        commands = [
            RedeemVoucherCommand(
                user_id=user_ids[index],
                voucher_id=voucher_id,
                redemption_code=(
                    redemption_codes[index]
                ),
            )
            for index in range(2)
        ]

        lock_barrier = Barrier(2)

        original_voucher_lock = (
            VoucherRepository.get_by_id_for_update
        )

        def synchronized_voucher_lock(
            repository: VoucherRepository,
            record_id: UUID,
        ) -> Voucher | None:
            if record_id == voucher_id:
                lock_barrier.wait(timeout=10)

            return original_voucher_lock(
                repository,
                record_id,
            )

        monkeypatch.setattr(
            VoucherRepository,
            "get_by_id_for_update",
            synchronized_voucher_lock,
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
                except InvalidStateError as error:
                    if str(error) == "voucher is out of stock":
                        return "out_of_stock"

                    raise

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
            "out_of_stock",
            "success",
        ]

        with Session(
            bind=database_engine
        ) as verification_session:
            stored_redemptions = list(
                verification_session.scalars(
                    select(VoucherRedemption).where(
                        VoucherRedemption.redemption_code.in_(
                            redemption_codes
                        )
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

            stored_voucher = VoucherRepository(
                verification_session
            ).get_by_id(voucher_id)

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
            assert len(stored_ledgers) == 1

            assert stored_voucher is not None
            assert stored_voucher.quantity_available == 0

            assert sorted(
                user.points_balance
                for user in stored_users
            ) == [50, 100]

    finally:
        cleanup_voucher_data(
            database_engine,
            redemption_codes=redemption_codes,
            user_ids=user_ids,
            voucher_ids=voucher_ids,
        )


def test_concurrent_redemptions_do_not_overspend_points(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()

    redemption_codes = [
        f"POINTS-RACE-{token}-{index}"
        for index in range(2)
    ]

    user_ids: list[UUID] = []
    voucher_ids: list[UUID] = []

    try:
        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as setup_session:
            with setup_session.begin():
                user = create_user(
                    setup_session,
                    token=token,
                    index=0,
                    points_balance=50,
                )

                user_id = user.id
                user_ids.append(user_id)

                for index in range(2):
                    voucher = create_voucher(
                        setup_session,
                        token=token,
                        index=index,
                        required_points=50,
                        quantity_available=1,
                    )

                    voucher_ids.append(voucher.id)

        commands = [
            RedeemVoucherCommand(
                user_id=user_id,
                voucher_id=voucher_ids[index],
                redemption_code=(
                    redemption_codes[index]
                ),
            )
            for index in range(2)
        ]

        lock_barrier = Barrier(2)

        original_user_lock = (
            UserRepository.get_by_id_for_update
        )

        def synchronized_user_lock(
            repository: UserRepository,
            record_id: UUID,
        ) -> User | None:
            if record_id == user_id:
                lock_barrier.wait(timeout=10)

            return original_user_lock(
                repository,
                record_id,
            )

        monkeypatch.setattr(
            UserRepository,
            "get_by_id_for_update",
            synchronized_user_lock,
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
                except InvalidStateError as error:
                    if str(error) == "insufficient points":
                        return "insufficient_points"

                    raise

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
            "insufficient_points",
            "success",
        ]

        with Session(
            bind=database_engine
        ) as verification_session:
            stored_user = UserRepository(
                verification_session
            ).get_by_id(user_id)

            stored_vouchers = list(
                verification_session.scalars(
                    select(Voucher).where(
                        Voucher.id.in_(voucher_ids)
                    )
                )
            )

            stored_redemptions = list(
                verification_session.scalars(
                    select(VoucherRedemption).where(
                        VoucherRedemption.redemption_code.in_(
                            redemption_codes
                        )
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

            assert stored_user is not None
            assert stored_user.points_balance == 0

            assert len(stored_redemptions) == 1
            assert len(stored_ledgers) == 1

            assert sorted(
                voucher.quantity_available
                for voucher in stored_vouchers
            ) == [0, 1]

    finally:
        cleanup_voucher_data(
            database_engine,
            redemption_codes=redemption_codes,
            user_ids=user_ids,
            voucher_ids=voucher_ids,
        )


def test_redemption_rolls_back_when_ledger_insert_fails(
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = uuid4().hex.upper()
    redemption_code = f"ROLLBACK-{token}"

    user_ids: list[UUID] = []
    voucher_ids: list[UUID] = []

    try:
        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as setup_session:
            with setup_session.begin():
                user = create_user(
                    setup_session,
                    token=token,
                    index=0,
                    points_balance=100,
                )

                voucher = create_voucher(
                    setup_session,
                    token=token,
                    index=0,
                    required_points=50,
                    quantity_available=2,
                )

                user_id = user.id
                voucher_id = voucher.id

                user_ids.append(user_id)
                voucher_ids.append(voucher_id)

        command = RedeemVoucherCommand(
            user_id=user_id,
            voucher_id=voucher_id,
            redemption_code=redemption_code,
        )

        with Session(
            bind=database_engine,
            expire_on_commit=False,
        ) as service_session:
            service = VoucherService(service_session)

            def fail_ledger_insert(
                _ledger: PointLedger,
            ) -> PointLedger:
                raise RuntimeError(
                    "forced voucher ledger failure"
                )

            monkeypatch.setattr(
                service.point_ledger_repository,
                "add",
                fail_ledger_insert,
            )

            with pytest.raises(
                RuntimeError,
                match="forced voucher ledger failure",
            ):
                service.redeem_voucher(command)

            assert not service_session.in_transaction()

        with Session(
            bind=database_engine
        ) as verification_session:
            stored_user = UserRepository(
                verification_session
            ).get_by_id(user_id)

            stored_voucher = VoucherRepository(
                verification_session
            ).get_by_id(voucher_id)

            stored_redemption = (
                verification_session.scalars(
                    select(VoucherRedemption).where(
                        VoucherRedemption.redemption_code
                        == redemption_code
                    )
                ).one_or_none()
            )

            stored_ledgers = list(
                verification_session.scalars(
                    select(PointLedger).where(
                        PointLedger.user_id == user_id,
                        PointLedger.source_type
                        == PointSourceType.VOUCHER_REDEMPTION,
                    )
                )
            )

            assert stored_user is not None
            assert stored_user.points_balance == 100

            assert stored_voucher is not None
            assert stored_voucher.quantity_available == 2

            assert stored_redemption is None
            assert stored_ledgers == []

    finally:
        cleanup_voucher_data(
            database_engine,
            redemption_codes=[redemption_code],
            user_ids=user_ids,
            voucher_ids=voucher_ids,
        )
