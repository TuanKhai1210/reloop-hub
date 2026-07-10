from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
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
    PointLedgerRepository,
    UserRepository,
    VoucherRedemptionRepository,
    VoucherRepository,
)


pytestmark = pytest.mark.integration


def create_test_user(
    db_session: Session,
    *,
    points_balance: int,
) -> User:
    token = uuid4().hex[:12].upper()

    return UserRepository(db_session).add(
        User(
            name="Voucher Flow Test User",
            phone=None,
            student_code=f"VOUCHER-USER-{token}",
            role=UserRole.USER,
            points_balance=points_balance,
            total_bottles_returned=0,
        )
    )


def create_test_voucher(
    db_session: Session,
    *,
    required_points: int = 50,
    quantity_available: int = 2,
    status: VoucherStatus = VoucherStatus.ACTIVE,
    valid_from: datetime | None = None,
    expires_at: datetime | None = None,
) -> Voucher:
    token = uuid4().hex[:12].upper()

    return VoucherRepository(db_session).add(
        Voucher(
            code=f"VOUCHER-{token}",
            name="Repository Test Voucher",
            partner_name="Test Canteen",
            description="Voucher flow integration test.",
            required_points=required_points,
            value_text="2,000 VND discount",
            quantity_available=quantity_available,
            status=status,
            valid_from=valid_from,
            expires_at=expires_at,
        )
    )


def redeem_voucher_contract(
    db_session: Session,
    *,
    user: User,
    voucher: Voucher,
    redemption_code: str,
) -> tuple[VoucherRedemption, PointLedger]:
    now = datetime.now(timezone.utc)

    if voucher.status != VoucherStatus.ACTIVE:
        raise ValueError("voucher is not active")

    if voucher.quantity_available <= 0:
        raise ValueError("voucher is out of stock")

    if (
        voucher.valid_from is not None
        and voucher.valid_from > now
    ):
        raise ValueError("voucher is not valid yet")

    if (
        voucher.expires_at is not None
        and voucher.expires_at <= now
    ):
        raise ValueError("voucher has expired")

    if user.points_balance < voucher.required_points:
        raise ValueError("insufficient points")

    redemption_repository = VoucherRedemptionRepository(
        db_session
    )
    ledger_repository = PointLedgerRepository(db_session)

    redemption = redemption_repository.add(
        VoucherRedemption(
            user_id=user.id,
            voucher_id=voucher.id,
            redemption_code=redemption_code,
            points_spent=voucher.required_points,
            status=VoucherRedemptionStatus.ISSUED,
            used_at=None,
            expires_at=now + timedelta(days=1),
        )
    )

    user.points_balance -= voucher.required_points
    voucher.quantity_available -= 1

    ledger = ledger_repository.add(
        PointLedger(
            user_id=user.id,
            source_type=PointSourceType.VOUCHER_REDEMPTION,
            source_id=redemption.id,
            points_change=-voucher.required_points,
            balance_after=user.points_balance,
            description=(
                f"Redeemed voucher {voucher.code}"
            ),
        )
    )

    db_session.flush()

    return redemption, ledger


def test_successful_voucher_redemption_flow(
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        points_balance=120,
    )
    voucher = create_test_voucher(
        db_session,
        required_points=50,
        quantity_available=2,
    )

    redemption_code = (
        f"REDEMPTION-{uuid4().hex[:12].upper()}"
    )

    redemption, ledger = redeem_voucher_contract(
        db_session,
        user=user,
        voucher=voucher,
        redemption_code=redemption_code,
    )

    user_id = user.id
    voucher_id = voucher.id
    redemption_id = redemption.id

    db_session.expire_all()

    stored_user = UserRepository(db_session).get_by_id(user_id)
    stored_voucher = VoucherRepository(db_session).get_by_id(
        voucher_id
    )
    stored_redemption = (
        VoucherRedemptionRepository(db_session).get_by_code(
            redemption_code
        )
    )
    usable_redemption = (
        VoucherRedemptionRepository(
            db_session
        ).get_usable_by_code(redemption_code)
    )
    stored_ledger = PointLedgerRepository(
        db_session
    ).get_by_source(
        PointSourceType.VOUCHER_REDEMPTION,
        redemption_id,
    )

    user_redemptions = VoucherRedemptionRepository(
        db_session
    ).list_by_user(
        user_id,
        status=VoucherRedemptionStatus.ISSUED,
    )

    assert stored_user is not None
    assert stored_user.points_balance == 70

    assert stored_voucher is not None
    assert stored_voucher.quantity_available == 1

    assert stored_redemption is not None
    assert stored_redemption.id == redemption_id
    assert stored_redemption.points_spent == 50
    assert stored_redemption.status == (
        VoucherRedemptionStatus.ISSUED
    )
    assert stored_redemption.used_at is None
    assert stored_redemption.expires_at is not None

    assert usable_redemption is not None
    assert usable_redemption.id == redemption_id

    assert len(user_redemptions) == 1
    assert user_redemptions[0].id == redemption_id

    assert stored_ledger is not None
    assert stored_ledger.id == ledger.id
    assert stored_ledger.points_change == -50
    assert stored_ledger.balance_after == 70
    assert stored_ledger.user_id == user_id


def test_redemption_rejected_when_points_are_insufficient(
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        points_balance=40,
    )
    voucher = create_test_voucher(
        db_session,
        required_points=50,
        quantity_available=2,
    )

    redemption_code = (
        f"INSUFFICIENT-{uuid4().hex[:12].upper()}"
    )

    with pytest.raises(
        ValueError,
        match="insufficient points",
    ):
        redeem_voucher_contract(
            db_session,
            user=user,
            voucher=voucher,
            redemption_code=redemption_code,
        )

    user_id = user.id
    voucher_id = voucher.id

    db_session.expire_all()

    stored_user = UserRepository(db_session).get_by_id(user_id)
    stored_voucher = VoucherRepository(db_session).get_by_id(
        voucher_id
    )
    stored_redemption = (
        VoucherRedemptionRepository(db_session).get_by_code(
            redemption_code
        )
    )
    ledger_entries = PointLedgerRepository(
        db_session
    ).list_by_user(user_id)

    assert stored_user is not None
    assert stored_user.points_balance == 40

    assert stored_voucher is not None
    assert stored_voucher.quantity_available == 2

    assert stored_redemption is None
    assert ledger_entries == []


def test_list_available_excludes_unavailable_vouchers(
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)

    available = create_test_voucher(
        db_session,
        quantity_available=2,
        status=VoucherStatus.ACTIVE,
        valid_from=now - timedelta(days=1),
        expires_at=now + timedelta(days=1),
    )

    inactive = create_test_voucher(
        db_session,
        quantity_available=2,
        status=VoucherStatus.INACTIVE,
    )

    out_of_stock = create_test_voucher(
        db_session,
        quantity_available=0,
        status=VoucherStatus.ACTIVE,
    )

    not_valid_yet = create_test_voucher(
        db_session,
        quantity_available=2,
        status=VoucherStatus.ACTIVE,
        valid_from=now + timedelta(days=1),
        expires_at=now + timedelta(days=2),
    )

    expired = create_test_voucher(
        db_session,
        quantity_available=2,
        status=VoucherStatus.ACTIVE,
        valid_from=now - timedelta(days=2),
        expires_at=now - timedelta(days=1),
    )

    available_codes = {
        voucher.code
        for voucher in VoucherRepository(
            db_session
        ).list_available(limit=1000)
    }

    assert available.code in available_codes
    assert inactive.code not in available_codes
    assert out_of_stock.code not in available_codes
    assert not_valid_yet.code not in available_codes
    assert expired.code not in available_codes


def test_duplicate_redemption_code_is_rejected(
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        points_balance=150,
    )
    voucher = create_test_voucher(
        db_session,
        required_points=50,
        quantity_available=3,
    )

    redemption_code = (
        f"DUPLICATE-{uuid4().hex[:12].upper()}"
    )

    first_redemption, _ = redeem_voucher_contract(
        db_session,
        user=user,
        voucher=voucher,
        redemption_code=redemption_code,
    )

    repository = VoucherRedemptionRepository(db_session)

    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            repository.add(
                VoucherRedemption(
                    user_id=user.id,
                    voucher_id=voucher.id,
                    redemption_code=redemption_code,
                    points_spent=50,
                    status=VoucherRedemptionStatus.ISSUED,
                    used_at=None,
                    expires_at=(
                        datetime.now(timezone.utc)
                        + timedelta(days=1)
                    ),
                )
            )

    stored_redemption = repository.get_by_code(
        redemption_code
    )
    user_redemptions = repository.list_by_user(user.id)

    assert stored_redemption is not None
    assert stored_redemption.id == first_redemption.id
    assert len(user_redemptions) == 1


def test_partial_redemption_failure_rolls_back_all_changes(
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session,
        points_balance=100,
    )
    voucher = create_test_voucher(
        db_session,
        required_points=50,
        quantity_available=2,
    )

    redemption_code = (
        f"ROLLBACK-{uuid4().hex[:12].upper()}"
    )
    redemption_id = None

    redemption_repository = VoucherRedemptionRepository(
        db_session
    )
    ledger_repository = PointLedgerRepository(db_session)

    with pytest.raises(
        RuntimeError,
        match="simulated downstream failure",
    ):
        with db_session.begin_nested():
            redemption = redemption_repository.add(
                VoucherRedemption(
                    user_id=user.id,
                    voucher_id=voucher.id,
                    redemption_code=redemption_code,
                    points_spent=50,
                    status=VoucherRedemptionStatus.ISSUED,
                    used_at=None,
                    expires_at=(
                        datetime.now(timezone.utc)
                        + timedelta(days=1)
                    ),
                )
            )
            redemption_id = redemption.id

            user.points_balance -= 50
            voucher.quantity_available -= 1

            ledger_repository.add(
                PointLedger(
                    user_id=user.id,
                    source_type=(
                        PointSourceType.VOUCHER_REDEMPTION
                    ),
                    source_id=redemption.id,
                    points_change=-50,
                    balance_after=user.points_balance,
                    description="Rollback test",
                )
            )

            db_session.flush()

            raise RuntimeError(
                "simulated downstream failure"
            )

    db_session.refresh(user)
    db_session.refresh(voucher)

    assert redemption_id is not None
    assert user.points_balance == 100
    assert voucher.quantity_available == 2

    assert redemption_repository.get_by_code(
        redemption_code
    ) is None

    assert ledger_repository.get_by_source(
        PointSourceType.VOUCHER_REDEMPTION,
        redemption_id,
    ) is None
