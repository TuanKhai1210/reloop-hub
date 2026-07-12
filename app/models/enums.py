from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    DRIVER = "DRIVER"
    OPERATOR = "OPERATOR"
    RECYCLER = "RECYCLER"


class MaterialType(StrEnum):
    PET = "PET"
    HDPE = "HDPE"
    UNKNOWN = "UNKNOWN"


class HubStatus(StrEnum):
    ACTIVE = "ACTIVE"
    NEAR_FULL = "NEAR_FULL"
    FULL = "FULL"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class ReturnSessionStatus(StrEnum):
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BottleTransactionStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class RejectReason(StrEnum):
    WRONG_SLOT = "WRONG_SLOT"
    BOTTLE_HAS_LIQUID = "BOTTLE_HAS_LIQUID"
    DIRTY_BOTTLE = "DIRTY_BOTTLE"
    UNSUPPORTED_MATERIAL = "UNSUPPORTED_MATERIAL"
    INVALID_SAMPLE_CODE = "INVALID_SAMPLE_CODE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    HUB_FULL = "HUB_FULL"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class VerificationLevel(StrEnum):
    LEVEL_1 = "LEVEL_1"
    LEVEL_2 = "LEVEL_2"
    LEVEL_3 = "LEVEL_3"


class CleanlinessStatus(StrEnum):
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    UNKNOWN = "UNKNOWN"


class PointSourceType(StrEnum):
    BOTTLE_RETURN = "BOTTLE_RETURN"
    BONUS = "BONUS"
    VOUCHER_REDEMPTION = "VOUCHER_REDEMPTION"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"


class VoucherStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class VoucherRedemptionStatus(StrEnum):
    ISSUED = "ISSUED"
    USED = "USED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class MaterialBatchStatus(StrEnum):
    STORING = "STORING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    PICKED_UP = "PICKED_UP"
    RECEIVED = "RECEIVED"


class PickupStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class VerificationResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class RouteStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TraceStage(StrEnum):
    DEPOSITED = "DEPOSITED"
    HUB_STORED = "HUB_STORED"
    PICKED_UP = "PICKED_UP"
    RECEIVED = "RECEIVED"
    REJECTED = "REJECTED"
