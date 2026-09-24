from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user

router = APIRouter(prefix="/api/gis", tags=["GIS Traffic Map"], dependencies=[Depends(get_current_user)])


def _congestion_tier(cam: models.Camera) -> str:
    if cam.status == models.CameraStatusEnum.OFFLINE:
        return "offline"
    if cam.avg_speed_kmh and cam.avg_speed_kmh < 30:
        return "high"
    if cam.avg_speed_kmh and cam.avg_speed_kmh < 42:
        return "medium"
    return "low"


@router.get("/snapshot", response_model=schemas.GISSnapshot)
def snapshot(db: Session = Depends(get_db)):
    cameras = db.query(models.Camera).all()
    nodes = [
        schemas.GISNode(camera_id=c.id, name=c.location.split()[0], lat=c.lat, lng=c.lng,
                         status=_congestion_tier(c))
        for c in cameras
    ]
    congested = sum(1 for n in nodes if n.status in ("medium", "high"))
    active_incidents = db.query(models.Alert).filter(models.Alert.status != models.AlertStatusEnum.RESOLVED).count()
    vehicles_on_network = sum(c.vehicles_per_min for c in cameras) * 12  # rough per-hour projection
    online = sum(1 for c in cameras if c.status == models.CameraStatusEnum.ONLINE)
    coverage = round((online / len(cameras)) * 100, 1) if cameras else 0.0

    routes = [
        schemas.GISRoute(name="Vijay Nagar → Rau Bypass", distance_km=6.8, eta_minutes=18, congestion="Heavy"),
        schemas.GISRoute(name="Palasia → Airport Road", distance_km=8.2, eta_minutes=14, congestion="Moderate"),
    ]

    return schemas.GISSnapshot(
        congested_corridors=congested,
        active_incidents=active_incidents,
        vehicles_on_network=vehicles_on_network,
        camera_coverage_pct=coverage,
        nodes=nodes,
        routes=routes,
    )
