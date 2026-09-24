"""
CityVision AI - Backend Configuration
--------------------------------------
Central settings object, loaded from environment variables / .env file.

DEMO_MODE (default true):
    When true, the ANPR pipeline and live-feed simulator never require a GPU,
    a real camera/CCTV feed, or any paid external API. Detections are produced
    by a deterministic, clearly-labelled simulation engine instead of live
    inference. Set DEMO_MODE=false and provide real model weights to switch
    the ANPR service over to real YOLO + PaddleOCR inference.
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "CityVision AI - Traffic Command Center Backend"
    ENV: str = "development"

    # --- Mode -------------------------------------------------------------
    DEMO_MODE: bool = Field(default=True)

    # --- Database (SQLite file, zero external services required) ---------
    DATABASE_URL: str = "sqlite:///./cityvision.db"

    # --- Auth ---------------------------------------------------------------
    SECRET_KEY: str = "cityvision-dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    # --- CORS (Vite dev server + generic localhost ports) ------------------
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # --- ANPR models ---------------------------------------------------------
    YOLO_PLATE_MODEL_PATH: str = "models/yolov8_plate.pt"
    PADDLEOCR_LANG: str = "en"
    ANPR_MIN_CONFIDENCE: float = 0.55

    # --- Live simulator -------------------------------------------------------
    SIMULATOR_TICK_SECONDS: float = 6.0
    SIMULATOR_ENABLED: bool = True

    # --- Uploaded frame / report storage --------------------------------------
    UPLOAD_DIR: str = "storage/uploads"
    REPORT_DIR: str = "storage/reports"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
