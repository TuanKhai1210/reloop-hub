from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import CollectionRoute, Deposit, DepositStatus, MaterialType, RouteStatus
from app.schemas import ESGReport


CO2_FACTORS = {MaterialType.PET: 1.7, MaterialType.HDPE: 1.5}


def report_range(period: str, anchor: date | None) -> tuple[date, date]:
    anchor = anchor or datetime.now(timezone.utc).date()
    if period == "day":
        return anchor, anchor
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        return anchor.replace(day=1), anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
    raise HTTPException(status_code=422, detail="period phải là day, week hoặc month")


def build_esg_report(db: Session, period: str, anchor: date | None = None) -> ESGReport:
    from_date, to_date = report_range(period, anchor)
    start_dt = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
    date_filter = (Deposit.created_at >= start_dt, Deposit.created_at < end_dt)

    rows = db.execute(
        select(Deposit.material_type, func.coalesce(func.sum(Deposit.weight_g), 0))
        .where(Deposit.status == DepositStatus.ACCEPTED, *date_filter)
        .group_by(Deposit.material_type)
    ).all()
    weights = {material: float(weight) / 1000 for material, weight in rows}
    pet = weights.get(MaterialType.PET, 0.0)
    hdpe = weights.get(MaterialType.HDPE, 0.0)

    accepted = db.scalar(
        select(func.count(Deposit.id)).where(Deposit.status == DepositStatus.ACCEPTED, *date_filter)
    ) or 0
    rejected = db.scalar(
        select(func.count(Deposit.id)).where(Deposit.status == DepositStatus.REJECTED, *date_filter)
    ) or 0
    users = db.scalar(
        select(func.count(distinct(Deposit.user_id))).where(
            Deposit.status == DepositStatus.ACCEPTED,
            Deposit.user_id.is_not(None),
            *date_filter,
        )
    ) or 0

    route_filter = (
        CollectionRoute.status == RouteStatus.COMPLETED,
        CollectionRoute.completed_at >= start_dt,
        CollectionRoute.completed_at < end_dt,
    )
    route_aggregate = db.execute(
        select(
            func.count(CollectionRoute.id),
            func.coalesce(func.sum(CollectionRoute.total_distance_km), 0),
            func.coalesce(func.sum(CollectionRoute.baseline_distance_km), 0),
        ).where(*route_filter)
    ).one()
    route_count, distance, baseline = int(route_aggregate[0]), float(route_aggregate[1]), float(route_aggregate[2])
    saved = max(0.0, baseline - distance)
    total_checks = accepted + rejected

    return ESGReport(
        period=period,
        from_date=from_date,
        to_date=to_date,
        pet_recovered_kg=round(pet, 3),
        hdpe_recovered_kg=round(hdpe, 3),
        total_plastic_recovered_kg=round(pet + hdpe, 3),
        co2_avoided_kg=round(pet * CO2_FACTORS[MaterialType.PET] + hdpe * CO2_FACTORS[MaterialType.HDPE], 3),
        collection_distance_km=round(distance, 3),
        baseline_distance_km=round(baseline, 3),
        distance_reduced_km=round(saved, 3),
        distance_reduced_percent=round(saved / baseline * 100, 2) if baseline else 0,
        participating_users=users,
        successful_transactions=accepted,
        rejected_transactions=rejected,
        quality_acceptance_rate_percent=round(accepted / total_checks * 100, 2) if total_checks else 0,
        completed_routes=route_count,
        methodology={
            "plastic": "Chỉ tính giao dịch PET/HDPE được Edge AI và cảm biến chấp nhận.",
            "co2": "Ước tính: PET 1,7 kgCO2e/kg; HDPE 1,5 kgCO2e/kg. Hệ số cấu hình cần được kiểm chứng cho báo cáo chính thức.",
            "logistics": "So sánh quãng đường tuyến DVRP với tổng quãng đường khứ hồi từng Hub của lịch cố định.",
        },
    )

