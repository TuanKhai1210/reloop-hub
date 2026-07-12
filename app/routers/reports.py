from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import DashboardSummary, ESGReport
from app.services import ReportingService


router = APIRouter(tags=["Dashboard and ESG"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DashboardSummary:
    return ReportingService(db).dashboard_summary()


@router.get("/reports/esg", response_model=ESGReport)
def esg_report(
    period: str = Query(default="day", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ESGReport:
    try:
        return ReportingService(db).esg_report(period)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
