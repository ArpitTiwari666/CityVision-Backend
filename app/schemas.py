import datetime as dt
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------ Auth ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool


# --------------------------------------------------------------- Camera ----
class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    location: str
    type: str
    status: str
    lat: float
    lng: float
    ip_address: str
    vehicles_per_min: int
    avg_speed_kmh: float
    health_pct: float
    anpr_enabled: bool
    last_plate: str
    last_active: dt.datetime


class CameraCreate(BaseModel):
    id: str
    location: str
    type: Literal["ANPR PTZ", "Fixed ANPR", "Traffic Cam"]
    lat: float = 0.0
    lng: float = 0.0
    ip_address: str = ""
    anpr_enabled: bool = True


class CameraUpdate(BaseModel):
    location: Optional[str] = None
    status: Optional[Literal["Online", "Warning", "Offline"]] = None
    anpr_enabled: Optional[bool] = None
    health_pct: Optional[float] = None


# ----------------------------------------------------------- Detections ----
class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    camera_id: str
    plate: str
    vehicle_type: str
    color: str
    speed_kmh: float
    confidence: float
    method: str
    direction: str
    timestamp: dt.datetime


class ANPRResult(BaseModel):
    plate: str
    confidence: float
    vehicle_type: str
    color: str
    method: Literal["REAL_AI", "SIMULATION"]
    bbox: Optional[List[float]] = None
    note: str


# ---------------------------------------------------------------- Alert ----
class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    severity: str
    title: str
    plate: str
    camera_id: str
    location: str
    status: str
    rule_triggered: str
    created_at: dt.datetime
    resolved_at: Optional[dt.datetime] = None


class AlertCreate(BaseModel):
    severity: Literal["Critical", "High", "Medium", "Low"]
    title: str
    plate: str = "—"
    camera_id: str = ""
    location: str = ""


class AlertUpdate(BaseModel):
    status: Literal["Open", "Investigating", "Resolved"]


# ------------------------------------------------------------- Dashboard ----
class KPI(BaseModel):
    label: str
    value: str
    delta: Optional[str] = None
    note: Optional[str] = None


class DashboardSummary(BaseModel):
    active_cameras: str
    vehicles_detected_today: int
    avg_speed_kmh: float
    active_alerts: int
    congestion_index: int
    congestion_label: str
    camera_status_breakdown: dict
    network_coverage_pct: float
    generated_at: dt.datetime


# ------------------------------------------------------------- Vehicles ----
class VehicleSighting(BaseModel):
    n: int
    location: str
    camera_id: str
    timestamp: dt.datetime
    plate: str


class VehicleProfile(BaseModel):
    plate: str
    vehicle_type: str
    color: str
    first_seen: Optional[dt.datetime]
    last_seen: Optional[dt.datetime]
    detection_count: int
    avg_confidence: float
    direction: str
    is_blacklisted: bool
    trajectory: List[VehicleSighting]


# -------------------------------------------------------------- GIS/map ----
class GISNode(BaseModel):
    camera_id: str
    name: str
    lat: float
    lng: float
    status: str  # low / medium / high / offline (congestion tier)


class GISRoute(BaseModel):
    name: str
    distance_km: float
    eta_minutes: int
    congestion: str


class GISSnapshot(BaseModel):
    congested_corridors: int
    active_incidents: int
    vehicles_on_network: int
    camera_coverage_pct: float
    nodes: List[GISNode]
    routes: List[GISRoute]


# ------------------------------------------------------------ Analytics ----
class SeriesPoint(BaseModel):
    label: str
    value: float


class VehicleMixPoint(BaseModel):
    name: str
    value: float


class Bottleneck(BaseModel):
    corridor: str
    index: int
    delay: str


class AnalyticsBundle(BaseModel):
    hourly_volume: List[SeriesPoint]
    weekly_congestion: List[SeriesPoint]
    vehicle_mix: List[VehicleMixPoint]
    speed_profile: List[SeriesPoint]
    bottlenecks: List[Bottleneck]


# --------------------------------------------------------------- Reports ----
class ReportTypeOut(BaseModel):
    key: str
    title: str
    description: str


class ReportGenerateRequest(BaseModel):
    report_type: Literal[
        "traffic_flow", "vehicle_detection", "camera_health", "alert_incident"
    ]
    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    format: Literal["csv", "json"] = "csv"


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_type: str
    title: str
    requested_by: str
    file_path: str
    generated_at: dt.datetime


# -------------------------------------------------------------- Settings ----
class SettingsOut(BaseModel):
    operations_mode: str
    data_refresh_seconds: int
    security_level: str
    default_map_layers: List[str]
    theme: str
    notifications: dict
    alert_thresholds: dict


class SettingsUpdate(BaseModel):
    data_refresh_seconds: Optional[int] = None
    security_level: Optional[str] = None
    default_map_layers: Optional[List[str]] = None
    theme: Optional[str] = None
    notifications: Optional[dict] = None
    alert_thresholds: Optional[dict] = None
