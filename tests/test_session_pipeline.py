"""Regression tests for the session/stint pipeline fixes (synthetic data only)."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.brake_fade import _fade_zones
from src.analytics.insights import analizar_errores_por_curva
from src.analytics.slip_angle import _integrate_slip, lateral_sign_convention
from src.analytics.stint import (
    calcular_evolucion_pista,
    descartar_segmentos_parciales,
    extraer_metricas_por_vuelta,
    segmentar_vueltas_desde_csv,
)
from src.analytics.thermal_management import _analyse_brake_temps, _analyse_tyre_pressure
from src.analytics.thermodynamics import analizar_neumaticos
from src.io.loaders import DataLoaderException, _best_time_step, load_telemetry_data
from src.telemetry.metrics import pair_corners
from src.telemetry.session_analyzer import analyze_session


# ── helpers ───────────────────────────────────────────────────────────────────

def _session_df(n_laps=4, lap_s=60.0, hz=20, tail_s=0.0):
    """Multi-lap session with a real time clock, lap counter and per-lap distance reset."""
    rows = []
    t_total = 0.0
    for lap in range(n_laps):
        n = int(lap_s * hz)
        t = np.arange(n) / hz
        speed = 120 + 40 * np.sin(2 * np.pi * t / lap_s)
        rows.append(pd.DataFrame({
            "Speed": speed, "Brake": 0.0, "Throttle": 100.0,
            "LapTime": t, "SessionLapCount": float(lap),
            "Distance": np.cumsum(speed / 3.6 / hz),
        }))
        t_total += lap_s
    if tail_s:
        n = int(tail_s * hz)
        t = np.arange(n) / hz
        rows.append(pd.DataFrame({
            "Speed": 100.0, "Brake": 0.0, "Throttle": 100.0, "LapTime": t,
            "SessionLapCount": float(n_laps), "Distance": np.cumsum(np.full(n, 100 / 3.6 / hz)),
        }))
    return pd.concat(rows, ignore_index=True)


# ── 1. unified lap segmentation ───────────────────────────────────────────────

def test_partial_trailing_segment_dropped_everywhere():
    df = _session_df(n_laps=4, tail_s=8.0)  # 4 real laps + 8 s stub
    laps = segmentar_vueltas_desde_csv(df)
    assert len(laps) == 4
    assert len(extraer_metricas_por_vuelta(laps)) == 4
    assert analyze_session(df)["total_laps"] == 4  # same count in /analyze-session


def test_descartar_segmentos_parciales_keeps_all_if_too_few_remain():
    short = [_session_df(1, lap_s=10.0), _session_df(1, lap_s=12.0)]
    assert len(descartar_segmentos_parciales(short)) == 2


# ── 2. corner windows must not overlap ────────────────────────────────────────

def _aligned(n=1000):
    d = np.arange(n, dtype=float)
    return pd.DataFrame({
        "Distance": d,
        "Delta_Time": d * 0.001,
        "Speed_Fast": 150.0, "Speed_Slow": 145.0,
        "Brake_Fast": 0.0, "Brake_Slow": 0.0,
        "Throttle_Fast": 100.0, "Throttle_Slow": 100.0,
    })


def test_corner_windows_do_not_overlap_and_keep_all_corners():
    apexes = pd.DataFrame({"Distance": [300.0, 380.0, 700.0], "Curvature": 0.02})
    out = analizar_errores_por_curva(_aligned(), apexes)
    assert [c["corner_number"] for c in out] == [1, 2, 3]
    for a, b in zip(out, out[1:]):
        assert a["end_distance"] <= b["start_distance"]
    # disjoint windows => summed loss can never exceed the total delta (1.0 s here)
    assert sum(c["time_loss_seconds"] for c in out) <= 1.0 + 1e-6


def test_braking_delta_uses_main_brake_zone_not_window_edge():
    df = _aligned()
    # Brake zone starts 180 m before the apex (outside the old 100 m window) for both
    # laps, B starts 20 m earlier. Old code reported 0.0 (both clipped to the window).
    df.loc[(df.Distance >= 420) & (df.Distance < 590), "Brake_Fast"] = 80.0
    df.loc[(df.Distance >= 400) & (df.Distance < 590), "Brake_Slow"] = 80.0
    out = analizar_errores_por_curva(df, pd.DataFrame({"Distance": [600.0], "Curvature": 0.02}))
    assert out[0]["braking_delta_meters"] == pytest.approx(20.0, abs=1.5)
    assert out[0]["braking_delta_available"] is True


def test_braking_delta_flagged_unavailable_when_no_braking():
    out = analizar_errores_por_curva(_aligned(), pd.DataFrame({"Distance": [500.0], "Curvature": 0.02}))
    assert out[0]["braking_delta_meters"] == 0.0
    assert out[0]["braking_delta_available"] is False


def test_pair_corners_matches_by_apex_not_index():
    mk = lambda d: {"apex": {"distance": d}}
    ref = [mk(500), mk(1000), mk(1500)]
    other = [mk(1005), mk(1498)]            # corner at 500 missed in this lap
    pairs = pair_corners(ref, other)
    assert [p[0] for p in pairs] == [1, 2]  # ref corners 2 and 3, not 1 and 2
    assert pairs[0][2]["apex"]["distance"] == 1005


# ── 3/4. channel handling ─────────────────────────────────────────────────────

def test_slip_angle_sign_convention_autodetected():
    n = 400
    t = np.arange(n) / 10
    yaw = 0.3 * np.sin(t)                        # rad/s
    speed = pd.Series(np.full(n, 100.0))          # km/h
    vx = speed / 3.6
    ay_g = pd.Series(yaw * vx / 9.80665)          # consistent convention
    beta_ok = _integrate_slip(speed, ay_g, pd.Series(yaw))
    beta_flipped = _integrate_slip(speed, -ay_g, pd.Series(yaw))   # AC-style opposite sign
    assert lateral_sign_convention(-ay_g * 9.80665, pd.Series(yaw), vx) == -1.0
    assert beta_ok.abs().max() < 5
    assert beta_flipped.abs().max() < 5          # used to diverge to tens of degrees


def test_fade_zones_ignore_leading_nan():
    d = pd.Series(np.arange(100, dtype=float))
    eff = pd.Series(np.nan, index=d.index)
    eff.iloc[50:60] = 1.0
    assert _fade_zones(d, eff, baseline=1.0) == []   # no bogus zone from lap start


def test_tyre_core_channel_is_found():
    df = pd.DataFrame({f"TyreTempCore{c}_Fast": [90.0] * 20 for c in ("FL", "FR", "RL", "RR")})
    for c in ("FL", "FR", "RL", "RR"):
        df[f"TyreTempMiddle{c}_Fast"] = 95.0
    res = analizar_neumaticos(df, suffix="_Fast")
    assert res["corners"][0]["core_mean"] == 90.0


def test_constant_brake_temp_channel_reports_reason():
    dfs = [pd.DataFrame({f"BrakeTemp{c}": [26.0] * 50 for c in ("FL", "FR", "RL", "RR")})] * 3
    res = _analyse_brake_temps(dfs)
    assert res["available"] is False and "constant" in res["reason"]


def test_missing_brake_temp_channel_reports_reason():
    res = _analyse_brake_temps([pd.DataFrame({"Speed": [1.0] * 5})])
    assert res["available"] is False and res["reason"]


def test_tyre_pressure_without_cold_channel_gives_no_advice():
    dfs = [pd.DataFrame({f"TyrePress{c}": np.linspace(1.5, 1.6, 100) for c in ("FL", "FR", "RL", "RR")})] * 3
    res = _analyse_tyre_pressure(dfs)
    assert res["available"] and res["recommendations"] == []
    assert "cold" not in res["corners"]["FL"]


def test_track_evolution_uses_lap_time_s():
    df_laps = pd.DataFrame({
        "lap_number": range(1, 9),
        "lap_time_s": [100, 99.5, 99.2, 99.0, 98.8, 98.7, 98.5, 98.4],
        "is_pit_lap": False,
    })
    res = calcular_evolucion_pista(df_laps)
    assert res["available"] and res["direction"] == "improving"
    assert calcular_evolucion_pista(df_laps.head(2))["available"] is False


def test_health_summary_recognises_stint_and_compare_keys():
    from main import _build_health_summary
    res = _build_health_summary({
        "thermal_analysis": {"available": True},
        "setup_sesion": {"available": False},          # truthy dict but unavailable
        "degradacion_neumatico": {"available": True},
        "racing_line_rl": {"available": True},
        "slip_angle": {"available": True},
        "curvas_sesion": {"available": True},
    })
    assert res["setup"] == "unavailable"
    assert res["tyre_degradation"] == res["racing_line"] == res["slip"] == res["corners"] == "ok"


# ── distance synthesis / loader validation ───────────────────────────────────

def test_square_wave_clock_is_not_used_for_distance():
    n = 400
    df = pd.DataFrame({
        "LR Sample Clock": (np.arange(n) // 10 % 2).astype(float),   # 0/1 square wave
        "Session Time Left": -(np.arange(n) * 0.05),
    })
    col, dt = _best_time_step(df)
    assert col == "Session Time Left"
    assert dt.iloc[1:].median() == pytest.approx(0.05)


def test_loader_rejects_empty_and_missing_channels(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(DataLoaderException, match="vacío"):
        load_telemetry_data(str(empty))

    nochan = tmp_path / "nochan.csv"
    nochan.write_text("a,b\n1,2\n")
    with pytest.raises(DataLoaderException, match="esenciales"):
        load_telemetry_data(str(nochan))

    text = tmp_path / "text.csv"
    text.write_text("Speed,Brake,Throttle\nx,y,z\nq,w,e\n")
    with pytest.raises(DataLoaderException, match="numéricos"):
        load_telemetry_data(str(text))


def test_analyze_session_single_lap_returns_message():
    res = analyze_session(_session_df(n_laps=1))
    assert res["total_laps"] == 0 and res["message"]
