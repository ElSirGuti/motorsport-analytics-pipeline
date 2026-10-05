"""Wear measured by the simulator (rubber grip) and laps with incidents left out of the pace trend."""
import numpy as np
import pandas as pd

from src.analytics.stint import extraer_metricas_por_vuelta, _projection_laps
from src.analytics.tyre_degradation import detect_wear_tracking, measure_rubber_grip, predecir_degradacion_neumatico


def _lap(i, grip_start, grip_end, wear_rate=1.0, n=400):
    t = np.arange(n) / 20.0
    d = pd.DataFrame({"Time": t, "Distance": np.linspace(0, 3000, n), "Speed": np.full(n, 150.0),
                      "Throttle": np.full(n, 80.0), "Brake": np.zeros(n), "LapTime": t,
                      "SessionLapCount": np.full(n, float(i))})
    for w in ("FL", "FR", "RL", "RR"):
        d[f"TyreGrip{w}"] = np.linspace(grip_start, grip_end, n)
    d["TireWearRate"] = wear_rate
    return d


def _session(loss_per_lap, n_laps=6, **kw):
    return [_lap(i, 100 - loss_per_lap * i, 100 - loss_per_lap * (i + 1), **kw) for i in range(n_laps)]


def test_wear_detected_from_grip_channels_under_the_loader_names():
    assert detect_wear_tracking(_session(0.05))["active"] is True      # 0.3 % over the session is real wear
    assert detect_wear_tracking(_session(0.0, wear_rate=0.0))["active"] is False


def test_measure_rubber_grip_levels_and_numbers():
    g = measure_rubber_grip(_session(0.05))
    assert g["available"] and g["level"] == "minimal"
    assert abs(g["loss_pct"] - 0.30) < 0.01 and abs(g["loss_pct_per_lap"] - 0.05) < 0.01 and g["n_laps"] == 6
    assert set(g["per_tyre"]) == {"FL", "FR", "RL", "RR"}
    assert measure_rubber_grip(_session(0.3))["level"] == "moderate"
    assert measure_rubber_grip(_session(1.0))["level"] == "high"
    assert measure_rubber_grip([pd.DataFrame({"Speed": [1.0, 2.0]})] * 3) == {"available": False}


def test_measured_wear_is_reported_even_when_lap_times_show_nothing():
    laps = _session(0.4, n_laps=8)
    df_laps = extraer_metricas_por_vuelta(laps)
    r = predecir_degradacion_neumatico(laps, df_laps)
    assert r["grip_measured"]["available"] and r["grip_measured"]["level"] == "moderate"
    assert r["wear_tracking"] is True
    assert r["wear_rate"] == 1.0
    if not r.get("degradation_detected"):
        assert "grip" in r["reason"].lower()                              # the measured figure is in the explanation


def test_incident_laps_are_left_out_of_the_trend_and_reported():
    laps = _session(0.05, n_laps=8)
    df_laps = extraer_metricas_por_vuelta(laps)
    df_laps["is_incident_lap"] = [i in (1, 2) for i in range(len(df_laps))]
    kept = set(_projection_laps(df_laps)["lap_number"].astype(int))
    assert 2 not in kept and 3 not in kept                                # lap numbers are 1-based: indexes 1, 2
    r = predecir_degradacion_neumatico(laps, df_laps)
    assert r["incident_laps_excluded"] == [2, 3]
