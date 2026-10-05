# Tests

| Suite | Files | Needs |
|---|---|---|
| Unit / API (synthetic data) | `test_*.py` | `pip install -r requirements-dev.txt` |
| Regression on real fixtures | `test_regression_real.py`, `fixtures/` | same (PDF checks need `pymupdf`) |
| End-to-end + visual | `e2e/` | `E2E=1`, `playwright`, `pillow`, Edge, Node (see `e2e/README.md`) |

## Run

PowerShell:

```powershell
python -m pytest tests -q                              # 569 collected: 539 run and pass, 30 e2e skipped (about 1 min)
python -m pytest tests/test_regression_real.py -q      # only the real-data regression tests
$env:E2E = "1"; python -m pytest tests/e2e -q          # browser tests (starts its own servers)
$env:E2E = "1"; $env:E2E_UPDATE_BASELINE = "1"; python -m pytest tests/e2e -k visual   # regenerate baselines
Remove-Item Env:E2E, Env:E2E_UPDATE_BASELINE -ErrorAction SilentlyContinue
```

bash:

```bash
python -m pytest tests -q
python -m pytest tests/test_regression_real.py -q
E2E=1 python -m pytest tests/e2e -q
E2E=1 E2E_UPDATE_BASELINE=1 python -m pytest tests/e2e -k visual
```

Counts (`python -m pytest tests --co -q`): 569 tests collected. Without `E2E=1`, `pytest tests -q` runs 539 and skips 26, all of them browser (e2e) tests. With `E2E=1` the 30 e2e tests run too.

Isolation: `tests/conftest.py` sets a temporary `DATABASE_URL` and `STORAGE_DIR` before importing the app, so the unit tests never touch `data/motorsport.db`, `data/storage` or the real lap history (`LAPTIME_HISTORY_DB` / `STORAGE_DIR` decide where `laptime_history.db` lives).

Notable suites: `test_compare_two_laps.py` (two-file compare mode: `/api/compare-laps` + `/api/telemetry/analyze`, same car vs different car, metadata merge), `test_history_db_path.py` (where the lap-history DB is stored), `test_container_build_context.py` and `test_k8s_manifests.py` (Docker build context and Kubernetes manifests, no Docker needed; the nginx test looks for the `sh` of Git for Windows), `test_settings_paths.py` (folders set from the UI), `test_tyre_grip_measured.py` (measured wear), `test_incidents.py` (spin / off-track detection and causes, synthetic and real fixtures), `test_native_pit_channel.py` (iRacing pit indicator), `test_upload_limit.py`, `test_perf_cache.py`, `test_check_contrast.py`.

Set `PYTHONUTF8=1` on Windows if you see encoding errors printing Spanish text.

The `e2e` marker is registered in `pytest.ini`; `-m "not e2e"` / `-m e2e` select or exclude those tests.
The real fixtures are described in `fixtures/README.md` and rebuilt with `scripts/make_fixtures.py`.
