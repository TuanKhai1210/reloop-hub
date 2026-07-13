"""add bottle cleanliness score

Revision ID: d81f4a6b2c09
Revises: c3a90f17b6e2
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d81f4a6b2c09"
down_revision: str | None = "c3a90f17b6e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bottle_transactions",
        sa.Column(
            "cleanliness_score",
            sa.Numeric(5, 4),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_bottle_transactions_cleanliness_score_valid",
        "bottle_transactions",
        "cleanliness_score IS NULL OR "
        "(cleanliness_score >= 0 AND cleanliness_score <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_bottle_transactions_cleanliness_score_valid",
        "bottle_transactions",
        type_="check",
    )
    op.drop_column("bottle_transactions", "cleanliness_score")
