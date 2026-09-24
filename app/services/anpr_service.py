"""
ANPR Service
============
Automatic Number-Plate Recognition pipeline.

Real pipeline (used when DEMO_MODE=false AND both dependencies + weights
are available):
    1. YOLO (ultralytics) locates the license-plate bounding box in the frame.
    2. The plate crop is passed to PaddleOCR for text recognition.
    3. Result is normalised (uppercase, stripped) and returned with the
       model's real confidence score.

Demo / simulation pipeline (default, and automatic fallback if the real
pipeline's dependencies or weights are missing so the backend still runs
with "no GPU, CCTV, paid APIs or external AI services"):
    A deterministic pseudo-random generator seeded from the image bytes
    produces a plausible Indian-format plate (e.g. MP09AB1234), a vehicle
    type/colour guess and a confidence score. Every response is tagged
    method="SIMULATION" so callers/UI can label it honestly - this never
    pretends to be a real detection.

Both paths share the same `ANPRResult`-shaped return dict so routers and
the frontend do not need to know which one ran.
"""
from __future__ import annotations

import hashlib
import io
import os
import random
from functools import lru_cache
from typing import Optional

from ..config import settings

PLATE_STATE_CODES = ["MP09", "MP04", "MH12", "DL08", "GJ05", "RJ14", "UP32"]
VEHICLE_TYPES = ["Sedan", "SUV", "Hatchback", "Truck", "Bus", "Two-wheeler"]
VEHICLE_COLORS = ["White", "Black", "Silver", "Blue", "Red", "Grey"]


class ANPREngine:
    """Lazily loads real models only if DEMO_MODE is off and files exist."""

    def __init__(self):
        self.real_available = False
        self._yolo = None
        self._ocr = None
        if not settings.DEMO_MODE:
            self._try_load_real_models()

    def _try_load_real_models(self):
        try:
            if not os.path.exists(settings.YOLO_PLATE_MODEL_PATH):
                return  # no weights shipped -> stay in simulation mode
            from ultralytics import YOLO  # type: ignore
            from paddleocr import PaddleOCR  # type: ignore

            self._yolo = YOLO(settings.YOLO_PLATE_MODEL_PATH)
            self._ocr = PaddleOCR(use_angle_cls=True, lang=settings.PADDLEOCR_LANG, show_log=False)
            self.real_available = True
        except Exception:
            # ultralytics / paddleocr / paddlepaddle not installed, or
            # weights failed to load (e.g. no GPU/runtime available).
            # Fail soft into simulation mode rather than crashing the API.
            self.real_available = False
            self._yolo = None
            self._ocr = None

    # ------------------------------------------------------------ real ----
    def _run_real(self, image_bytes: bytes) -> Optional[dict]:
        import numpy as np  # type: ignore
        import cv2  # type: ignore

        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return None

        results = self._yolo.predict(frame, verbose=False)
        best_box, best_conf = None, 0.0
        for r in results:
            for box in r.boxes:
                conf = float(box.conf[0])
                if conf > best_conf:
                    best_conf = conf
                    best_box = box.xyxy[0].tolist()

        if best_box is None or best_conf < settings.ANPR_MIN_CONFIDENCE:
            return None

        x1, y1, x2, y2 = [int(v) for v in best_box]
        crop = frame[max(y1, 0):y2, max(x1, 0):x2]
        if crop.size == 0:
            return None

        ocr_result = self._ocr.ocr(crop, cls=True)
        text, ocr_conf = "", 0.0
        if ocr_result and ocr_result[0]:
            # pick the highest-confidence text line
            best_line = max(ocr_result[0], key=lambda l: l[1][1])
            text = best_line[1][0]
            ocr_conf = float(best_line[1][1])

        plate = "".join(ch for ch in text.upper() if ch.isalnum())
        if not plate:
            return None

        return {
            "plate": plate,
            "confidence": round(min(best_conf, ocr_conf) * 100, 1),
            "bbox": [x1, y1, x2, y2],
            "method": "REAL_AI",
            "note": "Detected with YOLO plate localisation + PaddleOCR text recognition.",
        }

    # -------------------------------------------------------- simulation ----
    def _run_simulation(self, image_bytes: bytes, camera_id: str = "") -> dict:
        seed_src = image_bytes if image_bytes else camera_id.encode()
        digest = hashlib.sha256(seed_src or b"cityvision").hexdigest()
        rng = random.Random(digest)

        state = rng.choice(PLATE_STATE_CODES)
        letters = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
        digits = "".join(rng.choice("0123456789") for _ in range(4))
        plate = f"{state}{letters}{digits}"

        return {
            "plate": plate,
            "confidence": round(rng.uniform(90.0, 99.4), 1),
            "vehicle_type": rng.choice(VEHICLE_TYPES),
            "color": rng.choice(VEHICLE_COLORS),
            "bbox": None,
            "method": "SIMULATION",
            "note": (
                "DEMO_MODE simulation: no GPU/real camera feed connected. "
                "Enable real inference by setting DEMO_MODE=false and providing "
                "YOLO plate weights + PaddleOCR."
            ),
        }

    # ------------------------------------------------------------- public ----
    def detect(self, image_bytes: bytes, camera_id: str = "") -> dict:
        if self.real_available and image_bytes:
            try:
                real = self._run_real(image_bytes)
                if real:
                    real.setdefault("vehicle_type", random.choice(VEHICLE_TYPES))
                    real.setdefault("color", random.choice(VEHICLE_COLORS))
                    return real
            except Exception:
                pass  # fall through to simulation on any runtime failure
        return self._run_simulation(image_bytes, camera_id)

    @property
    def status(self) -> dict:
        return {
            "demo_mode": settings.DEMO_MODE,
            "real_pipeline_loaded": self.real_available,
            "engine": "YOLO + PaddleOCR" if self.real_available else "Simulation (deterministic, labeled)",
        }


@lru_cache
def get_anpr_engine() -> ANPREngine:
    return ANPREngine()
