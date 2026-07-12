from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import (
    CollectionRoute,
    Deposit,
    DepositStatus,
    Hub,
    HubStatus,
    RouteStatus,
    RouteStop,
    TraceEvent,
    TraceStage,
    User,
    UserRole,
    Vehicle,
)
from app.schemas import OptimizeRequest, PickupCreate, RouteRead, VehicleRead
from app.services.routing import optimize_nearest_neighbor


router = APIRouter(prefix="/routes", tags=["Dynamic collection routing"])


def load_route(db: Session, route_id: int) -> CollectionRoute:
    route = db.scalar(
        select(CollectionRoute)
        .where(CollectionRoute.id == route_id)
        .options(selectinload(CollectionRoute.stops))
    )
    if not route:
        raise HTTPException(status_code=404, detail="Không tìm thấy tuyến")
    return route


@router.get("/vehicles", response_model=list[VehicleRead])
def list_vehicles(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[Vehicle]:
    return list(db.scalars(select(Vehicle).where(Vehicle.active.is_(True))))


@router.post("/optimize", response_model=RouteRead, status_code=201)
def optimize_route(
    payload: OptimizeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> CollectionRoute:
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle or not vehicle.active:
        raise HTTPException(status_code=404, detail="Không tìm thấy xe đang hoạt động")
    conditions = [Hub.fill_level >= payload.fill_threshold, Hub.status.in_([HubStatus.ONLINE, HubStatus.FULL])]
    if payload.include_urgent_offline_hubs:
        conditions = [Hub.fill_level >= payload.fill_threshold]
    candidates = list(db.scalars(select(Hub).where(*conditions)))
    ordered, distance, baseline, load = optimize_nearest_neighbor(vehicle, candidates)
    if not ordered:
        raise HTTPException(status_code=409, detail="Không có Hub phù hợp với ngưỡng đầy và dung tích xe")
    saved_percent = round((baseline - distance) / baseline * 100, 2) if baseline else 0
    route = CollectionRoute(
        vehicle_id=vehicle.id,
        threshold_percent=payload.fill_threshold,
        total_distance_km=distance,
        baseline_distance_km=baseline,
        distance_saved_percent=max(0, saved_percent),
        estimated_load_kg=load,
    )
    db.add(route)
    db.flush()
    for sequence, (hub, leg) in enumerate(ordered, start=1):
        db.add(
            RouteStop(
                route_id=route.id,
                hub_id=hub.id,
                sequence=sequence,
                distance_from_previous_km=round(leg, 3),
                expected_load_kg=hub.current_load_kg,
            )
        )
    db.commit()
    return load_route(db, route.id)


@router.get("", response_model=list[RouteRead])
def list_routes(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[CollectionRoute]:
    return list(
        db.scalars(
            select(CollectionRoute)
            .options(selectinload(CollectionRoute.stops))
            .order_by(CollectionRoute.planned_at.desc())
        ).unique()
    )


@router.post("/{route_id}/start", response_model=RouteRead)
def start_route(
    route_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.DRIVER)),
) -> CollectionRoute:
    route = load_route(db, route_id)
    if route.status != RouteStatus.PLANNED:
        raise HTTPException(status_code=409, detail="Chỉ có thể bắt đầu tuyến đang planned")
    route.status = RouteStatus.IN_PROGRESS
    db.commit()
    return load_route(db, route.id)


@router.post("/{route_id}/stops/{stop_id}/pickup", response_model=RouteRead)
def record_pickup(
    route_id: int,
    stop_id: int,
    payload: PickupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.DRIVER)),
) -> CollectionRoute:
    route = load_route(db, route_id)
    if route.status != RouteStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Tuyến phải ở trạng thái in_progress")
    stop = db.scalar(select(RouteStop).where(RouteStop.id == stop_id, RouteStop.route_id == route_id))
    if not stop:
        raise HTTPException(status_code=404, detail="Không tìm thấy điểm dừng")
    if stop.collected_at:
        raise HTTPException(status_code=409, detail="Điểm dừng đã được thu gom")
    hub = db.get(Hub, stop.hub_id)
    stop.collected_load_kg = payload.collected_load_kg
    stop.collected_at = datetime.now(timezone.utc)
    hub.current_load_kg = 0
    hub.fill_level = 0
    hub.status = HubStatus.ONLINE

    previously_picked = exists(select(TraceEvent.id).where(
        TraceEvent.trace_code == Deposit.trace_code,
        TraceEvent.stage == TraceStage.PICKED_UP,
    ))
    deposits = db.scalars(
        select(Deposit).where(
            Deposit.hub_id == hub.id,
            Deposit.status == DepositStatus.ACCEPTED,
            ~previously_picked,
        )
    )
    for deposit in deposits:
        db.add(
            TraceEvent(
                trace_code=deposit.trace_code,
                stage=TraceStage.PICKED_UP,
                location_type="vehicle",
                location_ref=route.vehicle.code,
                actor_user_id=user.id,
                event_metadata={"route_id": route.id, "hub_code": hub.code},
            )
        )
    db.commit()
    return load_route(db, route.id)


@router.post("/{route_id}/complete", response_model=RouteRead)
def complete_route(
    route_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR, UserRole.DRIVER)),
) -> CollectionRoute:
    route = load_route(db, route_id)
    if route.status != RouteStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Tuyến phải ở trạng thái in_progress")
    if any(stop.collected_at is None for stop in route.stops):
        raise HTTPException(status_code=409, detail="Chưa hoàn thành tất cả điểm thu gom")
    route.status = RouteStatus.COMPLETED
    route.completed_at = datetime.now(timezone.utc)
    db.commit()
    return load_route(db, route.id)

