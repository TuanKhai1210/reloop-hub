from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BottleTransaction,
    BottleTransactionStatus,
    CollectionRoute,
    Hub,
    HubStatus,
    MaterialBatch,
    MaterialBatchStatus,
    MaterialType,
    Pickup,
    PickupStatus,
    RouteStatus,
    TraceEvent,
    User,
)
from app.schemas import DashboardSummary, ESGReport


class ReportingService:
    TRUCK_CO2_KG_PER_KM = Decimal("0.27")

    def __init__(self, session: Session) -> None:
        self.session = session

    def dashboard_summary(self) -> DashboardSummary:
        today = datetime.now(UTC).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        accepted_weight_grams = self.session.scalar(
            select(func.coalesce(func.sum(BottleTransaction.weight_gram), 0))
            .where(
                BottleTransaction.status
                == BottleTransactionStatus.ACCEPTED
            )
        )
        return DashboardSummary(
            users=self._count(User),
            active_hubs=self.session.scalar(
                select(func.count())
                .select_from(Hub)
                .where(
                    Hub.status.in_(
                        [HubStatus.ACTIVE, HubStatus.NEAR_FULL]
                    )
                )
            )
            or 0,
            transactions_today=self.session.scalar(
                select(func.count())
                .select_from(BottleTransaction)
                .where(BottleTransaction.created_at >= today)
            )
            or 0,
            accepted_bottles=self._transaction_count(
                BottleTransactionStatus.ACCEPTED
            ),
            rejected_bottles=self._transaction_count(
                BottleTransactionStatus.REJECTED
            ),
            recovered_weight_kg=(
                Decimal(accepted_weight_grams or 0) / Decimal("1000")
            ).quantize(Decimal("0.001")),
            ready_batches=self.session.scalar(
                select(func.count())
                .select_from(MaterialBatch)
                .where(
                    MaterialBatch.status
                    == MaterialBatchStatus.READY_FOR_PICKUP
                )
            )
            or 0,
            active_pickups=self.session.scalar(
                select(func.count())
                .select_from(Pickup)
                .where(
                    Pickup.status.in_(
                        [PickupStatus.PLANNED, PickupStatus.IN_PROGRESS]
                    )
                )
            )
            or 0,
        )

    def esg_report(self, period: str) -> ESGReport:
        start = self._period_start(period)
        accepted_filter = (
            BottleTransaction.status
            == BottleTransactionStatus.ACCEPTED,
            BottleTransaction.created_at >= start,
        )
        total_weight = self.session.scalar(
            select(func.coalesce(func.sum(BottleTransaction.weight_gram), 0))
            .where(*accepted_filter)
        )
        pet = self.session.scalar(
            select(func.count())
            .select_from(BottleTransaction)
            .where(
                *accepted_filter,
                BottleTransaction.material_type == MaterialType.PET,
            )
        )
        hdpe = self.session.scalar(
            select(func.count())
            .select_from(BottleTransaction)
            .where(
                *accepted_filter,
                BottleTransaction.material_type == MaterialType.HDPE,
            )
        )
        rejected = self.session.scalar(
            select(func.count())
            .select_from(BottleTransaction)
            .where(
                BottleTransaction.status
                == BottleTransactionStatus.REJECTED,
                BottleTransaction.created_at >= start,
            )
        )
        completed_routes = self.session.scalar(
            select(func.count())
            .select_from(CollectionRoute)
            .where(
                CollectionRoute.status == RouteStatus.COMPLETED,
                CollectionRoute.completed_at >= start,
            )
        )
        distance_saved = self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        CollectionRoute.baseline_distance_km
                        - CollectionRoute.total_distance_km
                    ),
                    0,
                )
            ).where(
                CollectionRoute.status == RouteStatus.COMPLETED,
                CollectionRoute.completed_at >= start,
            )
        )
        accepted_count = int(pet or 0) + int(hdpe or 0)
        traced_count = self.session.scalar(
            select(func.count(func.distinct(TraceEvent.transaction_id)))
            .where(
                TraceEvent.transaction_id.is_not(None),
                TraceEvent.occurred_at >= start,
            )
        )
        completeness = (
            Decimal(traced_count or 0)
            / Decimal(accepted_count)
            * Decimal("100")
            if accepted_count
            else Decimal("0")
        )
        saved = Decimal(distance_saved or 0)
        return ESGReport(
            period=period,
            total_plastic_recovered_kg=(
                Decimal(total_weight or 0) / Decimal("1000")
            ).quantize(Decimal("0.001")),
            pet_bottles=int(pet or 0),
            hdpe_bottles=int(hdpe or 0),
            rejected_bottles=int(rejected or 0),
            completed_routes=int(completed_routes or 0),
            distance_saved_km=saved.quantize(Decimal("0.01")),
            estimated_co2_saved_kg=(
                saved * self.TRUCK_CO2_KG_PER_KM
            ).quantize(Decimal("0.01")),
            traceability_completeness_percent=min(
                Decimal("100"), completeness
            ).quantize(Decimal("0.01")),
        )

    def _transaction_count(
        self,
        status: BottleTransactionStatus,
    ) -> int:
        return self.session.scalar(
            select(func.count())
            .select_from(BottleTransaction)
            .where(BottleTransaction.status == status)
        ) or 0

    def _count(self, model: type) -> int:
        return self.session.scalar(
            select(func.count()).select_from(model)
        ) or 0

    @staticmethod
    def _period_start(period: str) -> datetime:
        now = datetime.now(UTC)
        periods = {
            "day": timedelta(days=1),
            "week": timedelta(days=7),
            "month": timedelta(days=30),
        }
        if period not in periods:
            raise ValueError("period must be day, week, or month")
        return now - periods[period]
