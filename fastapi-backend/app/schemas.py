from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DepositStatus, HubStatus, MaterialType, RouteStatus, TraceStage, UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserRead(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    points_balance: int
    is_active: bool
    created_at: datetime


class UserAdminUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None


class RewardRedeem(BaseModel):
    points: int = Field(gt=0)
    reward_name: str = Field(min_length=2, max_length=120)
    payout_channel: str | None = Field(default=None, pattern="^(momo|zalopay|voucher|none)$")


class HubCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str
    address: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    capacity_kg: float = Field(gt=0)


class HubRead(ORMModel):
    id: int
    code: str
    name: str
    address: str
    latitude: float
    longitude: float
    capacity_kg: float
    current_load_kg: float
    fill_level: float
    status: HubStatus
    camera_online: bool
    sensor_online: bool
    last_seen_at: datetime | None


class TelemetryCreate(BaseModel):
    fill_level: float = Field(ge=0, le=100)
    weight_kg: float = Field(ge=0)
    camera_online: bool
    sensor_online: bool
    temperature_c: float | None = Field(default=None, ge=-20, le=100)


class DepositInspection(BaseModel):
    user_id: int | None = None
    hub_code: str
    material_type: MaterialType | None = None
    weight_g: float = Field(gt=0, le=10000)
    ai_confidence: float = Field(ge=0, le=1)
    cleanliness_score: float = Field(ge=0, le=1)
    liquid_detected: bool = False
    foreign_object_detected: bool = False


class DepositRead(ORMModel):
    id: int
    trace_code: str
    user_id: int | None
    hub_id: int
    material_type: MaterialType | None
    weight_g: float
    ai_confidence: float
    cleanliness_score: float
    liquid_detected: bool
    foreign_object_detected: bool
    status: DepositStatus
    rejection_reason: str | None
    points_earned: int
    created_at: datetime


class DepositResult(BaseModel):
    deposit: DepositRead
    machine_action: str
    user_message: str


class PointsTransactionRead(ORMModel):
    id: int
    user_id: int
    deposit_id: int | None
    points: int
    transaction_type: str
    description: str
    created_at: datetime


class VehicleRead(ORMModel):
    id: int
    code: str
    capacity_kg: float
    latitude: float
    longitude: float
    active: bool


class OptimizeRequest(BaseModel):
    vehicle_id: int
    fill_threshold: float = Field(default=70, ge=0, le=100)
    include_urgent_offline_hubs: bool = False


class RouteStopRead(ORMModel):
    id: int
    hub_id: int
    sequence: int
    distance_from_previous_km: float
    expected_load_kg: float
    collected_load_kg: float | None
    collected_at: datetime | None


class RouteRead(ORMModel):
    id: int
    vehicle_id: int
    status: RouteStatus
    threshold_percent: float
    total_distance_km: float
    baseline_distance_km: float
    distance_saved_percent: float
    estimated_load_kg: float
    planned_at: datetime
    completed_at: datetime | None
    stops: list[RouteStopRead]


class PickupCreate(BaseModel):
    collected_load_kg: float = Field(ge=0)


class TraceEventCreate(BaseModel):
    trace_code: str
    stage: TraceStage
    location_type: str
    location_ref: str
    notes: str | None = None
    event_metadata: dict = Field(default_factory=dict)


class TraceEventRead(ORMModel):
    id: int
    trace_code: str
    stage: TraceStage
    location_type: str
    location_ref: str
    actor_user_id: int | None
    notes: str | None
    event_metadata: dict
    occurred_at: datetime


class TraceabilityRead(BaseModel):
    trace_code: str
    material_type: MaterialType | None
    weight_g: float
    quality_status: DepositStatus
    current_stage: TraceStage
    events: list[TraceEventRead]


class ESGReport(BaseModel):
    period: str
    from_date: date
    to_date: date
    pet_recovered_kg: float
    hdpe_recovered_kg: float
    total_plastic_recovered_kg: float
    co2_avoided_kg: float
    collection_distance_km: float
    baseline_distance_km: float
    distance_reduced_km: float
    distance_reduced_percent: float
    participating_users: int
    successful_transactions: int
    rejected_transactions: int
    quality_acceptance_rate_percent: float
    completed_routes: int
    methodology: dict[str, str]


class DashboardSummary(BaseModel):
    hubs_total: int
    hubs_online: int
    hubs_full: int
    alerts: int
    plastic_today_kg: float
    transactions_today: int
    active_users_today: int
    co2_avoided_today_kg: float
