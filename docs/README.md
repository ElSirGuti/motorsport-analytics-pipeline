# Documentation — Motorsport Analytics Pipeline

[Ver en Español](./README.es.md)

---

## User Guides

| Document | Audience |
|----------|---------|
| [User Guide](./USER_GUIDE.md) | Pilots, engineers: how to use the app, session features (data quality, optimal lap, Assetto Corsa setups, library, PDF report, circuits, theme, comparing two single-lap files), export telemetry, read each panel, troubleshooting |
| [Quick Reference](./QUICK_REFERENCE.md) | Interpretation cheat sheet for track-side use: optimal lap, two-file compare mode, data-quality score, setup link, formats, limits and status codes |

## Project Documentation

| Document | Content |
|----------|---------|
| [Root README](../README.md) | Quick start, installation, features, formats, API table, configuration, tests, architecture |
| [Deployment](./DEPLOYMENT.md) | Local, Docker Compose and Kubernetes (Kustomize); environment contract (all variables), Windows install of Docker/kind, upload-once cache, what was verified on Docker Compose and kind and what was not, troubleshooting of the first deployment |
| [Tests](../tests/README.md) | Test suites (582 collected; 550 run by default, 32 e2e need `E2E=1`), real anonymised fixtures, two-file compare tests, end-to-end and visual tests |
| [Frontend README](../frontend/README.md) | UI structure, design system and themes, API client, i18n modules, build and lint |
| [CONTRIBUTING](../CONTRIBUTING.md) | How to contribute: workflow, translations by module, tests, no personal data |
| [LICENSE](../LICENSE) | MIT License |

---

## Feature Documentation

These features have no separate scientific document; they are described in the root README (design, limits, API) and in the User Guide (how to use them).

| Feature | Code | Documentation |
|---------|------|---------------|
| Optimal lap by microsectors | `src/analytics/optimal_lap.py`, `src/api/optimal_lap.py` | [README](../README.md#optimal-lap-by-microsectors), [User Guide](./USER_GUIDE.md#optimal-lap-by-microsectors) |
| Assetto Corsa setups | `src/analytics/ac_setups.py`, `src/api/setups.py` | [README](../README.md#assetto-corsa-setup-integration), [User Guide](./USER_GUIDE.md#assetto-corsa-setups) |
| Session library and comparison | `src/api/library.py`, `src/db/`, `src/analytics/session_compare.py`, `alembic/` | [README](../README.md#session-library-and-session-comparison), [User Guide](./USER_GUIDE.md#session-library-and-comparing-sessions) |
| Data quality | `src/analytics/data_quality.py` | [README](../README.md#data-quality-panel), [User Guide](./USER_GUIDE.md#data-quality-panel) |
| PDF report | `src/io/pdf_exporter.py`, `src/io/pdf_charts.py` | [README](../README.md#pdf-report), [User Guide](./USER_GUIDE.md#pdf-report) |
| `.ibt` and `.ld` formats (experimental) | `src/io/ibt_loader.py`, `ld_loader.py`, `native_common.py` | [README](../README.md#telemetry-formats), [User Guide](./USER_GUIDE.md#supported-formats) |
| Known circuits and corner names | `src/data/circuits.json`, `src/analytics/circuits.py` | [README](../README.md#known-circuits-and-corner-names), [User Guide](./USER_GUIDE.md#known-circuits-and-corner-names) |
| Themes | `frontend/src/styles/theme-light.css`, `scripts/check_contrast.py` | [README](../README.md#themes), [Frontend README](../frontend/README.md#design-system-and-themes) |
| Upload once and cache | `src/api/files.py`, `src/io/session_cache.py`, `scripts/profile_pipeline.py` | [README](../README.md#performance-and-upload-once), [Deployment](./DEPLOYMENT.md#upload-once-file_id-and-the-analysis-cache) |
| Realistic projections | `src/analytics/stint.py`, `tyre_degradation.py` | [README](../README.md#realistic-projections), modules [08](./08_stint_analysis.md) and [15](./15_tyre_degradation.md) |

---

## Technical Reference

Scientific documentation for all analysis modules. Each section covers the mathematical foundations, implemented algorithm, result interpretation, and generated visualizations.

---

## Modules

| # | Module | Description |
|---|--------|-------------|
| 01 | [Track Geometry](./01_geometry.md) | Savitzky-Golay filter, geometric curvature κ, apex detection |
| 02 | [Time Delta](./02_time_delta.md) | Cubic interpolation, distance-based alignment, RDP compression |
| 03 | [GG Diagram](./03_gg_diagram.md) | Friction circle, G-efficiency, kinematic G estimation |
| 04 | [Vehicle Dynamics](./04_dynamics.md) | Understeer / oversteer, three severity levels |
| 05 | [Anomaly Detection](./05_anomaly_detection.md) | Isolation Forest, multivariable scoring, zone extraction |
| 06 | [Style Clustering](./06_clustering.md) | K-Means, driving profiles, per-corner heat map |
| 07 | [Lap Time Potential](./07_lap_time_potential.md) | Reachable Lap P10, consistency, XGBoost with explanations |
| 08 | [Stint Analysis](./08_stint_analysis.md) | Linear degradation, fuel strategy, Monte Carlo |
| 09 | [Tyre Temperature](./09_thermodynamics.md) | Optimal thermal window, surface-to-core ΔT gradient, thermal stress |
| 10 | [Brake Fade](./10_brake_fade.md) | Efficiency \|LonG\|/pressure, fade detection by zone and baseline |
| 11 | [Driver Inputs](./11_driver_inputs.md) | Welch PSD on SteerAngle, nervousness index, brake-throttle overlap |
| 12 | [Suspension](./12_suspension.md) | Pitch and roll from SuspTravel FL/FR/RL/RR, bottoming detection |
| 13 | [Slip Angle](./13_slip_angle.md) | Kinematic sideslip β, αF/αR bicycle model, track balance |
| 14 | [Thermal Management](./14_thermal_management.md) | Fluid, brake and tyre-pressure thermal analysis with rule-based recommendations |
| 15 | [Tyre Degradation](./15_tyre_degradation.md) | Fuel-corrected tyre degradation rate, wear-tracking detection, cliff projection |
| 16 | [Racing Line Optimization (RL)](./16_racing_line_rl.md) | Per-corner tabular Q-learning over brake / apex / throttle execution bins |
| 17 | [Vehicle Setup Advisor](./17_setup_advisor.md) | Rule-based setup recommendations (lap and session) and Assetto Corsa setup linkage |
| 18 | [Incidents](./18_incidents.md) | Spin, saved-slide and off-track detection with a scored probable cause and advice |

---

## Regenerating Images

Images are generated by the scripts in `scripts/docs/`. To regenerate them:

```bash
python scripts/docs/gen_geometry.py
python scripts/docs/gen_time_delta.py
python scripts/docs/gen_gg_diagram.py
python scripts/docs/gen_dynamics.py
python scripts/docs/gen_anomaly.py
python scripts/docs/gen_clustering.py
python scripts/docs/gen_laptime.py
python scripts/docs/gen_stint.py
python scripts/docs/gen_thermodynamics.py
python scripts/docs/gen_brake_fade.py
python scripts/docs/gen_driver_inputs.py
python scripts/docs/gen_suspension.py
python scripts/docs/gen_slip_angle.py
```

Each script writes output to `docs/images/{module}/`. Modules 14-17 (thermal management, tyre degradation, racing line, setup advisor) have no image generator. The scientific documents 01-17 describe the algorithms as originally written; where the current behaviour differs (for example the more conservative stint projections), the root README is authoritative.

Run the scripts from the project root with the dependencies from `requirements.txt` installed.

---

## Conventions

- **Bold variables**: configurable parameters in the source code
- Equations written in inline LaTeX notation: `$κ = ...$`
- Empirical thresholds justified with a bibliographic reference where applicable
- Reproducible Python code with a fixed `numpy.random.seed` wherever simulations are used

---

*Also available in [Español](./README.es.md)*
