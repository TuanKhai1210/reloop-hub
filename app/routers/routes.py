from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_errors import service_http_error
from app.core.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import CollectionRoute, User, UserRole, Vehicle
from app.schemas import (
    PickupStopRequest,
    RouteOptimizeRequest,
    RouteRead,
    RouteStopRead,
)
from app.services import RouteService, ServiceError


router = APIRouter(prefix="/routes", tags=["Collection routes"])


def route_response(
    route: CollectionRoute,
    service: RouteService,
) -> RouteRead:
    data = RouteRead.model_validate(route).model_dump()
    data["stops"] = [
        RouteStopRead.model_validate(stop)
        for stop in service.get_route_stops(route.id)
    ]
    return RouteRead.model_validate(data)


@router.get("/vehicles")
def list_vehicles(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    vehicles = db.scalars(
        select(Vehicle).where(Vehicle.active.is_(True)).order_by(Vehicle.code)
    )
    return [
        {
            "id": str(vehicle.id),
            "code": vehicle.code,
            "driver_id": str(vehicle.driver_id)
            if vehicle.driver_id
            else None,
            "capacity_kg": vehicle.capacity_kg,
            "latitude": vehicle.latitude,
            "longitude": vehicle.longitude,
        }
        for vehicle in vehicles
    ]


@router.post("/optimize", response_model=RouteRead, status_code=201)
def optimize_route(
    payload: RouteOptimizeRequest,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.OPERATOR)
    ),
) -> RouteRead:
    service = RouteService(db)
    try:
        route = service.optimize_route(
            vehicle_id=payload.vehicle_id,
            fill_threshold=payload.fill_threshold,
        )
        return route_response(route, service)
    except ServiceError as error:
        raise service_http_error(error) from error


@router.get("", response_model=list[RouteRead])
def list_routes(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RouteRead]:
    service = RouteService(db)
    routes = db.scalars(
        select(CollectionRoute).order_by(
            CollectionRoute.planned_at.desc()
        )
    )
    return [route_response(route, service) for route in routes]


@router.post("/{route_id}/start", response_model=RouteRead)
def start_route(
    route_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.OPERATOR,
            UserRole.DRIVER,
        )
    ),
) -> RouteRead:
    service = RouteService(db)
    try:
        return route_response(service.start_route(route_id), service)
    except ServiceError as error:
        raise service_http_error(error) from error


@router.post("/{route_id}/stops/{stop_id}/pickup")
def collect_stop(
    route_id: UUID,
    stop_id: UUID,
    payload: PickupStopRequest,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.OPERATOR,
            UserRole.DRIVER,
        )
    ),
) -> RouteStopRead:
    try:
        stop = RouteService(db).collect_stop(
            route_id=route_id,
            stop_id=stop_id,
            collected_load_kg=Decimal(payload.collected_load_kg),
            actor_user_id=user.id,
        )
        return RouteStopRead.model_validate(stop)
    except ServiceError as error:
        raise service_http_error(error) from error


@router.post("/{route_id}/complete", response_model=RouteRead)
def complete_route(
    route_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.OPERATOR,
            UserRole.DRIVER,
        )
    ),
) -> RouteRead:
    service = RouteService(db)
    try:
        return route_response(service.complete_route(route_id), service)
    except ServiceError as error:
        raise service_http_error(error) from error
