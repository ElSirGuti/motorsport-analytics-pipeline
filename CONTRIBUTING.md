# Contributing

Thanks for your interest in improving this project! Contributions are welcome.

## How to contribute

1. **Fork** the repository and clone your fork.
2. Create a branch for your change: `git checkout -b feat/my-change`.
3. Make your changes, keeping them focused on a single topic.
4. Run the tests before committing:
   ```
   pip install -r requirements.txt -r requirements-dev.txt
   pytest
   ```
5. Commit with a clear message (e.g. `feat: add tyre temperature chart`, `fix: handle empty laps`).
6. Push to your fork and open a **Pull Request** against `main`.

## Rules

- `main` is protected: nobody can push to it directly. All changes go through a Pull Request approved by the maintainer.
- Keep PRs small and describe *what* changed and *why*.
- Do not commit telemetry files (CSV, `.ibt`, `.ld`), personal data or secrets (see below).
- By contributing, you agree that your work is released under the project's [MIT License](LICENSE).

## Translations, tests and data

**Translated text (i18n by module).** Every user-visible string exists in English and Spanish. Do not grow the core dictionaries: add the strings of a feature in its own pair of files.

- Frontend: `frontend/src/i18n/extra/<feature>.en.js` and `<feature>.es.js` with `export default { key: 'text' }` (values can be functions, e.g. `(n) => ...`). They are merged automatically (`import.meta.glob`) into `en.js` / `es.js`.
- Backend: `src/locales/extra/<feature>.en.json` and `<feature>.es.json` (flat key to string, `{placeholders}` allowed), merged by `src/i18n.py` on first use. Use `_l(lang, key, ...)` or `_()`.
- Keep keys unique across modules and provide both languages.

**Tests.** Run `python -m pytest tests -q` before every Pull Request (about 1 min; 582 tests are collected, 550 run and 26 end-to-end tests are skipped unless `E2E=1`; the unit tests use a temporary database and storage, never your data). Add a test with each fix or feature; use the anonymised real fixtures in `tests/fixtures/` for pipeline regressions (`tests/test_regression_real.py`). The optional browser tests (Playwright + Edge) run with `E2E=1 python -m pytest tests/e2e -q`; if you change the UI on purpose, regenerate the visual baselines with `E2E_UPDATE_BASELINE=1 ... -k visual` and review the diffs before committing. Details: [tests/README.md](tests/README.md). For UI changes also run `cd frontend && npm run lint && npm run build`, and `python scripts/check_contrast.py` if you touch colours.

**Never commit personal data or telemetry.** Do not commit CSV, `.ibt` or `.ld` files, databases with your sessions (`data/motorsport.db`, `data/storage/`), `.env` files or setup files from your game folder: they contain your driver name and personal sessions. Test fixtures are generated with `scripts/make_fixtures.py`, which anonymises the `Driver` field by default (`.csv.gz` extension on purpose). New circuit corner names need evidence from a real lap (see "Known circuits" in the [README](README.md#known-circuits-and-corner-names)).

### Traducciones, tests y datos (resumen en español)

- **i18n por módulos:** añade los textos de cada función en `frontend/src/i18n/extra/<modulo>.en.js` y `.es.js`, y en `src/locales/extra/<modulo>.en.json` y `.es.json`. Siempre ambos idiomas.
- **Tests:** `python -m pytest tests -q` antes de cada Pull Request; los e2e opcionales con `E2E=1` (líneas base visuales con `E2E_UPDATE_BASELINE=1`). Ver [tests/README.md](tests/README.md).
- **Datos personales:** no subas CSV, `.ibt`, `.ld`, bases de datos con tus sesiones, `.env` ni setups de tu carpeta del juego. Los fixtures reales se anonimizan con `scripts/make_fixtures.py`.

## Reporting bugs and ideas

Open an issue with steps to reproduce (and a small sample of data if relevant), or describe the feature you would like to see.
