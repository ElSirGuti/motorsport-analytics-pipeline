"""Comparación de DOS archivos de una vuelta (modo 'Comparar' de la interfaz).

Regresión: la interfaz llama a /api/compare-laps y a /api/telemetry/analyze con los mismos dos archivos y
fusiona ambas respuestas. Cada una trae `metadata` con claves distintas (driver_a/vehicle_a/same_vehicle
frente a driver_fast/vehicle_fast), y al reemplazar una por otra las tarjetas de identidad salían vacías
y el aviso de vehículos distintos mostraba 'undefined vs undefined' con el mismo coche.
Los fixtures son recortes anonimizados de vueltas reales del Red Bull Ring (scripts/make_fixtures.py).
"""
import gzip
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


@pytest.fixture(scope="module")
def laps(tmp_path_factory):
    out = tmp_path_factory.mktemp("laps")
    paths = {}
    for name in ("rbr_fast", "rbr_slow", "rbr_other_car"):
        src = FIXTURES / f"{name}.csv.gz"
        if not src.exists():
            pytest.skip(f"falta el fixture {src.name}")
        dst = out / f"{name}.csv"
        with gzip.open(src, "rb") as f, open(dst, "wb") as o:
            shutil.copyfileobj(f, o)
        paths[name] = dst
    return paths


def _post(client, endpoint, a, b, keys, lang="es"):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return client.post(
            f"/api/{endpoint}?lang={lang}",
            files={keys[0]: (a.name, fa, "text/csv"), keys[1]: (b.name, fb, "text/csv")},
        )


def _both(client, laps, a, b, lang="es"):
    basic = _post(client, "compare-laps", laps[a], laps[b], ("lap_a", "lap_b"), lang)
    advanced = _post(client, "telemetry/analyze", laps[a], laps[b], ("lap_fast", "lap_slow"), lang)
    return basic, advanced


@pytest.mark.parametrize("pair", [("rbr_fast", "rbr_slow"), ("rbr_fast", "rbr_other_car")])
def test_both_endpoints_succeed(client, laps, pair):
    basic, advanced = _both(client, laps, *pair)
    assert basic.status_code == 200, basic.text[:200]
    assert advanced.status_code == 200, advanced.text[:200]


def test_same_car_identity_and_no_false_mismatch(client, laps):
    basic, _ = _both(client, laps, "rbr_fast", "rbr_slow")
    meta = basic.json()["metadata"]
    assert meta["same_vehicle"] is True
    assert meta["vehicle_a"] and meta["vehicle_a"] == meta["vehicle_b"]
    assert meta["driver_a"] and meta["driver_b"]
    assert meta["label_a"] and meta["label_b"]
    assert meta["venue"] == "ks_red_bull_ring"


def test_different_cars_are_flagged_with_both_names(client, laps):
    basic, _ = _both(client, laps, "rbr_fast", "rbr_other_car")
    meta = basic.json()["metadata"]
    assert meta["same_vehicle"] is False
    assert meta["vehicle_a"] != meta["vehicle_b"]
    assert "maserati" in meta["vehicle_b"]


def test_metadata_keys_the_ui_merges_do_not_collide_destructively(client, laps):
    """La UI fusiona ambos metadata; el básico debe conservar las claves que la tarjeta de identidad lee."""
    basic, advanced = _both(client, laps, "rbr_fast", "rbr_slow")
    mb, ma = basic.json()["metadata"], advanced.json()["metadata"]
    merged = {**ma, **mb}
    for key in ("driver_a", "vehicle_a", "driver_b", "vehicle_b", "same_vehicle", "same_driver", "label_a", "label_b"):
        assert key in merged, key
    # el avanzado aporta claves propias que otros paneles usan
    assert "vehicle_fast" in ma and "venue" in ma


def test_fast_lap_is_actually_faster(client, laps):
    basic, _ = _both(client, laps, "rbr_fast", "rbr_slow")
    delta = basic.json()["summary"]["total_time_delta"]
    assert 2.5 < delta < 4.0  # la lenta pierde ~3.2 s en los datos reales


def test_responses_have_no_nan_or_inf(client, laps):
    import json
    import math

    basic, advanced = _both(client, laps, "rbr_fast", "rbr_slow")

    def walk(x):
        if isinstance(x, float):
            assert math.isfinite(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(json.loads(basic.text))
    walk(json.loads(advanced.text))


def test_es_and_en_have_same_top_level_keys(client, laps):
    es = _both(client, laps, "rbr_fast", "rbr_slow", "es")[1].json()
    en = _both(client, laps, "rbr_fast", "rbr_slow", "en")[1].json()
    assert set(es.keys()) == set(en.keys())
