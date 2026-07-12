from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from app.services import RedeemVoucherCommand


def test_redeem_voucher_command_is_immutable() -> None:
    user_id = uuid4()
    voucher_id = uuid4()

    command = RedeemVoucherCommand(
        user_id=user_id,
        voucher_id=voucher_id,
        redemption_code="REDEEM-REQUEST-001",
    )

    assert command.user_id == user_id
    assert command.voucher_id == voucher_id
    assert (
        command.redemption_code
        == "REDEEM-REQUEST-001"
    )

    with pytest.raises(FrozenInstanceError):
        setattr(
            command,
            "redemption_code",
            "REDEEM-REQUEST-002",
        )
