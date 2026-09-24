# CityVision AI — Backend

FastAPI backend for the Smart City Traffic Command Center frontend
(`smart-city-traffic-command-center`). This package is **backend only** —
no frontend code, and no external database service to stand up: it uses a
local SQLite file (`cityvision.db`) created automatically on first run, so
`pip install` + `python run.py` is enough to get a fully working API.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

The API is now at `http://localhost:8000`, interactive docs at
`http://localhost:8000/docs`.

On first boot it auto-creates the SQLite schema and seeds:
- The same 6 cameras / 4 alerts your frontend mock data uses (same IDs,
  locations, plates), so wiring the UI to real endpoints is a drop-in swap.
- ~24h of synthetic historical ANPR detections so the Analytics charts have
  real rows to aggregate from the first request.
- 4 demo login accounts, one per role:

  | username | password      | role     |
  |----------|---------------|----------|
  | admin    | admin123      | ADMIN    |
  | operator | operator123   | OPERATOR |
  | analyst  | analyst123    | ANALYST  |
  | viewer   | viewer123     | VIEWER   |

  Change these before deploying anywhere real.

## DEMO_MODE (default: on)

Per the project's own requirement, every AI-sounding feature is honestly
labeled `REAL_AI`, `RULE-BASED`, or `SIMULATION` — nothing claims 100%
accuracy and nothing pretends to be live CCTV when it isn't.

- **DEMO_MODE=true** (default): no GPU, no camera hardware, no paid APIs
  needed. A background task (`app/simulator.py`) manufactures new,
  clearly-tagged `SIMULATION` detection events every few seconds for
  "online" cameras and broadcasts them over WebSocket, so the dashboard,
  live feed, alerts badge, and analytics all visibly move over time.
- **DEMO_MODE=false**: the ANPR pipeline (`app/services/anpr_service.py`)
  switches to real inference — YOLO locates the plate, PaddleOCR reads the
  text — **if** `ultralytics` + `paddleocr` are installed *and* a weights
  file exists at `YOLO_PLATE_MODEL_PATH`. If either is missing it fails
  soft back into the labeled simulation rather than crashing, so the API
  never goes down for a missing model file.

Call `GET /api/anpr/status` any time to see which pipeline is actually
active.

## Auth

JWT bearer tokens, 4 roles (`ADMIN`, `OPERATOR`, `ANALYST`, `VIEWER`).
`POST /api/auth/login` → `{access_token, role, username}`. Send
`Authorization: Bearer <token>` on every other request. Role-gated actions
(registering/deleting cameras, resolving alerts, etc.) return `403` for
under-privileged roles — see each router for exact requirements.

## Endpoint map (mirrors the 9 frontend pages)

| Frontend page                | Endpoints |
|-------------------------------|-----------|
| Dashboard                     | `GET /api/dashboard/summary`, `GET /api/dashboard/activity-feed`, `WS /ws/feed` |
| Live Camera Feed              | `GET /api/cameras`, `POST /api/anpr/detect`, `WS /ws/feed/{camera_id}`, `GET /api/anpr/status` |
| Vehicle Search & Tracking     | `GET /api/vehicles/search/{plate}`, `POST /api/vehicles/{plate}/blacklist`, `GET /api/vehicles/recent` |
| GIS Traffic Map               | `GET /api/gis/snapshot` |
| Traffic Analytics             | `GET /api/analytics?hours=24` |
| Alerts                        | `GET /api/alerts`, `GET /api/alerts/kpis`, `POST /api/alerts`, `PATCH /api/alerts/{id}`, `WS /ws/alerts` |
| Camera Management             | `GET/POST/PATCH/DELETE /api/cameras`, `GET /api/cameras/{id}/detections` |
| Reports                       | `GET /api/reports/types`, `GET /api/reports/preview`, `POST /api/reports/generate`, `GET /api/reports/{id}/download` |
| Settings                      | `GET/PATCH /api/settings` |

Full interactive schema for every endpoint (request/response shapes, auth
requirements) is at `/docs` (Swagger UI) or `/redoc` once the server is
running.

## Connecting the existing frontend

The frontend currently renders hardcoded mock arrays in `src/main.jsx`.
To wire it to this backend: set `VITE_API_URL=http://localhost:8000` in
the frontend's `.env`, replace the mock arrays with `fetch`/React Query
calls to the endpoints above, and open the two `/ws/...` sockets for the
live activity feed and alert badge. CORS is already open for the default
Vite dev ports (5173/3000) in `app/config.py` — add your deployed frontend
origin to `CORS_ORIGINS` when you deploy.

## Project layout

```
backend/
  app/
    main.py            FastAPI app, CORS, lifespan (DB create + seed + simulator)
    config.py           Settings (env-driven)
    database.py          SQLAlchemy engine/session
    models.py             ORM tables
    schemas.py             Pydantic request/response models
    security.py             JWT auth + role-based dependency
    ws_manager.py             WebSocket broadcast manager
    seed_data.py               Seed cameras/alerts/users/history
    simulator.py                 Background live-traffic simulator
    services/
      anpr_service.py             YOLO+PaddleOCR pipeline w/ demo fallback
    routers/                       One file per frontend page/domain
  requirements.txt
  .env.example
  run.py
```

## Switching to a real database later

Nothing here is SQLite-specific beyond the connection string — SQLAlchemy
models and every router work unchanged against Postgres. Just point
`DATABASE_URL` at a Postgres instance (e.g. `postgresql+psycopg2://...`)
and install `psycopg2-binary`.
