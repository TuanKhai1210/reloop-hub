from typing import Protocol

from app.models import MaterialType, VerificationLevel


class RewardPolicy(Protocol):
    def points_for_bottle(
        self,
        *,
        material_type: MaterialType,
        verification_level: VerificationLevel,
    ) -> int: ...


class FixedBottleRewardPolicy:
    """Server-owned MVP reward policy.

    Campaign bonuses and partner-funded multipliers can later be
    implemented behind the same interface without trusting client input.
    """

    POINTS_PER_BOTTLE = 10

    def points_for_bottle(
        self,
        *,
        material_type: MaterialType,
        verification_level: VerificationLevel,
    ) -> int:
        del verification_level

        if material_type not in {
            MaterialType.PET,
            MaterialType.HDPE,
        }:
            raise ValueError("unsupported reward material")

        return self.POINTS_PER_BOTTLE
