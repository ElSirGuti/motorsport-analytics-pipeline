"""El historial de vueltas (laptime_history.db) debe ser escribible en contenedores.

Regresión: tras dejar de versionar data/laptime_history.db, /api/telemetry/analyze devolvía 500
('unable to open database file') en la imagen Docker/Kubernetes, donde /app/data es de solo lectura
y solo el volumen STORAGE_DIR es escribible.
"""
import importlib
from pathlib import Path

import pytest

from src.analytics import ml_laptime as M


def _reload(monkeypatch, **env):
    for key in ("LAPTIME_HISTORY_DB", "STORAGE_DIR"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(M)


@pytest.fixture(autouse=True)
def _restore_module():
    yield
    importlib.reload(M)


def test_explicit_path_wins(monkeypatch, tmp_path):
    target = tmp_path / "x" / "h.db"
    mod = _reload(monkeypatch, LAPTIME_HISTORY_DB=str(target), STORAGE_DIR=str(tmp_path / "s"))
    assert mod.DB_PATH == target


def test_storage_dir_is_used_when_set(monkeypatch, tmp_path):
    mod = _reload(monkeypatch, STORAGE_DIR=str(tmp_path / "storage"))
    assert mod.DB_PATH == tmp_path / "storage" / "laptime_history.db"


def test_defaults_to_repo_data_dir(monkeypatch):
    mod = _reload(monkeypatch)
    assert mod.DB_PATH == Path(mod.__file__).parent.parent.parent / "data" / "laptime_history.db"


def test_save_creates_missing_directory(monkeypatch, tmp_path):
    """La carpeta del historial no existe todavía: debe crearse al guardar, sin error."""
    target = tmp_path / "volumen" / "nuevo" / "laptime_history.db"
    mod = _reload(monkeypatch, LAPTIME_HISTORY_DB=str(target))
    assert not target.parent.exists()
    assert mod.n_observaciones_historial() == 0  # sin BD: no falla
    # reutiliza el mismo camino de escritura que usa la API
    target.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    conn = sqlite3.connect(str(mod.DB_PATH))
    mod._init_db(conn)
    conn.close()
    assert target.exists()
    assert mod.n_observaciones_historial() == 0
