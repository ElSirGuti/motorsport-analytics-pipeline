"""MAX_UPLOAD_MB enforcement: streaming cut-off (413) and early Content-Length check."""

import os

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


@pytest.fixture
def client():
    return TestClient(main.app)


def test_default_limit_is_positive():
    assert main.MAX_UPLOAD_BYTES == main.MAX_UPLOAD_MB * 1024 * 1024 > 0


def test_oversized_upload_returns_413_translated(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 7)
    big = b"a,b\n" + b"1,2\n" * 2000  # ~8 KB > 1 KB
    r = client.post("/api/analyze-session?lang=es",
                    files={"session_file": ("s.csv", big, "text/csv")})
    assert r.status_code == 413
    assert "7 MB" in r.json()["detail"]
    assert "máximo" in r.json()["detail"]
    r = client.post("/api/analyze-session?lang=en",
                    files={"session_file": ("s.csv", big, "text/csv")})
    assert r.status_code == 413 and "maximum" in r.json()["detail"]


def _run(coro):
    """Ejecuta una corrutina en un hilo propio.

    `asyncio.run` falla con 'cannot be called from a running event loop' si otro componente de la misma
    sesión de pytest (p. ej. la API síncrona de Playwright en los tests e2e) deja un bucle activo en el
    hilo principal. Un hilo nuevo no tiene bucle, así que funciona siempre.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def test_partial_file_is_removed(monkeypatch, tmp_path):
    import io

    class _Up:
        file = io.BytesIO(b"x" * 5000)

    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1000)
    dest = tmp_path / "p.csv"
    with pytest.raises(main.HTTPException) as exc:
        _run(main._save_upload(_Up(), str(dest)))
    assert exc.value.status_code == 413
    assert not dest.exists()


def test_small_upload_is_saved(monkeypatch, tmp_path):
    import io

    class _Up:
        file = io.BytesIO(b"x" * 500)

    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1000)
    dest = tmp_path / "ok.csv"
    _run(main._save_upload(_Up(), str(dest)))
    assert os.path.getsize(dest) == 500


def test_content_length_rejected_early(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1024)
    r = client.post("/api/analyze-session",
                    content=b"x", headers={"content-length": str(50 * 1024 * 1024)})
    assert r.status_code == 413
