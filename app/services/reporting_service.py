from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
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
    ReturnSession,
    RouteStatus,
    RouteStop,
    TraceEvent,
    User,
    Vehicle,
)
from app.schemas import DashboardSummary, ESGReport


class ReportingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def dashboard_summary(self, period: str = "day") -> DashboardSummary:
        start, end = self.period_window(period)
        today_start, _ = self.period_window("day")
        transaction_window = (
            BottleTransaction.created_at >= start,
            BottleTransaction.created_at < end,
        )

        accepted = self._transaction_count(
            BottleTransactionStatus.ACCEPTED,
            *transaction_window,
        )
        rejected = self._transaction_count(
            BottleTransactionStatus.REJECTED,
            *transaction_window,
        )
        total_transactions = accepted + rejected
        total_weight_grams = self.session.scalar(
            select(
                func.coalesce(func.sum(BottleTransaction.weight_gram), 0)
            ).where(
                BottleTransaction.status
                == BottleTransactionStatus.ACCEPTED,
                *transaction_window,
            )
        )
        recovered_weight_kg = (
            Decimal(total_weight_grams or 0) / Decimal("1000")
        )

        pet = self._material_count(MaterialType.PET, *transaction_window)
        hdpe = self._material_count(
            MaterialType.HDPE,
            *transaction_window,
        )
        participants = self.session.scalar(
            select(func.count(func.distinct(ReturnSession.user_id)))
            .select_from(BottleTransaction)
            .join(
                ReturnSession,
                ReturnSession.id == BottleTransaction.session_id,
            )
            .where(*transaction_window)
        )

        average_ai_confidence = self.session.scalar(
            select(func.avg(BottleTransaction.ai_confidence)).where(
                BottleTransaction.ai_confidence.is_not(None),
                *transaction_window,
            )
        )
        average_cleanliness_score = self.session.scalar(
            select(func.avg(BottleTransaction.cleanliness_score)).where(
                BottleTransaction.cleanliness_score.is_not(None),
                *transaction_window,
            )
        )
        rejection_rows = self.session.execute(
            select(
                BottleTransaction.reject_reason,
                func.count(BottleTransaction.id),
            )
            .where(
                BottleTransaction.status
                == BottleTransactionStatus.REJECTED,
                *transaction_window,
            )
            .group_by(BottleTransaction.reject_reason)
        ).all()
        rejection_reasons = {
            getattr(reason, "value", str(reason)): int(count)
            for reason, count in rejection_rows
            if reason is not None
        }

        route_filter = (
            CollectionRoute.status == RouteStatus.COMPLETED,
            CollectionRoute.completed_at >= start,
            CollectionRoute.completed_at < end,
        )
        completed_routes = self.session.scalar(
            select(func.count())
            .select_from(CollectionRoute)
            .where(*route_filter)
        ) or 0
        baseline_distance = Decimal(
            self.session.scalar(
                select(
                    func.coalesce(
                        func.sum(CollectionRoute.baseline_distance_km),
                        0,
                    )
                ).where(*route_filter)
            )
            or 0
        )
        optimized_distance = Decimal(
            self.session.scalar(
                select(
                    func.coalesce(
                        func.sum(CollectionRoute.total_distance_km),
                        0,
                    )
                ).where(*route_filter)
            )
            or 0
        )
        distance_saved = max(
            Decimal("0"), baseline_distance - optimized_distance
        )
        actual_collected_load = Decimal(
            self.session.scalar(
                select(
                    func.coalesce(func.sum(RouteStop.collected_load_kg), 0)
                )
                .select_from(RouteStop)
                .join(
                    CollectionRoute,
                    CollectionRoute.id == RouteStop.route_id,
                )
                .where(*route_filter)
            )
            or 0
        )
        available_vehicle_capacity = Decimal(
            self.session.scalar(
                select(
                    func.coalesce(func.sum(Vehicle.capacity_kg), 0)
                )
                .select_from(CollectionRoute)
                .join(Vehicle, Vehicle.id == CollectionRoute.vehicle_id)
                .where(*route_filter)
            )
            or 0
        )

        traced_count = self.session.scalar(
            select(func.count(func.distinct(BottleTransaction.id)))
            .select_from(BottleTransaction)
            .join(
                TraceEvent,
                TraceEvent.transaction_id == BottleTransaction.id,
            )
            .where(
                BottleTransaction.status
                == BottleTransactionStatus.ACCEPTED,
                *transaction_window,
            )
        ) or 0

        return DashboardSummary(
            period=period,
            period_start=start,
            period_end=end,
            reporting_timezone=settings.reporting_timezone,
            users=self._count(User),
            participants=int(participants or 0),
            active_hubs=self._hub_count(
                HubStatus.ACTIVE,
                HubStatus.NEAR_FULL,
                HubStatus.FULL,
            ),
            near_full_hubs=self._hub_count(
                HubStatus.NEAR_FULL,
                HubStatus.FULL,
            ),
            offline_hubs=self._hub_count(HubStatus.OFFLINE),
            camera_online_hubs=self._hub_boolean_count(
                Hub.camera_online
            ),
            sensor_online_hubs=self._hub_boolean_count(
                Hub.sensor_online
            ),
            transactions_today=self.session.scalar(
                select(func.count())
                .select_from(BottleTransaction)
                .where(
                    BottleTransaction.created_at >= today_start,
                    BottleTransaction.created_at < end,
                )
            )
            or 0,
            transactions_in_period=total_transactions,
            successful_transactions=accepted,
            accepted_bottles=accepted,
            rejected_bottles=rejected,
            success_rate_percent=self._percent(
                Decimal(accepted), Decimal(total_transactions)
            ),
            pet_bottles=pet,
            hdpe_bottles=hdpe,
            recovered_weight_kg=recovered_weight_kg.quantize(
                Decimal("0.001")
            ),
            average_ai_confidence=self._decimal_or_zero(
                average_ai_confidence,
                Decimal("0.0001"),
            ),
            average_cleanliness_score=self._decimal_or_zero(
                average_cleanliness_score,
                Decimal("0.0001"),
            ),
            rejection_reasons=rejection_reasons,
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
            completed_routes=int(completed_routes),
            baseline_distance_km=baseline_distance.quantize(
                Decimal("0.01")
            ),
            optimized_distance_km=optimized_distance.quantize(
                Decimal("0.01")
            ),
            distance_saved_km=distance_saved.quantize(Decimal("0.01")),
            distance_saved_percent=self._percent(
                distance_saved, baseline_distance
            ),
            collection_efficiency_kg_per_km=self._ratio(
                recovered_weight_kg,
                optimized_distance,
                Decimal("0.001"),
            ),
            vehicle_utilization_percent=self._percent(
                actual_collected_load,
                available_vehicle_capacity,
            ),
            estimated_co2_saved_kg=(
                distance_saved
                * settings.co2_emission_factor_kg_per_km
            ).quantize(Decimal("0.01")),
            traceability_completeness_percent=self._percent(
                Decimal(traced_count), Decimal(accepted)
            ),
        )

    def esg_report(self, period: str) -> ESGReport:
        summary = self.dashboard_summary(period)
        return ESGReport(
            period=summary.period,
            period_start=summary.period_start,
            period_end=summary.period_end,
            reporting_timezone=summary.reporting_timezone,
            participants=summary.participants,
            total_transactions=summary.transactions_in_period,
            successful_transactions=summary.successful_transactions,
            success_rate_percent=summary.success_rate_percent,
            total_plastic_recovered_kg=summary.recovered_weight_kg,
            pet_bottles=summary.pet_bottles,
            hdpe_bottles=summary.hdpe_bottles,
            rejected_bottles=summary.rejected_bottles,
            completed_routes=summary.completed_routes,
            baseline_distance_km=summary.baseline_distance_km,
            optimized_distance_km=summary.optimized_distance_km,
            distance_saved_km=summary.distance_saved_km,
            distance_saved_percent=summary.distance_saved_percent,
            collection_efficiency_kg_per_km=(
                summary.collection_efficiency_kg_per_km
            ),
            vehicle_utilization_percent=(
                summary.vehicle_utilization_percent
            ),
            estimated_co2_saved_kg=summary.estimated_co2_saved_kg,
            traceability_completeness_percent=(
                summary.traceability_completeness_percent
            ),
            co2_emission_factor_kg_per_km=(
                settings.co2_emission_factor_kg_per_km
            ),
            co2_methodology_version=settings.co2_methodology_version,
            co2_factor_source=settings.co2_factor_source,
        )

    def _transaction_count(
        self,
        status: BottleTransactionStatus,
        *filters: object,
    ) -> int:
        return self.session.scalar(
            select(func.count())
            .select_from(BottleTransaction)
            .where(BottleTransaction.status == status, *filters)
        ) or 0

    def _material_count(
        self,
        material_type: MaterialType,
        *filters: object,
    ) -> int:
        return self.session.scalar(
            select(func.count())
            .select_from(BottleTransaction)
            .where(
                BottleTransaction.status
                == BottleTransactionStatus.ACCEPTED,
                BottleTransaction.material_type == material_type,
                *filters,
            )
        ) or 0

    def _hub_count(self, *statuses: HubStatus) -> int:
        return self.session.scalar(
            select(func.count())
            .select_from(Hub)
            .where(Hub.status.in_(statuses))
        ) or 0

    def _hub_boolean_count(self, column: object) -> int:
        return self.session.scalar(
            select(func.count()).select_from(Hub).where(column.is_(True))
        ) or 0

    def _count(self, model: type) -> int:
        return self.session.scalar(
            select(func.count()).select_from(model)
        ) or 0

    @staticmethod
    def _decimal_or_zero(value: object, quantum: Decimal) -> Decimal:
        return Decimal(value or 0).quantize(quantum)

    @staticmethod
    def _ratio(
        numerator: Decimal,
        denominator: Decimal,
        quantum: Decimal,
    ) -> Decimal:
        if denominator <= 0:
            return Decimal("0").quantize(quantum)
        return (numerator / denominator).quantize(quantum)

    @classmethod
    def _percent(
        cls,
        numerator: Decimal,
        denominator: Decimal,
    ) -> Decimal:
        return cls._ratio(
            numerator * Decimal("100"),
            denominator,
            Decimal("0.01"),
        )

    @staticmethod
    def period_window(period: str) -> tuple[datetime, datetime]:
        try:
            timezone = ZoneInfo(settings.reporting_timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(
                "REPORTING_TIMEZONE is not a valid IANA timezone"
            ) from error

        now = datetime.now(timezone)
        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            ) - timedelta(days=now.weekday())
        elif period == "month":
            start = now.replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        else:
            raise ValueError("period must be day, week, or month")
        return start.astimezone(UTC), now.astimezone(UTC)
