"""
Background asyncio task that periodically manufactures new detection events
for online cameras and broadcasts them over WebSocket, so the Dashboard
"real-time feed", camera vehicle/speed counters and Live Camera Feed cards
change over time without needing a real CCTV/RTSP source.

Clearly a SIMULATION per the product requirement that every feature be
labeled REAL AI / RULE-BASED / SIMULATION - this module only ever emits
method="SIMULATION" rows (the /api/anpr/detect endpoint is the only place
that can produce REAL_AI rows, from an uploaded frame).
"""
import asyncio
import random
import datetime as dt

from .database import SessionLocal
from . import models
from .config import settings
from .ws_manager import manager

VEHICLE_TYPES = ["Sedan", "SUV", "Hatchback", "Truck", "Two-wheeler"]
COLORS = ["White", "Black", "Blue", "Silver", "Red"]

_rng = random.Random()


async def run_forever():
    if not settings.SIMULATOR_ENABLED:
        return
    while True:
        try:
            await _tick()
        except Exception:
            pass
        await asyncio.sleep(settings.SIMULATOR_TICK_SECONDS)


async def _tick():
    db = SessionLocal()
    try:
        cameras = db.query(models.Camera).filter(
            models.Camera.status != models.CameraStatusEnum.OFFLINE
        ).all()
        for cam in cameras:
            if _rng.random() > 0.6:
                continue  # not every camera fires every tick
            plate = f"MP09{_rng.choice('ABCDEFGHJK')}{_rng.choice('ABCDEFGHJK')}{_rng.randint(1000,9999)}"
            detection = models.Detection(
                camera_id=cam.id,
                plate=plate,
                vehicle_type=_rng.choice(VEHICLE_TYPES),
                color=_rng.choice(COLORS),
                speed_kmh=round(_rng.uniform(18, 58), 1),
                confidence=round(_rng.uniform(90, 99.5), 1),
                method=models.DetectionMethodEnum.SIMULATION,
                direction=_rng.choice(["North", "South", "East", "West", "North-East"]),
                timestamp=dt.datetime.utcnow(),
            )
            db.add(detection)
            cam.last_plate = plate
            cam.vehicles_per_min = max(0, int(_rng.gauss(cam.vehicles_per_min or 40, 6)))
            cam.avg_speed_kmh = round(max(5.0, _rng.gauss(cam.avg_speed_kmh or 35, 4)), 1)
            cam.last_active = dt.datetime.utcnow()
            db.commit()
            db.refresh(detection)

            payload = {
                "type": "detection",
                "camera_id": cam.id,
                "location": cam.location,
                "plate": plate,
                "vehicle_type": detection.vehicle_type,
                "confidence": detection.confidence,
                "timestamp": detection.timestamp.isoformat(),
                "method": "SIMULATION",
            }
            await manager.broadcast("feed", payload)
            await manager.broadcast(f"feed:{cam.id}", payload)

            # occasionally raise a rule-based alert on very low confidence
            if detection.confidence < 92 and _rng.random() < 0.3:
                alert_id = f"AL-{_rng.randint(3100, 3999)}"
                alert = models.Alert(
                    id=alert_id,
                    severity=models.SeverityEnum.MEDIUM,
                    title="ANPR mismatch confidence",
                    plate=plate,
                    camera_id=cam.id,
                    location=cam.location,
                    status=models.AlertStatusEnum.OPEN,
                    rule_triggered="confidence < 92%",
                )
                db.add(alert)
                db.commit()
                await manager.broadcast("alerts", {
                    "type": "alert", "id": alert_id, "severity": "Medium",
                    "title": alert.title, "plate": plate, "camera_id": cam.id,
                    "location": cam.location, "status": "Open",
                })
    finally:
        db.close()
