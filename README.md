# Motorsport Analytics Pipeline

> Automated lap telemetry comparison and analysis for Assetto Corsa / MoTeC compatible simulators.

🌐 [Leer en Español](README.es.md)

## Quick Start

**Requirements:** Python 3.10+ and Node.js 18+

1. **Install backend dependencies:**
```bash
pip install -r requirements.txt
```

2. **Install frontend dependencies:**
```bash
cd frontend
npm install
```

3. **Start the backend API:**
```bash
uvicorn main:app --reload --port 8000
```

4. **Start the frontend (in a separate terminal):**
```bash
cd frontend
npm run dev
```

5. **Open the app:**
Navigate to `http://localhost:5173`, upload your ACTI-exported CSV files (e.g. `slow_lap.csv` and `fast_lap.csv`) and click **Analyze**.

## Features

- 🏁 **Multi-Lap Comparison:** Supports loading and simultaneously comparing up to 6 laps, with automatic color coding and labels.
- 🔍 **Interactive Corner Zoom:** Clicking on a corner analysis card automatically zooms all charts into the braking and acceleration zone for that specific corner.
- 🆔 **Smart Identity Detection:** Extracts metadata from the MoTeC CSV (Driver, Vehicle, Circuit) to generate dynamic labels and flag mismatches (e.g. warns when comparing different vehicles).
- 📋 **Exportable Engineer Report:** Generates a plain-text, corner-by-corner summary with a built-in copy-to-clipboard button.
- 🌡️ **Tire Temperature Analysis:** Full thermal analysis per tire (Inner/Middle/Outer/Core), optimal operating window detection (configurable), surface-to-core ΔT gradient, and percentage of time in thermal stress.
- 🔴 **Brake Fade — Braking Efficiency:** |LonG| / pedal pressure ratio across all braking zones. Automatically detects efficiency degradation over the stint and pinpoints thermal fade zones.
- 🎮 **Driver Inputs Analysis (FFT):** Welch PSD on the SteerAngle channel to quantify high-frequency micro-corrections. Normalized jitter index + brake-throttle overlap percentage per lap.
- 🔧 **Suspension — Pitch & Roll:** Chassis pitch and roll from the 4 SuspTravel channels, bottoming event detection with severity, and peak dynamic load-transfer values.
- 📐 **Sideslip Angle (β):** Kinematic integration of Vy_dot = LateralG·g − YawRate·Vx to estimate chassis β. Calculation of αF and αR using the bicycle model; on-track balance (understeer vs oversteer) by distance.
- 🗺️ **Track Map:** Simplified circuit trace visualization based on GPS/game coordinates.
- ◎ **G-G Diagram (Friction Circle):** Visualizes the vehicle's available grip with points colored by G-Sum efficiency. Displays the traction limit (95th percentile) and the distribution of longitudinal and lateral forces.
- ⚠️ **Understeer & Oversteer Detection:** Algorithm that analyzes steering angle derivatives and Lateral-G to identify front-grip loss (understeer) or rear-grip loss (oversteer) in each corner, with severity and textual diagnosis.
- 🗜️ **RDP Compression (Ramer-Douglas-Peucker):** Reduces telemetry payload by up to 80% while preserving the shape of speed and delta curves, with forced apex retention to maintain accuracy in critical zones.
- 🗃️ **Unified View:** All analyses (basic + advanced) are presented on a single scrollable page with no tabs or toggles, loaded in parallel.

## Documentation

| For Users | For Developers |
|---|---|
| [User Guide](./docs/USER_GUIDE.md) — How to use the app and interpret results | [Scientific Docs](./docs/README.md) — Math, algorithms, visualizations |
| [Quick Reference](./docs/QUICK_REFERENCE.md) — Interpretation cheat sheet | [API Reference](#api-endpoints) — REST endpoints |
| [Español →](README.es.md) | [Docs en Español →](docs/README.es.md) |

## Project Structure

- `main.py` — FastAPI backend (endpoints and telemetry management)
- `src/` — Core telemetry engine logic
  - `io/` — Data loading and export (loaders, exporters)
  - `processing/` — Spatial alignment and filters (alignment, filters)
  - `telemetry/` — Lap comparison and session analysis (lap_comparator, session_analyzer)
  - `analytics/` — Advanced analysis modules
    - `geometry.py` — Track geometry, curvature-based apex detection
    - `alignment.py` — Lap alignment and time delta calculation
    - `insights.py` — Technical insight generation, corner by corner
    - `dynamics.py` — Friction circle (G-Sum, efficiency), understeer/oversteer detection
    - `compression.py` — Ramer-Douglas-Peucker (RDP) compression for payload reduction
    - `thermodynamics.py` — Tire thermal analysis: temperature window, ΔT, stress
    - `brake_fade.py` — Braking efficiency and brake fade detection per zone
    - `driver_inputs.py` — Welch FFT on SteerAngle, jitter index, brake-throttle overlap
    - `suspension.py` — Pitch, roll, and bottoming from SuspTravel FL/FR/RL/RR channels
    - `slip_angle.py` — Sideslip angle β (kinematic), αF/αR, and on-track balance
- `frontend/` — User interface (React + Vite, Recharts for charts)
  - `src/components/` — React components (SpeedChart, BrakeThrottleChart, TimeDeltaChart, TrackMap, CornerReport, GGDiagramChart, etc.)
  - `src/api/` — Axios client for API communication
  - `src/api/cursorStore.js` — Synchronous cursor store for cross-chart sync (60fps performance)
- `scripts/` — Additional utilities (e.g. synthetic data generator)
- `data/` — Directory for storing raw CSV files

## Architecture

The pipeline uses the following mathematical and logical architecture:

1. **Ingestion & Metadata:** Pandas loads the CSVs, reads the headers (Driver, Vehicle) and validates/cleans the essential channels (Speed, Brake, Throttle, Distance).
2. **Signal Filters:** Smoothing (moving average) and outlier cleaning on noisy sensor channels to avoid false positives in derivatives.
3. **Track Geometry & Apexes:** Dynamic curvature calculation to detect corner entry, apex, and exit points via curvature maxima and speed minima.
4. **Spatial Alignment:** Unlike traditional time-based telemetry, all laps are cubically interpolated onto a uniform X axis based on **distance** (1-meter resolution), including extra channels such as LateralG, LongitudinalG, and SteerAngle.
5. **Friction Circle (G-G Diagram):** G-Sum (√(G_Lat² + G_Long²)) calculated per sample, traction limit as the 95th percentile of G-Sum, and grip efficiency per point.
6. **Understeer/Oversteer Detection:** Analysis of steering angle derivatives in apex windows. Understeer = wheel keeps turning but Lateral-G does not increase. Oversteer = abrupt Lateral-G spike with simultaneous steering correction.
7. **Comparison & Visualization:** Generation of precise deltas in meters and seconds, RDP compression of the payload (preserving apexes), and delivery of the final JSON to the frontend for interactive Recharts rendering.
8. **State Persistence:** Components for each tab remain mounted (hidden via CSS) when switching tabs, preserving loaded files and results without reload. Cursor tracking outside React (store module + rAF + direct DOM) for 60fps with no re-renders.

## AI Pipeline

The system includes three AI models that activate progressively based on the accumulated history in `data/laptime_history.db`:

### Isolation Forest — Anomaly Detection
Trains on the fast lap (normal reference state) and scores the slow lap point by point. Zones with score > 0.60 are identified as driving anomalies.
- **Always active** — no historical data required
- Documentation: [docs/05_anomaly_detection.md](./docs/05_anomaly_detection.md)

### K-Means — Corner Style Profiles
Classifies each corner into semantic profiles: *Clean Attack*, *Aggressive Entry*, *Conservative*, *Late Exit*. Enables comparison of driving style across circuits and laps.
- **Always active** — based on current lap data
- Documentation: [docs/06_clustering.md](./docs/06_clustering.md)

### Reachable Lap (P10) + Consistency + XGBoost
Three layers of lap-time potential analysis:
1. **Historical P10** — activates with ≥3 observations per corner: statistically reachable time in the top 10%
2. **Consistency Score** — `max(0, 100 × (1 − σ/|μ|))`: how repeatable the driver is, corner by corner
3. **XGBoost** — activates with ≥30 total observations: predicts the optimum and explains the gap with the top-2 limiting factors
- Documentation: [docs/07_lap_time_potential.md](./docs/07_lap_time_potential.md)

### Stint Analysis — Monte Carlo
Full pipeline for complete race analysis:
- Lap time degradation: linear regression β₁ (s/lap)
- Fuel strategy with pit window calculated using conservative consumption (mean + 1.65σ)
- 500 reproducible Monte Carlo simulations (`seed=42`) with P10/P25/P50/P75/P90 bands
- Documentation: [docs/08_stint_analysis.md](./docs/08_stint_analysis.md)

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/compare-laps` | POST | Simple 2-lap comparison (SpeedChart, TrackMap, CornerReport) |
| `/api/telemetry/compare` | POST | Advanced pipeline with geometry, time delta, and sectorization |
| `/api/telemetry/analyze` | POST | Full pipeline: geometry + time delta + friction circle + dynamic events + RDP compression |
| `/api/analyze-session` | POST | Full session analysis with multiple laps |
| `/api/analyze` | POST | Full AI pipeline: geometry + time delta + Isolation Forest + K-Means + XGBoost + P10 |
| `/api/stint/analyze` | POST | Multi-lap analysis: linear degradation + fuel strategy + Monte Carlo 500 sims |

## Scientific Documentation

All modules are documented with mathematical foundations, pseudocode, and matplotlib visualizations:

| # | Module | File |
|---|--------|------|
| 01 | Track Geometry & Apex Detection | [docs/01_geometry.md](./docs/01_geometry.md) |
| 02 | Time Delta & Distance-Based Alignment | [docs/02_time_delta.md](./docs/02_time_delta.md) |
| 03 | G-G Diagram & Friction Circle | [docs/03_gg_diagram.md](./docs/03_gg_diagram.md) |
| 04 | Understeer / Oversteer (3 Severity Levels) | [docs/04_dynamics.md](./docs/04_dynamics.md) |
| 05 | Isolation Forest — Anomaly Detection | [docs/05_anomaly_detection.md](./docs/05_anomaly_detection.md) |
| 06 | K-Means — Driving Style Clustering | [docs/06_clustering.md](./docs/06_clustering.md) |
| 07 | Reachable Lap, Consistency & XGBoost | [docs/07_lap_time_potential.md](./docs/07_lap_time_potential.md) |
| 08 | Stint Analysis & Monte Carlo Simulation | [docs/08_stint_analysis.md](./docs/08_stint_analysis.md) |
| 09 | Tire Temperature — Thermal Window & ΔT | [docs/09_thermodynamics.md](./docs/09_thermodynamics.md) |
| 10 | Brake Fade — Braking Efficiency & Degradation | [docs/10_brake_fade.md](./docs/10_brake_fade.md) |
| 11 | Driver Inputs — FFT & Steering Jitter | [docs/11_driver_inputs.md](./docs/11_driver_inputs.md) |
| 12 | Suspension — Pitch, Roll & Bottoming | [docs/12_suspension.md](./docs/12_suspension.md) |
| 13 | Sideslip Angle — β & αF/αR Balance | [docs/13_slip_angle.md](./docs/13_slip_angle.md) |

See the full index at [docs/README.md](./docs/README.md).

---
*Documentation also available in [Español](README.es.md)*
