"""Optimal lap by microsectors: synthetic laps with known best microsectors."""

import io
import json

import numpy as np
import pandas as pd
import pytest

from src.analytics.optimal_lap import calcular_vuelta_optima, calcular_vuelta_optima_desde_df

L = 3000.0
N_ZONES = 6
ZONE = L / N_ZONES
BASE_KMH = 150.0


def _lap(k, mode="smooth", length_scale=1.0, coords=True, slowdown=0.0):
    """
    Lap k (0-based) is faster than the others in zone k only.
    mode "smooth": the speed bonus vanishes at the zone edges.
    mode "step":   abrupt speed steps at the zone edges.
    """
    d = np.arange(0.0, L, 2.0)
    zone = np.minimum((d // ZONE).astype(int), N_ZONES - 1)
    x_in = (d % ZONE) / ZONE
    if mode == "smooth":
        f = np.where(zone == k, 1.0 + 0.08 * np.sin(np.pi * x_in) ** 2, 1.0)
    else:
        f = np.where(zone == k, 1.06, 0.97)
    f = f * (1.0 - 0.001 * k) * (1.0 - slowdown)
    v = BASE_KMH * f
    t = np.cumsum(2.0 / (v / 3.6))
    t = t - t[0] + 0.05
    out = pd.DataFrame({"Distance": d * length_scale, "Speed": v, "LapTime": t})
    if coords:
        ang = 2 * np.pi * d / L
        r = L / (2 * np.pi)
        out["CarCoordX"] = r * np.cos(ang)
        out["CarCoordY"] = r * np.sin(ang)
        out["CarCoordZ"] = 0.0
    return out


def _expected_theoretical_gain(mode):
    """Lap 1 (the fastest) minus the sum of the per-zone minimum times."""
    zt = []
    for k in range(N_ZONES):
        lap = _lap(k, mode, coords=False)
        z = np.minimum((lap["Distance"].to_numpy() // ZONE).astype(int), N_ZONES - 1)
        dt = np.diff(lap["LapTime"].to_numpy(), prepend=0.05)
        zt.append([dt[z == zz].sum() for zz in range(N_ZONES)])
    zt = np.array(zt)
    return float(zt[0].sum() - zt.min(axis=0).sum())


@pytest.fixture
def smooth_laps():
    return [_lap(k, "smooth") for k in range(N_ZONES)]


def _session_df():
    rows = []
    for k in range(N_ZONES):
        lap = _lap(k, "smooth")
        lap["SessionLapCount"] = float(k)
        lap["Brake"] = 0.0
        lap["Throttle"] = 100.0
        rows.append(lap)
    return pd.concat(rows, ignore_index=True)


def test_theoretical_gain_matches_known_best_microsectors(smooth_laps):
    r = calcular_vuelta_optima(smooth_laps, lang="en")
    assert r["available"]
    assert r["best_lap"]["lap_number"] == 1
    assert r["optimal_theoretical"]["gain_s"] == pytest.approx(_expected_theoretical_gain("smooth"), abs=0.05)
    assert r["optimal_theoretical"]["gain_s"] > 1.0
    assert r["optimal_theoretical"]["time_s"] == pytest.approx(
        r["best_lap"]["time_s"] - r["optimal_theoretical"]["gain_s"], abs=0.001)
    # each zone's microsectors must come from the lap that is faster there
    by_zone = {}
    for m in r["microsectors"]:
        z = min(int(((m["d_start"] + m["d_end"]) / 2) // ZONE), N_ZONES - 1)
        by_zone.setdefault(z, []).append(m["lap_theoretical"])
    for z, laps in by_zone.items():
        assert max(set(laps), key=laps.count) == z + 1
    assert r["corners"] == [] or all("label" in c for c in r["corners"])


def test_realistic_between_best_and_theoretical(smooth_laps):
    r = calcular_vuelta_optima(smooth_laps, lang="en")
    th, re = r["optimal_theoretical"], r["optimal_realistic"]
    assert th["time_s"] <= re["time_s"] <= r["best_lap"]["time_s"]
    assert 0 <= re["gain_s"] <= th["gain_s"]
    assert r["realism_gap_s"] == pytest.approx(th["gain_s"] - re["gain_s"], abs=0.002)
    # speeds match at the zone edges, so most of the theoretical gain is reachable
    assert re["gain_s"] > 0.7 * th["gain_s"]
    assert re["n_switches"] >= 1


def _lap_zones(speeds, eps=0.0):
    d = np.arange(0.0, L, 2.0)
    zone = np.minimum((d // ZONE).astype(int), N_ZONES - 1)
    v = np.array(speeds, dtype=float)[zone] * (1.0 - eps)
    t = np.cumsum(2.0 / (v / 3.6)) + 0.05
    ang = 2 * np.pi * d / L
    r = L / (2 * np.pi)
    return pd.DataFrame({"Distance": d, "Speed": v, "LapTime": t,
                         "CarCoordX": r * np.cos(ang), "CarCoordY": r * np.sin(ang), "CarCoordZ": 0.0})


def test_realistic_is_limited_by_speed_continuity_and_tolerance():
    # Alternating 160/140 km/h zones: the laps are rarely within 3 km/h of each other, so
    # the theoretical optimum (160 everywhere) is mostly unreachable by combining them.
    laps = [_lap_zones([160, 140] * 3), _lap_zones([140, 160] * 3, eps=0.001), _lap_zones([150] * 6, eps=0.002)]
    r = calcular_vuelta_optima(laps, lang="en")
    th, re = r["optimal_theoretical"]["gain_s"], r["optimal_realistic"]["gain_s"]
    assert th > 3.0
    assert re < 0.5 * th
    assert r["realism_gap_s"] > 0.5 * th
    assert "lower bound" in r["explanation"]
    # a very loose tolerance lets every lap change through: realistic approaches theoretical
    loose = calcular_vuelta_optima(laps, lang="en", speed_tol_kmh=40.0)
    assert loose["optimal_realistic"]["gain_s"] > 0.9 * th
    assert loose["optimal_realistic"]["gain_s"] > re


def test_series_shapes_and_cumulative_gain(smooth_laps):
    r = calcular_vuelta_optima(smooth_laps, lang="en")
    cum = r["series"]["cumulative"]
    assert len(cum["distance"]) == r["n_microsectors"] + 1
    assert cum["gain_theoretical_s"][-1] == pytest.approx(r["optimal_theoretical"]["gain_s"], abs=0.002)
    assert cum["gain_realistic_s"][-1] == pytest.approx(r["optimal_realistic"]["gain_s"], abs=0.002)
    assert cum["gain_theoretical_s"][0] == 0
    sp = r["series"]["speed_profile"]
    assert len(sp["distance"]) == len(sp["optimal_realistic"]) == len(sp["best_lap"])
    assert len(r["track"]) == r["n_microsectors"] + 1
    assert sum(c["microsectors_realistic"] for c in r["lap_contributions"]) == r["n_microsectors"]
    assert 1 <= len(r["top_zones"]) <= 10
    assert [z["rank"] for z in r["top_zones"]] == list(range(1, len(r["top_zones"]) + 1))
    losses = [z["loss_realistic_s"] for z in r["top_zones"]]
    assert losses == sorted(losses, reverse=True)


def test_microsector_size_is_configurable(smooth_laps):
    r50 = calcular_vuelta_optima(smooth_laps, microsector_m=50, lang="en")
    r25 = calcular_vuelta_optima(smooth_laps, microsector_m=25, lang="en")
    assert r50["n_microsectors"] == pytest.approx(r25["n_microsectors"] / 2, abs=1)
    assert r50["params"]["microsector_m"] == 50


def test_too_few_laps_is_unavailable_and_translated():
    laps = [_lap(0), _lap(1)]
    es = calcular_vuelta_optima(laps, lang="es")
    en = calcular_vuelta_optima(laps, lang="en")
    assert es["available"] is False and en["available"] is False
    assert "vueltas" in es["reason"] and "laps" in en["reason"]
    assert es["reason"] != en["reason"]


def test_pit_slow_and_partial_laps_are_excluded(smooth_laps):
    pit = _lap(2, "smooth")
    pit["In Pit"] = 1.0
    slow = _lap(3, "smooth", slowdown=0.25)
    partial = _lap(4, "smooth").iloc[: len(smooth_laps[0]) // 2].reset_index(drop=True)
    laps = [smooth_laps[0], smooth_laps[1], pit, slow, partial, smooth_laps[5], _lap(1, "smooth")]
    r = calcular_vuelta_optima(laps, lang="en")
    assert r["available"]
    excl = {e["lap_number"]: e["code"] for e in r["laps_excluded"]}
    assert excl[3] == "pit"
    assert {4, 5}.issubset(excl)
    assert set(r["laps_used"]).isdisjoint({3, 4, 5})


@pytest.mark.parametrize("coords", [True, False])
def test_laps_with_slightly_different_length_are_aligned(coords):
    laps = [_lap(k, "smooth", length_scale=1.0 + 0.004 * (k % 3), coords=coords) for k in range(N_ZONES)]
    r = calcular_vuelta_optima(laps, lang="en", distance_synthetic=True)
    assert r["available"]
    assert r["alignment"] == ("position" if coords else "distance")
    assert r["n_laps_used"] == N_ZONES
    assert r["optimal_theoretical"]["gain_s"] > 1.0
    assert any("synthes" in w.lower() for w in r["warnings"])


def test_few_laps_warning():
    r = calcular_vuelta_optima([_lap(k) for k in range(4)], lang="es")
    assert r["available"] and r["warnings"]


def test_session_wrapper_is_json_safe():
    r = calcular_vuelta_optima_desde_df(_session_df(), lang="en")
    assert r["available"] and r["n_laps_used"] == N_ZONES
    json.dumps(r, allow_nan=False)


def test_endpoint_returns_result_and_translated_unavailable():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    import main

    client = TestClient(main.app)
    df = _session_df()
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    r = client.post("/api/optimal-lap?lang=en",
                    files={"session_file": ("s.csv", buf.getvalue().encode(), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] and body["optimal_theoretical"]["gain_s"] > 1.0

    buf2 = io.StringIO()
    df[df["SessionLapCount"] < 2].to_csv(buf2, index=False)
    r = client.post("/api/optimal-lap", data={"lang": "es"},
                    files={"session_file": ("s.csv", buf2.getvalue().encode(), "text/csv")})
    assert r.status_code == 200
    assert r.json()["available"] is False and "vueltas" in r.json()["reason"]
