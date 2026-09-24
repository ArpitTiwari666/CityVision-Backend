import datetime as dt
import random
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user, require_roles
from ..ws_manager import manager

router = APIRouter(prefix="/api/alerts", tags=["Alerts"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[schemas.AlertOut])
def list_alerts(
    severity: Optional[str] = Query(None, description="Critical | High | Medium | Low"),
    status: Optional[str] = Query(None, description="Open | Investigating | Resolved"),
    db: Session = Depends(get_db),
):
    query = db.query(models.Alert)
    if severity and severity != "All":
        query = query.filter(models.Alert.severity == severity)
    if status:
        query = query.filter(models.Alert.status == status)
    return query.order_by(models.Alert.created_at.desc()).all()


@router.get("/kpis")
def alert_kpis(db: Session = Depends(get_db)):
    today = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "open": db.query(models.Alert).filter(models.Alert.status == models.AlertStatusEnum.OPEN).count(),
        "investigating": db.query(models.Alert).filter(models.Alert.status == models.AlertStatusEnum.INVESTIGATING).count(),
        "resolved_today": db.query(models.Alert).filter(
            models.Alert.status == models.AlertStatusEnum.RESOLVED, models.Alert.resolved_at >= today
        ).count(),
        "blacklist_matches": db.query(models.BlacklistPlate).count(),
    }


@router.post("", response_model=schemas.AlertOut, status_code=201,
             dependencies=[Depends(require_roles("ADMIN", "OPERATOR", "ANALYST"))])
async def create_alert(payload: schemas.AlertCreate, db: Session = Depends(get_db)):
    alert_id = f"AL-{random.randint(3100, 3999)}"
    alert = models.Alert(id=alert_id, rule_triggered="manual", **payload.model_dump())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    await manager.broadcast("alerts", {"type": "alert", "id": alert.id, "severity": alert.severity.value,
                                        "title": alert.title, "status": alert.status.value})
    return alert


@router.patch("/{alert_id}", response_model=schemas.AlertOut,
              dependencies=[Depends(require_roles("ADMIN", "OPERATOR", "ANALYST"))])
def update_alert(alert_id: str, payload: schemas.AlertUpdate, db: Session = Depends(get_db)):
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = payload.status
    if payload.status == "Resolved":
        alert.resolved_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(alert)
    return alert
