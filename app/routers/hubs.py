from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, verify_device_key
from app.models import Hub, HubStatus, SensorReading, User
from app.realtime import hub_manager
from app.schemas import HubRead, HubTelemetry


router = APIRouter(prefix="/hubs", tags=["Hubs"])


@router.get("", response_model=list[HubRead])
def list_hubs(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Hub]:
    return list(db.scalars(select(Hub).order_by(Hub.code).limit(limit)))


@router.get("/{hub_code}", response_model=HubRead)
def get_hub(
    hub_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Hub:
    hub = db.scalar(select(Hub).where(Hub.code == hub_code))
    if hub is None:
        raise HTTPException(status_code=404, detail="Hub not found")
    return hub


@router.post("/{hub_code}/telemetry", response_model=HubRead)
async def record_telemetry(
    hub_code: str,
    payload: HubTelemetry,
    db: Session = Depends(get_db),
    _: None = Depends(verify_device_key),
) -> Hub:
    hub = db.scalar(
        select(Hub).where(Hub.code == hub_code).with_for_update()
    )
    if hub is None:
        raise HTTPException(status_code=404, detail="Hub not found")
    if payload.weight_kg > hub.capacity_kg:
        raise HTTPException(
            status_code=422,
            detail="Telemetry weight exceeds Hub capacity",
        )
    hub.current_load_kg = payload.weight_kg
    hub.fill_level = payload.fill_level
    hub.camera_online = payload.camera_online
    hub.sensor_online = payload.sensor_online
    hub.last_seen_at = datetime.now(UTC)
    if not payload.camera_online or not payload.sensor_online:
        hub.status = HubStatus.OFFLINE
    elif payload.fill_level >= Decimal("95"):
        hub.status = HubStatus.FULL
    elif payload.fill_level >= hub.pickup_threshold_percent:
        hub.status = HubStatus.NEAR_FULL
    else:
        hub.status = HubStatus.ACTIVE
    db.add(
        SensorReading(
            hub_id=hub.id,
            fill_level=payload.fill_level,
            weight_kg=payload.weight_kg,
            camera_online=payload.camera_online,
            sensor_online=payload.sensor_online,
            temperature_c=payload.temperature_c,
        )
    )
    db.flush()
    await hub_manager.broadcast(
        {
            "event": "hub.telemetry",
            "data": {
                "hub_code": hub.code,
                "fill_level": str(hub.fill_level),
                "status": hub.status.value,
            },
        }
    )
    return hub
