# Frontend - Motorsport Analytics

React 19 + Vite single-page app for the Motorsport Analytics API. It renders the "pit wall" workstation: upload telemetry, run the analysis and explore results with synchronised charts. [Resumen en español al final](#resumen-en-español).

## Contents

- [Requirements and commands](#requirements-and-commands)
- [Configuration](#configuration)
- [Stack](#stack)
- [UI structure](#ui-structure)
- [Design system](#design-system)
- [Source layout](#source-layout)
- [API client](#api-client)
- [State, i18n and persistence](#state-i18n-and-persistence)
- [Docker](#docker)

## Requirements and commands

Node.js 18+ (the Docker image uses Node 20) and the backend running on port 8000 (see the [root README](../README.md)).

```bash
npm install        # install dependencies
npm run dev        # Vite dev server on http://localhost:5173 (HMR)
npm run lint       # ESLint (flat config in eslint.config.js: recommended + react-hooks + react-refresh)
npm run build      # production build into dist/
npm run preview    # serve the production build locally
```

There is no frontend test suite; backend tests live in `../tests` (`python -m pytest tests -q`).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL of the API (read in `src/api/telemetry.js`). Set it in `frontend/.env` or in the environment before `npm run dev` / `npm run build`. It is baked into the bundle at build time. |

The backend must list the frontend origin in `CORS_ORIGINS` (the defaults already include `localhost:5173` and `localhost:3000`).

## Stack

React 19, Vite 5 (`@vitejs/plugin-react`), Recharts 3 for charts, axios for HTTP, react-dropzone (used only by the unmounted `FileUploader`), plain CSS (global CSS files plus CSS modules). No router and no global state library: `src/App.jsx` holds the application state with React hooks.

## UI structure

- **Top bar:** brand, language switch (ES/EN) and Pilot/Engineer mode toggle (`PilotEngineerToggle`).
- **Upload area:** accepts `.csv` files only. The mode is derived from the number of files: **1 CSV = full session** (segmented into laps by the backend) and **2 CSVs = two single laps compared**. A step progress bar is shown while analysing; once finished, the upload area collapses into a file bar with a **New analysis** button.
- **Side rail** (`Sidebar`, sections defined in `components/navSections.js`):
  - Session: Session overview, Stint analysis, Setup & strategy.
  - Comparison: Core lap, Vehicle dynamics, Driver & inputs, Strategy & setup.
- **Pilot mode** hides the technical sections (`PILOT_HIDDEN` in `navSections.js`: vehicle dynamics and driver & inputs).
- **Lap table** (session mode): select two laps (A/B) and press **Compare**, or **Best vs Worst**. Pit laps (`PIT`) and outlier laps are badged. Comparing calls `/compare-session-laps`.
- **Health panel** (`HealthDashboard`): shows `health_summary` from the API (thermal, setup, tyre degradation, racing line, slip, corners: `ok` or `unavailable`, plus an `overall` level).
- **Report actions:** copy the text report to the clipboard, or download the PDF (the already computed result is posted to `/report/pdf-from-json`).
- **Synchronised cursor:** hovering a chart moves the cursor on all the others.

## Design system

- `src/styles/design-system.css` - "Pit Wall" tokens: graphite surfaces (`--surface-0..3`), text (`--ink-1..4`), one blue accent (`--accent`), semantic status colours (`--ok`, `--warn`, `--bad`) and a lap series palette (`--lap-a..f`). It loads after `index.css` and redefines the legacy variable names, so unmigrated rules inherit the new palette. New code should use the semantic tokens.
- `src/styles/shell.css` - layout of the application shell (top bar, side rail, content).
- `src/components/ui/` - shared primitives, exported from `ui/index.js`:

| Component | Use |
|---|---|
| `Panel` | Standard card with header (icon, title, subtitle, actions) and body |
| `Stat` | KPI: label, large tabular value, optional hint; `tone`: `ok`, `warn`, `bad`, `accent` |
| `Badge` | Small status label; `tone`: `accent`, `ok`, `warn`, `bad` |
| `Icon` | Inline icon by name (`grid`, `trend`, `wrench`, `stopwatch`, `gauge`, `steering`, `flag`, ...) |
| `EmptyState` | Placeholder for panels with no data |

## Source layout

```
src/
  main.jsx, App.jsx           Entry point and application shell (state, upload flow, layout)
  App.css, index.css          Legacy global styles
  styles/                     design-system.css, shell.css
  api/
    telemetry.js              axios client and endpoint wrappers
    cursorStore.js            Module-level cursor position (no React re-renders)
  hooks/useCursorWriter.js    Writes the hovered distance into the cursor store from chart mouse events
  context/LanguageContext.js  Language provider (ES/EN)
  i18n/en.js, es.js           UI strings
  components/
    ui/                       Panel, Stat, Badge, Icon, EmptyState
    Sidebar.jsx, navSections.js, PilotEngineerToggle.jsx, usePilotMode.js
    HealthDashboard.jsx       API health_summary
    Lap comparison:  SpeedChart, BrakeThrottleChart, TimeDeltaChart, TrackMap, CurvatureMap,
                     SectorTable, SummaryCard, CornerReport, CornerAnalysisPanel,
                     GGDiagramChart, AnomalyReport, PotentialLapCard
    Vehicle/driver:  TyreHeatmap, BrakeFadeChart, DriverInputsChart, SuspensionChart, SlipAngleChart
    Session/stint:   LapTimelineChart, PitWindowWidget, TyreDegradationPanel, ThermalManagementPanel,
                     RacingLinePanel, SetupRecommendations
    Helpers:         chartKit.jsx, chartTheme.js, analysisKit.jsx, InfoButton.jsx (+ CSS modules)
    Not mounted by App.jsx (older tab-based UI): SessionTab, StintPanel, AdvancedComparePanel, FileUploader
```

## API client

`src/api/telemetry.js` creates an axios instance on `VITE_API_URL` with a 10-minute timeout (large session files) and sends the UI language as the `lang` query parameter. Wrappers:

| Function | Endpoint |
|---|---|
| `analyzeSession(file)` | `POST /analyze-session` |
| `analyzeStint(files)` | `POST /stint/analyze` |
| `compareLaps(a, b)` | `POST /compare-laps` |
| `analyzeTelemetry(fast, slow, resolutionM)` | `POST /telemetry/analyze` |
| `compareAdvanced(fast, slow, resolutionM)` | `POST /telemetry/compare` |
| `compareSessionLaps(file, lapA, lapB)` | `POST /compare-session-laps` (`0, 0` = best vs worst) |
| `downloadPdfReport(result)` | `POST /report/pdf-from-json` (blob) |

In session mode the app calls `analyzeSession` and then `analyzeStint` sequentially to avoid a memory spike with very large files. In two-file mode it calls `compareLaps` and `analyzeTelemetry` in parallel and merges the results. Server error messages (`detail`) are shown to the user.

## State, i18n and persistence

- All analysis state lives in `App.jsx` (`useState`); there is no router.
- UI strings are in `src/i18n/en.js` and `es.js`, read through `LanguageContext`.
- Persisted in `localStorage` (wrapped in try/catch): `lang` (language) and `motorsport_view_mode` (`pilot` or `engineer`).
- The synchronised cursor uses a module store (`api/cursorStore.js`) read by components outside React state (e.g. the track map marker via `requestAnimationFrame`), so moving the mouse does not re-render React components.

## Docker

`Dockerfile` builds with `node:20-alpine` (`npm ci && npm run build`) and serves `dist/` with nginx (`nginx.conf`: SPA fallback to `index.html`, long cache for static assets, gzip). The container listens on port 80; `../docker-compose.yml` maps it to host port 5173.

## Resumen en español

Aplicación React 19 + Vite que consume la API del backend (`VITE_API_URL`, por defecto `http://localhost:8000/api`).

- Comandos: `npm install`, `npm run dev` (http://localhost:5173), `npm run lint`, `npm run build`, `npm run preview`.
- Interfaz tipo "pit wall": barra superior (marca, idioma ES/EN, modo Piloto/Ingeniero), carga de CSV con detección de modo (1 CSV = sesión completa segmentada automáticamente; 2 CSV = comparación de dos vueltas), barra de progreso por pasos y, tras analizar, barra de archivo con "Nuevo análisis".
- Riel lateral: Resumen de sesión, Análisis de stint, Setup y estrategia (sesión); Vuelta base, Dinámica del vehículo, Piloto y entradas, Estrategia y setup (comparación). El modo Piloto oculta los paneles técnicos.
- Tabla de vueltas: elige dos vueltas (A/B) y pulsa "Comparar", o "Mejor vs Peor"; las vueltas de pit y atípicas aparecen marcadas. El panel de salud muestra qué módulos tienen datos.
- Sistema de diseño en `src/styles/design-system.css` y componentes base en `src/components/ui/` (`Panel`, `Stat`, `Badge`, `Icon`, `EmptyState`).
- El idioma y el modo de vista se guardan en `localStorage`. No hay tests de frontend; los tests del backend están en `../tests`.
