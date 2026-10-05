"""Infraestructura e2e: backend + vite en puertos libres, navegador Edge (Playwright).

Todo esto se OMITE salvo que E2E=1 y playwright + Edge esten disponibles. El pytest normal
no arranca ningun servidor: los servidores solo se levantan al usar el fixture `servers`,
que unicamente piden los tests e2e que no se han omitido.
"""
from __future__ import annotations

import gzip
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FRONTEND = ROOT / "frontend"
FIXTURES = ROOT / "tests" / "fixtures"
VIEWPORT = {"width": 1440, "height": 900}


def _e2e_enabled() -> bool:
    return os.environ.get("E2E", "").strip().lower() in ("1", "true", "yes")


def pytest_collection_modifyitems(config, items):
    """Marca como `e2e` todo lo de esta carpeta y lo omite si E2E no esta activado."""
    skip = pytest.mark.skip(reason="e2e: set E2E=1 (needs playwright + Microsoft Edge, node, frontend/node_modules)")
    for item in items:
        if HERE in Path(str(item.fspath)).resolve().parents:
            item.add_marker(pytest.mark.e2e)
            if not _e2e_enabled():
                item.add_marker(skip)


# ── i18n: leer textos de frontend/src/i18n por clave (resistente a cambios de copy) ──
_EXTRAS = ("_init", "cornerMap", "data_quality", "formats", "incidents", "tyreGrip", "settings", "library", "optimalLap", "pdf", "setups", "theme")
_I18N_FILES = {lg: [f"{lg}.js"] + [f"extra/{n}.{lg}.js" for n in _EXTRAS] for lg in ("en", "es")}
_i18n_cache: dict = {}


def _unescape(s: str) -> str:
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    return s.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def i18n(lang: str, key: str) -> str:
    """Valor de la cadena i18n `key` (solo cadenas literales, no funciones)."""
    if lang not in _i18n_cache:
        text = ""
        for f in _I18N_FILES[lang]:
            p = FRONTEND / "src" / "i18n" / f
            if p.exists():
                text += p.read_text(encoding="utf-8") + "\n"
        _i18n_cache[lang] = text
    src = _i18n_cache[lang]
    m = re.search(rf"^\s*{re.escape(key)}\s*:\s*'((?:[^'\\\n]|\\.)*)'", src, re.M)
    if not m:
        m = re.search(rf'^\s*{re.escape(key)}\s*:\s*"((?:[^"\\\n]|\\.)*)"', src, re.M)
    if not m:
        raise KeyError(f"i18n key {key!r} not found for {lang}")
    return _unescape(m.group(1))


# ── servidores ───────────────────────────────────────────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_http(url: str, proc: subprocess.Popen, what: str, timeout: float = 90.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"{what} exited early (code {proc.returncode})")
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500:
                    return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"{what} did not start in {timeout}s ({url})")


def _kill_tree(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=30)
        else:
            import signal
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        proc.kill()
    try:
        proc.wait(timeout=15)
    except Exception:
        pass


@pytest.fixture(scope="session")
def servers(tmp_path_factory):
    """Arranca backend (uvicorn) y frontend (vite) en puertos libres; los apaga siempre."""
    node = shutil.which("node")
    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    if not node or not vite.exists():
        pytest.skip("node or frontend/node_modules/vite missing (run `npm ci` in frontend/)")

    work = tmp_path_factory.mktemp("e2e_srv")
    api_port, web_port = _free_port(), _free_port()
    db_path = work / "e2e_library.db"
    popen_kw: dict = {"stderr": subprocess.STDOUT}
    if os.name == "nt":
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True

    back_env = {**os.environ,
                "CORS_ORIGINS": f"http://127.0.0.1:{web_port}",
                "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
                "SETTINGS_FILE": str(work / "settings.json"),
                "PYTHONUTF8": "1", "LOG_LEVEL": "WARNING"}
    web_env = {**os.environ, "VITE_API_URL": f"http://127.0.0.1:{api_port}/api"}

    back_log = open(work / "backend.log", "wb")
    web_log = open(work / "vite.log", "wb")
    back = web = None
    try:
        back = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(api_port)],
            cwd=ROOT, env=back_env, stdout=back_log, **popen_kw)
        web = subprocess.Popen(
            [node, str(vite), "--port", str(web_port), "--strictPort", "--host", "127.0.0.1"],
            cwd=FRONTEND, env=web_env, stdout=web_log, **popen_kw)
        try:
            _wait_http(f"http://127.0.0.1:{api_port}/api/health", back, "backend")
            _wait_http(f"http://127.0.0.1:{web_port}/", web, "vite")
        except RuntimeError as exc:
            tail = ""
            for lf in ("backend.log", "vite.log"):
                try:
                    tail += f"\n--- {lf} ---\n" + (work / lf).read_text(errors="ignore")[-1500:]
                except OSError:
                    pass
            pytest.fail(f"{exc}{tail}")
        yield {"api": f"http://127.0.0.1:{api_port}", "web": f"http://127.0.0.1:{web_port}",
               "db": db_path, "logs": work}
    finally:
        _kill_tree(web)
        _kill_tree(back)
        back_log.close()
        web_log.close()


# ── navegador ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    pw = sync_api.sync_playwright().start()
    try:
        try:
            b = pw.chromium.launch(channel="msedge", headless=True)
        except Exception as exc:  # Edge no instalado
            pytest.skip(f"Microsoft Edge not available for Playwright: {str(exc)[:120]}")
        try:
            yield b
        finally:
            b.close()
    finally:
        pw.stop()


@pytest.fixture
def page(browser, servers):
    """Pagina nueva (contexto aislado, localStorage limpio) con captura de errores."""
    ctx = browser.new_context(viewport=VIEWPORT, locale="en-US", color_scheme="light",
                              reduced_motion="reduce", accept_downloads=True)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(f"pageerror: {str(e)[:300]}"))

    def _console(m):
        if m.type == "error" and "favicon" not in ((m.location or {}).get("url", "") + m.text):
            pg.errors.append(f"console.error: {m.text[:300]}")

    pg.on("console", _console)
    pg.base_url = servers["web"]
    try:
        yield pg
    finally:
        ctx.close()


# ── datos ────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def imola_csv(tmp_path_factory) -> str:
    src = FIXTURES / "imola_5laps.csv.gz"
    if not src.exists():
        pytest.skip("tests/fixtures/imola_5laps.csv.gz missing")
    d = tmp_path_factory.mktemp("e2e_data")
    dst = d / "imola_5laps.csv"
    with gzip.open(src, "rb") as a, open(dst, "wb") as b:
        shutil.copyfileobj(a, b)
    return str(dst)


@pytest.fixture(scope="session")
def spin_csv(tmp_path_factory) -> str:
    """Synthetic 4-lap session with a spin (power oversteer) and an off-track in lap 2."""
    from tests.test_incidents import write_session_csv
    dst = tmp_path_factory.mktemp("e2e_spin") / "spin_session.csv"
    write_session_csv(dst, spin_lap=2)
    return str(dst)


@pytest.fixture(scope="session")
def single_laps(tmp_path_factory) -> dict:
    """Tres vueltas sueltas del Red Bull Ring: rapida/lenta (mismo coche) y rapida con otro coche."""
    d = tmp_path_factory.mktemp("e2e_laps")
    out = {}
    for name in ("rbr_fast", "rbr_slow", "rbr_other_car"):
        src = FIXTURES / f"{name}.csv.gz"
        if not src.exists():
            pytest.skip(f"tests/fixtures/{name}.csv.gz missing")
        dst = d / f"{name}.csv"
        with gzip.open(src, "rb") as a, open(dst, "wb") as b:
            shutil.copyfileobj(a, b)
        out[name] = str(dst)
    return out


# ── helpers de interaccion (los importan los tests) ──────────────────────────
def settle(pg, ms: int = 1500) -> None:
    """Deja terminar peticiones y animaciones de graficos."""
    try:
        pg.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        pass
    pg.wait_for_timeout(ms)


def set_lang(pg, lang: str) -> None:
    pg.get_by_role("button", name=lang.upper(), exact=True).first.click()
    pg.wait_for_function(
        "l => [...document.querySelectorAll('.ui-seg__item')].some(b => b.textContent.trim() === l.toUpperCase()"
        " && b.getAttribute('aria-pressed') === 'true')", arg=lang)


def open_app(pg, lang: str = "en") -> None:
    pg.goto(pg.base_url, wait_until="networkidle")
    set_lang(pg, lang)


def upload_and_analyze(pg, csv_path: str, timeout_s: int = 150) -> None:
    pg.set_input_files("input[type=file]", csv_path)
    pg.locator(".shell-actions button.ui-btn--primary").first.click()
    pg.locator("#section-overview").wait_for(timeout=timeout_s * 1000)
    pg.locator("#section-stint").wait_for(timeout=timeout_s * 1000)
    settle(pg)


@pytest.fixture
def analyzed(page, imola_csv):
    """Pagina con la sesion Imola ya analizada (EN)."""
    open_app(page, "en")
    upload_and_analyze(page, imola_csv)
    return page
