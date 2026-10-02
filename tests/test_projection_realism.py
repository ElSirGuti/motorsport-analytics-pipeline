"""Realism of the stint Monte Carlo projection and plausibility of corner deltas (synthetic data)."""

import numpy as np
import pandas as pd

from src.analytics.session_corner_analysis import analizar_curvas_sesion
from src.analytics.stint import analizar_degradacion_stint, simular_tiempos_stint
from src.telemetry.metrics import BRAKE_MAX_WINDOW_M, segment_corners


def _laps_df(times, fuel_burned=0.0):
    return pd.DataFrame({
        "lap_number": range(1, len(times) + 1),
        "lap_time_s": times,
        "is_pit_lap": False,
        "max_g_sum": 1.5,
        "fuel_burned": fuel_burned,
    })


def test_three_laps_do_not_extrapolate_steep_slope():
    # The real-world case: 2:35.0, 2:34.0, 2:33.4 -> raw OLS slope ~ -0.8 s/lap
    df = _laps_df([155.06, 154.065, 153.415])
    deg = analizar_degradacion_stint(df)
    mc = simular_tiempos_stint(df, deg)

    assert deg["available"] and mc["available"]
    assert deg["raw_slope_s_per_lap"] < -0.5          # the raw fit is steep...
    assert abs(deg["tasa_s_per_lap"]) <= 0.15         # ...but never projected
    assert deg["low_confidence"] is True and mc["low_confidence"] is True
    assert deg["confidence"] == "low" and deg["n_laps_used"] == 3
    assert deg["reason"] and mc["reason"]
    assert deg["slope_ci"][0] < deg["slope_ci"][1]

    best = min(df["lap_time_s"])
    assert min(mc["p10"]) >= best - 0.6               # never ~12 s faster than any real lap
    assert max(mc["p90"]) <= max(df["lap_time_s"]) + 3.0
    assert max(deg["projected_times"]) - min(deg["projected_times"]) < 0.2


def test_fifteen_laps_recover_known_degradation():
    rng = np.random.default_rng(1)
    true_slope = 0.06
    laps = np.arange(1, 16)
    times = 120.0 + true_slope * laps + rng.normal(0, 0.1, size=15)
    df = _laps_df(times.tolist())
    deg = analizar_degradacion_stint(df)
    mc = simular_tiempos_stint(df, deg)

    assert deg["n_laps_used"] >= 14                   # first lap may be dropped as out-lap
    assert deg["confidence"] in ("medium", "high")
    assert not deg["low_confidence"]
    assert abs(deg["tasa_s_per_lap"] - true_slope) < 0.03
    lo, hi = deg["slope_ci"]
    assert lo <= true_slope <= hi
    # Median projection keeps rising slowly and the band widens with the horizon
    assert mc["p50"][-1] > mc["p50"][0]
    w_first = mc["p90"][0] - mc["p10"][0]
    w_last = mc["p90"][-1] - mc["p10"][-1]
    assert w_last > w_first


def test_fuel_effect_modelled_explicitly():
    # 1.7 L/lap burned -> about -0.06 s/lap from fuel mass alone
    rng = np.random.default_rng(2)
    laps = np.arange(1, 13)
    times = 100.0 - 0.06 * laps + rng.normal(0, 0.05, size=12)
    deg = analizar_degradacion_stint(_laps_df(times.tolist(), fuel_burned=1.7))
    assert deg["fuel_effect_s_per_lap"] < -0.05
    assert abs(deg["degradation_s_per_lap"]) < 0.05    # nothing left to blame on tyres


def _corner_obs(brake_delta):
    return {2: [{"time_loss": 0.1, "brake_delta": brake_delta, "apex_delta": -2.0, "thtl_delta": 3.0},
                {"time_loss": 0.2, "brake_delta": brake_delta, "apex_delta": -3.0, "thtl_delta": 5.0}]}


def test_implausible_brake_delta_marked_not_measurable():
    df_laps = pd.DataFrame({"is_pit_lap": [False, False, False],
                            "lap_time_s": [100.0, 101.0, 102.0],
                            "lap_number": [1, 2, 3]})
    res = analizar_curvas_sesion([None] * 3, df_laps, lang="en", precomputed_obs=_corner_obs(-593.0))
    c = res["corners"][0]
    assert c["braking_available"] is False
    assert abs(c["braking_delta_meters"]) < 1e-9
    assert "braking" not in c["description"].lower()
    assert c["apex_available"] is True

    ok = analizar_curvas_sesion([None] * 3, df_laps, lang="en", precomputed_obs=_corner_obs(-25.0))
    assert ok["corners"][0]["braking_available"] is True
    assert ok["corners"][0]["braking_delta_meters"] == -25.0


def test_brake_point_beyond_window_is_not_used():
    # Brake applied 1000 m before the only apex (previous straight): must not be paired.
    n = 2000
    dist = np.arange(n, dtype=float)
    speed = np.full(n, 200.0)
    speed[1500:1700] = 200.0 - 120.0 * np.exp(-((np.arange(200) - 100) ** 2) / (2 * 25.0 ** 2))
    brake = np.zeros(n)
    brake[400:450] = 80.0
    throttle = np.full(n, 100.0)
    df = pd.DataFrame({"Distance": dist, "Speed": speed, "Brake": brake, "Throttle": throttle})
    assert 1600 - 450 > BRAKE_MAX_WINDOW_M
    for c in segment_corners(df):
        assert c["apex"]["distance"] - c["braking_point"]["distance"] <= BRAKE_MAX_WINDOW_M


# ── tyre degradation panel ───────────────────────────────────────────────────

def _tyre_dfs(n, wear_rate=0.0, grip=None):
    out = []
    for i in range(n):
        d = pd.DataFrame({"Speed": np.full(50, 150.0), "LateralG": np.full(50, 1.0),
                          "AID Tire Wear Rate": np.full(50, wear_rate)})
        if grip is not None:
            d["Tire Rubber Grip FL"] = grip(i)
        out.append(d)
    return out


def test_tyre_wear_disabled_returns_unavailable():
    from src.analytics.tyre_degradation import predecir_degradacion_neumatico
    times = [155.06, 154.065, 153.415, 153.0, 152.9, 152.8, 152.7]
    res = predecir_degradacion_neumatico(_tyre_dfs(7, wear_rate=0.0), _laps_df(times))
    assert res["available"] is False and res["wear_tracking"] is False
    assert res["reason"] and "projection" not in res and "top_wear_factors" not in res


def test_tyre_three_laps_with_wear_not_projected():
    from src.analytics.tyre_degradation import predecir_degradacion_neumatico
    res = predecir_degradacion_neumatico(_tyre_dfs(3, wear_rate=1.0), _laps_df([155.06, 154.065, 153.415]))
    assert res["available"] is False and res["low_confidence"] is True
    assert res["n_laps_used"] == 3 and res["reason"]


def test_tyre_negative_trend_is_not_degradation():
    from src.analytics.tyre_degradation import predecir_degradacion_neumatico
    times = (100.0 - 0.2 * np.arange(1, 13)).tolist()
    res = predecir_degradacion_neumatico(_tyre_dfs(12, wear_rate=1.0), _laps_df(times))
    assert res["available"] and res["degradation_rate_s_per_lap"] >= 0
    assert res["degradation_detected"] is False and res["remaining_laps"] is None
    assert res["wear_pct"] is None
    assert all(p["projected"] >= res["lap_data"][-1]["trend"] - 1e-9 for p in res["projection"])


def test_tyre_real_degradation_detected_and_consistent_with_stint():
    from src.analytics.tyre_degradation import predecir_degradacion_neumatico
    rng = np.random.default_rng(3)
    laps = np.arange(1, 17)
    times = (120.0 + 0.08 * laps + rng.normal(0, 0.05, 16)).tolist()
    df = _laps_df(times)
    res = predecir_degradacion_neumatico(_tyre_dfs(16, wear_rate=1.0), df)
    st = analizar_degradacion_stint(df)
    assert res["degradation_detected"] is True
    assert abs(res["degradation_rate_s_per_lap"] - 0.08) < 0.03
    assert abs(res["degradation_rate_s_per_lap"] - st["degradation_s_per_lap"]) < 1e-6
    proj = [p["projected"] for p in res["projection"]]
    assert proj == sorted(proj)
    assert res["remaining_laps"] is not None
    assert res["top_wear_factors"] is not None
    assert all(p["p90"] - p["p10"] >= 0 for p in res["projection"])
