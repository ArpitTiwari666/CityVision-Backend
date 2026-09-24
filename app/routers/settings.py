from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import datetime as dt

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user

router = APIRouter(prefix="/api/settings", tags=["Settings"], dependencies=[Depends(get_current_user)])

DEFAULTS = {
    "operations_mode": "Real-time command center profile",
    "data_refresh_seconds": 12,
    "security_level": "High",
    "default_map_layers": ["Traffic", "Cameras", "Incidents"],
    "theme": "dark",
    "notifications": {"push": True, "email": True, "control_room": True},
    "alert_thresholds": {"anpr_min_confidence": 92, "route_deviation_km": 1.5},
}


def _get_all(db: Session) -> dict:
    merged = dict(DEFAULTS)
    for row in db.query(models.SettingRecord).all():
        merged[row.key] = row.value
    return merged


@router.get("", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return schemas.SettingsOut(**_get_all(db))


@router.patch("", response_model=schemas.SettingsOut)
def update_settings(payload: schemas.SettingsUpdate, db: Session = Depends(get_db)):
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        row = db.get(models.SettingRecord, key)
        if row:
            row.value = value
            row.updated_at = dt.datetime.utcnow()
        else:
            db.add(models.SettingRecord(key=key, value=value))
    db.commit()
    return schemas.SettingsOut(**_get_all(db))
