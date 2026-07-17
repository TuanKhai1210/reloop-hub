"""Generate a deterministic, traceable ReLoop Hub showcase dataset."""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_UP
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    BottleTransaction,
    BottleTransactionStatus,
    CleanlinessStatus,
    CollectionRoute,
    Hub,
    HubStatus,
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
    Pickup,
    PickupStatus,
    PointLedger,
    PointSourceType,
    RejectReason,
    ReturnSession,
    ReturnSessionStatus,
    RouteStatus,
    RouteStop,
    SensorReading,
    TraceEvent,
    TraceStage,
    User,
    UserRole,
    Vehicle,
    VerificationEvent,
    VerificationLevel,
    VerificationResult,
    Voucher,
    VoucherRedemption,
    VoucherRedemptionStatus,
    VoucherStatus,
)
from app.services import ReportingService


DEMO_NAMESPACE = UUID("a3563f5f-2198-4b83-bb5a-8af34ee64a31")
DEMO_PREFIX = "DEMO-"
DEMO_EMAIL_PATTERN = "demo.%@reloop.vn"
BASE_HUB_CODE = "HUB-CANTEEN-01"
DRIVER_ID = UUID("00000000-0000-0000-0000-000000000003")
ADMIN_ID = UUID("00000000-0000-0000-0000-000000000002")
VOUCHER_2K_CODE = "CANTEEN-2K"
VOUCHER_5K_CODE = "CANTEEN-5K"

HUB_SPECS = (
    {
        "key": "H1",
        "code": "HUB-B3-01",
        "name": "B3 Main Gate Hub",
        "location": "B3 Building - Main Gate",
        "latitude": Decimal("10.772480"),
        "longitude": Decimal("106.657080"),
    },
    {
        "key": "H2",
        "code": BASE_HUB_CODE,
        "name": "Campus Canteen 1 Hub",
        "location": "Canteen 1 - B4/B6",
        "latitude": Decimal("10.773020"),
        "longitude": Decimal("106.658020"),
    },
    {
        "key": "H3",
        "code": "HUB-CANTEEN-02",
        "name": "Campus Canteen 2 Hub",
        "location": "Canteen 2 - C1",
        "latitude": Decimal("10.774080"),
        "longitude": Decimal("106.660180"),
    },
    {
        "key": "H4",
        "code": "HUB-LIBRARY-01",
        "name": "Main Library Hub",
        "location": "A2 Main Library",
        "latitude": Decimal("10.771580"),
        "longitude": Decimal("106.659180"),
    },
)

TARGET_FILL_LEVELS = {
    "H1": Decimal("61.00"),
    "H2": Decimal("84.00"),
    "H3": Decimal("47.00"),
    "H4": Decimal("36.00"),
}


def demo_id(kind: str, key: str) -> UUID:
    return uuid5(DEMO_NAMESPACE, f"{kind}:{key}")


def as_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def quantize_kg(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))


def ids_for(session: Session, model: type, *filters: object) -> list[UUID]:
    return list(session.scalars(select(model.id).where(*filters)))


def delete_for_ids(
    session: Session,
    model: type,
    column: object,
    values: list[UUID],
) -> None:
    if values:
        session.execute(delete(model).where(column.in_(values)))


def reset_demo_data(session: Session) -> None:
    """Delete only records owned by this showcase generator."""

    user_ids = ids_for(
        session,
        User,
        User.email.like(DEMO_EMAIL_PATTERN),
    )
    transaction_ids = ids_for(
        session,
        BottleTransaction,
        BottleTransaction.code.like(f"{DEMO_PREFIX}TX-%"),
    )
    route_ids = ids_for(
        session,
        CollectionRoute,
        CollectionRoute.code.like(f"{DEMO_PREFIX}ROUTE-%"),
    )
    batch_ids = ids_for(
        session,
        MaterialBatch,
        MaterialBatch.code.like(f"{DEMO_PREFIX}BATCH-%"),
    )
    pickup_ids = ids_for(
        session,
        Pickup,
        Pickup.code.like(f"{DEMO_PREFIX}PICKUP-%"),
    )
    redemption_ids = (
        ids_for(
            session,
            VoucherRedemption,
            VoucherRedemption.redemption_code.like(
                f"{DEMO_PREFIX}REDEEM-%"
            ),
        )
    )
    session_ids = (
        ids_for(session, ReturnSession, ReturnSession.user_id.in_(user_ids))
        if user_ids
        else []
    )
    hub_ids = ids_for(
        session,
        Hub,
        Hub.code.in_([spec["code"] for spec in HUB_SPECS]),
    )

    session.execute(
        delete(TraceEvent).where(
            TraceEvent.trace_code.like(f"{DEMO_PREFIX}TX-%")
        )
    )
    delete_for_ids(
        session,
        VerificationEvent,
        VerificationEvent.transaction_id,
        transaction_ids,
    )
    delete_for_ids(
        session,
        PointLedger,
        PointLedger.user_id,
        user_ids,
    )
    delete_for_ids(
        session,
        RouteStop,
        RouteStop.route_id,
        route_ids,
    )
    delete_for_ids(
        session,
        BottleTransaction,
        BottleTransaction.id,
        transaction_ids,
    )
    delete_for_ids(
        session,
        MaterialBatch,
        MaterialBatch.id,
        batch_ids,
    )
    delete_for_ids(
        session,
        Pickup,
        Pickup.id,
        pickup_ids,
    )
    delete_for_ids(
        session,
        CollectionRoute,
        CollectionRoute.id,
        route_ids,
    )
    delete_for_ids(
        session,
        VoucherRedemption,
        VoucherRedemption.id,
        redemption_ids,
    )
    delete_for_ids(
        session,
        ReturnSession,
        ReturnSession.id,
        session_ids,
    )
    delete_for_ids(
        session,
        SensorReading,
        SensorReading.hub_id,
        hub_ids,
    )
    session.execute(
        delete(Vehicle).where(Vehicle.code.like(f"{DEMO_PREFIX}VEHICLE-%"))
    )
    session.execute(
        delete(Voucher).where(Voucher.code.like(f"{DEMO_PREFIX}VOUCHER-%"))
    )
    delete_for_ids(session, User, User.id, user_ids)
    session.execute(
        delete(Hub).where(
            Hub.code.like(f"{DEMO_PREFIX}HUB-%")
        )
    )
    session.flush()


def ensure_hubs(session: Session, created_at: datetime) -> list[Hub]:
    hubs: list[Hub] = []
    for spec in HUB_SPECS:
        hub = session.scalar(select(Hub).where(Hub.code == spec["code"]))
        if hub is None:
            hub = Hub(
                id=demo_id("hub", str(spec["key"])),
                code=str(spec["code"]),
                name=str(spec["name"]),
                location_name=str(spec["location"]),
                latitude=spec["latitude"],
                longitude=spec["longitude"],
                status=HubStatus.ACTIVE,
                pet_capacity=80,
                hdpe_capacity=60,
                pet_current=0,
                hdpe_current=0,
                pickup_threshold_percent=80,
                capacity_kg=Decimal("5.000"),
                current_load_kg=Decimal("0"),
                fill_level=Decimal("0"),
                camera_online=True,
                sensor_online=True,
                last_seen_at=None,
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(hub)
        else:
            hub.name = str(spec["name"])
            hub.location_name = str(spec["location"])
            hub.latitude = spec["latitude"]
            hub.longitude = spec["longitude"]
            hub.pickup_threshold_percent = 80
        hubs.append(hub)
    session.flush()
    return hubs


def create_demo_users(
    session: Session,
    *,
    student_count: int,
    created_at: datetime,
) -> tuple[list[User], User, User]:
    student_password = hash_password("DemoStudent@123")
    staff_password = hash_password("DemoStaff@123")
    students: list[User] = []
    for index in range(1, student_count + 1):
        user = User(
            id=demo_id("user", f"student-{index}"),
            name=f"Demo Student {index:02d}",
            email=f"demo.student.{index:02d}@reloop.vn",
            hashed_password=student_password,
            is_active=True,
            phone=f"0988{index:06d}",
            student_code=f"SHOWCASE-STUDENT-{index:03d}",
            role=UserRole.USER,
            points_balance=0,
            total_bottles_returned=0,
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(user)
        students.append(user)

    operator = User(
        id=demo_id("user", "operator"),
        name="Demo Operations Staff",
        email="demo.operator@reloop.vn",
        hashed_password=staff_password,
        is_active=True,
        phone="0988999901",
        student_code=None,
        role=UserRole.OPERATOR,
        points_balance=0,
        total_bottles_returned=0,
        created_at=created_at,
        updated_at=created_at,
    )
    recycler = User(
        id=demo_id("user", "recycler"),
        name="Demo Recycler Staff",
        email="demo.recycler@reloop.vn",
        hashed_password=staff_password,
        is_active=True,
        phone="0988999902",
        student_code=None,
        role=UserRole.RECYCLER,
        points_balance=0,
        total_bottles_returned=0,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add_all([operator, recycler])
    session.flush()
    return students, operator, recycler


def ensure_vouchers(
    session: Session,
    *,
    start: datetime,
    end: datetime,
) -> list[Voucher]:
    definitions = (
        (
            VOUCHER_2K_CODE,
            "2,000 VND Canteen Voucher",
            "Campus Canteen",
            50,
            "2,000 VND discount",
        ),
        (
            VOUCHER_5K_CODE,
            "5,000 VND Canteen Voucher",
            "Campus Canteen",
            100,
            "5,000 VND discount",
        ),
        (
            "DEMO-VOUCHER-PRINT",
            "Campus Printing Voucher",
            "Student Service Center",
            80,
            "10 printed pages",
        ),
    )
    vouchers: list[Voucher] = []
    for code, name, partner, required_points, value_text in definitions:
        voucher = session.scalar(select(Voucher).where(Voucher.code == code))
        if voucher is None:
            voucher = Voucher(
                id=demo_id("voucher", code),
                code=code,
                name=name,
                partner_name=partner,
                description="Showcase reward for the campus pilot.",
                required_points=required_points,
                value_text=value_text,
                quantity_available=500,
                status=VoucherStatus.ACTIVE,
                valid_from=start,
                expires_at=end + timedelta(days=90),
                created_at=start,
                updated_at=start,
            )
            session.add(voucher)
        else:
            voucher.name = name
            voucher.partner_name = partner
            voucher.required_points = required_points
            voucher.value_text = value_text
            voucher.quantity_available = 500
            voucher.status = VoucherStatus.ACTIVE
            voucher.valid_from = start
            voucher.expires_at = end + timedelta(days=90)
        vouchers.append(voucher)
    session.flush()
    return vouchers


def create_vehicle(
    session: Session,
    *,
    driver_id: UUID,
    created_at: datetime,
) -> Vehicle:
    vehicle = Vehicle(
        id=demo_id("vehicle", "campus-cargo-01"),
        code="DEMO-VEHICLE-CARGO-01",
        driver_id=driver_id,
        capacity_kg=Decimal("20.000"),
        latitude=Decimal("10.771300"),
        longitude=Decimal("106.656700"),
        active=True,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(vehicle)
    return vehicle


def time_between(
    *,
    current_date: date,
    index: int,
    count: int,
    today: date,
    now_local: datetime,
    timezone: ZoneInfo,
) -> datetime:
    if current_date == today:
        end = now_local - timedelta(minutes=8)
        day_floor = datetime.combine(today, time(0, 1), timezone)
        start = max(day_floor, end - timedelta(hours=10))
    else:
        start = datetime.combine(current_date, time(8, 0), timezone)
        end = datetime.combine(current_date, time(19, 0), timezone)
    span_seconds = max(1, int((end - start).total_seconds()))
    offset = span_seconds * (index + 1) // (count + 1)
    return start + timedelta(seconds=offset)


def get_or_create_batch(
    session: Session,
    batches: dict[tuple[date, UUID, MaterialType], MaterialBatch],
    *,
    current_date: date,
    hub: Hub,
    hub_key: str,
    material_type: MaterialType,
    created_at: datetime,
) -> MaterialBatch:
    key = (current_date, hub.id, material_type)
    batch = batches.get(key)
    if batch is not None:
        return batch
    code = (
        f"DEMO-BATCH-{current_date:%Y%m%d}-"
        f"{hub_key}-{material_type.value}"
    )
    batch = MaterialBatch(
        id=demo_id("batch", code),
        code=code,
        hub_id=hub.id,
        pickup_id=None,
        material_type=material_type,
        bottle_count=0,
        estimated_weight_kg=Decimal("0"),
        status=MaterialBatchStatus.STORING,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(batch)
    session.flush([batch])
    batches[key] = batch
    return batch


def rejected_metadata(
    rng: random.Random,
    reason: RejectReason,
) -> tuple[MaterialType, CleanlinessStatus, Decimal, Decimal]:
    material = (
        MaterialType.UNKNOWN
        if reason == RejectReason.UNSUPPORTED_MATERIAL
        else rng.choice([MaterialType.PET, MaterialType.HDPE])
    )
    cleanliness = (
        CleanlinessStatus.DIRTY
        if reason == RejectReason.DIRTY_BOTTLE
        else CleanlinessStatus.UNKNOWN
    )
    confidence = (
        Decimal("0.6100")
        if reason == RejectReason.LOW_CONFIDENCE
        else Decimal(str(rng.uniform(0.82, 0.97))).quantize(
            Decimal("0.0001")
        )
    )
    cleanliness_score = (
        Decimal(str(rng.uniform(0.30, 0.64))).quantize(
            Decimal("0.0001")
        )
        if reason == RejectReason.DIRTY_BOTTLE
        else Decimal(str(rng.uniform(0.72, 0.95))).quantize(
            Decimal("0.0001")
        )
    )
    return material, cleanliness, confidence, cleanliness_score


def add_trace_event(
    session: Session,
    *,
    transaction: BottleTransaction,
    stage: TraceStage,
    location_type: str,
    location_ref: str,
    actor_user_id: UUID | None,
    occurred_at: datetime,
    notes: str,
    metadata: dict[str, str],
) -> TraceEvent:
    event = TraceEvent(
        id=demo_id("trace", f"{transaction.code}:{stage.value}"),
        trace_code=transaction.code,
        transaction_id=transaction.id,
        stage=stage,
        location_type=location_type,
        location_ref=location_ref,
        actor_user_id=actor_user_id,
        notes=notes,
        event_metadata=metadata,
        occurred_at=occurred_at,
    )
    session.add(event)
    return event


def create_transactions(
    session: Session,
    *,
    rng: random.Random,
    students: list[User],
    hubs: list[Hub],
    vouchers: list[Voucher],
    days: int,
    sessions_per_day: int,
    now_local: datetime,
    timezone: ZoneInfo,
) -> tuple[
    dict[tuple[date, UUID, MaterialType], MaterialBatch],
    dict[UUID, list[BottleTransaction]],
    dict[UUID, int],
    dict[UUID, int],
]:
    today = now_local.date()
    start_date = today - timedelta(days=days - 1)
    balances = {user.id: 0 for user in students}
    accepted_by_user = {user.id: 0 for user in students}
    batches: dict[tuple[date, UUID, MaterialType], MaterialBatch] = {}
    transactions_by_batch: dict[UUID, list[BottleTransaction]] = defaultdict(list)
    hub_key_by_id = {
        hub.id: str(spec["key"])
        for hub, spec in zip(hubs, HUB_SPECS, strict=True)
    }
    reasons = [
        RejectReason.DIRTY_BOTTLE,
        RejectReason.BOTTLE_HAS_LIQUID,
        RejectReason.LOW_CONFIDENCE,
        RejectReason.UNSUPPORTED_MATERIAL,
        RejectReason.WRONG_SLOT,
    ]

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        daily_sessions = sessions_per_day
        if current_date.weekday() >= 5:
            daily_sessions = max(4, sessions_per_day * 2 // 3)

        for session_index in range(daily_sessions):
            event_local = time_between(
                current_date=current_date,
                index=session_index,
                count=daily_sessions,
                today=today,
                now_local=now_local,
                timezone=timezone,
            )
            event_time = as_utc(event_local)
            user = students[(day_offset * 7 + session_index * 3) % len(students)]
            hub = hubs[(day_offset + session_index) % len(hubs)]
            return_session = ReturnSession(
                id=demo_id(
                    "session",
                    f"{current_date:%Y%m%d}:{session_index:03d}",
                ),
                user_id=user.id,
                hub_id=hub.id,
                status=ReturnSessionStatus.COMPLETED,
                total_accepted=0,
                total_rejected=0,
                total_points=0,
                finished_at=event_time + timedelta(minutes=4),
                created_at=event_time,
                updated_at=event_time + timedelta(minutes=4),
            )
            session.add(return_session)
            session.flush([return_session])
            bottle_count = rng.randint(4, 8)

            for bottle_index in range(bottle_count):
                transaction_time = event_time + timedelta(
                    seconds=20 + bottle_index * 28
                )
                code = (
                    f"DEMO-TX-{current_date:%Y%m%d}-"
                    f"{session_index:03d}-{bottle_index:02d}"
                )
                accepted = rng.random() < Decimal("0.84")
                if accepted:
                    material = (
                        MaterialType.PET
                        if rng.random() < 0.68
                        else MaterialType.HDPE
                    )
                    weight = (
                        Decimal(str(rng.uniform(21, 36)))
                        if material == MaterialType.PET
                        else Decimal(str(rng.uniform(38, 72)))
                    ).quantize(Decimal("0.01"))
                    confidence = Decimal(
                        str(rng.uniform(0.86, 0.99))
                    ).quantize(Decimal("0.0001"))
                    clean_score = Decimal(
                        str(rng.uniform(0.78, 0.98))
                    ).quantize(Decimal("0.0001"))
                    batch = get_or_create_batch(
                        session,
                        batches,
                        current_date=current_date,
                        hub=hub,
                        hub_key=hub_key_by_id[hub.id],
                        material_type=material,
                        created_at=transaction_time,
                    )
                    transaction = BottleTransaction(
                        id=demo_id("transaction", code),
                        code=code,
                        session_id=return_session.id,
                        batch_id=batch.id,
                        material_type=material,
                        verified_material_type=material,
                        status=BottleTransactionStatus.ACCEPTED,
                        reject_reason=None,
                        verification_level=VerificationLevel.LEVEL_2,
                        cleanliness_status=CleanlinessStatus.CLEAN,
                        weight_gram=weight,
                        ai_confidence=confidence,
                        cleanliness_score=clean_score,
                        points_awarded=10,
                        created_at=transaction_time,
                        updated_at=transaction_time,
                    )
                    session.add(transaction)
                    session.flush([transaction])
                    batch.bottle_count += 1
                    batch.estimated_weight_kg += weight / Decimal("1000")
                    batch.updated_at = transaction_time
                    transactions_by_batch[batch.id].append(transaction)
                    return_session.total_accepted += 1
                    return_session.total_points += 10
                    balances[user.id] += 10
                    accepted_by_user[user.id] += 1
                    session.add(
                        PointLedger(
                            id=demo_id("ledger", f"return:{code}"),
                            user_id=user.id,
                            source_type=PointSourceType.BOTTLE_RETURN,
                            source_id=transaction.id,
                            points_change=10,
                            balance_after=balances[user.id],
                            description="Accepted showcase bottle return",
                            created_at=transaction_time + timedelta(seconds=4),
                        )
                    )
                    session.add(
                        VerificationEvent(
                            id=demo_id("verification", code),
                            transaction_id=transaction.id,
                            verification_level=VerificationLevel.LEVEL_2,
                            result=VerificationResult.PASS,
                            verifier_name="showcase_hub_rule_engine",
                            verifier_version="2.1.0",
                            rule_code="PET_HDPE_CLEAN_CONFIDENT",
                            input_payload={
                                "selected_material": material.value,
                                "weight_gram": float(weight),
                                "cleanliness_score": float(clean_score),
                            },
                            output_payload={
                                "accepted": True,
                                "material_type": material.value,
                                "points": 10,
                            },
                            confidence=confidence,
                            processing_time_ms=rng.randint(180, 620),
                            failure_reason=None,
                            created_at=transaction_time + timedelta(seconds=2),
                        )
                    )
                    add_trace_event(
                        session,
                        transaction=transaction,
                        stage=TraceStage.DEPOSITED,
                        location_type="hub_input",
                        location_ref=hub.code,
                        actor_user_id=user.id,
                        occurred_at=transaction_time,
                        notes="Bottle accepted after Hub-side verification",
                        metadata={"session_id": str(return_session.id)},
                    )
                    add_trace_event(
                        session,
                        transaction=transaction,
                        stage=TraceStage.HUB_STORED,
                        location_type="material_batch",
                        location_ref=batch.code,
                        actor_user_id=None,
                        occurred_at=transaction_time + timedelta(minutes=2),
                        notes=f"Stored in separated {material.value} batch",
                        metadata={"batch_id": str(batch.id)},
                    )
                else:
                    reason = rng.choice(reasons)
                    (
                        material,
                        cleanliness,
                        confidence,
                        clean_score,
                    ) = rejected_metadata(rng, reason)
                    weight = Decimal(str(rng.uniform(25, 105))).quantize(
                        Decimal("0.01")
                    )
                    transaction = BottleTransaction(
                        id=demo_id("transaction", code),
                        code=code,
                        session_id=return_session.id,
                        batch_id=None,
                        material_type=material,
                        verified_material_type=material,
                        status=BottleTransactionStatus.REJECTED,
                        reject_reason=reason,
                        verification_level=VerificationLevel.LEVEL_2,
                        cleanliness_status=cleanliness,
                        weight_gram=weight,
                        ai_confidence=confidence,
                        cleanliness_score=clean_score,
                        points_awarded=0,
                        created_at=transaction_time,
                        updated_at=transaction_time,
                    )
                    session.add(transaction)
                    session.flush([transaction])
                    return_session.total_rejected += 1
                    session.add(
                        VerificationEvent(
                            id=demo_id("verification", code),
                            transaction_id=transaction.id,
                            verification_level=VerificationLevel.LEVEL_2,
                            result=VerificationResult.FAIL,
                            verifier_name="showcase_hub_rule_engine",
                            verifier_version="2.1.0",
                            rule_code=reason.value,
                            input_payload={
                                "selected_material": material.value,
                                "weight_gram": float(weight),
                                "cleanliness_score": float(clean_score),
                            },
                            output_payload={
                                "accepted": False,
                                "reason": reason.value,
                            },
                            confidence=confidence,
                            processing_time_ms=rng.randint(160, 540),
                            failure_reason=reason.value,
                            created_at=transaction_time + timedelta(seconds=2),
                        )
                    )
                    add_trace_event(
                        session,
                        transaction=transaction,
                        stage=TraceStage.REJECTED,
                        location_type="hub_input",
                        location_ref=hub.code,
                        actor_user_id=user.id,
                        occurred_at=transaction_time,
                        notes=f"Bottle rejected: {reason.value}",
                        metadata={"reason": reason.value},
                    )

        redemption_time_local = time_between(
            current_date=current_date,
            index=max(0, daily_sessions - 1),
            count=daily_sessions,
            today=today,
            now_local=now_local,
            timezone=timezone,
        ) + timedelta(minutes=8)
        redemption_time = as_utc(
            min(redemption_time_local, now_local - timedelta(minutes=2))
        )
        eligible = [user for user in students if balances[user.id] >= 50]
        if eligible and day_offset % 2 == 0:
            for sequence, user in enumerate(
                rng.sample(eligible, min(2, len(eligible))),
                start=1,
            ):
                affordable = [
                    voucher
                    for voucher in vouchers
                    if voucher.required_points <= balances[user.id]
                ]
                voucher = rng.choice(affordable)
                redemption_code = (
                    f"DEMO-REDEEM-{current_date:%Y%m%d}-"
                    f"{user.student_code}-{sequence}"
                )
                redemption_id = demo_id("redemption", redemption_code)
                used = current_date < today or rng.random() < 0.65
                redemption = VoucherRedemption(
                    id=redemption_id,
                    user_id=user.id,
                    voucher_id=voucher.id,
                    redemption_code=redemption_code,
                    points_spent=voucher.required_points,
                    status=(
                        VoucherRedemptionStatus.USED
                        if used
                        else VoucherRedemptionStatus.ISSUED
                    ),
                    used_at=(
                        redemption_time + timedelta(minutes=12)
                        if used
                        else None
                    ),
                    expires_at=redemption_time + timedelta(days=7),
                    created_at=redemption_time,
                    updated_at=(
                        redemption_time + timedelta(minutes=12)
                        if used
                        else redemption_time
                    ),
                )
                session.add(redemption)
                balances[user.id] -= voucher.required_points
                voucher.quantity_available -= 1
                session.add(
                    PointLedger(
                        id=demo_id("ledger", f"redeem:{redemption_code}"),
                        user_id=user.id,
                        source_type=PointSourceType.VOUCHER_REDEMPTION,
                        source_id=redemption_id,
                        points_change=-voucher.required_points,
                        balance_after=balances[user.id],
                        description=f"Redeemed {voucher.code}",
                        created_at=redemption_time,
                    )
                )

    for user in students:
        user.points_balance = balances[user.id]
        user.total_bottles_returned = accepted_by_user[user.id]
        user.updated_at = as_utc(now_local)
    for batch in batches.values():
        batch.estimated_weight_kg = quantize_kg(batch.estimated_weight_kg)
    session.flush()
    return batches, transactions_by_batch, balances, accepted_by_user


def lifecycle_time(
    deposit_date: date,
    *,
    now_local: datetime,
    timezone: ZoneInfo,
) -> tuple[datetime, datetime, datetime]:
    scheduled = datetime.combine(
        deposit_date + timedelta(days=1), time(7, 30), timezone
    )
    started = scheduled + timedelta(minutes=10)
    completed = started + timedelta(minutes=55)
    if completed >= now_local:
        completed = now_local - timedelta(minutes=12)
        started = completed - timedelta(minutes=45)
        scheduled = started - timedelta(minutes=10)
    return as_utc(scheduled), as_utc(started), as_utc(completed)


def create_pickups_routes_and_receipts(
    session: Session,
    *,
    batches: dict[tuple[date, UUID, MaterialType], MaterialBatch],
    transactions_by_batch: dict[UUID, list[BottleTransaction]],
    hubs: list[Hub],
    vehicle: Vehicle,
    now_local: datetime,
    timezone: ZoneInfo,
) -> tuple[list[str], list[str]]:
    today = now_local.date()
    hub_by_id = {hub.id: hub for hub in hubs}
    hub_key_by_id = {
        hub.id: str(spec["key"])
        for hub, spec in zip(hubs, HUB_SPECS, strict=True)
    }
    batches_by_date_hub: dict[tuple[date, UUID], list[MaterialBatch]] = (
        defaultdict(list)
    )
    for (batch_date, hub_id, _), batch in batches.items():
        if batch.bottle_count:
            batches_by_date_hub[(batch_date, hub_id)].append(batch)

    received_trace_codes: list[str] = []
    stored_trace_codes: list[str] = []
    dates = sorted({batch_date for batch_date, _, _ in batches})
    for batch_date in dates:
        if batch_date >= today:
            for (item_date, _, _), batch in batches.items():
                if item_date == batch_date:
                    stored_trace_codes.extend(
                        transaction.code
                        for transaction in transactions_by_batch[batch.id]
                    )
            continue

        pickup_rows: list[tuple[Hub, Pickup, list[MaterialBatch]]] = []
        for hub in hubs:
            grouped = batches_by_date_hub.get((batch_date, hub.id), [])
            if not grouped:
                continue
            if batch_date == today - timedelta(days=1) and hub.code == (
                BASE_HUB_CODE
            ):
                for batch in grouped:
                    batch.status = MaterialBatchStatus.READY_FOR_PICKUP
                stored_trace_codes.extend(
                    transaction.code
                    for batch in grouped
                    for transaction in transactions_by_batch[batch.id]
                )
                continue

            scheduled, started, completed = lifecycle_time(
                batch_date,
                now_local=now_local,
                timezone=timezone,
            )
            pickup_code = (
                f"DEMO-PICKUP-{batch_date:%Y%m%d}-"
                f"{hub_key_by_id[hub.id]}"
            )
            total_bottles = sum(batch.bottle_count for batch in grouped)
            total_weight = quantize_kg(
                sum(
                    (batch.estimated_weight_kg for batch in grouped),
                    start=Decimal("0"),
                )
            )
            pickup = Pickup(
                id=demo_id("pickup", pickup_code),
                code=pickup_code,
                hub_id=hub.id,
                driver_id=DRIVER_ID,
                status=PickupStatus.COMPLETED,
                scheduled_at=scheduled,
                started_at=started,
                completed_at=completed,
                total_batches=len(grouped),
                total_bottles=total_bottles,
                estimated_weight_kg=total_weight,
                notes="Completed showcase threshold-based pickup",
                created_at=scheduled,
                updated_at=completed,
            )
            session.add(pickup)
            session.flush([pickup])
            for batch in grouped:
                batch.pickup_id = pickup.id
                batch.status = MaterialBatchStatus.RECEIVED
                batch.updated_at = completed + timedelta(hours=2)
            pickup_rows.append((hub, pickup, grouped))

        if not pickup_rows:
            continue
        scheduled, started, completed = lifecycle_time(
            batch_date,
            now_local=now_local,
            timezone=timezone,
        )
        route_code = f"DEMO-ROUTE-{batch_date:%Y%m%d}"
        stop_count = len(pickup_rows)
        optimized_distance = (
            Decimal("0.75") * stop_count + Decimal("0.60")
        ).quantize(Decimal("0.01"))
        baseline_distance = (
            Decimal("1.30") * stop_count + Decimal("1.00")
        ).quantize(Decimal("0.01"))
        saved_percent = (
            (baseline_distance - optimized_distance)
            * Decimal("100")
            / baseline_distance
        ).quantize(Decimal("0.01"))
        total_load = quantize_kg(
            sum(
                (pickup.estimated_weight_kg for _, pickup, _ in pickup_rows),
                start=Decimal("0"),
            )
        )
        route = CollectionRoute(
            id=demo_id("route", route_code),
            code=route_code,
            vehicle_id=vehicle.id,
            status=RouteStatus.COMPLETED,
            threshold_percent=80,
            total_distance_km=optimized_distance,
            baseline_distance_km=baseline_distance,
            distance_saved_percent=saved_percent,
            estimated_load_kg=total_load,
            planned_at=scheduled,
            started_at=started,
            completed_at=completed,
            created_at=scheduled,
            updated_at=completed,
        )
        session.add(route)
        session.flush([route])
        segment_distance = (optimized_distance / stop_count).quantize(
            Decimal("0.01")
        )
        for sequence, (hub, pickup, grouped) in enumerate(
            pickup_rows, start=1
        ):
            collected_at = started + timedelta(minutes=sequence * 10)
            session.add(
                RouteStop(
                    id=demo_id("route-stop", f"{route_code}:{sequence}"),
                    route_id=route.id,
                    hub_id=hub.id,
                    pickup_id=pickup.id,
                    sequence=sequence,
                    distance_from_previous_km=segment_distance,
                    expected_load_kg=pickup.estimated_weight_kg,
                    collected_load_kg=pickup.estimated_weight_kg,
                    collected_at=collected_at,
                )
            )
            received_at = completed + timedelta(hours=2, minutes=sequence * 5)
            for batch in grouped:
                for transaction in transactions_by_batch[batch.id]:
                    add_trace_event(
                        session,
                        transaction=transaction,
                        stage=TraceStage.PICKED_UP,
                        location_type="hub",
                        location_ref=hub.code,
                        actor_user_id=DRIVER_ID,
                        occurred_at=collected_at,
                        notes=f"Collected on route {route.code}",
                        metadata={
                            "pickup_id": str(pickup.id),
                            "route_id": str(route.id),
                        },
                    )
                    add_trace_event(
                        session,
                        transaction=transaction,
                        stage=TraceStage.RECEIVED,
                        location_type="recycler",
                        location_ref="DEMO-RECYCLER-HCM-01",
                        actor_user_id=ADMIN_ID,
                        occurred_at=received_at,
                        notes="Batch weight confirmed at recycler",
                        metadata={
                            "batch_id": str(batch.id),
                            "pickup_id": str(pickup.id),
                            "received_weight_kg": str(
                                batch.estimated_weight_kg
                            ),
                        },
                    )
                    received_trace_codes.append(transaction.code)

    ready_batches = [
        batch
        for batch in batches.values()
        if batch.status == MaterialBatchStatus.READY_FOR_PICKUP
    ]
    if ready_batches:
        planned_time = as_utc(now_local + timedelta(hours=2))
        session.add(
            Pickup(
                id=demo_id("pickup", f"planned:{today}"),
                code=f"DEMO-PICKUP-PLANNED-{today:%Y%m%d}",
                hub_id=ready_batches[0].hub_id,
                driver_id=DRIVER_ID,
                status=PickupStatus.PLANNED,
                scheduled_at=planned_time,
                started_at=None,
                completed_at=None,
                total_batches=0,
                total_bottles=0,
                estimated_weight_kg=Decimal("0"),
                notes="Upcoming pickup for ready showcase batches",
                created_at=as_utc(now_local),
                updated_at=as_utc(now_local),
            )
        )
    session.flush()
    return received_trace_codes, stored_trace_codes


def update_hub_snapshots_and_telemetry(
    session: Session,
    *,
    hubs: list[Hub],
    batches: dict[tuple[date, UUID, MaterialType], MaterialBatch],
    days: int,
    now_local: datetime,
    timezone: ZoneInfo,
    rng: random.Random,
) -> None:
    today = now_local.date()
    open_statuses = {
        MaterialBatchStatus.STORING,
        MaterialBatchStatus.READY_FOR_PICKUP,
    }
    hub_key_by_id = {
        hub.id: str(spec["key"])
        for hub, spec in zip(hubs, HUB_SPECS, strict=True)
    }
    for hub in hubs:
        open_batches = [
            batch
            for (_, hub_id, _), batch in batches.items()
            if hub_id == hub.id and batch.status in open_statuses
        ]
        pet_current = sum(
            batch.bottle_count
            for batch in open_batches
            if batch.material_type == MaterialType.PET
        )
        hdpe_current = sum(
            batch.bottle_count
            for batch in open_batches
            if batch.material_type == MaterialType.HDPE
        )
        key = hub_key_by_id[hub.id]
        target_fill = TARGET_FILL_LEVELS[key]
        hub.pet_current = pet_current
        hub.hdpe_current = hdpe_current
        hub.pet_capacity = max(
            pet_current + 1,
            int(
                (Decimal(max(1, pet_current)) * 100 / target_fill)
                .to_integral_value(rounding=ROUND_UP)
            ),
        )
        hub.hdpe_capacity = max(
            hdpe_current + 1,
            int(
                (Decimal(max(1, hdpe_current)) * 100 / target_fill)
                .to_integral_value(rounding=ROUND_UP)
            ),
        )
        open_weight = quantize_kg(
            sum(
                (batch.estimated_weight_kg for batch in open_batches),
                start=Decimal("0"),
            )
        )
        hub.capacity_kg = max(
            Decimal("1.000"),
            quantize_kg(open_weight * Decimal("100") / target_fill),
        )
        hub.current_load_kg = min(open_weight, hub.capacity_kg)
        hub.fill_level = target_fill
        hub.last_seen_at = as_utc(now_local - timedelta(minutes=4))
        if key == "H4":
            hub.status = HubStatus.OFFLINE
            hub.camera_online = False
            hub.sensor_online = False
        elif target_fill >= hub.pickup_threshold_percent:
            hub.status = HubStatus.NEAR_FULL
            hub.camera_online = True
            hub.sensor_online = True
        else:
            hub.status = HubStatus.ACTIVE
            hub.camera_online = True
            hub.sensor_online = True
        hub.updated_at = as_utc(now_local)

    start_date = today - timedelta(days=days - 1)
    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        for hub in hubs:
            hub_key = hub_key_by_id[hub.id]
            for slot, hour in enumerate((8, 12, 16, 20)):
                reading_local = datetime.combine(
                    current_date, time(hour, 0), timezone
                )
                if reading_local >= now_local:
                    continue
                progress = Decimal(day_offset + 1) / Decimal(days)
                base = Decimal("18") + progress * Decimal("48")
                variation = Decimal(str(rng.uniform(-7, 8)))
                fill = max(
                    Decimal("5"),
                    min(Decimal("92"), base + variation + slot * 3),
                ).quantize(Decimal("0.01"))
                camera_online = not (
                    hub_key == "H4" and current_date == today
                )
                sensor_online = camera_online
                session.add(
                    SensorReading(
                        id=demo_id(
                            "sensor",
                            f"{hub.code}:{reading_local.isoformat()}",
                        ),
                        hub_id=hub.id,
                        fill_level=fill,
                        weight_kg=quantize_kg(
                            hub.capacity_kg * fill / Decimal("100")
                        ),
                        camera_online=camera_online,
                        sensor_online=sensor_online,
                        temperature_c=Decimal(
                            str(rng.uniform(27.2, 33.8))
                        ).quantize(Decimal("0.01")),
                        recorded_at=as_utc(reading_local),
                    )
                )
        if current_date < today:
            continue

    for hub in hubs:
        session.add(
            SensorReading(
                id=demo_id("sensor", f"{hub.code}:latest"),
                hub_id=hub.id,
                fill_level=hub.fill_level,
                weight_kg=hub.current_load_kg,
                camera_online=hub.camera_online,
                sensor_online=hub.sensor_online,
                temperature_c=Decimal("30.20"),
                recorded_at=hub.last_seen_at,
            )
        )
    session.flush()


def validate_and_print(
    session: Session,
    *,
    received_trace_codes: list[str],
    stored_trace_codes: list[str],
) -> None:
    summaries = {
        period: ReportingService(session).dashboard_summary(period)
        for period in ("day", "week", "month")
    }
    if not (
        summaries["day"].transactions_in_period
        <= summaries["week"].transactions_in_period
        <= summaries["month"].transactions_in_period
    ):
        raise RuntimeError("day/week/month transaction windows are invalid")
    if summaries["month"].traceability_completeness_percent != Decimal(
        "100.00"
    ):
        raise RuntimeError("accepted bottles are missing trace events")

    received_code = received_trace_codes[-1]
    received_stages = list(
        session.scalars(
            select(TraceEvent.stage)
            .where(TraceEvent.trace_code == received_code)
            .order_by(TraceEvent.occurred_at)
        )
    )
    expected_stages = [
        TraceStage.DEPOSITED,
        TraceStage.HUB_STORED,
        TraceStage.PICKED_UP,
        TraceStage.RECEIVED,
    ]
    if received_stages != expected_stages:
        raise RuntimeError(
            f"trace {received_code} is incomplete: {received_stages}"
        )

    total_transactions = session.scalar(
        select(func.count())
        .select_from(BottleTransaction)
        .where(BottleTransaction.code.like("DEMO-TX-%"))
    ) or 0
    accepted = session.scalar(
        select(func.count())
        .select_from(BottleTransaction)
        .where(
            BottleTransaction.code.like("DEMO-TX-%"),
            BottleTransaction.status == BottleTransactionStatus.ACCEPTED,
        )
    ) or 0
    rejected = total_transactions - accepted
    print("\nShowcase dataset ready.")
    print(f"Total generated transactions: {total_transactions}")
    print(f"Accepted / rejected: {accepted} / {rejected}")
    for period, summary in summaries.items():
        print(
            f"{period.upper():5} | transactions={summary.transactions_in_period:4} "
            f"participants={summary.participants:2} "
            f"recovered_kg={summary.recovered_weight_kg} "
            f"routes={summary.completed_routes:2} "
            f"trace={summary.traceability_completeness_percent}%"
        )
    print(f"Full received trace code: {received_code}")
    if stored_trace_codes:
        print(f"Hub-stored trace code: {stored_trace_codes[-1]}")
    rejected_code = session.scalar(
        select(BottleTransaction.code)
        .where(
            BottleTransaction.code.like("DEMO-TX-%"),
            BottleTransaction.status == BottleTransactionStatus.REJECTED,
        )
        .order_by(BottleTransaction.created_at.desc())
    )
    if rejected_code:
        print(f"Rejected trace code: {rejected_code}")


def build_dataset(
    *,
    days: int,
    students: int,
    sessions_per_day: int,
    reset: bool,
) -> None:
    if settings.app_env.casefold() == "production":
        raise RuntimeError("showcase data cannot be generated in production")
    timezone = ZoneInfo(settings.reporting_timezone)
    now_local = datetime.now(timezone).replace(microsecond=0)
    start = as_utc(now_local - timedelta(days=days + 30))
    rng = random.Random(20260715)

    with SessionLocal.begin() as session:
        existing = session.scalar(
            select(func.count())
            .select_from(BottleTransaction)
            .where(BottleTransaction.code.like("DEMO-TX-%"))
        ) or 0
        if existing and not reset:
            raise RuntimeError(
                "showcase data already exists; rerun with --reset to rebuild"
            )
        if reset:
            reset_demo_data(session)

        driver = session.get(User, DRIVER_ID)
        admin = session.get(User, ADMIN_ID)
        if driver is None or driver.role != UserRole.DRIVER:
            raise RuntimeError("run python -m scripts.seed_database first")
        if admin is None or admin.role != UserRole.ADMIN:
            raise RuntimeError("run python -m scripts.seed_database first")

        hubs = ensure_hubs(session, start)
        demo_students, _, _ = create_demo_users(
            session,
            student_count=students,
            created_at=start,
        )
        vouchers = ensure_vouchers(
            session,
            start=start,
            end=as_utc(now_local),
        )
        vehicle = create_vehicle(
            session,
            driver_id=driver.id,
            created_at=start,
        )
        (
            batches,
            transactions_by_batch,
            _,
            _,
        ) = create_transactions(
            session,
            rng=rng,
            students=demo_students,
            hubs=hubs,
            vouchers=vouchers,
            days=days,
            sessions_per_day=sessions_per_day,
            now_local=now_local,
            timezone=timezone,
        )
        received_codes, stored_codes = create_pickups_routes_and_receipts(
            session,
            batches=batches,
            transactions_by_batch=transactions_by_batch,
            hubs=hubs,
            vehicle=vehicle,
            now_local=now_local,
            timezone=timezone,
        )
        update_hub_snapshots_and_telemetry(
            session,
            hubs=hubs,
            batches=batches,
            days=days,
            now_local=now_local,
            timezone=timezone,
            rng=rng,
        )
        session.flush()
        validate_and_print(
            session,
            received_trace_codes=received_codes,
            stored_trace_codes=stored_codes,
        )

    print("\nStaff accounts for the connected dashboard:")
    print("  admin@reloop.vn / Admin@123")
    print("  demo.operator@reloop.vn / DemoStaff@123")
    print("  demo.recycler@reloop.vn / DemoStaff@123")
    print("Example API-only student account:")
    print("  demo.student.01@reloop.vn / DemoStudent@123")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a large traceable ReLoop showcase dataset."
    )
    parser.add_argument("--days", type=int, default=35)
    parser.add_argument("--students", type=int, default=36)
    parser.add_argument("--sessions-per-day", type=int, default=12)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and rebuild only generator-owned demo data.",
    )
    args = parser.parse_args()
    if args.days < 8:
        parser.error("--days must be at least 8")
    if args.students < 8:
        parser.error("--students must be at least 8")
    if args.sessions_per_day < 4:
        parser.error("--sessions-per-day must be at least 4")
    return args


def main() -> None:
    args = parse_args()
    build_dataset(
        days=args.days,
        students=args.students,
        sessions_per_day=args.sessions_per_day,
        reset=args.reset,
    )


if __name__ == "__main__":
    main()
