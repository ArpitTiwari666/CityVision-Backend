import datetime as dt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Traffic Analytics"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=schemas.AnalyticsBundle)
def analytics_bundle(hours: int = 24, db: Session = Depends(get_db)):
    since = dt.datetime.utcnow() - dt.timedelta(hours=hours)
    rows = db.query(models.Detection).filter(models.Detection.timestamp >= since).all()

    # ---- hourly volume -----------------------------------------------------
    by_hour: dict[str, int] = {}
    for r in rows:
        key = r.timestamp.strftime("%H")
        by_hour[key] = by_hour.get(key, 0) + 1
    hourly_volume = [schemas.SeriesPoint(label=h, value=v) for h, v in sorted(by_hour.items())]

    # ---- weekly congestion index (rule-based: volume vs avg speed) --------
    by_day: dict[str, list] = {}
    week_rows = db.query(models.Detection).filter(
        models.Detection.timestamp >= dt.datetime.utcnow() - dt.timedelta(days=7)
    ).all()
    for r in week_rows:
        key = r.timestamp.strftime("%a")
        by_day.setdefault(key, []).append(r)
    weekly_congestion = []
    for day, items in by_day.items():
        avg_speed = sum(i.speed_kmh for i in items) / len(items) if items else 40
        idx = int(min(100, max(0, (100 - (avg_speed / 50 * 100)) * 0.6 + len(items) * 0.05)))
        weekly_congestion.append(schemas.SeriesPoint(label=day, value=idx))

    # ---- vehicle mix ---------------------------------------------------------
    total = len(rows) or 1
    mix_counts: dict[str, int] = {}
    for r in rows:
        mix_counts[r.vehicle_type] = mix_counts.get(r.vehicle_type, 0) + 1
    vehicle_mix = [
        schemas.VehicleMixPoint(name=k, value=round(v / total * 100, 1))
        for k, v in sorted(mix_counts.items(), key=lambda kv: -kv[1])
    ]

    # ---- speed profile ---------------------------------------------------------
    speed_by_hour: dict[str, list] = {}
    for r in rows:
        speed_by_hour.setdefault(r.timestamp.strftime("%H"), []).append(r.speed_kmh)
    speed_profile = [
        schemas.SeriesPoint(label=h, value=round(sum(v) / len(v), 1))
        for h, v in sorted(speed_by_hour.items())
    ]

    # ---- bottlenecks: cameras with lowest avg speed / highest load --------
    cams = db.query(models.Camera).filter(models.Camera.status != models.CameraStatusEnum.OFFLINE).all()
    ranked = sorted(cams, key=lambda c: (c.avg_speed_kmh or 999))[:4]
    bottlenecks = []
    for c in ranked:
        idx = int(min(100, max(0, (100 - ((c.avg_speed_kmh or 40) / 50 * 100)) * 0.9 + (c.vehicles_per_min or 0) * 0.1)))
        delay_min = max(1, int(idx / 10))
        bottlenecks.append(schemas.Bottleneck(corridor=c.location, index=idx, delay=f"{delay_min} min delay"))

    return schemas.AnalyticsBundle(
        hourly_volume=hourly_volume,
        weekly_congestion=weekly_congestion,
        vehicle_mix=vehicle_mix,
        speed_profile=speed_profile,
        bottlenecks=bottlenecks,
    )
