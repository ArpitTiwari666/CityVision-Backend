import datetime as dt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/summary", response_model=schemas.DashboardSummary)
def summary(db: Session = Depends(get_db)):
    total_cameras = db.query(models.Camera).count()
    online = db.query(models.Camera).filter(models.Camera.status == models.CameraStatusEnum.ONLINE).count()
    warning = db.query(models.Camera).filter(models.Camera.status == models.CameraStatusEnum.WARNING).count()
    offline = db.query(models.Camera).filter(models.Camera.status == models.CameraStatusEnum.OFFLINE).count()

    since_midnight = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    vehicles_today = db.query(models.Detection).filter(models.Detection.timestamp >= since_midnight).count()

    avg_speed = db.query(func.avg(models.Camera.avg_speed_kmh)).filter(
        models.Camera.status != models.CameraStatusEnum.OFFLINE
    ).scalar() or 0.0

    active_alerts = db.query(models.Alert).filter(models.Alert.status != models.AlertStatusEnum.RESOLVED).count()

    # simple, transparent rule-based congestion index: weighted mix of
    # active-alert pressure and inverse average speed vs a 50 km/h baseline
    congestion_index = int(min(100, max(0, (100 - (avg_speed / 50 * 100)) * 0.7 + active_alerts * 2)))
    label = "LOW" if congestion_index < 35 else "MODERATE" if congestion_index < 70 else "HIGH"

    coverage = round((online / total_cameras) * 100, 1) if total_cameras else 0.0

    return schemas.DashboardSummary(
        active_cameras=f"{online} / {total_cameras}",
        vehicles_detected_today=vehicles_today,
        avg_speed_kmh=round(avg_speed, 1),
        active_alerts=active_alerts,
        congestion_index=congestion_index,
        congestion_label=label,
        camera_status_breakdown={"Online": online, "Warning": warning, "Offline": offline},
        network_coverage_pct=coverage,
        generated_at=dt.datetime.utcnow(),
    )


@router.get("/activity-feed", response_model=list[schemas.DetectionOut])
def activity_feed(limit: int = 10, db: Session = Depends(get_db)):
    rows = db.query(models.Detection).order_by(models.Detection.timestamp.desc()).limit(limit).all()
    return rows
