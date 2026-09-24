import datetime as dt
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/api/cameras", tags=["Camera Management"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[schemas.CameraOut])
def list_cameras(
    status: Optional[str] = Query(None, description="Online | Warning | Offline"),
    q: Optional[str] = Query(None, description="Search by id or location"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Camera)
    if status:
        query = query.filter(models.Camera.status == status)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            (models.Camera.id.ilike(like)) | (models.Camera.location.ilike(like))
        )
    return query.order_by(models.Camera.id).all()


@router.get("/{camera_id}", response_model=schemas.CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    return cam


@router.post("", response_model=schemas.CameraOut, status_code=201,
             dependencies=[Depends(require_roles("ADMIN", "OPERATOR"))])
def register_camera(payload: schemas.CameraCreate, db: Session = Depends(get_db)):
    if db.get(models.Camera, payload.id):
        raise HTTPException(409, "Camera id already exists")
    cam = models.Camera(
        id=payload.id, location=payload.location, type=payload.type,
        lat=payload.lat, lng=payload.lng, ip_address=payload.ip_address,
        anpr_enabled=payload.anpr_enabled, status=models.CameraStatusEnum.ONLINE,
        last_active=dt.datetime.utcnow(),
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@router.patch("/{camera_id}", response_model=schemas.CameraOut,
              dependencies=[Depends(require_roles("ADMIN", "OPERATOR"))])
def update_camera(camera_id: str, payload: schemas.CameraUpdate, db: Session = Depends(get_db)):
    cam = db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cam, field, value)
    db.commit()
    db.refresh(cam)
    return cam


@router.delete("/{camera_id}", status_code=204, dependencies=[Depends(require_roles("ADMIN"))])
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    cam = db.get(models.Camera, camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found")
    db.delete(cam)
    db.commit()


@router.get("/{camera_id}/detections", response_model=list[schemas.DetectionOut])
def camera_detections(camera_id: str, limit: int = 25, db: Session = Depends(get_db)):
    if not db.get(models.Camera, camera_id):
        raise HTTPException(404, "Camera not found")
    return (
        db.query(models.Detection)
        .filter(models.Detection.camera_id == camera_id)
        .order_by(models.Detection.timestamp.desc())
        .limit(limit)
        .all()
    )
