from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles, verify_device_key
from app.models import Hub, HubStatus, SensorReading, User, UserRole
from app.realtime import hub_manager
from app.schemas import HubCreate, HubRead, TelemetryCreate


router = APIRouter(prefix="/hubs", tags=["Smart RVM Hubs"])


@router.get("", response_model=list[HubRead])
def list_hubs(
    status: HubStatus | None = None,
    min_fill: float | None = Query(default=None, ge=0, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Hub]:
    query = select(Hub).order_by(Hub.fill_level.desc())
    if status:
        query = query.where(Hub.status == status)
    if min_fill is not None:
        query = query.where(Hub.fill_level >= min_fill)
    return list(db.scalars(query))


@router.get("/{hub_code}", response_model=HubRead)
def get_hub(hub_code: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Hub:
    hub = db.scalar(select(Hub).where(Hub.code == hub_code))
    if not hub:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hub")
    return hub


@router.post("", response_model=HubRead, status_code=201)
def create_hub(
    payload: HubCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Hub:
    if db.scalar(select(Hub).where(Hub.code == payload.code)):
        raise HTTPException(status_code=409, detail="Mã Hub đã tồn tại")
    hub = Hub(**payload.model_dump())
    db.add(hub)
    db.commit()
    db.refresh(hub)
    return hub


@router.post("/{hub_code}/telemetry", response_model=HubRead)
async def ingest_telemetry(
    hub_code: str,
    payload: TelemetryCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
) -> Hub:
    hub = db.scalar(select(Hub).where(Hub.code == hub_code))
    if not hub:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hub")
    if payload.weight_kg > hub.capacity_kg * 1.1:
        raise HTTPException(status_code=422, detail="Khối lượng vượt quá giới hạn vật lý của Hub")
    hub.fill_level = payload.fill_level
    hub.current_load_kg = payload.weight_kg
    hub.camera_online = payload.camera_online
    hub.sensor_online = payload.sensor_online
    hub.last_seen_at = datetime.now(timezone.utc)
    hub.status = (
        HubStatus.OFFLINE
        if not payload.sensor_online
        else HubStatus.FULL
        if payload.fill_level >= 90
        else HubStatus.ONLINE
    )
    db.add(SensorReading(hub_id=hub.id, **payload.model_dump()))
    db.commit()
    db.refresh(hub)
    await hub_manager.broadcast({"event": "hub.telemetry", "data": HubRead.model_validate(hub).model_dump(mode="json")})
    return hub


@router.get("/{hub_code}/telemetry")
def telemetry_history(
    hub_code: str,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[dict]:
    hub = db.scalar(select(Hub).where(Hub.code == hub_code))
    if not hub:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hub")
    readings = db.scalars(
        select(SensorReading).where(SensorReading.hub_id == hub.id).order_by(SensorReading.recorded_at.desc()).limit(limit)
    )
    return [
        {
            "fill_level": item.fill_level,
            "weight_kg": item.weight_kg,
            "camera_online": item.camera_online,
            "sensor_online": item.sensor_online,
            "temperature_c": item.temperature_c,
            "recorded_at": item.recorded_at,
        }
        for item in readings
    ]
