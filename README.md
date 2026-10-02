# Motorsport Analytics Pipeline

> Lap and session telemetry analysis for Assetto Corsa and iRacing, from MoTeC-style CSV exports: lap comparison, corner-by-corner diagnosis, stint and tyre analysis, and setup recommendations.

[Leer en Español](README.es.md)

## Quick start

```bash
# 1. Backend (from the project root)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# 2. Frontend (second terminal)
cd frontend && npm install && npm run dev

# 3. Open http://localhost:5173 and drop a CSV (see "Using the app")
```

## Table of contents

- [What it is](#what-it-is)
- [Installation](#installation)
- [Using the app](#using-the-app)
- [Telemetry formats](#telemetry-formats)
- [Data quality notes and behaviour](#data-quality-notes-and-behaviour)
- [Example result](#example-result)
- [Architecture](#architecture)
- [API](#api)
- [Configuration](#configuration)
- [Development and tests](#development-and-tests)
- [Documentation](#documentation)
- [Known limitations](#known-limitations)
- [Contributing](#contributing)
- [License](#license)

## What it is

A FastAPI backend plus a React frontend. You upload telemetry CSV files and get back:

- **Session mode (1 CSV):** the full session is split into laps automatically. You get a lap table (pit and outlier laps flagged), stint analysis (pace degradation, fuel strategy, Monte Carlo projection, pit window, track evolution), per-corner session analysis, tyre degradation, thermal management, racing-line optimisation and setup recommendations.
- **Comparison mode (2 CSVs of one lap each, or 2 laps picked from a session):** distance-aligned time delta, speed/brake/throttle overlays, corner-by-corner diagnosis, G-G diagram, understeer/oversteer events, tyre/brake/suspension/driver-input/slip-angle analysis, ML modules (anomaly detection, style clustering, lap-time potential) and a PDF report.

The UI has two views: **Engineer** (everything) and **Pilot** (technical panels hidden). Languages: English and Spanish (API messages and reports follow the `lang` query parameter or `Accept-Language`).

## Installation

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.10+ (the Docker image uses 3.11) |
| Node.js | 18+ (the Docker image uses 20) |
| Git | any |

### Local

```bash
git clone https://github.com/ElSirGuti/motorsport-analytics-pipeline.git
cd motorsport-analytics-pipeline

python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt    # add -r requirements-dev.txt for tests

cd frontend && npm install && cd ..
```

Run the two processes in separate terminals:

```bash
uvicorn main:app --reload --port 8000     # API on http://localhost:8000 (docs at /docs)
cd frontend && npm run dev                # UI on http://localhost:5173
```

You can also run `python main.py`, which reads `API_HOST`, `API_PORT` and `API_RELOAD` from the environment.

### Docker

```bash
docker compose up --build
```

`docker-compose.yml` starts the `backend` (port 8000, health check on `/api/health`) and the `frontend` (nginx serving the production build on port 5173). The frontend image bakes the API URL at build time (`VITE_API_URL`, default `http://localhost:8000/api`), so the browser must be able to reach the API at that address.

## Using the app

1. Open `http://localhost:5173` and choose the language (ES/EN) and the mode (Pilot/Engineer) in the top bar.
2. Drop CSV files in the upload area. The mode is detected from the number of files:
   - **1 CSV = full session**, segmented into laps automatically.
   - **2 CSVs = two single laps** to compare.
3. Click analyze. A step progress bar shows the stages (large files can take a few minutes; a ~57 MB session took about 25 s). Once the analysis is done, the upload area collapses into a file bar with a **New analysis** button.
4. Navigate with the side rail:
   - Session: *Session overview*, *Stint analysis*, *Setup & strategy*.
   - Comparison: *Core lap*, *Vehicle dynamics*, *Driver & inputs*, *Strategy & setup*.
   - Pilot mode hides the technical panels (vehicle dynamics and driver inputs).
5. In the session lap table, tick **two laps (A/B)** and press **Compare**, or use **Best vs Worst**. Pit and outlier laps are marked in the table.
6. A health panel shows which analysis modules produced data and which are unavailable for this file.
7. Compare results can be copied as a text report or downloaded as a PDF.

Full walkthrough: [User Guide](docs/USER_GUIDE.md).

## Telemetry formats

The loader (`src/io/loaders.py`) reads **CSV** only. Supported sources:

| Source | Notes |
|---|---|
| Assetto Corsa via ACTI, exported as MoTeC CSV | Comma or semicolon separator is auto-detected; the MoTeC header block (Driver, Vehicle, Venue) is read as metadata and the units row is skipped. |
| iRacing exported to CSV (`.ibt` converted with MoTeC i2 or a third-party tool) | Detected by `SessionTime`, `Session Time` or `SessionLapCount`. Speed in m/s is converted to km/h, pedals in 0-1 are scaled to 0-100, suspension in metres to mm, tyre pressure kPa/PSI to bar, brake bias fraction to percent. |
| iRacing `.ibt` and MoTeC `.ld` (native, **experimental**) | Detected by extension or binary signature. Units are normalised to the canonical channels; see "Supported formats" in `docs/USER_GUIDE.md`. |

The export steps for each program (ACTI, MoTeC i2, iRacing) are in the [User Guide](docs/USER_GUIDE.md#exporting-telemetry).

**Required channels:** `Speed`, `Brake`, `Throttle`. If any is missing or has no numeric values, the API answers `400` with a message listing the columns found.

**Distance:** if the `Distance` channel is absent (or never exceeds 10 m), it is synthesised by integrating `Speed` over a valid time clock (`LR/HR/MR Sample Clock`, `SessionTime`, `Time`, `Lap Time`; a clock that is a 0/1 square wave is rejected; falls back to `Session Time Left`, then the lap timer, then a fixed 100 Hz). Responses that carry metadata (`/api/compare-session-laps`, `/api/report/pdf`) set `metadata.distance_synthetic = true`. Synthetic distance is fine for stint and session analysis; lap-to-lap comparison is more reliable with a real distance channel.

**Recognised channels (canonical name: examples of accepted aliases):**

| Group | Canonical names | Examples of aliases |
|---|---|---|
| Core | `Speed`, `Brake`, `Throttle`, `Distance`, `Gear`, `RPM` | `Ground Speed`, `Brake Pos`, `Throttle Pos`, `Lap Distance` |
| Dynamics | `SteerAngle`, `LateralG`, `LongitudinalG`, `YawRate` | `Steering Angle`, `CG Accel Lateral`, `CG Accel Longitudinal`, `Chassis Yaw Rate` |
| Laps and time | `LapTime`, `SessionLapCount` | `Lap Time`, `Session Lap Count`, `Lap` |
| Position | `CarCoordX/Y/Z` | `Car Coord X` |
| Weather | `AirTemp`, `RoadTemp` | `Air Temp`, `Road Temp` |
| Tyre temperature (4 zones x 4 corners) | `TyreTemp{Core,Inner,Middle,Outer}{FL,FR,RL,RR}` | `Tire Temp Core FL`, `LFtempCL` |
| Tyre pressure | `TyrePress{FL..RR}`, `TyrePressCold{FL..RR}` | `Tire Pressure FL`, `LFpressure`, `LFcoldPressure` |
| Suspension travel | `SuspTravel{FL..RR}` | `Suspension Travel FL`, `LFshockDefl` |
| Brakes | `BrakeTemp{FL..RR}`, `BrakeBias` | `Brake Temp FL`, `dcBrakeBias` |
| Fluids | `WaterTemp`, `OilTemp` | `Coolant Temp`, `Eng Oil Temp` |

The complete alias table is `COLUMN_ALIASES` in `src/io/loaders.py`. Missing optional channels do not abort the analysis: the affected panel reports itself as unavailable.

## Data quality notes and behaviour

- **Lap segmentation** is unified across all endpoints: by lap-counter channel (`Session Lap Count`, `Lap`, ...) or, failing that, by distance resets. Partial segments shorter than 30 s are discarded. If fewer than 2 laps are found the API answers with an error message.
- **Pit and outlier laps:** a lap is marked as pit if the `In Pit` channel says so; laps outside 70-115 % of the median lap time are also flagged as outliers and excluded from regressions and projections.
- **Corner windows do not overlap:** each window is trimmed at the midpoint between neighbouring apexes. The comparison `summary` includes `corners_time_delta_s` (time gained/lost inside corners) and `outside_corners_delta_s` (the remainder).
- **Corner matching** between two laps uses the apex distance, not the corner index.
- **Not-measurable values:** `braking_delta_available` and `throttle_delta_available` flag whether the braking/throttle deltas could be measured. A `0.0` with `available = false` means "not measurable", not "no difference".
- **Constant channels** (for example brake temperatures fixed at one value) return `available: false` with a `reason` instead of generating false recommendations.
- **Slip angle sign convention:** the sign convention of `LateralG` is detected from its correlation with the yaw rate and flipped when needed (Assetto Corsa logs it inverted) before computing the slip angle.
- **Input validation:** an empty CSV or one without the minimum channels returns `400` with a clear message. Invalid lap selections return `422`.
- **Track evolution** (`track_evolution`) and **`health_summary`** are part of the stint and compare-session responses.

## Example result

Validated with a Porsche Cayman GT4 Clubsport at Imola (Assetto Corsa, ~57 MB MoTeC CSV with no `Distance` channel):

| Item | Value |
|---|---|
| Laps detected | 21 (laps 1 and 21 are pit laps) |
| Best lap | Lap 11, 1:57.605 |
| Race-lap range | 117.6 - 122.4 s |
| Track length | ~4862 m |
| Top speed | 243.9 km/h |
| Corners by geometry | 11 |
| Fuel consumption | 1.758 L/lap |
| Degradation trend | -0.077 s/lap (the car gets faster as fuel burns off) |
| Full analysis time | ~25 s |

The CSV itself is not part of the repository.

## Architecture

```
main.py                  FastAPI app: endpoints, CORS, logging, error mapping
src/
  io/                    loaders.py (CSV ingestion, aliases, unit normalisation, distance synthesis)
                         exporters.py (text report), pdf_exporter.py (PDF report)
  processing/            alignment.py (distance alignment), filters.py (signal filters)
  telemetry/             lap_comparator.py, metrics.py, session_analyzer.py
  analytics/             Advanced modules (see table below)
  i18n.py, locales/      Backend translations (en.json, es.json)
  visualization/         (empty package)
frontend/                React 19 + Vite + Recharts (see frontend/README.md)
tests/                   pytest suite (48 tests)
scripts/                 Sample data generator and documentation image generators
data/                    laptime_history.db (history used by the ML lap-time module)
docs/                    User guides and scientific documentation (EN/ES)
```

`src/analytics/` modules:

| Module | Purpose | Doc |
|---|---|---|
| `geometry.py` | Curvature and apex detection | [01](docs/01_geometry.md) |
| `alignment.py` | Distance alignment and time delta | [02](docs/02_time_delta.md) |
| `dynamics.py` | G-G diagram, understeer/oversteer events | [03](docs/03_gg_diagram.md), [04](docs/04_dynamics.md) |
| `compression.py` | RDP compression of the payload | [02](docs/02_time_delta.md) |
| `insights.py` | Corner-by-corner diagnosis | [01](docs/01_geometry.md) |
| `ml_anomaly.py` | Isolation Forest anomaly zones | [05](docs/05_anomaly_detection.md) |
| `ml_clustering.py` | K-Means corner style profiles | [06](docs/06_clustering.md) |
| `ml_laptime.py` | Reachable lap (P10), consistency, XGBoost, history in SQLite | [07](docs/07_lap_time_potential.md) |
| `stint.py` | Lap segmentation, per-lap metrics, degradation, fuel, Monte Carlo, track evolution | [08](docs/08_stint_analysis.md) |
| `thermodynamics.py` | Tyre thermal window (comparison) | [09](docs/09_thermodynamics.md) |
| `brake_fade.py` | Braking efficiency and fade | [10](docs/10_brake_fade.md) |
| `driver_inputs.py` | Steering FFT, nervousness, pedal overlap | [11](docs/11_driver_inputs.md) |
| `suspension.py` | Pitch, roll, bottoming | [12](docs/12_suspension.md) |
| `slip_angle.py` | Sideslip and balance | [13](docs/13_slip_angle.md) |
| `thermal_management.py` | Tyre, brake and fluid temperatures and pressures over a session | [14](docs/14_thermal_management.md) |
| `tyre_degradation.py` | Tyre degradation prediction | [15](docs/15_tyre_degradation.md) |
| `racing_line_rl.py` | Racing-line optimisation | [16](docs/16_racing_line_rl.md) |
| `setup_advisor.py` | Setup recommendations (lap comparison and session) | [17](docs/17_setup_advisor.md) |
| `session_corner_analysis.py` | Corner statistics across all laps of a session | [08](docs/08_stint_analysis.md) |
| `session_telemetry_analysis.py` | Session-level tyre, brake, suspension, inputs and balance aggregates | [08](docs/08_stint_analysis.md) |

## API

Base URL: `http://localhost:8000`. Interactive documentation: `/docs` (Swagger). All POST endpoints take `multipart/form-data` unless noted. Add `?lang=es` or `?lang=en` (otherwise `Accept-Language` is used) to choose the language of messages and reports. Errors: `400` for unreadable or invalid CSV, `422` for invalid selections (lap out of range, same lap twice, fewer than 3 laps for stint), `500` for internal errors; the body is `{"detail": "..."}`.

| Endpoint | Method | Form fields | Returns |
|---|---|---|---|
| `/api/health` | GET | none | `{status, service, version}` |
| `/api/analyze-session` | POST | `session_file` (CSV) | JSON with `laps` (time, pit/outlier flags), `fastest_lap`, `track_map`, `total_laps`. If no laps can be segmented, empty `laps` and a `message`. |
| `/api/stint/analyze` | POST | `laps`: one session CSV, or 3 or more single-lap CSVs | JSON: `laps`, `degradacion`, `combustible`, `montecarlo`, `curvas_sesion`, `telemetria_sesion`, `setup_sesion`, `thermal_analysis`, `degradacion_neumatico`, `racing_line_rl`, `track_evolution`, `health_summary` |
| `/api/compare-laps` | POST | `lap_a`, `lap_b` (CSVs) | Basic comparison: `summary`, speed/brake/throttle comparisons, `time_delta_series`, `corners`, `track_map`, `metadata`, `text_report`, `setup_advisor` and the advanced module results when available |
| `/api/telemetry/analyze` | POST | `lap_fast`, `lap_slow` (CSVs); query `resolution_m` (default 5) | Advanced pipeline: `telemetria`, `curvatura`, `apexes`, `sectores`, `corners`, `gg_diagram`, `g_limit`, `dynamic_events`, `anomaly`, `corner_clusters`, `tiempo_potencial`, `xgboost_pred`, tyre/brake/inputs/suspension/slip results |
| `/api/telemetry/compare` | POST | `lap_fast`, `lap_slow` (CSVs); query `resolution_m` | Geometry and time-delta subset: `metadata`, `telemetria`, `curvatura`, `apexes`, `sectores`, `corners` |
| `/api/compare-session-laps` | POST | `session_file` (CSV), `lap_a`, `lap_b` (1-based integers; `0` = auto: fastest and slowest flying lap) | Full comparison of two laps of a session: everything from `compare-laps` plus `telemetria`, `curvatura`, `apexes`, `sectores`, `gg_diagram`, `anomaly`, tyre/brake/inputs/suspension/slip/`thermal_analysis`, `setup_advisor`, `text_report`, `health_summary`; `metadata` includes `distance_synthetic` |
| `/api/report/pdf` | POST | `session_file` (CSV), `lap_a`, `lap_b` (same rules as above) | `application/pdf` attachment `report_V{a}_vs_V{b}.pdf` |
| `/api/report/pdf-from-json` | POST | JSON body: a comparison result already computed (as returned by the compare endpoints) | `application/pdf` attachment, no recomputation |

Notes:

- The UI calls `/api/analyze-session` then `/api/stint/analyze` for a session, `/api/compare-laps` plus `/api/telemetry/analyze` for two files, `/api/compare-session-laps` for lap pairs, and `/api/report/pdf-from-json` for the PDF button.
- `/api/telemetry/analyze` appends an observation to `data/laptime_history.db`, which feeds the historical P10 and XGBoost layers over time.
- A module that cannot run returns `{"available": false, ...}` (often with `reason`) instead of failing the whole request.

## Configuration

Copy `.env.example` to `.env` (loaded with `python-dotenv`).

| Variable | Default | Effect |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TEMP_DIR` | `<project>/tmp` | Directory for temporary upload files (created if missing; uploads are deleted after each request) |
| `API_HOST` / `API_PORT` / `API_RELOAD` | `0.0.0.0` / `8000` / `false` | Used only when running `python main.py` |
| `VITE_API_URL` | `http://localhost:8000/api` | API URL used by the frontend (read by Vite at build/dev time) |
| `MAX_UPLOAD_MB` | n/a | Present in `.env.example` and `docker-compose.yml` but **not read by the code**: the backend does not enforce an upload size limit |

## Development and tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q          # 48 tests

cd frontend
npm run lint                       # ESLint
npm run build                      # production build into frontend/dist
```

Test files: `tests/test_alignment.py`, `test_loaders.py`, `test_metrics.py`, `test_session_pipeline.py` (fixtures in `tests/conftest.py`). Synthetic sample laps can be generated with `python scripts/generate_sample_data.py` (writes `data/raw/lap_clean.csv` and `data/raw/lap_errors.csv`, which are git-ignored).

## Documentation

| Audience | Document |
|---|---|
| Users | [User Guide](docs/USER_GUIDE.md), [Quick Reference](docs/QUICK_REFERENCE.md) |
| Developers | [Docs index](docs/README.md) with the 17 scientific module documents (math, algorithms, figures), [frontend/README.md](frontend/README.md) |
| Spanish | [README.es.md](README.es.md), [Guia de Usuario](docs/GUIA_USUARIO.es.md), [Referencia Rapida](docs/REFERENCIA_RAPIDA.es.md), [docs/README.es.md](docs/README.es.md) |

## Known limitations

- Speed-based corner detection finds fewer corners than geometry-based detection (7 vs 11 at Imola, because chicanes merge).
- Suspension bottoming is a heuristic: travel at or above 90 % of the maximum observed travel.
- Some channels may be absent depending on the simulator and export; the corresponding panels say so instead of guessing.
- CSV is the stable input. iRacing `.ibt` and MoTeC `.ld` are read natively but are **experimental** (see "Supported formats" in `docs/USER_GUIDE.md`).
- No upload size limit is enforced (see `MAX_UPLOAD_MB` above); very large files need memory and time.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: fork, branch, run `python -m pytest tests -q`, open a Pull Request against `main`. Do not commit telemetry CSVs or secrets.

## License

[MIT](LICENSE) - Copyright (c) 2026 Andres Gutierrez.
