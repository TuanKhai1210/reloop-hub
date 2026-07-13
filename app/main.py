from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.security import decode_access_token
from app.models import User
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends
from app.realtime import hub_manager
from app.routers import (
    auth,
    deposits,
    hubs,
    reports,
    routes,
    traceability,
    users,
    vouchers,
)


app = FastAPI(
    title=settings.app_name,
    version="2.1.0",
    description=(
        "Unified ReLoop Hub backend for verified PET/HDPE returns, "
        "Green Points, collection routing, recycler receipt, realtime "
        "operations, and calendar-based Dashboard/ESG reporting."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(hubs.router, prefix=API_PREFIX)
app.include_router(deposits.router, prefix=API_PREFIX)
app.include_router(vouchers.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(routes.router, prefix=API_PREFIX)
app.include_router(traceability.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)


@app.get("/health", tags=["System"])
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.websocket("/ws/hubs")
async def hub_updates(websocket: WebSocket, token: str) -> None:
    try:
        user_id = decode_access_token(token)
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is None or not user.is_active:
                raise ValueError("inactive user")
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return

    await hub_manager.connect(websocket)
    try:
        await websocket.send_json(
            {"event": "connected", "data": {"channel": "hubs"}}
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub_manager.disconnect(websocket)
