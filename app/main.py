import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine, SessionLocal
from . import models  # noqa: F401  (ensures models are registered on Base)
from .seed_data import seed
from .simulator import run_forever as simulator_run_forever

from .routers import auth, dashboard, cameras, live_feed, vehicles, gis, analytics, alerts, reports, settings as settings_router

_simulator_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _simulator_task
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.REPORT_DIR, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()

    _simulator_task = asyncio.create_task(simulator_run_forever())
    yield
    if _simulator_task:
        _simulator_task.cancel()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Backend for the CityVision AI Smart City Traffic Command Center. "
        f"Running with DEMO_MODE={'ON' if settings.DEMO_MODE else 'OFF'} — "
        "in demo mode, ANPR and live-feed data are produced by a labeled "
        "simulation engine so the API runs with no GPU, CCTV, or paid services."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(cameras.router)
app.include_router(live_feed.router)
app.include_router(vehicles.router)
app.include_router(gis.router)
app.include_router(analytics.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(settings_router.router)


@app.get("/api/health", tags=["System"])
def health():
    return {
        "status": "operational",
        "demo_mode": settings.DEMO_MODE,
        "app": settings.APP_NAME,
    }
