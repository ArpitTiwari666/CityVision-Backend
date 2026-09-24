from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import datetime as dt

from ..database import get_db
from .. import models, schemas
from ..security import get_current_user
from ..ws_manager import manager
from ..services.anpr_service import get_anpr_engine

router = APIRouter(tags=["Live Camera Feed"])


@router.get("/api/anpr/status")
def anpr_status():
    return get_anpr_engine().status


@router.post("/api/anpr/detect", response_model=schemas.ANPRResult,
             dependencies=[Depends(get_current_user)])
async def detect_plate(camera_id: str = "", file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Runs the ANPR pipeline on a single uploaded frame/image.
    Real inference when DEMO_MODE=false and model weights are present,
    otherwise a clearly-labeled deterministic simulation (see anpr_service).
    Also logs the result as a Detection row tied to `camera_id`, if given.
    """
    if camera_id and not db.get(models.Camera, camera_id):
        raise HTTPException(404, "Unknown camera_id")

    image_bytes = await file.read()
    result = get_anpr_engine().detect(image_bytes, camera_id=camera_id)

    if camera_id:
        det = models.Detection(
            camera_id=camera_id,
            plate=result["plate"],
            vehicle_type=result.get("vehicle_type", "Sedan"),
            color=result.get("color", "White"),
            confidence=result["confidence"],
            method=models.DetectionMethodEnum(result["method"]),
            timestamp=dt.datetime.utcnow(),
        )
        db.add(det)
        cam = db.get(models.Camera, camera_id)
        cam.last_plate = result["plate"]
        cam.last_active = dt.datetime.utcnow()
        db.commit()
        await manager.broadcast("feed", {
            "type": "detection", "camera_id": camera_id, "plate": result["plate"],
            "confidence": result["confidence"], "method": result["method"],
            "timestamp": det.timestamp.isoformat(),
        })

    return schemas.ANPRResult(**result)


@router.websocket("/ws/feed")
async def ws_all_cameras(ws: WebSocket):
    """Subscribe to every camera's simulated/real detection events (Dashboard feed)."""
    await manager.connect("feed", ws)
    try:
        while True:
            await ws.receive_text()  # ping/keepalive from client, ignored
    except WebSocketDisconnect:
        await manager.disconnect("feed", ws)


@router.websocket("/ws/feed/{camera_id}")
async def ws_single_camera(ws: WebSocket, camera_id: str):
    """Subscribe to one camera's live events (Live Camera Feed detail panel)."""
    channel = f"feed:{camera_id}"
    await manager.connect(channel, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(channel, ws)


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await manager.connect("alerts", ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect("alerts", ws)
