import math
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BottleTransaction,
    CollectionRoute,
    Hub,
    MaterialBatch,
    MaterialBatchStatus,
    PickupStatus,
    RouteStatus,
    RouteStop,
    TraceEvent,
    TraceStage,
    User,
    UserRole,
    Vehicle,
)
from app.services.errors import EntityNotFoundError, InvalidStateError
from app.services.pickup_commands import (
    AssignBatchCommand,
    CreatePickupCommand,
)
from app.services.pickup_service import PickupService


class RouteService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.pickup_service = PickupService(session)

    def optimize_route(
        self,
        *,
        vehicle_id: UUID,
        fill_threshold: int,
    ) -> CollectionRoute:
        vehicle = self.session.get(Vehicle, vehicle_id)
        if vehicle is None or not vehicle.active:
            raise EntityNotFoundError("active vehicle not found")
        if vehicle.driver_id is None:
            raise InvalidStateError("vehicle has no assigned driver")
        driver = self.session.get(User, vehicle.driver_id)
        if driver is None or driver.role != UserRole.DRIVER:
            raise InvalidStateError(
                "vehicle driver is missing or has an invalid role"
            )

        rows = self.session.execute(
            select(
                Hub,
                func.sum(MaterialBatch.estimated_weight_kg),
            )
            .join(MaterialBatch, MaterialBatch.hub_id == Hub.id)
            .where(
                MaterialBatch.status
                == MaterialBatchStatus.READY_FOR_PICKUP,
                MaterialBatch.pickup_id.is_(None),
            )
            .group_by(Hub.id)
        ).all()
        candidates = [
            (hub, Decimal(str(weight or 0)))
            for hub, weight in rows
            if hub.fill_level >= fill_threshold
            or hub.status.value in {"NEAR_FULL", "FULL"}
        ]
        if not candidates:
            raise InvalidStateError("no collection-ready hubs")

        ordered_all = self._nearest_neighbor(vehicle, candidates)
        ordered: list[tuple[Hub, Decimal, Decimal]] = []
        selected_weight = Decimal("0")
        for item in ordered_all:
            if selected_weight + item[1] > vehicle.capacity_kg:
                continue
            ordered.append(item)
            selected_weight += item[1]
        if not ordered:
            raise InvalidStateError(
                "collection-ready load exceeds vehicle capacity"
            )
        selected_candidates = [
            (hub, weight) for hub, weight, _ in ordered
        ]
        total_distance = sum(item[2] for item in ordered)
        baseline_distance = self._baseline_distance(
            vehicle,
            selected_candidates,
        )
        saved_percent = (
            (baseline_distance - total_distance)
            / baseline_distance
            * Decimal("100")
            if baseline_distance > 0
            else Decimal("0")
        )
        route = CollectionRoute(
            code=f"ROUTE-{uuid4().hex[:12].upper()}",
            vehicle_id=vehicle.id,
            status=RouteStatus.PLANNED,
            threshold_percent=fill_threshold,
            total_distance_km=total_distance.quantize(Decimal("0.01")),
            baseline_distance_km=baseline_distance.quantize(
                Decimal("0.01")
            ),
            distance_saved_percent=max(
                Decimal("0"), saved_percent
            ).quantize(Decimal("0.01")),
            estimated_load_kg=sum(
                (weight for _, weight in selected_candidates),
                start=Decimal("0"),
            ),
        )
        self.session.add(route)
        self.session.flush()

        for sequence, (hub, weight, distance) in enumerate(
            ordered,
            start=1,
        ):
            self.session.add(
                RouteStop(
                    route_id=route.id,
                    hub_id=hub.id,
                    pickup_id=None,
                    sequence=sequence,
                    distance_from_previous_km=distance,
                    expected_load_kg=weight,
                    collected_load_kg=None,
                    collected_at=None,
                )
            )
        self.session.flush()
        return route

    def start_route(self, route_id: UUID) -> CollectionRoute:
        route = self._lock_route(route_id)
        if route.status != RouteStatus.PLANNED:
            raise InvalidStateError("route is not planned")
        route.status = RouteStatus.IN_PROGRESS
        route.started_at = datetime.now(UTC)
        self.session.flush()
        return route

    def collect_stop(
        self,
        *,
        route_id: UUID,
        stop_id: UUID,
        collected_load_kg: Decimal,
        actor_user_id: UUID,
    ) -> RouteStop:
        route = self._lock_route(route_id)
        if route.status != RouteStatus.IN_PROGRESS:
            raise InvalidStateError("route is not in progress")

        stop = self.session.scalar(
            select(RouteStop)
            .where(
                RouteStop.id == stop_id,
                RouteStop.route_id == route.id,
            )
            .with_for_update()
        )
        if stop is None:
            raise EntityNotFoundError("route stop not found")
        if stop.collected_at is not None:
            raise InvalidStateError("route stop is already collected")

        vehicle = self.session.get(Vehicle, route.vehicle_id)
        if vehicle is None or vehicle.driver_id is None:
            raise InvalidStateError("route vehicle has no driver")
        collected_so_far = self.session.scalar(
            select(func.coalesce(func.sum(RouteStop.collected_load_kg), 0))
            .where(RouteStop.route_id == route.id)
        )
        if Decimal(collected_so_far or 0) + collected_load_kg > (
            vehicle.capacity_kg
        ):
            raise InvalidStateError(
                "collected route load exceeds vehicle capacity"
            )

        batches = list(
            self.session.scalars(
                select(MaterialBatch)
                .where(
                    MaterialBatch.hub_id == stop.hub_id,
                    MaterialBatch.status
                    == MaterialBatchStatus.READY_FOR_PICKUP,
                    MaterialBatch.pickup_id.is_(None),
                )
                .order_by(MaterialBatch.id)
            )
        )
        if not batches:
            raise InvalidStateError(
                "route stop has no collection-ready batches"
            )

        pickup = self.pickup_service.create_pickup(
            CreatePickupCommand(
                code=f"PICKUP-{uuid4().hex[:12].upper()}",
                hub_id=stop.hub_id,
                driver_id=vehicle.driver_id,
                notes=f"Route {route.code}, stop {stop.sequence}",
            )
        )
        for batch in batches:
            self.pickup_service.assign_batch(
                AssignBatchCommand(
                    pickup_id=pickup.id,
                    batch_id=batch.id,
                )
            )
        self.pickup_service.complete_pickup(pickup.id)

        hub = self.session.get(Hub, stop.hub_id)
        if hub is None:
            raise EntityNotFoundError("route stop hub not found")
        transactions = self.session.scalars(
            select(BottleTransaction).where(
                BottleTransaction.batch_id.in_(
                    [batch.id for batch in batches]
                )
            )
        )
        for transaction in transactions:
            self.session.add(
                TraceEvent(
                    trace_code=transaction.code,
                    transaction_id=transaction.id,
                    stage=TraceStage.PICKED_UP,
                    location_type="hub",
                    location_ref=hub.code,
                    actor_user_id=actor_user_id,
                    notes=f"Collected by route {route.code}",
                    event_metadata={"pickup_id": str(pickup.id)},
                    occurred_at=datetime.now(UTC),
                )
            )

        stop.pickup_id = pickup.id
        stop.collected_load_kg = collected_load_kg
        stop.collected_at = datetime.now(UTC)
        self.session.flush()
        return stop

    def complete_route(self, route_id: UUID) -> CollectionRoute:
        route = self._lock_route(route_id)
        if route.status != RouteStatus.IN_PROGRESS:
            raise InvalidStateError("route is not in progress")
        uncollected = self.session.scalar(
            select(func.count())
            .select_from(RouteStop)
            .where(
                RouteStop.route_id == route.id,
                RouteStop.collected_at.is_(None),
            )
        )
        if uncollected:
            raise InvalidStateError("route has uncollected stops")
        route.status = RouteStatus.COMPLETED
        route.completed_at = datetime.now(UTC)
        self.session.flush()
        return route

    def get_route_stops(self, route_id: UUID) -> list[RouteStop]:
        return list(
            self.session.scalars(
                select(RouteStop)
                .where(RouteStop.route_id == route_id)
                .order_by(RouteStop.sequence)
            )
        )

    def _lock_route(self, route_id: UUID) -> CollectionRoute:
        route = self.session.scalar(
            select(CollectionRoute)
            .where(CollectionRoute.id == route_id)
            .with_for_update()
        )
        if route is None:
            raise EntityNotFoundError("route not found")
        return route

    @classmethod
    def _nearest_neighbor(
        cls,
        vehicle: Vehicle,
        candidates: list[tuple[Hub, Decimal]],
    ) -> list[tuple[Hub, Decimal, Decimal]]:
        remaining = candidates.copy()
        latitude = Decimal(vehicle.latitude)
        longitude = Decimal(vehicle.longitude)
        ordered: list[tuple[Hub, Decimal, Decimal]] = []
        while remaining:
            selected = min(
                remaining,
                key=lambda item: cls._distance(
                    latitude,
                    longitude,
                    Decimal(item[0].latitude or 0),
                    Decimal(item[0].longitude or 0),
                ),
            )
            hub, weight = selected
            distance = cls._distance(
                latitude,
                longitude,
                Decimal(hub.latitude or 0),
                Decimal(hub.longitude or 0),
            )
            ordered.append((hub, weight, distance))
            latitude = Decimal(hub.latitude or 0)
            longitude = Decimal(hub.longitude or 0)
            remaining.remove(selected)
        return ordered

    @classmethod
    def _baseline_distance(
        cls,
        vehicle: Vehicle,
        candidates: list[tuple[Hub, Decimal]],
    ) -> Decimal:
        return sum(
            (
                cls._distance(
                    Decimal(vehicle.latitude),
                    Decimal(vehicle.longitude),
                    Decimal(hub.latitude or 0),
                    Decimal(hub.longitude or 0),
                )
                * 2
                for hub, _ in candidates
            ),
            start=Decimal("0"),
        )

    @staticmethod
    def _distance(
        lat1: Decimal,
        lon1: Decimal,
        lat2: Decimal,
        lon2: Decimal,
    ) -> Decimal:
        lat_scale = Decimal("111.32")
        lon_scale = Decimal(
            str(111.32 * math.cos(math.radians(float(lat1))))
        )
        lat_delta = (lat2 - lat1) * lat_scale
        lon_delta = (lon2 - lon1) * lon_scale
        return Decimal(
            str(math.sqrt(float(lat_delta**2 + lon_delta**2)))
        )
