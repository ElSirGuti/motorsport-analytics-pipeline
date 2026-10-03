"""Regression tests on small REAL telemetry fixtures (tests/fixtures/*.csv.gz).

The rest of the suite uses synthetic data, which never exposed bugs that real logs do
(Distance synthesized with an invalid clock, partial segments, overlapping corner windows,
3-point extrapolation, LateralG sign...). These tests load real Assetto Corsa / MoTeC
recordings and assert ROBUST INVARIANTS, not brittle exact values.

Fixtures (see tests/fixtures/README.md):
  imola_5laps  5 laps, Distance channel absent (synthesized), wear active.
  spa_3laps    3 laps + a partial last segment, tyre wear disabled in the sim.
"""
from __future__ import annotations

import glob
import gzip
import json
import math
import os
import re
import shutil
import statistics
from functools import lru_cache

import numpy as np
import pytest
from fastapi.testclient import TestClient

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
NAMES = ("imola_5laps", "spa_3laps")

pytestmark = pytest.mark.skipif(
    not all(os.path.exists(os.path.join(FIXTURES, f"{n}.csv.gz")) for n in NAMES),
    reason="real fixtures missing (run scripts/make_fixtures.py)",
)


# ── helpers ───────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("real_fixtures")
    for n in NAMES:
        with gzip.open(os.path.join(FIXTURES, f"{n}.csv.gz"), "rb") as src, \
                open(d / f"{n}.csv", "wb") as dst:
            shutil.copyfileobj(src, dst)
    return d


@pytest.fixture(scope="module")
def client():
    import main
    return TestClient(main.app)


@pytest.fixture(scope="module")
def api(client, csv_dir):
    """api(path, name, lang='en', **form) -> parsed JSON (cached for the whole module)."""
    cache: dict = {}

    def call(path: str, name: str, lang: str = "en", raw: bool = False, **form):
        key = (path, name, lang, raw, tuple(sorted(form.items())))
        if key not in cache:
            field = "laps" if path.endswith("stint/analyze") else "session_file"
            with open(csv_dir / f"{name}.csv", "rb") as fh:
                r = client.post(f"{path}?lang={lang}", files={field: (f"{name}.csv", fh.read(), "text/csv")},
                                data={k: str(v) for k, v in form.items()},
                                headers={"Accept-Language": lang})
            assert r.status_code == 200, f"{path} {name}: {r.status_code} {r.text[:300]}"
            cache[key] = r if raw else json.loads(r.text, parse_constant=_no_constants)
        return cache[key]

    return call


def _no_constants(c):
    raise AssertionError(f"NaN/Infinity literal in JSON output: {c}")


def _walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, o


@pytest.fixture(scope="module")
def loaded(csv_dir):
    from src.io.loaders import load_telemetry_data
    out = {}
    for n in NAMES:
        out[n] = load_telemetry_data(str(csv_dir / f"{n}.csv"))
    return out


@pytest.fixture(scope="module")
def stint_inputs(loaded):
    """name -> (dfs, df_laps) built with the same functions the endpoint uses."""
    from src.analytics.stint import extraer_metricas_por_vuelta, segmentar_vueltas_desde_csv
    res = {}
    for n, df in loaded.items():
        dfs = segmentar_vueltas_desde_csv(df)
        res[n] = (dfs, extraer_metricas_por_vuelta(dfs))
    return res


# ── loader / header ───────────────────────────────────────────────────────────
def test_header_is_motec_and_driver_is_anonymised(csv_dir):
    from src.io.loaders import read_motec_metadata
    m = read_motec_metadata(str(csv_dir / "imola_5laps.csv"))
    assert m["venue"] == "fn_imola"
    assert "cayman" in m["vehicle"]
    assert m["driver"] == "Test Driver"  # real owner name must not be committed


def test_distance_is_synthesized_from_a_valid_clock(loaded):
    """Regression: the LR/HR Sample Clock are 0/1 square waves -> wrong lap lengths."""
    for name, df in loaded.items():
        assert df.attrs.get("distance_synthetic") is True, name
        d = df["Distance"].to_numpy()
        assert np.all(np.diff(d) >= -1e-9), f"{name}: Distance not monotonic"
        assert d[-1] > 10_000


def test_pedals_scaled_0_100(loaded):
    for df in loaded.values():
        assert 90 <= df["Brake"].max() <= 100.5
        assert 90 <= df["Throttle"].max() <= 100.5


def test_lateral_g_sign_convention_is_detected(loaded):
    """Regression (LateralG sign): AC logs lateral accel anti-correlated with yaw rate;
    lateral_sign_convention must return the factor that restores the agreement."""
    from src.analytics.slip_angle import lateral_sign_convention
    df = loaded["imola_5laps"]
    speed = df["Speed"].to_numpy() / 3.6
    ay = df["LateralG"].to_numpy() * 9.80665
    yaw = df["YawRate"].to_numpy()
    yaw = yaw if np.abs(yaw).max() <= 6.3 else np.deg2rad(yaw)
    k = lateral_sign_convention(ay, yaw, speed)
    moving = speed > 10
    corr = np.corrcoef(k * ay[moving], (yaw * speed)[moving])[0, 1]
    assert corr > 0.5, f"after applying convention LateralG must follow yaw*v (corr={corr:.2f}, k={k})"


# ── lap segmentation ─────────────────────────────────────────────────────────
def test_imola_lap_count_and_best_lap(api):
    r = api("/api/analyze-session", "imola_5laps")
    laps = r["laps"]
    assert len(laps) == 5
    assert not any(l["is_pit_lap"] for l in laps)
    best = min(l["lap_time"] for l in laps)
    assert 118.0 <= best <= 119.6          # real best: 118.79 s (AC timer)
    fastest = [l for l in laps if l["is_fastest"]]
    assert len(fastest) == 1 and fastest[0]["lap_time"] == best
    assert r["fastest_lap"]["lap_number"] == fastest[0]["lap_number"]


def test_spa_partial_segment_is_flagged_and_never_best(api):
    r = api("/api/analyze-session", "spa_3laps")
    laps = r["laps"]
    assert len(laps) in (3, 4)
    full = [l for l in laps if not l["is_pit_lap"]]
    partial = [l for l in laps if l["is_pit_lap"]]
    assert len(full) == 3
    assert all(l["lap_time"] > 100 for l in full)
    for p in partial:  # the half lap at the end of the log
        assert p["lap_time"] < 0.7 * min(l["lap_time"] for l in full)
        assert not p["is_fastest"]
    assert 152.0 <= r["fastest_lap"]["lap_time"] <= 154.8   # real best: 153.4 s
    assert not r["fastest_lap"]["is_pit_lap"]


@pytest.mark.parametrize("name", NAMES)
def test_lap_length_is_roughly_constant(api, name):
    laps = [l for l in api("/api/analyze-session", name)["laps"] if not l["is_pit_lap"]]
    dist = [l["lap_distance"] for l in laps]
    med = statistics.median(dist)
    assert all(abs(d - med) / med < 0.015 for d in dist), dist


def test_stint_flags_partial_segment_and_projects_from_full_laps(api):
    j = api("/api/stint/analyze", "spa_3laps")
    flagged = [l for l in j["laps"] if l["is_pit_lap"]]
    assert [l["lap_number"] for l in flagged] == [j["n_laps"]], "only the trailing half lap is flagged"
    assert j["degradacion"]["actual_laps"] == [1, 2, 3]
    assert j["montecarlo"]["n_laps_used"] == 3


# ── corner windows ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,a,b", [("imola_5laps", 4, 3), ("spa_3laps", 3, 1)])
def test_corner_windows_ordered_and_not_overlapping(api, name, a, b):
    j = api("/api/compare-session-laps", name, lap_a=a, lap_b=b)
    corners = j["corners"]
    assert len(corners) >= 5
    nums = [c["corner_number"] for c in corners]
    assert nums == sorted(nums) and len(set(nums)) == len(nums)
    starts = [c["start_distance"] for c in corners]
    assert starts == sorted(starts), "corner numbering must follow track order"
    for c in corners:
        assert c["start_distance"] <= c["apex_distance"] <= c["end_distance"]
    for prev, nxt in zip(corners, corners[1:]):
        assert prev["end_distance"] <= nxt["start_distance"] + 1e-6, \
            f"overlapping windows: {prev['corner_number']} / {nxt['corner_number']}"


@pytest.mark.parametrize("name", NAMES)
def test_braking_deltas_plausible_when_available(api, name):
    j = api("/api/stint/analyze", name)
    n_checked = 0
    for c in j["curvas_sesion"]["corners"]:
        if c.get("braking_available"):
            assert abs(c["braking_delta_meters"]) < 150, c
            n_checked += 1
        if c.get("apex_available"):
            assert abs(c["apex_speed_delta_kmh"]) < 80, c
    assert n_checked >= 1
    cmp = api("/api/compare-session-laps", "imola_5laps", lap_a=4, lap_b=3)
    for c in cmp["corners"]:
        if c.get("braking_delta_available"):
            assert abs(c["braking_delta_meters"]) < 150, c


# ── Monte Carlo / projections ─────────────────────────────────────────────────
def _mc(df_laps, k):
    from src.analytics.stint import analizar_degradacion_stint, simular_tiempos_stint
    sub = df_laps.iloc[:k].copy()
    deg = analizar_degradacion_stint(sub)
    return sub, deg, simular_tiempos_stint(sub, deg)


@pytest.mark.parametrize("k", [3, 4])
def test_monte_carlo_does_not_extrapolate_with_few_laps(stint_inputs, k):
    """Regression: a 3-point trend line was extrapolated 12 laps ahead."""
    _, df_laps = stint_inputs["imola_5laps"]
    sub, deg, mc = _mc(df_laps, k)
    assert mc["available"] and mc["low_confidence"] and mc["n_laps_used"] == k
    times = sub["lap_time_s"].to_numpy()
    # By design (stint.py): below MIN_LAPS_FOR_TREND the slope is ONLY the physical fuel effect;
    # the noisy OLS slope of 3-4 points (raw_slope_s_per_lap) must not be projected.
    assert deg["tasa_s_per_lap"] == pytest.approx(deg["fuel_effect_s_per_lap"], abs=1e-3)
    assert abs(deg["tasa_s_per_lap"]) <= 0.15
    p50 = np.array(mc["p50"])
    assert abs(p50[0] - statistics.median(times[-3:])) < 1.0
    assert p50.max() - p50.min() < 1.5, "p50 must be ~flat (no trend extrapolation)"


@pytest.mark.parametrize("k", [3, 4, 5])
def test_monte_carlo_band_is_ordered_wide_and_widens(stint_inputs, k):
    _, df_laps = stint_inputs["imola_5laps"]
    sub, deg, mc = _mc(df_laps, k)
    p10, p25, p50, p75, p90 = (np.array(mc[q]) for q in ("p10", "p25", "p50", "p75", "p90"))
    assert np.all(p10 <= p25 + 1e-9) and np.all(p25 <= p50 + 1e-9)
    assert np.all(p50 <= p75 + 1e-9) and np.all(p75 <= p90 + 1e-9)
    width = p90 - p10
    assert width.max() > 0.5, "band must not collapse to a line"
    # Upper half-band is never clipped by the best-lap floor, so it must not shrink with the
    # horizon (tolerance: 500 simulations of sampling noise).
    up = p90 - p50
    assert up[-3:].mean() >= up[:3].mean() - 0.3, "band should not narrow with the horizon"
    lo, hi = mc["clip_range_s"]
    assert p10.min() >= lo - 1e-6 and p90.max() <= hi + 1e-6
    assert lo >= sub["lap_time_s"].min() - 0.5 - 1e-6


@pytest.mark.parametrize("name", NAMES)
def test_stint_projection_never_beats_best_lap_by_more_than_clip(api, name):
    j = api("/api/stint/analyze", name)
    best = min(l["lap_time_s"] for l in j["laps"] if not l["is_pit_lap"])
    mc = j["montecarlo"]
    assert min(mc["p10"]) >= best - 0.5 - 1e-6
    assert abs(j["degradacion"]["tasa_s_per_lap"]) <= 0.15 + 1e-9


# ── tyre wear / degradation ──────────────────────────────────────────────────
def test_detect_wear_tracking_spa_inactive_imola_active(stint_inputs):
    from src.analytics.tyre_degradation import detect_wear_tracking
    spa = detect_wear_tracking(stint_inputs["spa_3laps"][0])
    assert spa["active"] is False and spa["evidence"]
    imola = detect_wear_tracking(stint_inputs["imola_5laps"][0])
    assert imola["active"] is True


def test_spa_reports_wear_off_instead_of_inventing_degradation(api):
    d = api("/api/stint/analyze", "spa_3laps")["degradacion_neumatico"]
    assert d["available"] is False and d["wear_tracking"] is False
    assert d.get("reason")


def test_imola_degradation_is_non_negative(api):
    d = api("/api/stint/analyze", "imola_5laps")["degradacion_neumatico"]
    assert d["available"] is True and d["wear_tracking"] is True
    assert d["degradation_rate_s_per_lap"] >= 0
    if d.get("wear_pct") is not None:
        assert 0 <= d["wear_pct"] <= 100
    if d.get("remaining_laps") is not None:
        assert d["remaining_laps"] >= 0


# ── optimal lap ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", NAMES)
def test_optimal_lap_ordering(api, name):
    r = api("/api/optimal-lap", name)
    assert r["available"] is True
    best = r["best_lap"]["time_s"]
    theo = r["optimal_theoretical"]["time_s"]
    real = r["optimal_realistic"]["time_s"]
    assert theo <= real + 1e-6, "theoretical optimum is a lower bound of the realistic one"
    assert real <= best + 1e-6, "realistic optimum cannot be slower than the best lap"
    assert 0 <= r["optimal_theoretical"]["gain_s"] < 0.06 * best, "gain must be plausible (<6 %)"
    assert r["realism_gap_s"] >= -1e-6
    assert r["n_laps_used"] >= 3
    assert abs(r["track_length_m"] - statistics.median(
        l["lap_distance"] for l in api("/api/analyze-session", name)["laps"] if not l["is_pit_lap"])) < 100


def test_optimal_lap_excludes_partial_segment(api):
    r = api("/api/optimal-lap", "spa_3laps")
    assert r["laps_used"] == [1, 2, 3]
    assert any(e["lap_number"] == 4 for e in r["laps_excluded"])


# ── JSON hygiene ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("path,kw", [
    ("/api/analyze-session", {}),
    ("/api/stint/analyze", {}),
    ("/api/optimal-lap", {}),
    ("/api/compare-session-laps", {"lap_a": 4, "lap_b": 3}),
])
def test_no_nan_or_inf_in_json(api, path, kw):
    # `api` already parses with parse_constant that rejects NaN/Infinity literals
    j = api(path, "imola_5laps", **kw)
    for p, v in _walk(j):
        if isinstance(v, float):
            assert math.isfinite(v), p


# ── ES / EN ──────────────────────────────────────────────────────────────────
def _key_paths(o, prefix=""):
    """Set of key paths; list items merged (union of their keys)."""
    out = set()
    if isinstance(o, dict):
        for k, v in o.items():
            out.add(prefix + "." + k)
            out |= _key_paths(v, prefix + "." + k)
    elif isinstance(o, list):
        for v in o:
            out |= _key_paths(v, prefix + "[]")
    return out


def test_es_en_responses_have_the_same_keys(api):
    es = api("/api/stint/analyze", "imola_5laps", "es")
    en = api("/api/stint/analyze", "imola_5laps", "en")
    ke, kn = _key_paths(es), _key_paths(en)
    # Free-form per-lap dictionaries aside, both languages must expose the same schema.
    assert ke == kn, sorted(ke ^ kn)[:20]
    assert es["data_quality"]["lang"] == "es" and en["data_quality"]["lang"] == "en"


def test_es_en_texts_actually_differ(api):
    es = api("/api/optimal-lap", "imola_5laps", "es")
    en = api("/api/optimal-lap", "imola_5laps", "en")
    assert es["explanation"] != en["explanation"]
    assert es["optimal_theoretical"]["time_s"] == en["optimal_theoretical"]["time_s"]


# ── PDF ──────────────────────────────────────────────────────────────────────
ES_WORDS = re.compile(r"\b(el|los|las|una|para|con|por|que|del|vuelta|curva|frenada|sesión|mejor|ritmo|más)\b", re.I)
EN_WORDS = re.compile(r"\b(the|and|with|for|of|lap|corner|braking|session|best|pace|is|are|your)\b", re.I)


@pytest.mark.parametrize("lang,own,foreign", [("es", ES_WORDS, EN_WORDS), ("en", EN_WORDS, ES_WORDS)])
def test_pdf_has_no_language_mixing(api, lang, own, foreign):
    fitz = pytest.importorskip("pymupdf")
    r = api("/api/report/pdf", "imola_5laps", lang, raw=True)
    assert r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
    doc = fitz.open(stream=r.content, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    n_own, n_foreign = len(own.findall(text)), len(foreign.findall(text))
    assert n_own > 40, "PDF has too little text in its own language"
    assert n_foreign <= 0.05 * n_own + 3, (lang, n_own, n_foreign)


# ── data quality ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name,n_laps", [("imola_5laps", 5), ("spa_3laps", 3)])
def test_data_quality_is_coherent(api, name, n_laps):
    dq = api("/api/stint/analyze", name)["data_quality"]
    assert dq["available"] is True
    assert 0 <= dq["score"] <= 100
    assert dq["level"] == ("good" if dq["score"] >= 75 else "fair" if dq["score"] >= 50 else "poor")
    w = sum(b["weight"] for b in dq["breakdown"].values())
    assert abs(w - 1.0) < 1e-9
    expected = round(sum(b["score"] * b["weight"] for b in dq["breakdown"].values()))
    assert abs(dq["score"] - expected) <= 3
    src = dq["source"]
    assert src["sim"] == "assetto_corsa"
    assert src["time_clock"] == "Session Time Left", "must not use the 0/1 'LR Sample Clock'"
    assert 9 <= src["sample_rate_hz"] <= 11
    assert src["n_channels"] > 40
    dist = next(c for c in dq["channels"] if c["key"] == "distance")
    assert dist["status"] == "synthesized" and dist["params"]["pct"] < 1.0
    cs = dq["channel_summary"]
    assert cs["ok"] + cs["warning"] + cs["missing"] == cs["total"] == len(dq["channels"])
    ms = dq["module_summary"]
    assert sum(ms.values()) == len(dq["modules"])


# ── setups parser (synthetic INI) ────────────────────────────────────────────
SETUP_INI = """[CAR]
MODEL=ks_test_car
[FRONT_BIAS]
VALUE=64
[PRESSURE_LF]
VALUE=26
[PRESSURE_RF]
VALUE=26
[CAMBER_LF]
VALUE=-30
[SPRING_RATE_LF]
VALUE=120000
"""


def test_setups_parse_endpoint_with_synthetic_ini(client, csv_dir):
    r = client.post("/api/setups/parse?lang=en", files={"file": ("last.ini", SETUP_INI.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["car_model"] == "ks_test_car"
    assert s["n_params"] == 5
    assert s["params"]["PRESSURE_LF"]["value"] == 26
    assert s["params"]["PRESSURE_LF"]["wheel"] == "FL"
    bad = client.post("/api/setups/parse", files={"file": ("x.exe", SETUP_INI.encode(), "text/plain")})
    assert bad.status_code == 400
    with open(csv_dir / "imola_5laps.csv", "rb") as fh:
        det = client.post("/api/setups/detect", files={"header": ("h.csv", fh.read(65536), "text/csv")})
    assert det.status_code == 200
    assert det.json()["venue"] == "fn_imola" and det.json()["driver"] == "Test Driver"


# ── real native files (only if present on this machine) ──────────────────────
_IR_DIR = os.path.join(os.path.expanduser("~"), "Documents", "iRacing", "Telemetry")
_REAL_NATIVE = sorted(glob.glob(os.path.join(_IR_DIR, "*oran south*20-15-58.ibt"))
                      + glob.glob(os.path.join(_IR_DIR, "*oran south*20-15-58_Stint_1.ld")))


@pytest.mark.skipif(not _REAL_NATIVE, reason="no real .ibt/.ld files on this machine")
@pytest.mark.parametrize("path", _REAL_NATIVE or ["-"])
def test_real_native_session_analyzes_without_nan(client, path):
    with open(path, "rb") as fh:
        r = client.post("/api/analyze-session?lang=en",
                        files={"session_file": (os.path.basename(path), fh.read(), "application/octet-stream")})
    assert r.status_code == 200, r.text[:300]
    j = json.loads(r.text, parse_constant=_no_constants)
    # this short outing may hold no complete lap: only require a clean, finite response
    assert isinstance(j["laps"], list)
    assert all(math.isfinite(l["lap_time"]) for l in j["laps"] if l["lap_time"] is not None)


# ── short-sample projection realism (real Imola, 5 laps) ─────────────────────
def test_imola5_projection_floor_and_widening(stint_inputs):
    """5 real laps (< 8): fuel effect alone must not push p50 under the best real lap
    (floor best-0.15 s), confidence stays low, and the band widens with the horizon."""
    _, df_laps = stint_inputs["imola_5laps"]
    _, deg, mc = _mc(df_laps, 5)
    best = float(df_laps["lap_time_s"].min())
    p10, p50, p90 = (np.array(mc[q]) for q in ("p10", "p50", "p90"))
    assert mc["confidence"] == "low" and deg["confidence"] == "low" and mc["low_confidence"]
    assert p50.min() >= best - 0.15 - 1e-6
    assert (p90[-1] - p10[-1]) > (p90[0] - p10[0]) + 0.5
    sigma = mc["sigma_real_s"]
    assert (p90 - p50)[-1] >= 0.9 * 1.2816 * sigma * math.sqrt(1 + 12 / 4) - 0.15
