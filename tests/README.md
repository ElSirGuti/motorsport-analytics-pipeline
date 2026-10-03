# Tests

| Suite | Files | Needs |
|---|---|---|
| Unit / API (synthetic data) | `test_*.py` | `pip install -r requirements-dev.txt` |
| Regression on real fixtures | `test_regression_real.py`, `fixtures/` | same (PDF checks need `pymupdf`) |
| End-to-end + visual | `e2e/` | `E2E=1`, `playwright`, `pillow`, Edge, Node (see `e2e/README.md`) |

## Run

PowerShell:

```powershell
python -m pytest tests -q                              # everything except e2e (skipped), < 1 min
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

Set `PYTHONUTF8=1` on Windows if you see encoding errors printing Spanish text.

The `e2e` marker is registered in `pytest.ini`; `-m "not e2e"` / `-m e2e` select or exclude those tests.
The real fixtures are described in `fixtures/README.md` and rebuilt with `scripts/make_fixtures.py`.
