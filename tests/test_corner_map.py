"""src/analytics/corner_map.py: unified corner map (synthetic laps + real fixtures)."""
import gzip
import json
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics import circuits as C
from src.analytics.corner_map import DEFAULTS, build_corner_map

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def make_lap(length, dips, seed=0, jitter=0.0, brake=True):
    """Synthetic lap on a 1 m grid: 200 km/h with speed dips at ``dips`` = [(apex_m, min_speed_kmh, width_m)].

    A dip with brake=True also gets a braking zone just before the apex (like a real corner)."""
    rng = np.random.default_rng(seed)
    d = np.arange(0.0, length, 1.0)
    speed = np.full(d.shape, 200.0)
    bk = np.zeros(d.shape)
    thr = np.full(d.shape, 100.0)
    for apex, vmin, w in dips:
        apex = apex + rng.normal(0.0, jitter) if jitter else apex
        speed -= (200.0 - vmin) * np.exp(-((d - apex) ** 2) / (2.0 * (w / 2.5) ** 2))
        if brake:
            zone = (d > apex - 120) & (d < apex - 20)
            bk[zone] = 70.0
            thr[zone] = 0.0
    speed = np.maximum(speed, 30.0)
    return pd.DataFrame({"Distance": d, "Speed": speed, "Brake": bk, "Throttle": thr})


THREE = [(600.0, 90.0, 90.0), (1500.0, 70.0, 90.0), (2400.0, 100.0, 90.0)]


def laps_of(dips, n=5, length=3000.0, **kw):
    return [make_lap(length, dips, seed=i, jitter=6.0, **kw) for i in range(n)]


# -- synthetic cases ------------------------------------------------------------------

def test_three_clear_corners_ordered_and_numbered():
    r = build_corner_map(laps_of(THREE), venue=None)
    cs = r["corners"]
    assert [c["number"] for c in cs] == [1, 2, 3]
    pos = [c["apex_distance_m"] for c in cs]
    assert pos == sorted(pos)
    for p, (apex, _v, _w) in zip(pos, THREE):
        assert abs(p - apex) < 30.0
    for c in cs:
        assert c["kind"] == "braking" and c["flat_out_share"] == 0.0
        assert "speed" in c["sources"] and c["evidence"]["laps_found"] == 5 == c["evidence"]["laps_total"]
        assert 0.5 < c["confidence"] <= 1.0 and c["name"] is None and c["start_m"] < c["apex_distance_m"] < c["end_m"]
    assert abs(cs[1]["evidence"]["speed_min_kmh"] - 70.0) < 6
    s = r["summary"]
    assert s["n_corners"] == 3 and s["n_named"] == 0 and s["circuit"] is None and s["method"] == "consensus"
    json.dumps(r)    # serialisable as is


def test_chicane_is_one_compound_corner_with_sub_apexes():
    dips = [(800.0, 100.0, 40.0), (880.0, 100.0, 40.0), (2000.0, 80.0, 90.0)]
    r = build_corner_map(laps_of(dips), venue=None)
    chic = [c for c in r["corners"] if abs(c["apex_distance_m"] - 840) < 80]
    assert len(chic) == 1 and chic[0]["is_complex"] and len(chic[0]["sub_apexes"]) == 2
    assert [c["is_complex"] for c in r["corners"]].count(False) == 1
    subs = chic[0]["sub_apexes"]
    assert all(40 < b["distance_m"] - a["distance_m"] < 120 for a, b in zip(subs, subs[1:]))


def test_single_spurious_apex_is_removed_by_consensus():
    laps = laps_of(THREE)
    laps[2] = make_lap(3000.0, THREE + [(2000.0, 90.0, 60.0)], seed=2, jitter=6.0)
    r = build_corner_map(laps, venue=None)
    assert [round(c["apex_distance_m"], -2) for c in r["corners"]] == [600.0, 1500.0, 2400.0]
    assert any(abs(x["apex_distance_m"] - 2000) < 60 and x["reason"] == "no consensus" for x in r["discarded"])
    # with a single lap there is no consensus to remove it: relaxed mode keeps it, with a warning
    one = build_corner_map([laps[2]], venue=None)
    assert len(one["corners"]) == 4 and any("relaxed" in w for w in one["summary"]["warnings"])


def test_single_lap_is_relaxed_with_lower_confidence():
    laps = laps_of(THREE)
    many = build_corner_map(laps, venue=None)["corners"]
    one = build_corner_map(laps[0], venue=None)          # accepts a bare DataFrame
    assert len(one["corners"]) == 3
    assert all(a["confidence"] < b["confidence"] for a, b in zip(one["corners"], many))
    assert one["summary"]["n_laps"] == 1


def test_unknown_circuit_has_no_names_and_no_template():
    r = build_corner_map(laps_of(THREE), venue="zz_nowhere_ring")
    assert r["summary"]["circuit"] is None and r["summary"]["n_named"] == 0
    assert any("unknown circuit" in w for w in r["summary"]["warnings"])


def test_length_that_does_not_fit_gives_no_names():
    r = build_corner_map(laps_of(THREE, length=3000.0), venue="imola")   # Imola is 4909 m
    assert r["summary"]["n_named"] == 0 and any("does not fit" in w for w in r["summary"]["warnings"])


def test_bad_input_and_options():
    assert build_corner_map([], venue=None)["corners"] == []
    assert build_corner_map([pd.DataFrame({"x": [1, 2]})])["summary"]["n_laps"] == 0
    with pytest.raises(ValueError):
        build_corner_map(laps_of(THREE), options={"nope": 1})


def test_deterministic_and_fast():
    laps = laps_of(THREE, n=8)
    t0 = time.perf_counter()
    a = build_corner_map(laps, venue=None)
    assert time.perf_counter() - t0 < 1.0
    assert a == build_corner_map(laps, venue=None)


def test_flat_out_corner_kept_by_table_and_named():
    """Imola: nothing happens at Variante Bassa (0.94 of the lap), the map keeps it as a named flat_out corner."""
    imola = C.get_circuit("imola")
    L = float(imola["length_m"])
    dips = [(k["apex_fraction"] * L, 90.0, 80.0) for k in imola["corners"] if k["name"] != "Variante Bassa"]
    r = build_corner_map(laps_of(dips, length=L), venue="imola")
    by = {c["name"]: c for c in r["corners"] if c["name"]}
    assert set(by) == {k["name"] for k in imola["corners"]}
    bassa = by["Variante Bassa"]
    assert bassa["kind"] == "flat_out" and bassa["flat_out_share"] == 1.0 and "table" in bassa["sources"]
    assert abs(bassa["fraction"] - 0.94) < 0.03 and bassa["evidence"]["laps_found"] == 0
    assert by["Tamburello"]["kind"] == "braking"
    # without the table the geometry template cannot name it: the bend (R=478 m) is above the 400 m cut
    nt = build_corner_map(laps_of(dips, length=L), venue="imola", options={"use_table": False})
    assert "Variante Bassa" not in {c["name"] for c in nt["corners"]}


def test_geometry_bend_without_telemetry_evidence_is_kept_not_dropped():
    """Spa Eau Rouge: a geometric bend with no speed minimum stays in the map, at its geometric position."""
    spa = C.get_circuit("spa_francorchamps")
    L = float(spa["length_m"])
    dips = [(k["apex_fraction"] * L, 90.0, 80.0) for k in spa["corners"] if k["name"] != "Eau Rouge / Raidillon"]
    r = build_corner_map(laps_of(dips, length=L), venue="spa")
    eau = [c for c in r["corners"] if c["name"] == "Eau Rouge / Raidillon"]
    assert len(eau) == 1 and eau[0]["kind"] in ("flat_out", "lift") and "track_geometry" in eau[0]["sources"]
    assert eau[0]["min_radius_m"] is not None and eau[0]["direction"] in ("left", "right")


# -- circuits.json additions ----------------------------------------------------------

def test_database_accepts_flat_out_kind_and_rejects_unknown_kind():
    data = json.loads(C.DB_PATH.read_text(encoding="utf-8"))
    assert C.validate_database(data) == []
    imola = next(c for c in data["circuits"] if c["id"] == "imola")
    assert imola["corners"][-1]["kind"] == "flat_out"
    imola["corners"][-1]["kind"] = "banana"
    assert any("kind" in e for e in C.validate_database(data))


# -- real fixtures --------------------------------------------------------------------

def _fixture_laps(name):
    from src.analytics.stint import segmentar_vueltas_desde_csv
    from src.io.loaders import load_telemetry_data
    src = FIXTURES / f"{name}.csv.gz"
    if not src.exists():
        pytest.skip(f"missing fixture {src.name}")
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / f"{name}.csv"
        with gzip.open(src, "rb") as a, open(dst, "wb") as b:
            shutil.copyfileobj(a, b)
        df = load_telemetry_data(str(dst))
    laps = segmentar_vueltas_desde_csv(df)
    lens = [float(l["Distance"].max() - l["Distance"].min()) for l in laps]
    med = float(np.median(lens))
    return [l.reset_index(drop=True) for l, n in zip(laps, lens) if abs(n - med) <= 0.04 * med and n > 800]


def test_real_imola_five_laps():
    laps = _fixture_laps("imola_5laps")
    t0 = time.perf_counter()
    r = build_corner_map(laps, venue="imola")
    assert time.perf_counter() - t0 < 1.0
    names = [c["name"] for c in r["corners"] if c["name"]]
    expected = ["Tamburello", "Villeneuve", "Tosa", "Piratella", "Acque Minerali", "Variante Alta", "Rivazza 1",
                "Rivazza 2", "Variante Bassa"]
    assert names == expected                        # all named, once, in lap order
    by = {c["name"]: c for c in r["corners"] if c["name"]}
    assert by["Variante Bassa"]["kind"] == "flat_out" and by["Variante Bassa"]["flat_out_share"] == 1.0
    assert all(by[n]["kind"] == "braking" for n in expected[:6])
    assert by["Tamburello"]["is_complex"] and by["Tamburello"]["direction"] == "left"
    length = r["summary"]["lap_length_m"]
    for c in r["corners"]:
        if c["name"]:
            tab = next(k for k in C.get_circuit("imola")["corners"] if k["name"] == c["name"])
            assert abs(c["apex_distance_m"] - tab["apex_fraction"] * length) <= C.apex_tolerance_m(length)
    nums = [c["number"] for c in r["corners"]]
    assert nums == list(range(1, len(nums) + 1))
    assert [c["apex_distance_m"] for c in r["corners"]] == sorted(c["apex_distance_m"] for c in r["corners"])
    assert r["summary"]["n_named"] == 9 and r["summary"]["circuit"]["id"] == "imola"


def test_real_spa_fixture_and_single_lap():
    laps = _fixture_laps("spa_3laps")
    r = build_corner_map(laps, venue="spa")
    names = {c["name"] for c in r["corners"] if c["name"]}
    assert names == {k["name"] for k in C.get_circuit("spa_francorchamps")["corners"]}
    one = build_corner_map(laps[:1], venue="spa")
    assert {c["name"] for c in one["corners"] if c["name"]} == names
    assert max(c["confidence"] for c in one["corners"]) <= max(c["confidence"] for c in r["corners"]) + 1e-9
    assert all(c["start_m"] <= c["apex_distance_m"] <= c["end_m"] for c in r["corners"])


def test_defaults_documented_in_summary():
    r = build_corner_map(laps_of(THREE), venue=None, options={"min_share": 0.7})
    assert r["summary"]["params"]["min_share"] == 0.7 and set(DEFAULTS) <= set(r["summary"]["params"])
