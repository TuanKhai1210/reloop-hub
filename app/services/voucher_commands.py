from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RedeemVoucherCommand:
    user_id: UUID
    voucher_id: UUID
    redemption_code: str
