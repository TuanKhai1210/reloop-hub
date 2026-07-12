from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import (
    PointSourceType,
    User,
    UserRole,
    Voucher,
    VoucherRedemptionStatus,
    VoucherStatus,
)
from app.repositories import (
    PointLedgerRepository,
    UserRepository,
    VoucherRedemptionRepository,
    VoucherRepository,
)
from app.services import (
    ConflictError,
    EntityNotFoundError,
    InvalidStateError,
    RedeemVoucherCommand,
    VoucherService,
)


pytestmark = pytest.mark.integration


def create_user(
    session: Session,
    *,
    points_balance: int,
) -> User:
    token = uuid4().hex[:12].upper()

    return UserRepository(session).add(
        User(
            name="Voucher Service User",
            phone=None,
            student_code=f"SERVICE-USER-{token}",
            role=UserRole.USER,
            points_balance=points_balance,
            total_bottles_returned=0,
        )
    )


def create_voucher(
    session: Session,
    *,
    required_points: int = 50,
    quantity_available: int = 2,
    status: VoucherStatus = VoucherStatus.ACTIVE,
    valid_from: datetime | None = None,
    expires_at: datetime | None = None,
) -> Voucher:
    token = uuid4().hex[:12].upper()

    return VoucherRepository(session).add(
        Voucher(
            code=f"SERVICE-VOUCHER-{token}",
            name="Voucher Service Test",
            partner_name="Test Canteen",
            description="Voucher service integration test.",
            required_points=required_points,
            value_text="2,000 VND discount",
            quantity_available=quantity_available,
            status=status,
            valid_from=valid_from,
            expires_at=expires_at,
        )
    )


def create_command(
    *,
    user_id: UUID,
    voucher_id: UUID,
    prefix: str = "REDEEM",
) -> RedeemVoucherCommand:
    return RedeemVoucherCommand(
        user_id=user_id,
        voucher_id=voucher_id,
        redemption_code=(
            f"{prefix}-{uuid4().hex[:12].upper()}"
        ),
    )


def test_redeem_voucher_updates_all_records(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)

    user = create_user(
        db_session,
        points_balance=120,
    )

    voucher = create_voucher(
        db_session,
        required_points=50,
        quantity_available=2,
        valid_from=now - timedelta(hours=1),
        expires_at=now + timedelta(days=2),
    )

    command = create_command(
        user_id=user.id,
        voucher_id=voucher.id,
    )

    redemption = VoucherService(
        db_session
    ).redeem_voucher(command)

    user_id = user.id
    voucher_id = voucher.id
    redemption_id = redemption.id

    db_session.expire_all()

    stored_user = UserRepository(
        db_session
    ).get_by_id(user_id)

    stored_voucher = VoucherRepository(
        db_session
    ).get_by_id(voucher_id)

    stored_redemption = (
        VoucherRedemptionRepository(
            db_session
        ).get_by_code(command.redemption_code)
    )

    stored_ledger = PointLedgerRepository(
        db_session
    ).get_by_source(
        PointSourceType.VOUCHER_REDEMPTION,
        redemption_id,
    )

    assert stored_user is not None
    assert stored_user.points_balance == 70

    assert stored_voucher is not None
    assert stored_voucher.quantity_available == 1

    assert stored_redemption is not None
    assert stored_redemption.id == redemption_id
    assert stored_redemption.user_id == user_id
    assert stored_redemption.voucher_id == voucher_id
    assert stored_redemption.points_spent == 50
    assert (
        stored_redemption.status
        == VoucherRedemptionStatus.ISSUED
    )
    assert stored_redemption.used_at is None
    assert stored_redemption.expires_at is not None

    assert stored_ledger is not None
    assert stored_ledger.user_id == user_id
    assert stored_ledger.points_change == -50
    assert stored_ledger.balance_after == 70
    assert (
        stored_ledger.source_type
        == PointSourceType.VOUCHER_REDEMPTION
    )
    assert stored_ledger.source_id == redemption_id


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("inactive", "voucher is not active"),
        ("out_of_stock", "voucher is out of stock"),
        ("not_valid_yet", "voucher is not valid yet"),
        ("expired", "voucher has expired"),
    ],
)
def test_redeem_voucher_rejects_unavailable_voucher(
    db_session: Session,
    case: str,
    expected_error: str,
) -> None:
    now = datetime.now(UTC)

    user = create_user(
        db_session,
        points_balance=100,
    )

    voucher_options: dict[str, object] = {
        "required_points": 50,
        "quantity_available": 2,
        "status": VoucherStatus.ACTIVE,
        "valid_from": None,
        "expires_at": None,
    }

    if case == "inactive":
        voucher_options["status"] = (
            VoucherStatus.INACTIVE
        )
    elif case == "out_of_stock":
        voucher_options["quantity_available"] = 0
    elif case == "not_valid_yet":
        voucher_options["valid_from"] = (
            now + timedelta(days=1)
        )
        voucher_options["expires_at"] = (
            now + timedelta(days=2)
        )
    elif case == "expired":
        voucher_options["valid_from"] = (
            now - timedelta(days=2)
        )
        voucher_options["expires_at"] = (
            now - timedelta(days=1)
        )

    voucher = create_voucher(
        db_session,
        **voucher_options,
    )

    command = create_command(
        user_id=user.id,
        voucher_id=voucher.id,
        prefix="UNAVAILABLE",
    )

    with pytest.raises(
        InvalidStateError,
        match=expected_error,
    ):
        VoucherService(
            db_session
        ).redeem_voucher(command)

    db_session.refresh(user)
    db_session.refresh(voucher)

    assert user.points_balance == 100
    assert voucher.quantity_available == (
        voucher_options["quantity_available"]
    )

    assert (
        VoucherRedemptionRepository(
            db_session
        ).get_by_code(command.redemption_code)
        is None
    )

    assert PointLedgerRepository(
        db_session
    ).list_by_user(user.id) == []


def test_redeem_voucher_rejects_insufficient_points(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        points_balance=40,
    )

    voucher = create_voucher(
        db_session,
        required_points=50,
        quantity_available=2,
    )

    command = create_command(
        user_id=user.id,
        voucher_id=voucher.id,
        prefix="INSUFFICIENT",
    )

    with pytest.raises(
        InvalidStateError,
        match="insufficient points",
    ):
        VoucherService(
            db_session
        ).redeem_voucher(command)

    db_session.refresh(user)
    db_session.refresh(voucher)

    assert user.points_balance == 40
    assert voucher.quantity_available == 2


def test_redeem_voucher_rejects_empty_code(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        points_balance=100,
    )

    voucher = create_voucher(db_session)

    command = RedeemVoucherCommand(
        user_id=user.id,
        voucher_id=voucher.id,
        redemption_code="   ",
    )

    with pytest.raises(
        InvalidStateError,
        match="redemption code must not be empty",
    ):
        VoucherService(
            db_session
        ).redeem_voucher(command)

    db_session.refresh(user)
    db_session.refresh(voucher)

    assert user.points_balance == 100
    assert voucher.quantity_available == 2


def test_redeem_voucher_rejects_duplicate_code(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        points_balance=120,
    )

    voucher = create_voucher(
        db_session,
        required_points=50,
        quantity_available=2,
    )

    command = create_command(
        user_id=user.id,
        voucher_id=voucher.id,
        prefix="DUPLICATE",
    )

    service = VoucherService(db_session)

    first_redemption = service.redeem_voucher(command)

    with pytest.raises(
        ConflictError,
        match="redemption code already exists",
    ):
        service.redeem_voucher(command)

    db_session.refresh(user)
    db_session.refresh(voucher)

    redemptions = (
        VoucherRedemptionRepository(
            db_session
        ).list_by_user(user.id)
    )

    ledgers = PointLedgerRepository(
        db_session
    ).list_by_user(
        user.id,
        source_type=(
            PointSourceType.VOUCHER_REDEMPTION
        ),
    )

    assert user.points_balance == 70
    assert voucher.quantity_available == 1
    assert len(redemptions) == 1
    assert redemptions[0].id == first_redemption.id
    assert len(ledgers) == 1


def test_redeem_voucher_rejects_unknown_user(
    db_session: Session,
) -> None:
    voucher = create_voucher(db_session)

    command = create_command(
        user_id=uuid4(),
        voucher_id=voucher.id,
        prefix="UNKNOWN-USER",
    )

    with pytest.raises(
        EntityNotFoundError,
        match="user not found",
    ):
        VoucherService(
            db_session
        ).redeem_voucher(command)

    db_session.refresh(voucher)

    assert voucher.quantity_available == 2


def test_redeem_voucher_rejects_unknown_voucher(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        points_balance=100,
    )

    command = create_command(
        user_id=user.id,
        voucher_id=uuid4(),
        prefix="UNKNOWN-VOUCHER",
    )

    with pytest.raises(
        EntityNotFoundError,
        match="voucher not found",
    ):
        VoucherService(
            db_session
        ).redeem_voucher(command)

    db_session.refresh(user)

    assert user.points_balance == 100
