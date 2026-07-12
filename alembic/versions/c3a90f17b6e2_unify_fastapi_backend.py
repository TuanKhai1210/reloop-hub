"""unify FastAPI backend with PostgreSQL domain

Revision ID: c3a90f17b6e2
Revises: 85c4b02d47a1
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c3a90f17b6e2"
down_revision: str | Sequence[str] | None = "85c4b02d47a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


route_status_enum = postgresql.ENUM(
    "PLANNED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
    name="route_status_enum",
    create_type=False,
)
trace_stage_enum = postgresql.ENUM(
    "DEPOSITED",
    "HUB_STORED",
    "PICKED_UP",
    "RECEIVED",
    "REJECTED",
    name="trace_stage_enum",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "ALTER TYPE user_role_enum "
        "ADD VALUE IF NOT EXISTS 'OPERATOR'"
    )
    op.execute(
        "ALTER TYPE user_role_enum "
        "ADD VALUE IF NOT EXISTS 'RECYCLER'"
    )

    op.add_column(
        "users",
        sa.Column("email", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
    )

    op.add_column(
        "hubs",
        sa.Column(
            "capacity_kg",
            sa.Numeric(12, 3),
            nullable=False,
            server_default="200",
        ),
    )
    op.add_column(
        "hubs",
        sa.Column(
            "current_load_kg",
            sa.Numeric(12, 3),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "hubs",
        sa.Column(
            "fill_level",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "hubs",
        sa.Column(
            "camera_online",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "hubs",
        sa.Column(
            "sensor_online",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "hubs",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_hubs_capacity_kg_positive",
        "hubs",
        "capacity_kg > 0",
    )
    op.create_check_constraint(
        "ck_hubs_current_load_valid",
        "hubs",
        "current_load_kg >= 0 AND current_load_kg <= capacity_kg",
    )
    op.create_check_constraint(
        "ck_hubs_fill_level_valid",
        "hubs",
        "fill_level >= 0 AND fill_level <= 100",
    )

    route_status_enum.create(op.get_bind(), checkfirst=True)
    trace_stage_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sensor_readings",
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fill_level", sa.Numeric(5, 2), nullable=False),
        sa.Column("weight_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("camera_online", sa.Boolean(), nullable=False),
        sa.Column("sensor_online", sa.Boolean(), nullable=False),
        sa.Column("temperature_c", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "fill_level >= 0 AND fill_level <= 100",
            name="ck_sensor_readings_fill_level_valid",
        ),
        sa.CheckConstraint(
            "weight_kg >= 0",
            name="ck_sensor_readings_weight_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            name="fk_sensor_readings_hub_id_hubs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sensor_readings"),
    )
    op.create_index(
        "ix_sensor_readings_hub_id", "sensor_readings", ["hub_id"]
    )
    op.create_index(
        "ix_sensor_readings_recorded_at",
        "sensor_readings",
        ["recorded_at"],
    )

    op.create_table(
        "vehicles",
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("capacity_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "capacity_kg > 0", name="ck_vehicles_capacity_positive"
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["users.id"],
            name="fk_vehicles_driver_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vehicles"),
        sa.UniqueConstraint("code", name="uq_vehicles_code"),
    )
    op.create_index("ix_vehicles_driver_id", "vehicles", ["driver_id"])

    op.create_table(
        "collection_routes",
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column(
            "vehicle_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "status",
            route_status_enum,
            nullable=False,
            server_default="PLANNED",
        ),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column(
            "total_distance_km",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "baseline_distance_km",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "distance_saved_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "estimated_load_kg",
            sa.Numeric(12, 3),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "planned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "threshold_percent BETWEEN 1 AND 100",
            name="ck_collection_routes_threshold_valid",
        ),
        sa.CheckConstraint(
            "total_distance_km >= 0 AND baseline_distance_km >= 0",
            name="ck_collection_routes_distance_non_negative",
        ),
        sa.CheckConstraint(
            "estimated_load_kg >= 0",
            name="ck_collection_routes_load_non_negative",
        ),
        sa.CheckConstraint(
            "(status = 'PLANNED' AND started_at IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'IN_PROGRESS' AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'COMPLETED' AND started_at IS NOT NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'CANCELLED' AND completed_at IS NULL)",
            name="ck_collection_routes_status_time_consistent",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            name="fk_collection_routes_vehicle_id_vehicles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collection_routes"),
        sa.UniqueConstraint("code", name="uq_collection_routes_code"),
    )
    op.create_index(
        "ix_collection_routes_status", "collection_routes", ["status"]
    )
    op.create_index(
        "ix_collection_routes_vehicle_id",
        "collection_routes",
        ["vehicle_id"],
    )

    op.create_table(
        "route_stops",
        sa.Column("route_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pickup_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "distance_from_previous_km", sa.Numeric(10, 2), nullable=False
        ),
        sa.Column("expected_load_kg", sa.Numeric(12, 3), nullable=False),
        sa.Column("collected_load_kg", sa.Numeric(12, 3), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "sequence > 0", name="ck_route_stops_sequence_positive"
        ),
        sa.CheckConstraint(
            "distance_from_previous_km >= 0",
            name="ck_route_stops_distance_non_negative",
        ),
        sa.CheckConstraint(
            "expected_load_kg >= 0 AND "
            "(collected_load_kg IS NULL OR collected_load_kg >= 0)",
            name="ck_route_stops_load_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["collection_routes.id"],
            name="fk_route_stops_route_id_collection_routes",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hub_id"],
            ["hubs.id"],
            name="fk_route_stops_hub_id_hubs",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pickup_id"],
            ["pickups.id"],
            name="fk_route_stops_pickup_id_pickups",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_route_stops"),
        sa.UniqueConstraint(
            "route_id",
            "sequence",
            name="uq_route_stops_route_sequence",
        ),
    )
    op.create_index("ix_route_stops_route_id", "route_stops", ["route_id"])
    op.create_index("ix_route_stops_hub_id", "route_stops", ["hub_id"])

    op.create_table(
        "trace_events",
        sa.Column("trace_code", sa.String(80), nullable=False),
        sa.Column(
            "transaction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("stage", trace_stage_enum, nullable=False),
        sa.Column("location_type", sa.String(40), nullable=False),
        sa.Column("location_ref", sa.String(100), nullable=False),
        sa.Column(
            "actor_user_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "event_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["bottle_transactions.id"],
            name="fk_trace_events_transaction_id_bottle_transactions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_trace_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trace_events"),
    )
    op.create_index(
        "ix_trace_events_code_time",
        "trace_events",
        ["trace_code", "occurred_at"],
    )
    op.create_index(
        "ix_trace_events_transaction_id",
        "trace_events",
        ["transaction_id"],
    )
    op.create_index("ix_trace_events_stage", "trace_events", ["stage"])


def downgrade() -> None:
    op.drop_table("trace_events")
    op.drop_table("route_stops")
    op.drop_table("collection_routes")
    op.drop_table("vehicles")
    op.drop_table("sensor_readings")

    trace_stage_enum.drop(op.get_bind(), checkfirst=True)
    route_status_enum.drop(op.get_bind(), checkfirst=True)


    op.drop_constraint(
        "ck_hubs_fill_level_valid", "hubs", type_="check"
    )
    op.drop_constraint(
        "ck_hubs_current_load_valid", "hubs", type_="check"
    )
    op.drop_constraint(
        "ck_hubs_capacity_kg_positive", "hubs", type_="check"
    )
    op.drop_column("hubs", "last_seen_at")
    op.drop_column("hubs", "sensor_online")
    op.drop_column("hubs", "camera_online")
    op.drop_column("hubs", "fill_level")
    op.drop_column("hubs", "current_load_kg")
    op.drop_column("hubs", "capacity_kg")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_column("users", "is_active")
    op.drop_column("users", "hashed_password")
    op.drop_column("users", "email")

    # PostgreSQL enum values are intentionally retained. Removing enum
    # values requires rebuilding the type and is unsafe for shared data.
