"""
Seeds the database with the same cameras / alerts / detections shown in the
frontend's mock data, plus ~24h of synthetic historical detections so the
Analytics charts have something real to aggregate from the first run.
"""
import datetime as dt
import random
from sqlalchemy.orm import Session

from . import models
from .security import hash_password

CAMERAS = [
    dict(id="CAM-014", location="Vijay Nagar Junction", type=models.CameraTypeEnum.ANPR_PTZ,
         status=models.CameraStatusEnum.ONLINE, lat=22.7533, lng=75.8937, vehicles_per_min=84,
         avg_speed_kmh=38, last_plate="MP09AB1234", health_pct=97),
    dict(id="CAM-027", location="Palasia Square", type=models.CameraTypeEnum.FIXED_ANPR,
         status=models.CameraStatusEnum.ONLINE, lat=22.7256, lng=75.8860, vehicles_per_min=71,
         avg_speed_kmh=31, last_plate="MP09CD7721", health_pct=97),
    dict(id="CAM-041", location="Airport Road Gate", type=models.CameraTypeEnum.ANPR_PTZ,
         status=models.CameraStatusEnum.WARNING, lat=22.7268, lng=75.8037, vehicles_per_min=46,
         avg_speed_kmh=52, last_plate="MP09EF9044", health_pct=68),
    dict(id="CAM-063", location="MR-10 Corridor", type=models.CameraTypeEnum.TRAFFIC_CAM,
         status=models.CameraStatusEnum.ONLINE, lat=22.7350, lng=75.8400, vehicles_per_min=96,
         avg_speed_kmh=27, last_plate="MP09GH1189", health_pct=97),
    dict(id="CAM-078", location="Bhawarkua Circle", type=models.CameraTypeEnum.ANPR_PTZ,
         status=models.CameraStatusEnum.OFFLINE, lat=22.6867, lng=75.8650, vehicles_per_min=0,
         avg_speed_kmh=0, last_plate="—", health_pct=9),
    dict(id="CAM-093", location="Rau Bypass", type=models.CameraTypeEnum.FIXED_ANPR,
         status=models.CameraStatusEnum.ONLINE, lat=22.6580, lng=75.8150, vehicles_per_min=52,
         avg_speed_kmh=44, last_plate="MP09JK5207", health_pct=97),
]

ALERTS = [
    dict(id="AL-3091", severity=models.SeverityEnum.CRITICAL, title="Blacklisted vehicle detected",
         plate="MP09AB1234", camera_id="CAM-014", location="Vijay Nagar Junction",
         status=models.AlertStatusEnum.OPEN),
    dict(id="AL-3088", severity=models.SeverityEnum.HIGH, title="ANPR mismatch confidence",
         plate="MP09EF9044", camera_id="CAM-041", location="Airport Road Gate",
         status=models.AlertStatusEnum.INVESTIGATING),
    dict(id="AL-3085", severity=models.SeverityEnum.MEDIUM, title="Unusual route deviation",
         plate="MP09JK5207", camera_id="CAM-093", location="Rau Bypass",
         status=models.AlertStatusEnum.OPEN),
    dict(id="AL-3081", severity=models.SeverityEnum.LOW, title="Camera packet loss",
         plate="—", camera_id="CAM-078", location="Bhawarkua Circle",
         status=models.AlertStatusEnum.RESOLVED),
]

USERS = [
    dict(username="admin", full_name="Control Room Admin", email="admin@cityvision.local",
         role=models.RoleEnum.ADMIN, password="admin123"),
    dict(username="operator", full_name="Shift Operator", email="operator@cityvision.local",
         role=models.RoleEnum.OPERATOR, password="operator123"),
    dict(username="analyst", full_name="Traffic Analyst", email="analyst@cityvision.local",
         role=models.RoleEnum.ANALYST, password="analyst123"),
    dict(username="viewer", full_name="Read Only Viewer", email="viewer@cityvision.local",
         role=models.RoleEnum.VIEWER, password="viewer123"),
]

VEHICLE_TYPES = ["Sedan", "SUV", "Hatchback", "Truck", "Two-wheeler"]
COLORS = ["White", "Black", "Blue", "Silver", "Red"]


def seed(db: Session):
    if not db.query(models.User).first():
        for u in USERS:
            db.add(models.User(
                username=u["username"], full_name=u["full_name"], email=u["email"],
                role=u["role"], hashed_password=hash_password(u["password"]),
            ))

    if not db.query(models.Camera).first():
        for c in CAMERAS:
            db.add(models.Camera(**c))

    if not db.query(models.BlacklistPlate).first():
        db.add(models.BlacklistPlate(plate="MP09AB1234", reason="Reported stolen vehicle", added_by="admin"))

    db.commit()

    if not db.query(models.Alert).first():
        base = dt.datetime.utcnow()
        for i, a in enumerate(ALERTS):
            created = base - dt.timedelta(minutes=[0, 5, 19, 32][i])
            resolved = created + dt.timedelta(minutes=8) if a["status"] == models.AlertStatusEnum.RESOLVED else None
            db.add(models.Alert(**a, created_at=created, resolved_at=resolved))
        db.commit()

    if not db.query(models.Detection).first():
        _seed_historical_detections(db)
        db.commit()


def _seed_historical_detections(db: Session, hours_back: int = 24):
    """Generates a plausible 24h detection history so analytics endpoints
    have real rows to aggregate on first boot (clearly a SIMULATION seed,
    same spirit as the live simulator)."""
    rng = random.Random(42)
    now = dt.datetime.utcnow()
    camera_ids = [c["id"] for c in CAMERAS if c["status"] != models.CameraStatusEnum.OFFLINE]

    for hour_offset in range(hours_back, 0, -1):
        ts_hour = now - dt.timedelta(hours=hour_offset)
        # rush-hour shaped volume curve
        hour_of_day = ts_hour.hour
        base_volume = 20 if hour_of_day < 6 else 90 if 7 <= hour_of_day <= 10 else \
            110 if 16 <= hour_of_day <= 19 else 55
        n_events = max(3, int(rng.gauss(base_volume / 8, 4)))
        for _ in range(n_events):
            cam = rng.choice(camera_ids)
            ts = ts_hour + dt.timedelta(minutes=rng.randint(0, 59), seconds=rng.randint(0, 59))
            plate = f"MP09{rng.choice('ABCDEFGHJK')}{rng.choice('ABCDEFGHJK')}{rng.randint(1000,9999)}"
            db.add(models.Detection(
                camera_id=cam,
                plate=plate,
                vehicle_type=rng.choice(VEHICLE_TYPES),
                color=rng.choice(COLORS),
                speed_kmh=round(rng.uniform(18, 58), 1),
                confidence=round(rng.uniform(90, 99.5), 1),
                method=models.DetectionMethodEnum.SIMULATION,
                direction=rng.choice(["North", "South", "East", "West", "North-East"]),
                timestamp=ts,
            ))
