from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user

router = APIRouter(prefix="/api/vehicles", tags=["Vehicle Search & Tracking"],
                    dependencies=[Depends(get_current_user)])


@router.get("/search/{plate}", response_model=schemas.VehicleProfile)
def search_vehicle(plate: str, db: Session = Depends(get_db)):
    plate = plate.upper().strip()
    rows = (
        db.query(models.Detection)
        .filter(models.Detection.plate == plate)
        .order_by(models.Detection.timestamp.desc())
        .all()
    )
    if not rows:
        raise HTTPException(404, f"No sightings found for plate {plate}")

    blacklisted = db.query(models.BlacklistPlate).filter(models.BlacklistPlate.plate == plate).first() is not None
    latest = rows[0]

    trajectory = [
        schemas.VehicleSighting(
            n=i + 1, location=(db.get(models.Camera, r.camera_id).location if db.get(models.Camera, r.camera_id) else r.camera_id),
            camera_id=r.camera_id, timestamp=r.timestamp, plate=r.plate,
        )
        for i, r in enumerate(rows)
    ]
    avg_conf = sum(r.confidence for r in rows) / len(rows)

    return schemas.VehicleProfile(
        plate=plate,
        vehicle_type=latest.vehicle_type,
        color=latest.color,
        first_seen=rows[-1].timestamp,
        last_seen=rows[0].timestamp,
        detection_count=len(rows),
        avg_confidence=round(avg_conf, 1),
        direction=latest.direction,
        is_blacklisted=blacklisted,
        trajectory=trajectory,
    )


@router.post("/{plate}/blacklist", status_code=201)
def add_to_blacklist(plate: str, reason: str = "", db: Session = Depends(get_db)):
    plate = plate.upper().strip()
    if db.query(models.BlacklistPlate).filter(models.BlacklistPlate.plate == plate).first():
        raise HTTPException(409, "Already blacklisted")
    db.add(models.BlacklistPlate(plate=plate, reason=reason or "Flagged from vehicle tracking console"))
    db.commit()
    return {"plate": plate, "blacklisted": True}


@router.get("/recent", response_model=list[schemas.DetectionOut])
def recent_vehicles(limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(models.Detection)
        .order_by(models.Detection.timestamp.desc())
        .limit(limit)
        .all()
    )
