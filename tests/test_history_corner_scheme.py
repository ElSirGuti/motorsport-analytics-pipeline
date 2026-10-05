"""El historial de vueltas se indexa por (circuito, número de curva).

El mapa unificado de curvas numera distinto que los detectores antiguos (Imola pasa de 7 a 10 curvas),
así que mezclar filas de ambos esquemas atribuiría tiempos de una curva a otra y falsearía el percentil 10
y la consistencia. Cada fila guarda `corner_scheme` y las consultas por curva solo usan el esquema vigente.
"""
import importlib
import sqlite3

import pytest

from src.analytics import ml_laptime as M


def _reload(monkeypatch, db, **env):
    for key in ("LAPTIME_HISTORY_DB", "CORNER_DETECTION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LAPTIME_HISTORY_DB", str(db))
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(M)


@pytest.fixture(autouse=True)
def _restore():
    yield
    importlib.reload(M)


def _insert(conn, scheme, corner, loss, venue="imola", n=3):
    cols = ", ".join(M.HISTORY_FEATURES)
    marks = ", ".join(["?"] * len(M.HISTORY_FEATURES))
    for i in range(n):
        vals = [venue, "car", corner, 4900.0, 100.0, 80.0, 90.0, 0.0, 0.0, 70.0, 1.0, 100.0, loss + i * 0.01]
        if scheme is None:  # fila anterior al versionado: sin la columna
            conn.execute(f"INSERT INTO lap_history ({cols}) VALUES ({marks})", vals)
        else:
            conn.execute(f"INSERT INTO lap_history ({cols}, corner_scheme) VALUES ({marks}, ?)", vals + [scheme])
    conn.commit()


def _corners(*numbers):
    return [{"corner_number": n} for n in numbers]


def test_scheme_follows_the_detection_switch(monkeypatch, tmp_path):
    assert _reload(monkeypatch, tmp_path / "h.db")._corner_scheme() == "map"
    assert _reload(monkeypatch, tmp_path / "h.db", CORNER_DETECTION="legacy")._corner_scheme() == "legacy"
    assert _reload(monkeypatch, tmp_path / "h.db", CORNER_DETECTION="MAP")._corner_scheme() == "map"


def test_old_database_is_migrated_without_losing_rows(monkeypatch, tmp_path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    # esquema anterior: sin corner_scheme
    cols = ", ".join(f"{f} REAL" if f not in ("venue", "vehicle") else f"{f} TEXT" for f in M.HISTORY_FEATURES)
    conn.execute(f"CREATE TABLE lap_history (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols}, created_at TEXT)")
    _insert(conn, None, 1, 0.30, n=4)
    conn.close()

    mod = _reload(monkeypatch, db)
    conn = sqlite3.connect(db)
    mod._init_db(conn)
    rows = conn.execute("SELECT corner_scheme FROM lap_history").fetchall()
    conn.close()
    assert len(rows) == 4 and {r[0] for r in rows} == {"legacy"}


def test_map_scheme_ignores_legacy_rows(monkeypatch, tmp_path):
    db = tmp_path / "mix.db"
    mod = _reload(monkeypatch, db)
    conn = sqlite3.connect(db)
    mod._init_db(conn)
    _insert(conn, "legacy", 3, 9.0)   # la curva 3 de los detectores antiguos era OTRA curva
    _insert(conn, "map", 3, 0.20)
    conn.close()
    hist = mod._get_hist_by_corner(_corners(3), {"venue": "imola"})
    assert 3 in hist and hist[3]["mean"] < 1.0  # solo cuenta la fila del mapa, no los 9 s antiguos


def test_legacy_mode_only_sees_legacy_rows(monkeypatch, tmp_path):
    db = tmp_path / "mix2.db"
    mod = _reload(monkeypatch, db, CORNER_DETECTION="legacy")
    conn = sqlite3.connect(db)
    mod._init_db(conn)
    _insert(conn, "legacy", 3, 9.0)
    _insert(conn, "map", 3, 0.20)
    conn.close()
    hist = mod._get_hist_by_corner(_corners(3), {"venue": "imola"})
    assert hist[3]["mean"] > 5.0


def test_map_scheme_on_unmigrated_database_returns_nothing(monkeypatch, tmp_path):
    """Una BD antigua sin columna: todas sus filas son 'legacy', el esquema 'map' no debe usarlas."""
    db = tmp_path / "unmig.db"
    conn = sqlite3.connect(db)
    cols = ", ".join(f"{f} REAL" if f not in ("venue", "vehicle") else f"{f} TEXT" for f in M.HISTORY_FEATURES)
    conn.execute(f"CREATE TABLE lap_history (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols}, created_at TEXT)")
    _insert(conn, None, 3, 9.0)
    conn.close()
    assert _reload(monkeypatch, db)._get_hist_by_corner(_corners(3), {"venue": "imola"}) == {}
    assert _reload(monkeypatch, db, CORNER_DETECTION="legacy")._get_hist_by_corner(_corners(3), {"venue": "imola"})[3]["mean"] > 5.0
