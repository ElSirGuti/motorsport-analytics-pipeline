# Frontend - Motorsport Analytics

React 19 + Vite single-page app for the Motorsport Analytics API. It renders the "pit wall" workstation: upload telemetry, run the analysis and explore results with synchronised charts. [Resumen en español al final](#resumen-en-español).

## Contents

- [Requirements and commands](#requirements-and-commands)
- [Configuration](#configuration)
- [Stack](#stack)
- [UI structure](#ui-structure)
- [Design system and themes](#design-system-and-themes)
- [Source layout](#source-layout)
- [API client](#api-client)
- [State, i18n and persistence](#state-i18n-and-persistence)
- [Adding translated text](#adding-translated-text)
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

There is no unit-test suite for the frontend. Backend tests live in `../tests` (`python -m pytest tests -q`); the browser end-to-end and visual tests (Playwright + Edge, `E2E=1`) are in `../tests/e2e` and exercise this UI (see [../tests/README.md](../tests/README.md)).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api` | Base URL of the API (read in `src/api/telemetry.js`). Set it in `frontend/.env` or in the environment before `npm run dev` / `npm run build`. It is baked into the bundle at build time. |

The backend must list the frontend origin in `CORS_ORIGINS` (the defaults already include `localhost:5173` and `localhost:3000`).

## Stack

React 19, Vite 5 (`@vitejs/plugin-react`), Recharts 3 for charts, axios for HTTP, react-dropzone (used only by the unmounted `FileUploader`), plain CSS (global CSS files plus CSS modules). No router and no global state library: `src/App.jsx` holds the application state with React hooks.

## UI structure

- **Top bar:** brand, view switch (**Analysis / Library / Compare sessions**), language switch (ES/EN), theme selector (`ThemeSwitch`: system, light, dark) and Pilot/Engineer mode toggle (`PilotEngineerToggle`).
- **Upload area:** accepts `.csv`, `.ibt` and `.ld` (`src/utils/formats.js`; `.ibt` and `.ld` carry an **Experimental** badge, `FormatBadge`). The mode is derived from the number of files: **1 file = full session** (segmented into laps by the backend) and **2 files = two single laps compared**. The file is uploaded once (`POST /files`); a stage progress component (`PerfProgress`) shows upload, session, stint and optimal lap, and results are rendered as each stage finishes. Once finished, the upload area collapses into a file bar with **New analysis**, **Save to library** (`SaveToLibrary`, with an optional automatic save) and **Download report**.
- **Data-quality panel** (`DataQualityPanel`): shown first; score, channels, laps, modules and how to improve.
- **Circuit badge** (`CircuitBadge`): recognised circuit and its confidence; corner labels come from `utils/cornerLabel.js` ("Corner 4 - Tamburello" when the backend sends a `corner_name`).
- **Side rail** (`Sidebar`, sections defined in `components/navSections.js`):
  - Session: Session overview, Stint analysis, Setup & strategy.
  - Comparison: Core lap, Vehicle dynamics, Driver & inputs, Strategy & setup.
- **Pilot mode** hides the technical sections (`PILOT_HIDDEN` in `navSections.js`: vehicle dynamics and driver & inputs).
- **Lap table** (session mode): select two laps (A/B) and press **Compare**, or **Best vs Worst**. Pit laps (`PIT`) and outlier laps are badged. Comparing calls `/compare-session-laps`.
- **Health panel** (`HealthDashboard`): shows `health_summary` from the API (thermal, setup, tyre degradation, racing line, slip, corners: `ok` or `unavailable`, plus an `overall` level).
- **Optimal lap** (`OptimalLapPanel`, session overview): theoretical and realistic optimal lap, microsector size selector (10/25/50/100 m), gain charts, track map of where time is lost, zones, corners and contributing laps; it is fetched in the background (`prefetchOptimalLap`).
- **Setup used** (`SetupSelector`, `SetupLink`, `SetupSection`): finds the Assetto Corsa setup (`/setups/*`), lets you pick or upload the `.ini` and shows **Current -> Suggested** in the recommendations. The choice is remembered per car and track in `localStorage` (`acSetup:<car>|<track>`).
- **Library views** (`components/library/`): `LibraryView` (search, filters, pagination, open, rename, delete), `CompareSessionsView` (two sessions of the same circuit and car), `SaveToLibrary`.
- **Report actions:** copy the text report to the clipboard, or download the PDF: the already computed result is posted to `/report/pdf-from-json` (comparison) or `/report/session-pdf-from-json` (session and stint, `downloadSessionPdfReport`).
- **Synchronised cursor:** hovering a chart moves the cursor on all the others.

## Design system and themes

- `src/styles/design-system.css` - "Pit Wall" tokens: graphite surfaces (`--surface-0..3`), text (`--ink-1..4`), one blue accent (`--accent`), semantic status colours (`--ok`, `--warn`, `--bad`) and a lap series palette (`--lap-a..f`). It loads after `index.css` and redefines the legacy variable names, so unmigrated rules inherit the new palette. New code should use the semantic tokens.
- `src/styles/theme-light.css` - light theme: redefines the same tokens under `[data-theme="light"]`. `src/hooks/useTheme.js` keeps the preference (`system`, `light`, `dark`; `localStorage` key `ma-theme`), applies `data-theme` on `<html>` and follows the OS setting; `index.html` applies it before the first paint. `python ../scripts/check_contrast.py` verifies WCAG contrast: the light theme passes every pair, the dark theme has 10 pairs below AA documented as known debt.
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
  styles/                     design-system.css (dark tokens), theme-light.css, shell.css
  utils/                      formats.js (accepted extensions), cornerLabel.js (corner and country labels)
  api/
    telemetry.js              axios client and endpoint wrappers (analysis, PDF)
    files.js                  upload once (`ensureFileId`, `withFile`: 410 -> re-upload and retry once)
    optimalLap.js, setups.js, library.js   wrappers for /optimal-lap, /setups/*, /library*
    cursorStore.js            Module-level cursor position (no React re-renders)
  hooks/                      useCursorWriter.js (hovered distance into the cursor store), useTheme.js, useThemeColors.js
  context/LanguageContext.js  Language provider (ES/EN)
  i18n/en.js, es.js           Core UI strings; i18n/extra/<feature>.en.js / .es.js are merged automatically
  components/
    ui/                       Panel, Stat, Badge, Icon, EmptyState
    Sidebar.jsx, navSections.js, PilotEngineerToggle.jsx, usePilotMode.js
    HealthDashboard.jsx, DataQualityPanel.jsx, CircuitBadge.jsx, FormatBadge.jsx, PerfProgress.jsx, ThemeSwitch.jsx
    OptimalLapPanel.jsx       Optimal lap by microsectors
    SetupSelector.jsx, SetupLink.jsx, SetupSection.jsx   Assetto Corsa setup integration
    library/                  LibraryView, CompareSessionsView, SaveToLibrary
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

`src/api/telemetry.js` creates an axios instance on `VITE_API_URL` with a 10-minute timeout (large session files) and sends the UI language as the `lang` query parameter. `src/api/files.js` uploads a file once (`POST /files`) and caches its `file_id` by name, size and date; the session wrappers send that `file_id` instead of the file, and on **HTTP 410** (the server no longer has the file) they upload again and retry once. Wrappers:

| Function | Endpoint |
|---|---|
| `ensureFileId(file)` | `POST /files` |
| `analyzeSession(file)` | `POST /analyze-session` (with `file_id`) |
| `analyzeStint(files)` | `POST /stint/analyze` (with `file_id` for one session file) |
| `analyzeOptimalLap(file)` / `prefetchOptimalLap(file)` | `POST /optimal-lap` |
| `compareLaps(a, b)` | `POST /compare-laps` |
| `analyzeTelemetry(fast, slow, resolutionM)` | `POST /telemetry/analyze` |
| `compareAdvanced(fast, slow, resolutionM)` | `POST /telemetry/compare` |
| `compareSessionLaps(file, lapA, lapB)` | `POST /compare-session-laps` (`0, 0` = best vs worst) |
| `downloadPdfReport(result)` | `POST /report/pdf-from-json` (blob) |
| `downloadSessionPdfReport({session, stint, comparison, metadata})` | `POST /report/session-pdf-from-json` (blob) |
| `detectSessionMeta`, `fetchSetupCandidates`, `fetchSetupById`, `uploadSetup`, `annotateRecommendations` | `/setups/detect`, `/candidates`, `/file`, `/parse`, `/annotate` |
| `saveToLibrary`, `listLibrary`, `getLibrarySession`, `patchLibrarySession`, `deleteLibrarySession`, `libraryFacets`, `compareLibrarySessions`, `sniffMetadata` | `/library*` |

In session mode the app uploads the file once and then runs `analyzeSession`, `analyzeStint` and the optimal lap as separate stages, showing each result as soon as it arrives (the stages share the backend's in-memory cache of the parsed file). In two-file mode it calls `compareLaps` and `analyzeTelemetry` in parallel and merges the results. Server error messages (`detail`) are shown to the user.

## State, i18n and persistence

- All analysis state lives in `App.jsx` (`useState`); there is no router.
- UI strings are in `src/i18n/en.js` and `es.js`, read through `LanguageContext`.
- Persisted in `localStorage` (always wrapped in try/catch, the UI works without it): `lang` (language), `motorsport_view_mode` (`pilot` or `engineer`), `ma-theme` (`system`, `light`, `dark`), `library.autosave` (`1`/`0`) and `acSetup:<car>|<track>` (remembered Assetto Corsa setup).
- The synchronised cursor uses a module store (`api/cursorStore.js`) read by components outside React state (e.g. the track map marker via `requestAnimationFrame`), so moving the mouse does not re-render React components.

## Adding translated text

The core dictionaries are `src/i18n/en.js` and `es.js`. New features add their strings in `src/i18n/extra/<feature>.en.js` and `<feature>.es.js` (`export default { key: 'text' }`; values can be functions such as `(n) => ...`). `en.js` and `es.js` load every `extra/*.<lang>.js` through `import.meta.glob` and merge them, so adding a module needs no change to the core files. Provide both languages and keep keys unique across modules. Existing modules: `circuits`, `data_quality`, `formats`, `library`, `optimalLap`, `pdf`, `perf`, `setups`, `theme`. The backend equivalent is `src/locales/extra/*.json` (see [CONTRIBUTING.md](../CONTRIBUTING.md)).

## Docker

`Dockerfile` builds with `node:20-alpine` (`npm ci && npm run build`) and serves `dist/` with nginx (`nginx.conf`: SPA fallback to `index.html`, long cache for static assets, gzip, proxy to the backend). The image is based on unprivileged nginx and listens on port 8080 (health check at `/healthz`); it proxies `/api` to the backend, so production builds use the relative `/api`. `../docker-compose.yml` publishes it on `FRONTEND_PORT` (default 8080). Docker images were not built on the author's machine; see [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).

## Resumen en español

Aplicación React 19 + Vite que consume la API del backend (`VITE_API_URL`, por defecto `http://localhost:8000/api`).

- Comandos: `npm install`, `npm run dev` (http://localhost:5173), `npm run lint`, `npm run build`, `npm run preview`.
- Interfaz tipo "pit wall": barra superior (marca, idioma ES/EN, modo Piloto/Ingeniero), selector de tema (sistema, claro, oscuro), vistas Análisis / Biblioteca / Comparar sesiones, carga de `.csv`, `.ibt` y `.ld` (los dos últimos experimentales) con detección de modo (1 archivo = sesión completa segmentada automáticamente; 2 archivos = comparación de dos vueltas), subida única con barra de progreso por etapas y resultados progresivos y, tras analizar, barra de archivo con "Nuevo análisis", "Guardar en biblioteca" y "Descargar informe".
- Riel lateral: Resumen de sesión, Análisis de stint, Setup y estrategia (sesión); Vuelta base, Dinámica del vehículo, Piloto y entradas, Estrategia y setup (comparación). El modo Piloto oculta los paneles técnicos.
- Tabla de vueltas: elige dos vueltas (A/B) y pulsa "Comparar", o "Mejor vs Peor"; las vueltas de pit y atípicas aparecen marcadas. El panel de salud y el panel de calidad de datos muestran qué módulos tienen datos. También hay vuelta óptima por microsectores, enlace con los setups de Assetto Corsa (Actual -> Sugerido) y nombres de curva en circuitos conocidos.
- Sistema de diseño en `src/styles/design-system.css` y componentes base en `src/components/ui/` (`Panel`, `Stat`, `Badge`, `Icon`, `EmptyState`).
- Textos traducidos: añade `src/i18n/extra/<modulo>.en.js` y `<modulo>.es.js`; se cargan solos con `import.meta.glob`.
- El idioma, el modo de vista, el tema, el autoguardado de la biblioteca y el setup recordado se guardan en `localStorage`. No hay tests unitarios de frontend; los tests del backend están en `../tests` y los e2e de navegador (`E2E=1`) en `../tests/e2e`.
