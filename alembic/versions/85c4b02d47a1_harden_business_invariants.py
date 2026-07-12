"""harden business invariants

Revision ID: 85c4b02d47a1
Revises: 1562e08ca875
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op


revision: str = "85c4b02d47a1"
down_revision: str | Sequence[str] | None = "1562e08ca875"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_users_points_balance_non_negative",
        "users",
        "points_balance >= 0",
    )
    op.create_check_constraint(
        "ck_users_bottles_returned_non_negative",
        "users",
        "total_bottles_returned >= 0",
    )
    op.create_check_constraint(
        "ck_return_sessions_status_time_consistent",
        "return_sessions",
        "(status = 'OPEN' AND finished_at IS NULL) OR "
        "(status IN ('COMPLETED', 'CANCELLED') "
        "AND finished_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_bottle_transactions_outcome_consistent",
        "bottle_transactions",
        "(status = 'ACCEPTED' AND batch_id IS NOT NULL "
        "AND reject_reason IS NULL) OR "
        "(status = 'REJECTED' AND batch_id IS NULL "
        "AND reject_reason IS NOT NULL AND points_awarded = 0)",
    )
    op.create_check_constraint(
        "ck_material_batches_pickup_consistent",
        "material_batches",
        "(status = 'STORING' AND pickup_id IS NULL) OR "
        "status = 'READY_FOR_PICKUP' OR "
        "(status IN ('PICKED_UP', 'RECEIVED') "
        "AND pickup_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_pickups_status_time_consistent",
        "pickups",
        "(status = 'PLANNED' AND started_at IS NULL "
        "AND completed_at IS NULL) OR "
        "(status = 'IN_PROGRESS' AND started_at IS NOT NULL "
        "AND completed_at IS NULL) OR "
        "(status = 'COMPLETED' AND started_at IS NOT NULL "
        "AND completed_at IS NOT NULL) OR "
        "(status = 'CANCELLED' AND completed_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_voucher_redemptions_usage_consistent",
        "voucher_redemptions",
        "(status = 'USED' AND used_at IS NOT NULL) OR "
        "(status <> 'USED' AND used_at IS NULL)",
    )

    op.drop_constraint(
        "fk_material_batches_pickup_id_pickups",
        "material_batches",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_material_batches_pickup_id_pickups",
        "material_batches",
        "pickups",
        ["pickup_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "fk_pickups_driver_id_users",
        "pickups",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_pickups_driver_id_users",
        "pickups",
        "users",
        ["driver_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "fk_verification_events_transaction_id_bottle_transactions",
        "verification_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_verification_events_transaction_id_bottle_transactions",
        "verification_events",
        "bottle_transactions",
        ["transaction_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_verification_events_transaction_id_bottle_transactions",
        "verification_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_verification_events_transaction_id_bottle_transactions",
        "verification_events",
        "bottle_transactions",
        ["transaction_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "fk_pickups_driver_id_users",
        "pickups",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_pickups_driver_id_users",
        "pickups",
        "users",
        ["driver_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "fk_material_batches_pickup_id_pickups",
        "material_batches",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_material_batches_pickup_id_pickups",
        "material_batches",
        "pickups",
        ["pickup_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "ck_voucher_redemptions_usage_consistent",
        "voucher_redemptions",
        type_="check",
    )
    op.drop_constraint(
        "ck_pickups_status_time_consistent",
        "pickups",
        type_="check",
    )
    op.drop_constraint(
        "ck_material_batches_pickup_consistent",
        "material_batches",
        type_="check",
    )
    op.drop_constraint(
        "ck_bottle_transactions_outcome_consistent",
        "bottle_transactions",
        type_="check",
    )
    op.drop_constraint(
        "ck_return_sessions_status_time_consistent",
        "return_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_users_bottles_returned_non_negative",
        "users",
        type_="check",
    )
    op.drop_constraint(
        "ck_users_points_balance_non_negative",
        "users",
        type_="check",
    )
