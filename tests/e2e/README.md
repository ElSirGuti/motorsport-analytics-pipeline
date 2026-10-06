# End-to-end and visual tests (Playwright + Edge)

Skipped unless `E2E=1`; plain `pytest` never starts a server or a browser.

`conftest.py` starts, per session, the FastAPI backend (uvicorn) and Vite on **free dynamic
ports** with the right `CORS_ORIGINS`, an isolated SQLite library (`DATABASE_URL` to a temp
file) and always kills both process trees (also if a test fails).

## Requirements

* `pip install playwright pillow` (Edge is driven through `channel="msedge"`, no browser download).
* Microsoft Edge installed, Node.js on PATH and `npm ci` done in `frontend/`.
* The fixtures in `tests/fixtures/`.

## Run

PowerShell:

```powershell
$env:E2E = "1"; python -m pytest tests/e2e -q
Remove-Item Env:E2E
```

bash:

```bash
E2E=1 python -m pytest tests/e2e -q
```

## What is covered

`test_e2e_flows.py`: smoke (upload -> analyze -> sections, data-quality panel, optimal lap, 5-lap table, no console
errors), 2-lap comparison from a session, two-file compare mode with the single-lap fixtures `rbr_fast`/`rbr_slow` (same car, no vehicle warning) and `rbr_fast`/`rbr_other_car` (different cars, warning shown), in both languages, ES/EN switch without reload, automatic sweep for leftover English in the Spanish UI
(stop-word heuristic with an allow-list for technical terms such as Monte Carlo, P10, Setup, Brake bias; set
`E2E_LANG_VERBOSE=1` to print near misses), Pilot mode hiding technical sections, library save -> list -> open ->
delete, empty CSV (visible, translated error), basic accessibility (alt text, accessible names, visible focus
in the top bar).
Selectors use roles, stable ids (`#section-*`, `#data-quality`, `#optimal-lap`) and UI strings read from
`frontend/src/i18n` by key, so copy changes do not break them.

`test_e2e_theme.py`: theme switch (system/light/dark) keeps the analysis state and persists.

`test_e2e_visual.py`: screenshots at 1440x900 (light theme, reduced motion) compared with PIL against
`baseline/*.png`: a pixel counts as different when any channel differs by more than 24/255, and the test fails above
1.5 % different pixels. Dynamic zones (library dates) are masked. On failure `_artifacts/` (git-ignored) receives
`*.actual.png`, `*.baseline.png` and `*.diff.png`.

32 e2e tests in total. With `E2E=1` they run; without it they are skipped.

## Baselines

```powershell
$env:E2E = "1"; $env:E2E_UPDATE_BASELINE = "1"; python -m pytest tests/e2e -k visual
```

> **Warning:** the baselines depend on fonts, the renderer (Edge/Chromium version, OS text
> rendering) and the current UI. They were generated on Windows 11 + Edge 154 and may need regenerating on
> another machine or after intentional UI changes (review the diff images before committing new ones).
