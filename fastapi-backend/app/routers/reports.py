from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Deposit, DepositStatus, Hub, HubStatus, User
from app.schemas import DashboardSummary, ESGReport
from app.services.reporting import CO2_FACTORS, build_esg_report


router = APIRouter(tags=["Dashboard & ESG"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> DashboardSummary:
    today = datetime.now(timezone.utc).date()
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    accepted_filter = (
        Deposit.status == DepositStatus.ACCEPTED,
        Deposit.created_at >= start,
        Deposit.created_at < end,
    )
    material_rows = db.execute(
        select(Deposit.material_type, func.coalesce(func.sum(Deposit.weight_g), 0))
        .where(*accepted_filter)
        .group_by(Deposit.material_type)
    ).all()
    plastic_kg = sum(float(weight) for _, weight in material_rows) / 1000
    co2 = sum(float(weight) / 1000 * CO2_FACTORS[material] for material, weight in material_rows)
    hubs_total = db.scalar(select(func.count(Hub.id))) or 0
    hubs_online = db.scalar(select(func.count(Hub.id)).where(Hub.status == HubStatus.ONLINE)) or 0
    hubs_full = db.scalar(select(func.count(Hub.id)).where(Hub.status == HubStatus.FULL)) or 0
    alerts = db.scalar(
        select(func.count(Hub.id)).where(
            (Hub.status.in_([HubStatus.OFFLINE, HubStatus.MAINTENANCE, HubStatus.FULL]))
            | (Hub.camera_online.is_(False))
            | (Hub.sensor_online.is_(False))
        )
    ) or 0
    transactions = db.scalar(select(func.count(Deposit.id)).where(*accepted_filter)) or 0
    active_users = db.scalar(
        select(func.count(distinct(Deposit.user_id))).where(Deposit.user_id.is_not(None), *accepted_filter)
    ) or 0
    return DashboardSummary(
        hubs_total=hubs_total,
        hubs_online=hubs_online,
        hubs_full=hubs_full,
        alerts=alerts,
        plastic_today_kg=round(plastic_kg, 3),
        transactions_today=transactions,
        active_users_today=active_users,
        co2_avoided_today_kg=round(co2, 3),
    )


@router.get("/reports/esg", response_model=ESGReport)
def esg_report(
    period: str = Query(default="month", pattern="^(day|week|month)$"),
    anchor_date: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ESGReport:
    return build_esg_report(db, period, anchor_date)

