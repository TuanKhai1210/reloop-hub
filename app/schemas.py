from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    BottleTransactionStatus,
    HubStatus,
    MaterialBatchStatus,
    MaterialType,
    ReturnSessionStatus,
    RouteStatus,
    TraceStage,
    UserRole,
    VoucherRedemptionStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    student_code: str | None = Field(default=None, max_length=30)


class UserRead(ORMModel):
    id: UUID
    email: str | None
    name: str
    student_code: str | None
    role: UserRole
    points_balance: int
    total_bottles_returned: int
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HubRead(ORMModel):
    id: UUID
    code: str
    name: str
    location_name: str
    latitude: Decimal | None
    longitude: Decimal | None
    status: HubStatus
    pet_capacity: int
    hdpe_capacity: int
    pet_current: int
    hdpe_current: int
    pickup_threshold_percent: int
    capacity_kg: Decimal
    current_load_kg: Decimal
    fill_level: Decimal
    camera_online: bool
    sensor_online: bool
    last_seen_at: datetime | None


class HubTelemetry(BaseModel):
    fill_level: Decimal = Field(ge=0, le=100)
    weight_kg: Decimal = Field(ge=0)
    camera_online: bool
    sensor_online: bool
    temperature_c: Decimal | None = None


class DepositInspection(BaseModel):
    user_id: UUID
    hub_code: str
    material_type: MaterialType
    weight_g: Decimal = Field(gt=0)
    ai_confidence: Decimal = Field(ge=0, le=1)
    cleanliness_score: Decimal = Field(ge=0, le=1)
    liquid_detected: bool = False
    foreign_object_detected: bool = False


class DepositRead(ORMModel):
    id: UUID
    code: str
    session_id: UUID
    batch_id: UUID | None
    material_type: MaterialType
    verified_material_type: MaterialType | None
    status: BottleTransactionStatus
    points_awarded: int
    weight_gram: Decimal | None
    ai_confidence: Decimal | None
    cleanliness_score: Decimal | None
    created_at: datetime


class ReturnSessionRead(ORMModel):
    id: UUID
    user_id: UUID
    hub_id: UUID
    status: ReturnSessionStatus
    total_accepted: int
    total_rejected: int
    total_points: int
    finished_at: datetime | None


class DepositResult(BaseModel):
    deposit: DepositRead
    machine_action: str
    user_message: str


class VoucherRead(ORMModel):
    id: UUID
    code: str
    name: str
    partner_name: str
    required_points: int
    value_text: str
    quantity_available: int


class VoucherRedeemRequest(BaseModel):
    voucher_id: UUID


class VoucherRedemptionRead(ORMModel):
    id: UUID
    voucher_id: UUID
    redemption_code: str
    points_spent: int
    status: VoucherRedemptionStatus
    expires_at: datetime | None


class RouteOptimizeRequest(BaseModel):
    vehicle_id: UUID
    fill_threshold: int = Field(default=70, ge=1, le=100)


class RouteStopRead(ORMModel):
    id: UUID
    hub_id: UUID
    pickup_id: UUID | None
    sequence: int
    distance_from_previous_km: Decimal
    expected_load_kg: Decimal
    collected_load_kg: Decimal | None
    collected_at: datetime | None


class RouteRead(ORMModel):
    id: UUID
    code: str
    vehicle_id: UUID
    status: RouteStatus
    threshold_percent: int
    total_distance_km: Decimal
    baseline_distance_km: Decimal
    distance_saved_percent: Decimal
    estimated_load_kg: Decimal
    planned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    stops: list[RouteStopRead] = Field(default_factory=list)


class PickupStopRequest(BaseModel):
    collected_load_kg: Decimal = Field(ge=0)


class SensorReadingRead(ORMModel):
    id: UUID
    hub_id: UUID
    fill_level: Decimal
    weight_kg: Decimal
    camera_online: bool
    sensor_online: bool
    temperature_c: Decimal | None
    recorded_at: datetime


class TraceEventRead(ORMModel):
    stage: TraceStage
    location_type: str
    location_ref: str
    notes: str | None
    event_metadata: dict
    occurred_at: datetime


class TraceabilityRead(BaseModel):
    trace_code: str
    current_stage: TraceStage
    events: list[TraceEventRead]


class BatchReceiptRequest(BaseModel):
    facility_code: str = Field(min_length=1, max_length=100)
    received_weight_kg: Decimal = Field(ge=0)
    notes: str | None = Field(default=None, max_length=500)


class BatchReceiptRead(BaseModel):
    batch_id: UUID
    batch_code: str
    status: MaterialBatchStatus
    facility_code: str
    received_weight_kg: Decimal
    bottle_count: int
    trace_events_created: int
    received_at: datetime


class DashboardSummary(BaseModel):
    period: Literal["day", "week", "month"]
    period_start: datetime
    period_end: datetime
    reporting_timezone: str
    users: int
    participants: int
    active_hubs: int
    near_full_hubs: int
    offline_hubs: int
    camera_online_hubs: int
    sensor_online_hubs: int
    transactions_today: int
    transactions_in_period: int
    successful_transactions: int
    accepted_bottles: int
    rejected_bottles: int
    success_rate_percent: Decimal
    pet_bottles: int
    hdpe_bottles: int
    recovered_weight_kg: Decimal
    average_ai_confidence: Decimal
    average_cleanliness_score: Decimal
    rejection_reasons: dict[str, int]
    ready_batches: int
    active_pickups: int
    completed_routes: int
    baseline_distance_km: Decimal
    optimized_distance_km: Decimal
    distance_saved_km: Decimal
    distance_saved_percent: Decimal
    collection_efficiency_kg_per_km: Decimal
    vehicle_utilization_percent: Decimal
    estimated_co2_saved_kg: Decimal
    traceability_completeness_percent: Decimal


class ESGReport(BaseModel):
    period: Literal["day", "week", "month"]
    period_start: datetime
    period_end: datetime
    reporting_timezone: str
    participants: int
    total_transactions: int
    successful_transactions: int
    success_rate_percent: Decimal
    total_plastic_recovered_kg: Decimal
    pet_bottles: int
    hdpe_bottles: int
    rejected_bottles: int
    completed_routes: int
    baseline_distance_km: Decimal
    optimized_distance_km: Decimal
    distance_saved_km: Decimal
    distance_saved_percent: Decimal
    collection_efficiency_kg_per_km: Decimal
    vehicle_utilization_percent: Decimal
    estimated_co2_saved_kg: Decimal
    traceability_completeness_percent: Decimal
    co2_emission_factor_kg_per_km: Decimal
    co2_methodology_version: str
    co2_factor_source: str
