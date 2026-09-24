import csv
import io
import os
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..config import settings
from ..security import get_current_user

router = APIRouter(prefix="/api/reports", tags=["Reports"], dependencies=[Depends(get_current_user)])

REPORT_TYPES = [
    schemas.ReportTypeOut(key="traffic_flow", title="Traffic Flow Report",
                          description="Traffic volumes, speeds and corridor congestion"),
    schemas.ReportTypeOut(key="vehicle_detection", title="Vehicle Detection Report",
                          description="ANPR detections and camera-wise sightings"),
    schemas.ReportTypeOut(key="camera_health", title="Camera Health Report",
                          description="Availability, uptime and device health"),
    schemas.ReportTypeOut(key="alert_incident", title="Alert Incident Report",
                          description="Open, investigated and resolved incidents"),
]


@router.get("/types", response_model=list[schemas.ReportTypeOut])
def list_report_types():
    return REPORT_TYPES


@router.get("/preview")
def daily_preview(db: Session = Depends(get_db)):
    today = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    detections_today = db.query(models.Detection).filter(models.Detection.timestamp >= today).all()
    alerts_today = db.query(models.Alert).filter(models.Alert.created_at >= today).count()
    peak = 0
    by_hour: dict[int, int] = {}
    for d in detections_today:
        by_hour[d.timestamp.hour] = by_hour.get(d.timestamp.hour, 0) + 1
    if by_hour:
        peak = max(by_hour.values())
    avg_speed = round(sum(d.speed_kmh for d in detections_today) / len(detections_today), 1) if detections_today else 0.0
    trend = [{"t": f"{h:02d}:00", "v": by_hour.get(h, 0)} for h in range(0, 24, 2)]
    return {
        "title": f"Daily Traffic Intelligence — {dt.datetime.utcnow().strftime('%d %b %Y')}",
        "vehicles_detected": len(detections_today),
        "peak_volume_per_hr": peak * 6,  # extrapolate the busiest 10-min bucket to hourly
        "avg_speed_kmh": avg_speed,
        "alerts_triggered": alerts_today,
        "trend": trend,
    }


@router.post("/generate", response_model=schemas.ReportOut, status_code=201)
def generate_report(payload: schemas.ReportGenerateRequest, db: Session = Depends(get_db)):
    os.makedirs(settings.REPORT_DIR, exist_ok=True)
    date_from = payload.date_from or (dt.date.today() - dt.timedelta(days=1))
    date_to = payload.date_to or dt.date.today()

    rows, headers = _collect_report_rows(db, payload.report_type, date_from, date_to)

    ts = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    filename = f"{payload.report_type}_{ts}.csv"
    filepath = os.path.join(settings.REPORT_DIR, filename)
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    report_type_title = next((t.title for t in REPORT_TYPES if t.key == payload.report_type), payload.report_type)
    report = models.Report(
        report_type=payload.report_type,
        title=report_type_title,
        requested_by="api-user",
        params={"date_from": str(date_from), "date_to": str(date_to)},
        file_path=filepath,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _collect_report_rows(db: Session, report_type: str, date_from: dt.date, date_to: dt.date):
    start = dt.datetime.combine(date_from, dt.time.min)
    end = dt.datetime.combine(date_to, dt.time.max)

    if report_type == "traffic_flow":
        cams = db.query(models.Camera).all()
        headers = ["camera_id", "location", "vehicles_per_min", "avg_speed_kmh", "status"]
        rows = [[c.id, c.location, c.vehicles_per_min, c.avg_speed_kmh, c.status.value] for c in cams]
    elif report_type == "vehicle_detection":
        dets = db.query(models.Detection).filter(
            models.Detection.timestamp.between(start, end)
        ).order_by(models.Detection.timestamp.desc()).all()
        headers = ["timestamp", "camera_id", "plate", "vehicle_type", "color", "confidence", "method"]
        rows = [[d.timestamp.isoformat(), d.camera_id, d.plate, d.vehicle_type, d.color, d.confidence, d.method.value] for d in dets]
    elif report_type == "camera_health":
        cams = db.query(models.Camera).all()
        headers = ["camera_id", "location", "status", "health_pct", "last_active"]
        rows = [[c.id, c.location, c.status.value, c.health_pct, c.last_active.isoformat()] for c in cams]
    elif report_type == "alert_incident":
        alerts = db.query(models.Alert).filter(models.Alert.created_at.between(start, end)).all()
        headers = ["id", "severity", "title", "plate", "camera_id", "status", "created_at"]
        rows = [[a.id, a.severity.value, a.title, a.plate, a.camera_id, a.status.value, a.created_at.isoformat()] for a in alerts]
    else:
        raise HTTPException(400, "Unknown report type")
    return rows, headers


@router.get("", response_model=list[schemas.ReportOut])
def list_reports(db: Session = Depends(get_db)):
    return db.query(models.Report).order_by(models.Report.generated_at.desc()).all()


@router.get("/{report_id}/download")
def download_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(models.Report, report_id)
    if not report or not os.path.exists(report.file_path):
        raise HTTPException(404, "Report file not found")
    return FileResponse(report.file_path, filename=os.path.basename(report.file_path), media_type="text/csv")
