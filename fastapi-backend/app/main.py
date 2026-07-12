from contextlib import asynccontextmanager

import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User
from app.realtime import hub_manager
from app.routers import auth, deposits, hubs, reports, routes, traceability, users
from app.security import decode_access_token


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Backend cho ReLoop Hub: Smart RVM realtime, kiểm soát chất lượng 3 lớp, "
        "DVRP, điểm thưởng, truy xuất nguồn gốc và báo cáo ESG."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(hubs.router, prefix=api_prefix)
app.include_router(deposits.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(routes.router, prefix=api_prefix)
app.include_router(traceability.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)


@app.get("/health", tags=["System"])
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.websocket("/ws/hubs")
async def hub_updates(websocket: WebSocket, token: str) -> None:
    try:
        payload = decode_access_token(token)
        with SessionLocal() as db:
            user = db.get(User, int(payload["sub"]))
            if not user or not user.is_active:
                raise ValueError("inactive user")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        await websocket.close(code=1008, reason="Invalid token")
        return
    await hub_manager.connect(websocket)
    try:
        await websocket.send_json({"event": "connected", "data": {"channel": "hubs"}})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub_manager.disconnect(websocket)
