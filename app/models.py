import enum
import datetime as dt
from sqlalchemy import (
    String, Integer, Float, DateTime, Enum, Text, ForeignKey, Boolean, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now():
    return dt.datetime.utcnow()


# ---------------------------------------------------------------- Enums ----
class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class CameraStatusEnum(str, enum.Enum):
    ONLINE = "Online"
    WARNING = "Warning"
    OFFLINE = "Offline"


class CameraTypeEnum(str, enum.Enum):
    ANPR_PTZ = "ANPR PTZ"
    FIXED_ANPR = "Fixed ANPR"
    TRAFFIC_CAM = "Traffic Cam"


class SeverityEnum(str, enum.Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class AlertStatusEnum(str, enum.Enum):
    OPEN = "Open"
    INVESTIGATING = "Investigating"
    RESOLVED = "Resolved"


class DetectionMethodEnum(str, enum.Enum):
    REAL_AI = "REAL_AI"
    SIMULATION = "SIMULATION"


# --------------------------------------------------------------- Models ----
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    email: Mapped[str] = mapped_column(String(128), default="")
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum), default=RoleEnum.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. CAM-014
    location: Mapped[str] = mapped_column(String(128))
    type: Mapped[CameraTypeEnum] = mapped_column(Enum(CameraTypeEnum))
    status: Mapped[CameraStatusEnum] = mapped_column(Enum(CameraStatusEnum), default=CameraStatusEnum.ONLINE)
    lat: Mapped[float] = mapped_column(Float, default=0.0)
    lng: Mapped[float] = mapped_column(Float, default=0.0)
    ip_address: Mapped[str] = mapped_column(String(32), default="")
    vehicles_per_min: Mapped[int] = mapped_column(Integer, default=0)
    avg_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    health_pct: Mapped[float] = mapped_column(Float, default=97.0)
    anpr_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_plate: Mapped[str] = mapped_column(String(16), default="")
    last_active: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)

    detections: Mapped[list["Detection"]] = relationship(back_populates="camera")


class Detection(Base):
    """A single ANPR plate-read event, real or simulated."""
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.id"), index=True)
    plate: Mapped[str] = mapped_column(String(16), index=True)
    vehicle_type: Mapped[str] = mapped_column(String(32), default="Sedan")
    color: Mapped[str] = mapped_column(String(24), default="White")
    speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[DetectionMethodEnum] = mapped_column(Enum(DetectionMethodEnum), default=DetectionMethodEnum.SIMULATION)
    direction: Mapped[str] = mapped_column(String(24), default="North-East")
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)

    camera: Mapped["Camera"] = relationship(back_populates="detections")


class BlacklistPlate(Base):
    __tablename__ = "blacklist_plates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    reason: Mapped[str] = mapped_column(String(256), default="")
    added_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # AL-xxxx
    severity: Mapped[SeverityEnum] = mapped_column(Enum(SeverityEnum))
    title: Mapped[str] = mapped_column(String(256))
    plate: Mapped[str] = mapped_column(String(16), default="—")
    camera_id: Mapped[str] = mapped_column(String(16), default="")
    location: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[AlertStatusEnum] = mapped_column(Enum(AlertStatusEnum), default=AlertStatusEnum.OPEN)
    rule_triggered: Mapped[str] = mapped_column(String(64), default="rule-based")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now, index=True)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256))
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str] = mapped_column(String(256), default="")
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class SettingRecord(Base):
    """Simple per-key JSON settings store backing the Settings page."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)
