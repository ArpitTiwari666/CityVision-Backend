import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine, SessionLocal
from . import models
from .seed_data import seed
from .simulator import run_forever as simulator_run_forever

from .routers import (
    auth,
    dashboard,
    cameras,
    live_feed,
    vehicles,
    gis,
    analytics,
    alerts,
    reports,
    settings as settings_router,
)

_simulator_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _simulator_task

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.REPORT_DIR, exist_ok=True)

    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Seed demo data
    db = SessionLocal()

    try:
        seed(db)
    finally:
        db.close()

    # Start simulator
    _simulator_task = asyncio.create_task(
        simulator_run_forever()
    )

    yield

    # Stop simulator
    if _simulator_task:
        _simulator_task.cancel()

        try:
            await _simulator_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Backend for the CityVision AI Smart City Traffic "
        "Command Center. "
        f"Running with DEMO_MODE="
        f"{'ON' if settings.DEMO_MODE else 'OFF'}."
    ),
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================

ALLOWED_ORIGINS = [
    # GitHub Pages production frontend
    "https://arpittiwari666.github.io",

    # Local development
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

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


# ============================================================
# SYSTEM ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "CityVision AI Backend",
        "message": "CityVision API is running",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health", tags=["System"])
def health():
    return {
        "status": "operational",
        "demo_mode": settings.DEMO_MODE,
        "app": settings.APP_NAME,
    }