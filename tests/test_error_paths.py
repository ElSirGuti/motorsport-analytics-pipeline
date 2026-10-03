"""Client-error paths: single-lap files, binary / header-only uploads, CORS on errors."""
from __future__ import annotations

import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

import main
from tests.test_perf_cache import _motec_csv

ORIGIN = "http://localhost:5173"
SESSION_ENDPOINTS = [
    ("/api/compare-session-laps", "session_file"),
    ("/api/stint/analyze", "laps"),
    ("/api/analyze-session", "session_file"),
    ("/api/optimal-lap", "session_file"),
    ("/api/report/pdf", "session_file"),
]


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app, raise_server_exceptions=False)


def _post(client, path, field, data, lang="es"):
    return client.post(f"{path}?lang={lang}", files={field: ("x.csv", data, "text/csv")},
                       headers={"Origin": ORIGIN})


@pytest.mark.parametrize("lang,needle", [("es", "una sola vuelta"), ("en", "single lap")])
def test_single_lap_compare_is_422_translated(client, lang, needle):
    r = _post(client, "/api/compare-session-laps", "session_file", _motec_csv(n_laps=1), lang=lang)
    assert r.status_code == 422, r.text
    assert needle in r.json()["detail"]
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_single_lap_pdf_is_422(client):
    r = _post(client, "/api/report/pdf", "session_file", _motec_csv(n_laps=1))
    assert r.status_code == 422
    assert "una sola vuelta" in r.json()["detail"]


def test_single_lap_other_endpoints_never_500(client):
    data = _motec_csv(n_laps=1)
    for path, field in SESSION_ENDPOINTS:
        r = _post(client, path, field, data)
        assert r.status_code < 500, (path, r.status_code, r.text[:200])


@pytest.mark.parametrize("name,payload", [
    ("binary", bytes(range(256)) * 40),
    ("random", np.random.default_rng(0).bytes(5000)),
    ("header_only", b"Time,Speed,Brake,Throttle\n"),
    ("empty", b""),
])
def test_bad_files_are_client_errors_with_cors(client, name, payload):
    for path, field in SESSION_ENDPOINTS:
        r = _post(client, path, field, payload)
        assert 400 <= r.status_code < 500, (name, path, r.status_code, r.text[:200])
        assert r.headers.get("access-control-allow-origin") == ORIGIN, (name, path)
        assert isinstance(r.json().get("detail"), str)


def test_unhandled_exception_keeps_cors_headers():
    @main.app.get("/api/_boom_test")
    def _b():
        raise RuntimeError("kaboom")

    c = TestClient(main.app, raise_server_exceptions=False)
    r = c.get("/api/_boom_test", headers={"Origin": ORIGIN})
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == ORIGIN
    assert "detail" in r.json()


_REAL = r"C:\Users\elgut\Downloads\vuelta_rapida.csv"


@pytest.mark.skipif(not os.path.exists(_REAL), reason="real single-lap file not available")
def test_real_single_lap_file(client):
    with open(_REAL, "rb") as fh:
        data = fh.read()
    r = _post(client, "/api/compare-session-laps", "session_file", data)
    assert r.status_code == 422 and "una sola vuelta" in r.json()["detail"]
