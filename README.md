# Motorsport Analytics Pipeline

> Lap and session telemetry analysis for Assetto Corsa and iRacing: lap comparison, corner-by-corner diagnosis, stint and tyre analysis, optimal lap by microsectors, setup recommendations linked to your Assetto Corsa setups, a session library and a bilingual PDF report.

[Leer en Español](README.es.md)

## Quick start

```bash
# 1. Backend (from the project root)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# 2. Frontend (second terminal)
cd frontend && npm install && npm run dev

# 3. Open http://localhost:5173 and drop a CSV, .ibt or .ld file (see "Using the app")
```

With Docker (backend + frontend + PostgreSQL, UI on http://localhost:8080): `cp .env.example .env && docker compose up --build -d` (Windows PowerShell: `Copy-Item .env.example .env`). Docker Compose and Kubernetes (kind) were built and run on the author's Windows 11 machine; see [Installation](#installation), [Deployment](#deployment) and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for what was and was not verified.

## Table of contents

- [What it is](#what-it-is)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Route A: local, without Docker](#route-a-local-without-docker)
  - [Route B: Docker Compose](#route-b-docker-compose)
  - [Route C: Kubernetes with kind](#route-c-kubernetes-with-kind)
- [Installation troubleshooting](#installation-troubleshooting)
- [Deployment](#deployment)
- [Using the app](#using-the-app)
- [Main features](#main-features)
- [Telemetry formats](#telemetry-formats)
- [Known circuits and corner names](#known-circuits-and-corner-names)
- [Themes](#themes)
- [Performance and upload once](#performance-and-upload-once)
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

A FastAPI backend plus a React frontend. You upload telemetry and get back:

- **Session mode (1 file):** the full session is split into laps automatically. You get a lap table (pit and outlier laps flagged), stint analysis (pace degradation, fuel strategy, Monte Carlo projection, pit window, track evolution), the optimal lap by microsectors, per-corner session analysis, tyre degradation, thermal management, racing-line optimisation, setup recommendations and a data-quality panel.
- **Comparison mode (2 files of one lap each, or 2 laps picked from a session):** distance-aligned time delta, speed/brake/throttle overlays, corner-by-corner diagnosis, G-G diagram, understeer/oversteer events, tyre/brake/suspension/driver-input/slip-angle analysis, ML modules (anomaly detection, style clustering, lap-time potential) and a PDF report.
- **Library:** analysed sessions can be saved to a database, reopened without the original file and compared with each other.

The UI has two views: **Engineer** (everything) and **Pilot** (technical panels hidden). Languages: English and Spanish (API messages and reports follow the `lang` query parameter or `Accept-Language`).

## Installation

Pick one of three routes. All of them start with:

```bash
git clone https://github.com/ElSirGuti/motorsport-analytics-pipeline.git
cd motorsport-analytics-pipeline
```

### Prerequisites

| Tool | Route | Version |
|---|---|---|
| Git | all | any |
| Python | A | 3.10 or newer (tested by the author with 3.11.5; the Docker image uses 3.11) |
| Node.js + npm | A | 18 or newer (tested with Node 21; the Docker image uses 20) |
| Docker with Compose v2 | B, C | Docker Desktop on Windows/macOS or Docker Engine on Linux (tested with Docker 29.8 and Compose v5.5) |
| kind and kubectl | C | kind 0.33 was tested; Docker Desktop already ships `kubectl` |

Dependencies are pinned to the tested line in `requirements.txt` (`pandas>=2.2.0,<3`, `numpy>=1.26.0,<2`). Do not upgrade to pandas 3: it breaks reading MoTeC CSV files with a decimal comma (see [troubleshooting](#installation-troubleshooting)).

### Route A: local, without Docker

The fastest way to try the app. Needs Python and Node only.

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1          # if scripts are blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt     # add -r requirements-dev.txt to run the tests
cd frontend; npm install; cd ..
```

macOS / Linux (bash):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt     # add -r requirements-dev.txt to run the tests
(cd frontend && npm install)
```

Run two processes, one per terminal (activate the virtual environment in the first one):

```bash
# Terminal 1, project root: API on http://localhost:8000 (Swagger at /docs)
uvicorn main:app --reload --port 8000

# Terminal 2: UI on http://localhost:5173
cd frontend
npm run dev
```

Open http://localhost:5173. You can also run `python main.py`, which reads `API_HOST`, `API_PORT` and `API_RELOAD` from the environment. Without a `.env` file everything works with the defaults; the frontend calls `http://localhost:8000/api` (`VITE_API_URL`).

What is created automatically (nothing to set up):

- `data/motorsport.db`: SQLite database of the session library, created on the first library request.
- `data/laptime_history.db`: SQLite history of laps used by the ML layers. It is **not versioned**; it is created on the first `POST /api/telemetry/analyze` (override the path with `LAPTIME_HISTORY_DB`).
- `tmp/`: temporary and uploaded files (`TEMP_DIR`, `UPLOAD_DIR`).

Expected time: `pip install` takes a few minutes (it downloads xgboost, scipy, scikit-learn and matplotlib) and `npm install` about a minute.

### Route B: Docker Compose

Starts PostgreSQL 16, the backend and the frontend (nginx). The UI is served on http://localhost:8080; backend and database are only on the internal Docker network.

**1. Prerequisites on Windows (Docker Desktop needs virtualization).**

1. Enable virtualization in the BIOS/UEFI (Intel VT-x, or AMD-V / SVM on AMD). You can check it in Task Manager, Performance, CPU, "Virtualization: Enabled".
2. Install WSL 2 from an administrator PowerShell and reboot: `wsl --install`. Afterwards `wsl --status` must show `Default Version: 2`.
3. Install Docker Desktop: `winget install -e --id Docker.DockerDesktop` (or download it from docker.com), then open it once and wait until it says it is running.
4. Check from a new terminal: `docker version` (client and server) and `docker compose version`.

On macOS install Docker Desktop; on Linux install Docker Engine and the Compose plugin. Nothing else is needed.

**2. Create `.env`.** `docker compose up` **fails without it** (`required variable POSTGRES_PASSWORD is missing a value`). `.env` is git-ignored.

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

Open `.env` and set `POSTGRES_PASSWORD`. The example value is for a local machine only.

**3. Build and start.**

```bash
docker compose up --build -d      # or: make up (macOS/Linux, creates .env if missing)
```

The first build of the backend image takes **more than 10 minutes** (pip downloads xgboost, scipy, scikit-learn and matplotlib); later builds use the cache and take seconds. A network cut during the build shows `TimeoutError: The read operation timed out`: simply run the build again.

**4. Verify.**

```bash
docker compose ps                          # postgres, backend and frontend "healthy"
curl -f http://localhost:8080/api/health   # Windows PowerShell: curl.exe -f http://localhost:8080/api/health
docker compose exec backend id             # uid=10001: the backend does not run as root
```

Open http://localhost:8080. The backend filesystem is read-only; it only writes to the `storage` volume and a `tmpfs`. On start it runs `alembic upgrade head` against PostgreSQL (table `library_sessions`, revision `0001`).

**5. Stop.**

```bash
docker compose down        # stops and removes the containers, keeps the data (volumes)
docker compose down -v     # also deletes the volumes: the PostgreSQL library and stored files are lost
```

Optional dev profile (backend with hot reload on http://127.0.0.1:8010, run Vite locally): `docker compose --profile dev up postgres backend-dev`.

### Route C: Kubernetes with kind

Creates a local cluster named `motorsport` with ingress-nginx and the Kustomize overlay `k8s/overlays/local`. Needs Docker running (see route B, step 1) plus kind and kubectl.

**1. Install kind and kubectl.**

```powershell
# Windows (winget); Docker Desktop already includes kubectl, so the second line is optional
winget install -e --id Kubernetes.kind
winget install -e --id Kubernetes.kubectl
```

```bash
# macOS (Homebrew); on Linux use the binaries from kind.sigs.k8s.io and kubernetes.io
brew install kind kubectl
```

Open a new terminal afterwards and check `kind version` and `kubectl version --client`.

**2. Create the cluster and deploy.** It creates the cluster, installs ingress-nginx, builds both images, loads them into kind and applies the overlay:

```powershell
# Windows PowerShell
scripts\kind-up.ps1               # if blocked: powershell -ExecutionPolicy Bypass -File scripts\kind-up.ps1
```

```bash
# macOS / Linux (also Git Bash on Windows with make installed)
make kind-up                      # or: bash scripts/kind-up.sh
```

The script reuses an existing cluster with the same name. It takes more than 10 minutes the first time because of the image build (same as Docker Compose).

**3. Verify.**

```bash
kubectl -n motorsport get pods              # backend, frontend and postgres-0 in Running
curl http://localhost:8088/api/health       # Windows PowerShell: curl.exe http://localhost:8088/api/health
```

Open http://localhost:8088. The backend runs an `initContainer` named `migrate` (`alembic upgrade head`); if PostgreSQL is not ready yet it can fail once and Kubernetes retries it by itself, so a pod in `Init:Error` or `Init:CrashLoopBackOff` for a short while is normal.

**4. Delete.**

```bash
kind delete cluster --name motorsport       # or: make kind-down
```

After changing code, run the script again (it rebuilds, reloads the images and applies the overlay); if the pods keep the old image, run `kubectl -n motorsport rollout restart deploy/backend deploy/frontend`.

## Installation troubleshooting

| Symptom | Cause and fix |
|---|---|
| Docker Desktop: `Virtualization support not detected` | Enable Intel VT-x or AMD-V (SVM) in the BIOS/UEFI, run `wsl --install` in an administrator PowerShell, reboot, then open Docker Desktop. Check with `wsl --status` (Default Version: 2) and `docker version`. |
| `required variable POSTGRES_PASSWORD is missing a value` | `.env` does not exist. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` on PowerShell, `cp .env.example .env` on bash) and set `POSTGRES_PASSWORD`. |
| `TimeoutError: The read operation timed out` during `docker build` | pip lost the connection while downloading the scientific packages. Run the build again; completed layers are cached. |
| `Essential channel Speed has no valid numeric values` with a MoTeC CSV | pandas 3 is installed. Reinstall the pinned versions: `pip install -r requirements.txt` (`pandas>=2.2.0,<3`, `numpy>=1.26.0,<2`). |
| `unable to open database file` | The folder of the SQLite file is not writable (typically a read-only container filesystem or a volume without permissions). Point `STORAGE_DIR` (and, for the lap history, `LAPTIME_HISTORY_DB`) to a writable directory or volume. |
| Blank page in the Vite dev server | Stale Vite cache. Stop `npm run dev`, start it again (if needed delete `frontend/node_modules/.vite`) and hard-reload the browser. |
| `port is already allocated` / address already in use | Another program uses the port. Defaults: 8000 (API) and 5173 (Vite) in route A, 8080 (`FRONTEND_PORT`) in route B, 8088 and 8443 in route C. Close the other program or change the port (`FRONTEND_PORT` in `.env`, `--port` for uvicorn). |

## Deployment

Full guide, including architecture, environment contract, troubleshooting and security notes: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) ([Español](docs/DEPLOYMENT.es.md)).

| Method | Command | Result |
|---|---|---|
| Docker Compose | `cp .env.example .env` then `docker compose up --build -d` (or `make up`) | UI on `http://localhost:8080` (`FRONTEND_PORT`); backend and PostgreSQL stay on the internal network |
| Compose dev profile | `docker compose --profile dev up postgres backend-dev` | API with hot reload on `http://127.0.0.1:8010` (`BACKEND_DEV_PORT`) |
| Kubernetes (kind) | `make kind-up` (or `scripts/kind-up.sh`, `scripts/kind-up.ps1`) | Local cluster with Kustomize overlay `k8s/overlays/local`, UI on `http://localhost:8088` |
| Kubernetes (other) | `kubectl apply -k k8s/overlays/local` or `k8s/overlays/prod` | See the deployment guide |

Step-by-step instructions for each method are in [Installation](#installation). `.env` must exist (copy `.env.example`) and `POSTGRES_PASSWORD` must be set; the example values are for a local machine only. Compose runs `alembic upgrade head` on start.

**What was and was not verified.** Verified on the author's machine (Windows 11, Docker Desktop with Docker 29.8.1 and Compose v5.5.1, kind v0.33.0):

- Docker Compose: `docker compose up --build -d` starts PostgreSQL 16, backend and frontend healthy; the UI answers on `http://localhost:8080` and `/api/health` returns OK; the backend runs as uid 10001 with a read-only filesystem; the Alembic migrations reach a real PostgreSQL (table `library_sessions`, revision `0001`).
- Kubernetes: `scripts\kind-up.ps1` creates the `motorsport` cluster, installs ingress-nginx, loads the images and applies `k8s/overlays/local`; the three pods (backend, frontend, `postgres-0`) reach Running and the UI answers on `http://localhost:8088`.
- Static checks (YAML, Kubernetes schemas with `scripts/validate_k8s.py` and `kubeconform`, `yamllint`, `hadolint`, `shellcheck`).

**Not verified:** the HorizontalPodAutoscaler, PodDisruptionBudgets and NetworkPolicies are not exercised in kind (its default network plugin does not enforce policies, and the local overlay removes the HPA and PDBs); the `k8s/overlays/prod` overlay has been rendered and validated but never applied to a cluster; macOS and Linux were not tried; there is **no authentication**, so do not expose the application to the internet as is.

The Compose and kind commands to reproduce the checks are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#what-has-been-verified).

**Assetto Corsa setups inside Docker.** A container cannot see your `Documents\Assetto Corsa\setups` folder. Either upload the setup `.ini` manually in the UI, or bind-mount the folder read-only and set `AC_SETUPS_DIR` (see `docker-compose.override.example.yml`).

## Using the app

1. Open the UI (`http://localhost:5173` in dev, `http://localhost:8080` with Docker) and choose the language (ES/EN) and the mode (Pilot/Engineer) in the top bar. The **Analysis / Library / Compare sessions** switch selects the view.
2. Drop telemetry files in the upload area. The mode is detected from the number of files:
   - **1 file = full session**, segmented into laps automatically.
   - **2 files = two single laps** to compare (the UI calls `/api/compare-laps` and `/api/telemetry/analyze`; it warns if the two files come from different cars).
3. Click analyze. The file is uploaded once and a stage progress bar shows session, stint and optimal-lap analysis; results appear as each stage finishes (a ~57 MB session showed its first result in about 2 s and finished in about 3 s on the author's machine, see [Performance](#performance-and-upload-once)). Once the analysis is done, the upload area collapses into a file bar with **New analysis**, **Save to library** and **Download report** actions.
4. A **data-quality panel** appears first: score, channels, laps and analysis modules, with a list of what would improve the analysis.
5. Navigate with the side rail:
   - Session: *Session overview* (lap table, track map, optimal lap), *Stint analysis*, *Setup & strategy*.
   - Comparison: *Core lap*, *Vehicle dynamics*, *Driver & inputs*, *Strategy & setup*.
   - Pilot mode hides the technical panels (vehicle dynamics and driver inputs).
6. In the session lap table, tick **two laps (A/B)** and press **Compare**, or use **Best vs Worst**. Pit and outlier laps are marked in the table.
7. Compare results can be copied as a text report or downloaded as a PDF.

Full walkthrough: [User Guide](docs/USER_GUIDE.md).

## Main features

### Optimal lap by microsectors

`POST /api/optimal-lap` (module `src/analytics/optimal_lap.py`, UI panel `OptimalLapPanel` in the session overview). Every valid lap is normalised to the median track length and cut into microsectors; the panel reports two estimates:

- **Theoretical:** the sum of the best time of every microsector. It is an optimistic lower bound because it ignores that the exit speed of one microsector is the entry speed of the next.
- **Realistic:** dynamic programming that only switches from one lap to another where the speeds match (tolerance `speed_tol_kmh`, default 3 km/h) and keeps a minimum run of 75 m on the same lap, so kinematic continuity is preserved.

The microsector length is configurable in the UI (10, 25, 50 or 100 m; the API takes any value in `microsector_m`, default 25). Limits: the theoretical figure grows as the microsector shrinks (it has more freedom to cherry-pick); with a synthesised `Distance` channel the alignment is less precise and the result is indicative only (the API adds a warning). It needs at least 3 usable laps; pit, outlier and partial laps are excluded. The panel also shows time gain per microsector on the track map, the zones where the best lap loses the most, gain per corner and the laps that contribute the most.

Imola example (Porsche Cayman GT4, 21 laps): best lap 1:57.605, realistic optimal 1:54.107 (-3.498 s), theoretical optimal 1:52.885 (-4.720 s).

### Assetto Corsa setup integration

Module `src/analytics/ac_setups.py`, router `src/api/setups.py`, UI `SetupSelector` and `SetupLink`. The setup you used is linked to the Setup Advisor so each recommendation can show **Current -> Suggested**.

Lookup order:

1. `<Documents>\Assetto Corsa\setups\<car>\<track>\*.ini` (car and track come from the telemetry header; `AC_SETUPS_DIR` overrides the folder). If several exist you choose which one you used.
2. `<car>\generic\last.ini`, only after you confirm it was the setup used in that session.
3. Manual upload of a `.ini` file (always available).

Notes: the setups folder is only readable when the backend runs on the same machine as the game. In Docker you upload manually or use a read-only bind mount. Values are shown in the game's raw units (clicks); units are applied only where they are certain (tyre pressure in psi, front brake bias and brake power in %, fuel in litres), and min/max ranges only when the car's unpacked `data/setup.ini` exists (encrypted `data.acd` files are deliberately not opened). Security: car and track names are validated against a strict character set and matched against the real directory listing, the resolved path must stay inside the setups folder (path traversal is rejected), and only `.ini`/`.sp` files up to 256 KB are read.

### Session library and session comparison

Code in `src/api/library.py`, `src/db/` (SQLAlchemy models and engine), `src/analytics/session_compare.py` and migrations in `alembic/`. Use **Save to library** in the file bar (or enable automatic saving), then reopen the session from **Library** without the CSV, or pick two sessions in **Compare sessions** to see differences in average and median pace, consistency, fuel per lap and time lost per corner.

- Storage: `DATABASE_URL` (default `sqlite:///data/motorsport.db`; PostgreSQL in the containers, `postgresql+psycopg://...`), optional `STORAGE_DIR` (default `./data/storage`). The schema is created or migrated automatically on the first library request (Alembic, falling back to `create_all`); Compose and the Kubernetes init container also run `alembic upgrade head` on start.
- Saving the same file (SHA-256) for the same circuit updates the existing entry instead of duplicating it.
- Sessions must be from the same circuit and car to be compared; a forced comparison is possible and flagged.
- Limits: the saved payload is limited to **5 MB** (HTTP 413); listing is paginated (`limit` up to 200).
- There is **no authentication yet**. The `owner_id` column is reserved for a future user system and is always empty today.

### Data-quality panel

Module `src/analytics/data_quality.py`. Included in the responses as `data_quality` and shown first in the UI. It gives a **0-100 score** (good >= 75, fair >= 50, poor below) with a breakdown, and lists: source (sim, car, circuit, sample rate, duration), **channels** (present, missing, constant, synthesised, sparse, partial), **laps** (valid, pit, outliers, partial segments dropped), **analysis modules** (ok, degraded or unavailable, with the concrete reason) and a prioritised **how to improve** list. It reuses the `available`/`reason`/`low_confidence` flags the modules already produce instead of recomputing them.

### PDF report

Redesigned and bilingual (ES/EN, follows the UI language). **Download report** in the UI posts the already computed results to `POST /api/report/session-pdf-from-json` (session, stint and optionally a comparison); two-file and lap-pair comparisons use `POST /api/report/pdf-from-json`. Sections include executive summary, key findings, recommended actions, data quality and limitations, pace and laps, corners in track order, setup recommendations, strategy and tyres, and (in comparisons) car telemetry and trace comparisons. File name: `motorsport_<circuit>_<car>_<date>.pdf`.

### Realistic projections

The stint and tyre projections (`src/analytics/stint.py`, `tyre_degradation.py`) are conservative. With fewer than 5 valid laps or a very wide slope confidence interval, the projection falls back to the recent pace and is flagged `low_confidence: true`, with `confidence` (`low`/`medium`/`high`), `reason_code` (`insufficient_sample`, `wide_slope_ci`, `short_sample`) and a translated `reason`. Below 8 valid laps the confidence is always `low` and the projected median cannot fall under a plausible pace floor (`proj_floor_s`); the fuel-burn gain stops when the fuel runs out (`fuel_laps_remaining`). If tyre wear does not seem enabled in the simulator (zero wear rate and constant rubber grip), degradation is reported as `available: false`, `reason_code: "wear_inactive"` instead of inventing a trend, because degradation cannot be separated from fuel burn and track evolution.

## Telemetry formats

The loader (`src/io/loaders.py`) reads CSV and, **experimentally**, two native formats.

| Source | Status | Notes |
|---|---|---|
| Assetto Corsa via ACTI, exported as MoTeC CSV | Stable | Comma or semicolon separator is auto-detected; the MoTeC header block (Driver, Vehicle, Venue) is read as metadata and the units row is skipped. |
| iRacing exported to CSV | Stable | Detected by `SessionTime`, `Session Time` or `SessionLapCount`. Speed in m/s is converted to km/h, pedals in 0-1 are scaled to 0-100, suspension in metres to mm, tyre pressure kPa/PSI to bar, brake bias fraction to percent. |
| iRacing `.ibt` (`src/io/ibt_loader.py`) | **Experimental** | Detected by extension or binary signature. Units are normalised to the canonical channels. |
| MoTeC `.ld` (`src/io/ld_loader.py`) | **Experimental** | Channels at different rates are resampled to the fastest; shared code in `src/io/native_common.py`. |

> **Experimental.** The `.ibt` and `.ld` readers follow the publicly documented layouts and were validated with synthetic round-trip tests and 53 real files from the author (iRacing BMW M2 and Ford Mustang GT4, their MoTeC `.ld` exports, and Assetto Corsa/ACTI `.ld` logs). More simulators, cars and loggers need to be tested. The UI shows an Experimental badge. If a result looks wrong, compare with the CSV export. Native sessions above 2 million samples (`NATIVE_MAX_ROWS`) are rejected.

The export steps for each program are in the [User Guide](docs/USER_GUIDE.md#exporting-telemetry).

**Required channels:** `Speed`, `Brake`, `Throttle`. If any is missing or has no numeric values, the API answers `400` with a message listing the columns found.

**Distance:** if the `Distance` channel is absent (or never exceeds 10 m), it is synthesised by integrating `Speed` over a valid time clock (`LR/HR/MR Sample Clock`, `SessionTime`, `Time`, `Lap Time`; a clock that is a 0/1 square wave is rejected; falls back to `Session Time Left`, then the lap timer, then a fixed 100 Hz). Responses that carry metadata (`/api/compare-session-laps`, `/api/report/pdf`) set `metadata.distance_synthetic = true`. Synthetic distance is fine for stint and session analysis; lap-to-lap comparison and the optimal lap are more reliable with a real distance channel.

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

## Known circuits and corner names

`src/data/circuits.json` (19 circuits), logic in `src/analytics/circuits.py`. The circuit is recognised from the `Venue` of the telemetry header (aliases such as `imola`, `fn_imola`, `ks_spa`) and checked against the measured lap length (tolerance 4 %). Responses carry a `circuit` object (`id`, `name`, `short_name`, `country`, `length_m`, `recognized`, `matched`, `confidence`, `named_corners`, `measured_length_m`, `length_deviation_pct`) and every corner and apex gets a `corner_name` (null when unknown). The UI shows "Corner 4 - Tamburello" through the helper `frontend/src/utils/cornerLabel.js`.

- **Corner names exist for Imola, Spa-Francorchamps, Monaco, Silverstone GP and Le Mans (`high`: fitted against several real laps/logs) and for Mugello and Brands Hatch (`medium`: one lap, partial tables)**. The rest (Monza, Red Bull Ring, Nordschleife, Barcelona, Laguna Seca, Zandvoort, Vallelunga, Magione, Sepang, Oran Park GP and South, Lime Rock GP) are **recognition only** (no corner names, `confidence: medium`). A circuit may tighten matching with `apex_tolerance_m`.
- If the measured length does not fit (probably another layout or a partial lap) the circuit is flagged `low` confidence and no names are assigned. An apex without a tabulated corner nearby keeps its number.
- **Honesty rule:** a corner table is published only when its order and its positions were verified against telemetry. Never add names from memory or from a layout map without checking where each apex falls on a real lap.
- **Geometric reference (car independent).** `src/data/track_geometry/<circuit_id>.json` holds, for the 16 Assetto Corsa circuits of the database, where the bends are according to the geometry of the game's AI racing line (`ai/fast_lane.ai`): lap fraction, minimum radius, direction, class (slow < 60 m, medium 60-150 m, fast 150-400 m; a fast bend may still be flat out for a car with a lot of downforce) and chicane/compound grouping. It is read with `circuits.get_track_geometry(circuit_id)` (None when absent) and `validate_database` logs a warning if a tabulated corner is more than 250 m from every geometric corner. The files travel in the repo because Docker/Kubernetes do not see the game; to regenerate or inspect them (read-only on the game folder, found through `AC_CONTENT_DIR`/`AC_INSTALL_DIR` or the usual Steam paths): `python scripts/ac_track_reference.py imola --compare` and `python scripts/ac_track_reference.py --export-all`.

**Adding a circuit or its corner names** (all in `src/data/circuits.json`):

1. **Recognition.** Append an entry with `id`, `name`, `short_name`, `country`, `length_m`, `aliases` (the `Venue` text of your logs, e.g. `ks_red_bull_ring`), `confidence`, `source`, `notes` and `corners: []`. This alone makes the circuit recognized (badge in the UI).
2. **Find where the corners are.** Run the helper on a real log, ideally a session with several laps (and a second car or file before calling it `high`):

   ```bash
   python scripts/circuit_apexes.py path/to/log.csv --json     # also .ibt and .ld
   ```

   It detects apexes (track curvature and speed minima) in **every** complete lap, groups them by position and keeps only the ones present in at least 60% of the laps (`--min-share`). It prints each `apex_fraction` (position as a fraction of the lap), the speed there and, if the circuit is already in the table, the name it currently gets. With `--json` it prints the `corners` block to paste. A single-lap file also works, but it shows a warning because there is no consensus.
3. **Name them.** Replace each `"?"` with the real corner name, with the official layout in front of you. `order` must follow the lap and `apex_fraction` must be strictly increasing. Corners that appear in the list but are not in the official layout are noise: delete them.
4. **Record the evidence.** Set `confidence` to `medium` (one lap or one car) or `high` (several laps and at least two files or cars) and say in `source` which logs you used. Never publish names you are not sure about: a wrong name is worse than none.
5. **Validate.** `python -m pytest tests/test_circuits.py -q` checks ids, aliases, ordering and ranges (`validate_database`). Then upload a log of that circuit and check that the names appear in the corner panels.

**Limits to know.** A corner is only named if the detector finds an apex near its tabulated position (tolerance 2.5% of the lap, between 120 and 180 m, or `apex_tolerance_m` per circuit). A bend that a car takes **flat out** has no speed minimum and almost no curvature, so it produces no apex and is never named: that is why Variante Bassa at Imola is not in the table (in 26 laps of 5 cars the speed keeps rising there). Such bends do not appear in the helper's output either, so a missing entry in that list is information, not a bug.

## Themes

Light, dark or follow the operating system (selector in the top bar; the choice is stored in the browser). Files: `frontend/src/styles/theme-light.css`, `frontend/src/hooks/useTheme.js`; the dark tokens are in `design-system.css`. `python scripts/check_contrast.py` checks the WCAG contrast of both: both themes currently pass all 64 pairs (0 failing).

## Performance and upload once

The UI sends the file once with `POST /api/files` and then calls every analysis with the returned `file_id` (the SHA-256 of the content, so uploading the same file twice is idempotent). The backend keeps parsed frames in an in-memory LRU cache (`src/io/session_cache.py`, bounded by `SESSION_CACHE_MAX_MB` and `SESSION_CACHE_TTL_MIN`); stored files live in `UPLOAD_DIR` and are removed after `UPLOAD_TTL_HOURS`. If a file is no longer there (expired, or another replica without a shared volume) the endpoints answer **410** and the UI uploads again and retries. The classic mode (sending the file to each endpoint) still works. Results are progressive: the session table appears first, stint analysis and the optimal lap follow in parallel.

Imola (57 MB): first result about 2.1 s and everything about 2.9 s, instead of about 15 s and 21 s, with a peak of 724 MB of memory (author's machine). Reproduce with `python scripts/profile_pipeline.py FILE --repeat 3` (options `--cprofile`, `--dump`, `--compare`).

## Data quality notes and behaviour

- **Lap segmentation** is unified across all endpoints: by lap-counter channel (`Session Lap Count`, `Lap`, ...) or, failing that, by distance resets. Partial segments shorter than 30 s are discarded. If fewer than 2 laps are found the API answers with an error message.
- **Pit and outlier laps:** a lap is marked as pit if the `In Pit` channel says so; laps outside 70-115 % of the median lap time are also flagged as outliers and excluded from regressions and projections.
- **Corner windows do not overlap:** each window is trimmed at the midpoint between neighbouring apexes. The comparison `summary` includes `corners_time_delta_s` (time gained/lost inside corners) and `outside_corners_delta_s` (the remainder).
- **Corner matching** between two laps uses the apex distance, not the corner index.
- **Not-measurable values:** `braking_delta_available` and `throttle_delta_available` flag whether the braking/throttle deltas could be measured. A `0.0` with `available = false` means "not measurable", not "no difference".
- **Constant channels** (for example brake temperatures fixed at one value) return `available: false` with a `reason` instead of generating false recommendations.
- **Low confidence:** projections with too few laps carry `low_confidence`, `confidence` and `reason` (see "Realistic projections").
- **Slip angle sign convention:** the sign convention of `LateralG` is detected from its correlation with the yaw rate and flipped when needed (Assetto Corsa logs it inverted) before computing the slip angle.
- **Input validation:** an empty file or one without the minimum channels returns `400` with a clear message. Invalid lap selections return `422`. A file above `MAX_UPLOAD_MB` returns `413`.
- **Track evolution** (`track_evolution`), **`health_summary`** and **`data_quality`** are part of the stint and compare-session responses.

## Example result

Validated with a Porsche Cayman GT4 Clubsport at Imola (Assetto Corsa, ~57 MB MoTeC CSV with no `Distance` channel):

| Item | Value |
|---|---|
| Laps detected | 21 (laps 1 and 21 are pit laps) |
| Best lap | Lap 11, 1:57.605 |
| Optimal lap (realistic / theoretical) | 1:54.107 (-3.498 s) / 1:52.885 (-4.720 s) |
| Race-lap range | 117.6 - 122.4 s |
| Track length | ~4862 m |
| Top speed | 243.9 km/h |
| Corners by geometry | 11 |
| Fuel consumption | 1.758 L/lap |
| Degradation trend | -0.077 s/lap (the car gets faster as fuel burns off) |
| Analysis time | first result ~2.1 s, everything ~2.9 s (author's machine; it was ~15 s / ~21 s before the performance work) |

The CSV itself is not part of the repository. The optimal lap figures were computed with this file, whose `Distance` was synthesised, so they are indicative.

## Architecture

```
main.py                  FastAPI app: core endpoints, CORS, logging, upload limit (413), error mapping
src/
  api/                   Routers: files.py (upload once), library.py, optimal_lap.py, setups.py
  data/                  circuits.json (known circuits and corner names)
  db/                    SQLAlchemy models and engine (SQLite / PostgreSQL)
  io/                    loaders.py (CSV, aliases, units, distance synthesis), ibt_loader.py, ld_loader.py,
                         native_common.py (experimental native formats), session_cache.py (upload store + LRU cache), exporters.py (text report),
                         pdf_exporter.py, pdf_charts.py (PDF report)
  processing/            alignment.py (distance alignment), filters.py (signal filters)
  telemetry/             lap_comparator.py, metrics.py, session_analyzer.py
  analytics/             Advanced modules (see table below)
  i18n.py, locales/      Backend translations: en.json, es.json and locales/extra/*.json
  visualization/         (empty package)
alembic/, alembic.ini    Database migrations (library tables)
frontend/                React 19 + Vite + Recharts (see frontend/README.md)
Dockerfile, docker/      Backend image and entrypoint; frontend/Dockerfile + nginx.conf for the UI
docker-compose.yml       backend + frontend + postgres (+ docker-compose.override.example.yml)
k8s/                     Kustomize: base/ and overlays/local, overlays/prod
scripts/                 kind-up.sh/.ps1, kind-cluster.yaml, validate_k8s.py, dev.ps1, check_contrast.py,
                         profile_pipeline.py, make_fixtures.py, generate_sample_data.py, docs/ (image generators)
Makefile                 env, up, down, logs, ps, build, test, lint, k8s-validate, kind-up, kind-down
tests/                   pytest suite (514 collected: 491 run by default, 23 e2e skipped without E2E=1), fixtures/, e2e/
data/                    laptime_history.db (ML history) and motorsport.db (library), both created on demand and git-ignored
docs/                    User guides, deployment guide and scientific documentation (EN/ES)
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
| `tyre_degradation.py` | Tyre degradation prediction, wear-tracking detection | [15](docs/15_tyre_degradation.md) |
| `racing_line_rl.py` | Racing-line optimisation | [16](docs/16_racing_line_rl.md) |
| `setup_advisor.py` | Setup recommendations (lap comparison and session) | [17](docs/17_setup_advisor.md) |
| `session_corner_analysis.py` | Corner statistics across all laps of a session | [08](docs/08_stint_analysis.md) |
| `session_telemetry_analysis.py` | Session-level tyre, brake, suspension, inputs and balance aggregates | [08](docs/08_stint_analysis.md) |
| `circuits.py` | Known circuits, corner names, `circuit` object | this README |
| `optimal_lap.py` | Optimal lap by microsectors (theoretical and realistic) | this README |
| `ac_setups.py` | Assetto Corsa setup lookup, parsing and "current -> suggested" linking | this README |
| `data_quality.py` | Data-quality score, channels, modules, how to improve | this README |
| `session_compare.py` | Comparison of two saved sessions | this README |

## API

There are 26 endpoints (13 analysis and reports, 5 setups, 8 library), listed below. Base URL: `http://localhost:8000` (with Docker or kind, the same paths under `/api` on the UI origin: `http://localhost:8080` or `http://localhost:8088`). Interactive documentation: `/docs` (Swagger). POST endpoints that receive files take `multipart/form-data`; the others take JSON. Add `?lang=es` or `?lang=en` (otherwise `Accept-Language` is used) to choose the language of messages and reports. Errors: `400` for unreadable or invalid files, `404` for unknown library sessions, `413` for uploads above `MAX_UPLOAD_MB` (or library payloads above 5 MB), `422` for invalid selections (lap out of range, same lap twice, fewer than 3 laps for stint), `500` for internal errors; the body is `{"detail": "..."}`.

### Analysis and reports

| Endpoint | Method | Input | Returns |
|---|---|---|---|
| `/api/health` | GET | none | `{status, service, version}` |
| `/api/files` | POST | `file`: CSV, `.ibt` or `.ld` | `{file_id, filename, size_bytes, format, venue, vehicle, driver, ttl_hours}`; `413` above `MAX_UPLOAD_MB`, `400` if empty |
| `/api/files/{file_id}` | GET | SHA-256 id | `{file_id, filename, size_bytes}`, or `410` if the client must upload again |
| `/api/analyze-session` | POST | `session_file` or `file_id` | JSON with `laps` (time, pit/outlier flags), `fastest_lap`, `track_map`, `total_laps`, `circuit`, `data_quality`. If no laps can be segmented, empty `laps` and a `message`. |
| `/api/stint/analyze` | POST | `laps`: one session file, or 3 or more single-lap files; or `file_id` of a session | `laps`, `degradacion`, `combustible`, `montecarlo`, `curvas_sesion`, `telemetria_sesion`, `setup_sesion`, `thermal_analysis`, `degradacion_neumatico`, `racing_line_rl`, `track_evolution`, `health_summary`, `data_quality` |
| `/api/optimal-lap` | POST | `session_file` or `file_id`; optional `microsector_m` (default 25), `speed_tol_kmh` (default 3) | Theoretical and realistic optimal lap, gains, microsectors, zones, corners, contributions, warnings (see "Optimal lap") |
| `/api/compare-laps` | POST | `lap_a`, `lap_b` | Basic comparison: `summary`, speed/brake/throttle comparisons, `time_delta_series`, `corners`, `track_map`, `metadata`, `text_report`, `setup_advisor` and the advanced module results when available |
| `/api/telemetry/analyze` | POST | `lap_fast`, `lap_slow` (or `lap_fast_id`, `lap_slow_id`); query `resolution_m` (default 5) | Advanced pipeline: `telemetria`, `curvatura`, `apexes`, `sectores`, `corners`, `gg_diagram`, `g_limit`, `dynamic_events`, `anomaly`, `corner_clusters`, `tiempo_potencial`, `xgboost_pred`, tyre/brake/inputs/suspension/slip results, `data_quality` |
| `/api/telemetry/compare` | POST | `lap_fast`, `lap_slow`; query `resolution_m` | Geometry and time-delta subset: `metadata`, `telemetria`, `curvatura`, `apexes`, `sectores`, `corners` |
| `/api/compare-session-laps` | POST | `session_file` or `file_id`, `lap_a`, `lap_b` (1-based; `0` = auto: fastest and slowest flying lap) | Full comparison of two laps of a session; `metadata` includes `distance_synthetic`; also `health_summary`, `data_quality` |
| `/api/report/pdf` | POST | `session_file`, `lap_a`, `lap_b` | `application/pdf` attachment `report_V{a}_vs_V{b}.pdf` |
| `/api/report/pdf-from-json` | POST | JSON: a comparison result already computed | `application/pdf` attachment, no recomputation |
| `/api/report/session-pdf-from-json` | POST | JSON: `{session, stint, comparison, metadata}` (`session` with `laps` required; others optional) | Session PDF `motorsport_<circuit>_<car>_<date>.pdf`, no recomputation |

### Assetto Corsa setups (`/api/setups`)

| Endpoint | Method | Input | Returns |
|---|---|---|---|
| `/api/setups/detect` | POST | `header`: first bytes of the telemetry file (max 64 KB), or `file_id` | Vehicle, venue and driver read from the MoTeC header |
| `/api/setups/candidates` | GET | query `vehicle`, `venue`, `lang` | Candidate setups: `track_setups`, `generic_last`, `state` (`track_setups`, `generic_only`, `none`, `no_access`), `needs_confirmation` |
| `/api/setups/file` | GET | query `vehicle`, `setup_id`, `venue`, `lang` | Parsed setup (by identifier from `candidates`, never by raw path) |
| `/api/setups/parse` | POST | `file`: a setup `.ini` (max 256 KB); query `vehicle` | Parsed uploaded setup |
| `/api/setups/annotate` | POST | JSON `{setup, recommendations}` (max 500 recommendations) | Recommendations annotated with current and suggested values |

### Session library (`/api/library`)

| Endpoint | Method | Input | Returns |
|---|---|---|---|
| `/api/library` | POST | JSON: metadata (`title`, `vehicle`, `venue`, `driver`, `notes`, `file_sha256`, ...) and `payload` `{session, stint, extras}` (max 5 MB) | `{status: created or updated, duplicate, session}` |
| `/api/library` | GET | query `q`, `venue`, `vehicle`, `date_from`, `date_to`, `limit` (1-200), `offset` | `{items, total, limit, offset}` without the heavy payload |
| `/api/library/facets` | GET | none | Circuits, cars and circuit+car combinations with counts |
| `/api/library/sniff` | POST | `head`: first KB of a CSV (max 256 KB) | Circuit, car and driver from the MoTeC header |
| `/api/library/compare` | POST | JSON `{a, b, force}` (session UUIDs) | Pace, consistency, fuel and per-corner differences, compatibility and warnings; `400` if circuit or car differ and `force` is false |
| `/api/library/{id}` | GET | UUID | Summary plus saved `payload` |
| `/api/library/{id}` | PATCH | JSON with any of `title`, `notes`, `venue`, `vehicle`, `driver` | Updated summary |
| `/api/library/{id}` | DELETE | UUID | `{status: "deleted", id}` |

Notes:

- Endpoints that read a session (`analyze-session`, `compare-session-laps`, `optimal-lap`, `stint/analyze`, `setups/detect`) accept the form field `file_id` instead of the file; `telemetry/analyze` accepts `lap_fast_id` and `lap_slow_id`. Unknown or expired ids answer `410`, malformed ones `422`.
- The UI calls `POST /api/files`, then `/api/analyze-session` then `/api/stint/analyze` for a session, `/api/optimal-lap` in the background, `/api/compare-laps` plus `/api/telemetry/analyze` for two files, `/api/compare-session-laps` for lap pairs, and the PDF endpoints for the download buttons.
- `/api/telemetry/analyze` appends an observation to the lap history (`LAPTIME_HISTORY_DB`; default `STORAGE_DIR/laptime_history.db` if `STORAGE_DIR` is set, else `./data/laptime_history.db`; the file is not versioned and is created on the first call), which feeds the historical P10 and XGBoost layers over time.
- A module that cannot run returns `{"available": false, ...}` (often with `reason`) instead of failing the whole request.

## Configuration

Copy `.env.example` to `.env` (loaded with `python-dotenv`; Docker Compose also reads it).

| Variable | Default | Effect |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000` | Comma-separated allowed origins |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TEMP_DIR` | `<project>/tmp` | Directory for temporary upload files (deleted after each request) |
| `API_HOST` / `API_PORT` / `API_RELOAD` | `0.0.0.0` / `8000` / `false` | Used only when running `python main.py` |
| `MAX_UPLOAD_MB` | `2048` | Maximum size **per uploaded file**. Enforced by the backend (HTTP 413, partial file deleted); nginx and the Ingress derive their body limit from it |
| `NATIVE_MAX_ROWS` | `2000000` | Maximum samples accepted for `.ibt` / `.ld` after resampling |
| `DATABASE_URL` | `sqlite:///data/motorsport.db` | Library database. PostgreSQL in containers: `postgresql+psycopg://user:pass@host:5432/db` |
| `STORAGE_DIR` | `./data/storage` | Optional directory for original files |
| `LAPTIME_HISTORY_DB` | `STORAGE_DIR/laptime_history.db` if `STORAGE_DIR` is set, else `./data/laptime_history.db` | SQLite lap history for the ML layers (not versioned; created on the first `/api/telemetry/analyze`) |
| `UPLOAD_DIR` | `STORAGE_DIR/uploads` if `STORAGE_DIR` is set, else `TEMP_DIR/uploads` | Where `POST /api/files` stores uploads (use a shared volume with several replicas) |
| `UPLOAD_TTL_HOURS` | `24` | Stored uploads unused for this long are deleted |
| `SESSION_CACHE_MAX_MB` | `1024` | Maximum memory of the parsed-session cache per process |
| `SESSION_CACHE_TTL_MIN` | `60` | Minutes without use before a session leaves the cache |
| `AC_SETUPS_DIR` | auto (`<Documents>\Assetto Corsa\setups`) | Explicit Assetto Corsa setups folder |
| `VITE_API_URL` | `http://localhost:8000/api` | API URL used by the frontend in dev (read by Vite at build/dev time; production containers use the relative `/api`) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `motorsport` / `change-me-local-only` / `motorsport` | Compose only. Example values for a local machine, never for production |
| `FRONTEND_PORT` / `BACKEND_DEV_PORT` | `8080` / `8010` | Compose host ports (UI; backend with `--profile dev`) |
| `UVICORN_WORKERS` | `1` | Uvicorn workers in the container (each keeps its own memory) |
| `RUN_MIGRATIONS` | `0` in the image, `1` in Compose | Run `alembic upgrade head` on container start |
| `PROXY_TIMEOUT` | `900s` | nginx proxy timeout in the frontend container |

## Development and tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q          # 514 collected: 491 run, 23 skipped (all e2e, they run with E2E=1)

cd frontend
npm run lint                       # ESLint
npm run build                      # production build into frontend/dist

make lint                          # yamllint + scripts/validate_k8s.py + frontend lint
make k8s-validate                  # static check of the Kubernetes manifests
```

Real-data regression and browser tests: `tests/fixtures/*.csv.gz` are anonymised cut-outs of real Assetto Corsa exports (rebuilt with `scripts/make_fixtures.py`, options `--imola`, `--spa`, `--lap-fast`, `--lap-slow`, `--lap-other-car`), used by `tests/test_regression_real.py`. End-to-end and visual tests (Playwright + Edge) live in `tests/e2e/` and run only with `E2E=1`; visual baselines may need regenerating with `E2E_UPDATE_BASELINE=1` on another machine. Details in [tests/README.md](tests/README.md).

Test files in `tests/`: `test_alignment.py`, `test_loaders.py`, `test_metrics.py`, `test_session_pipeline.py`, `test_optimal_lap.py`, `test_ac_setups.py`, `test_library.py`, `test_data_quality.py`, `test_pdf_report.py`, `test_formats.py`, `test_projection_realism.py`, `test_upload_limit.py`, `test_k8s_manifests.py`, `test_circuits.py`, `test_perf_cache.py`, `test_check_contrast.py`, `test_regression_real.py`, `test_visual_tool.py` (fixtures in `tests/conftest.py`). Synthetic sample laps can be generated with `python scripts/generate_sample_data.py` (writes `data/raw/lap_clean.csv` and `data/raw/lap_errors.csv`, which are git-ignored).

### Adding translated text

Backend and frontend strings live in two per-language dictionaries (`en`, `es`) that are extended **per feature module** so contributors do not edit the large core files:

- Frontend: create `frontend/src/i18n/extra/<feature>.en.js` and `<feature>.es.js` with `export default { key: 'text' }` (values can be functions, e.g. `(n) => ...`). They are loaded automatically (`import.meta.glob`) and merged into `en.js` / `es.js`.
- Backend: create `src/locales/extra/<feature>.en.json` and `<feature>.es.json` (flat key to string, with `{placeholders}`). `src/i18n.py` merges every file in that folder on first use. Use `_l(lang, key, ...)` or `_()`.

Always add both languages; keep keys unique across modules. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentation

| Audience | Document |
|---|---|
| Users | [User Guide](docs/USER_GUIDE.md), [Quick Reference](docs/QUICK_REFERENCE.md) |
| Operators | [Deployment: local, Docker, Kubernetes](docs/DEPLOYMENT.md) |
| Developers | [Docs index](docs/README.md) with the 17 scientific module documents (math, algorithms, figures), [frontend/README.md](frontend/README.md), [CONTRIBUTING.md](CONTRIBUTING.md) |
| Spanish | [README.es.md](README.es.md), [Guia de Usuario](docs/GUIA_USUARIO.es.md), [Referencia Rapida](docs/REFERENCIA_RAPIDA.es.md), [Despliegue](docs/DEPLOYMENT.es.md), [docs/README.es.md](docs/README.es.md) |

## Known limitations

- Speed-based corner detection finds fewer corners than geometry-based detection (7 vs 11 at Imola, because chicanes merge).
- Suspension bottoming is a heuristic: travel at or above 90 % of the maximum observed travel.
- Some channels may be absent depending on the simulator and export; the corresponding panels say so instead of guessing.
- CSV is the stable input. iRacing `.ibt` and MoTeC `.ld` are **experimental**: tested on 53 real files from one author, other simulators and cars are untested.
- The theoretical optimal lap grows as the microsector shrinks, and with a synthesised `Distance` the optimal lap is only indicative.
- Setup units are shown only where they are certain; encrypted car data (`data.acd`) is never opened, so ranges are missing for most cars.
- **No authentication or authorization.** The library is shared by anyone who can reach the API (the `owner_id` column is reserved for the future). Do not expose the app to the internet as is.
- Docker Compose and the kind overlay were run on one Windows machine; the HPA, PodDisruptionBudgets and NetworkPolicies are not exercised in kind and the `prod` overlay has never been applied (see [Deployment](#deployment)).
- The first build of the backend image takes more than 10 minutes and needs a stable network (pip downloads the scientific stack).
- Library payloads are limited to 5 MB; very large uploads need memory and time (the limit is per file, `MAX_UPLOAD_MB`).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: fork, branch, run `python -m pytest tests -q`, open a Pull Request against `main`. Do not commit telemetry files or secrets.

## License

[MIT](LICENSE) - Copyright (c) 2026 Andres Gutierrez.
