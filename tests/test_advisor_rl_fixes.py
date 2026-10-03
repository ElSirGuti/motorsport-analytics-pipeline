"""Regression tests for the bugs found while reconciling docs 16/17 with the code (synthetic data).

1. racing_line_rl: heatmap ``count`` counted training epochs, not observations.
2. racing_line_rl: throttle-axis labels / recommendation were inverted (positive thtl_delta = LATER).
3. setup_advisor: "high degradation" session rule unreachable (threshold above the clamped slope).
4. setup_advisor: lap and session modes gave opposite camber / pressure advice for the same sign.
5. setup_advisor: the ``lang`` argument was ignored (language came only from the i18n context).
"""
import numpy as np
import pandas as pd

from src import i18n
from src.analytics import setup_advisor as sa
from src.analytics.racing_line_rl import optimizar_trazada_rl
from src.analytics.session_corner_analysis import get_corner_observations


# ── 1. heatmap count ─────────────────────────────────────────────────────────

def _obs(rows):
    return {1: [{"time_loss": tl, "brake_delta": b, "apex_delta": a, "thtl_delta": th}
                for tl, b, a, th in rows]}


def test_heatmap_count_is_number_of_observations_not_epochs():
    obs = _obs([(0.30, 0.0, 0.0, 0.0), (0.20, 0.0, 0.0, 0.0), (0.10, 20.0, 5.0, 0.0),
                (0.05, 0.0, 0.0, 20.0)])
    res = optimizar_trazada_rl([], None, precomputed_obs=obs)
    corner = res["corners"][0]
    cells = {(c["brake"], c["apex"]): c["count"] for c in corner["q_heatmap"]}
    assert cells[("similar", "similar")] == 3     # 2 laps in thtl 'similar' + 1 in thtl 'late'
    assert cells[("late", "fast")] == 1           # was 30 before the fix
    assert sum(cells.values()) == len(obs[1]) == corner["n_laps"]


# ── 2. throttle axis ─────────────────────────────────────────────────────────

def _corner_lap(throttle_full_at, n=2000):
    """One corner: brake 700-750, apex ~800, full throttle reached at `throttle_full_at`."""
    dist = np.arange(n, dtype=float)
    speed = np.full(n, 200.0)
    speed[700:900] = 200.0 - 120.0 * np.exp(-((np.arange(200) - 100) ** 2) / (2 * 25.0 ** 2))
    brake = np.zeros(n)
    brake[700:750] = 80.0
    throttle = np.full(n, 100.0)
    throttle[700:throttle_full_at] = 20.0
    return pd.DataFrame({"Distance": dist, "Speed": speed, "Brake": brake, "Throttle": throttle})


def test_thtl_delta_positive_means_later_throttle_through_the_chain():
    ref = _corner_lap(850)
    later = _corner_lap(880)       # gets on the power 30 m LATER than the reference
    earlier = _corner_lap(830)     # 20 m EARLIER
    dfs = [ref, later, earlier]
    df_laps = pd.DataFrame({"is_pit_lap": [False] * 3, "lap_time_s": [90.0, 91.0, 90.5],
                            "lap_number": [1, 2, 3]})
    obs = get_corner_observations(dfs, df_laps)
    deltas = sorted(o["thtl_delta"] for o in obs[1])
    assert deltas[0] < -10 and deltas[-1] > 10          # earlier -> negative, later -> positive

    # ... and the discretised labels / recommendation say the same thing
    i18n.set_language("en")
    base = {"brake_delta": 0.0, "apex_delta": 0.0}
    # best pattern = throttle LATER (+30 m); the driver's recent laps are 'similar'
    late_best = {1: [dict(base, time_loss=0.5, thtl_delta=0.0)] * 3
                 + [dict(base, time_loss=0.0, thtl_delta=30.0)] * 1 + [dict(base, time_loss=0.5, thtl_delta=0.0)] * 3}
    r = optimizar_trazada_rl([], None, precomputed_obs=late_best)["corners"][0]
    assert r["optimal_execution"]["exit"] == "late"
    assert r["recommendations"] == ["Apply throttle later"]
    # best pattern = throttle EARLIER (-30 m)
    early_best = {1: [dict(base, time_loss=0.5, thtl_delta=0.0)] * 3
                  + [dict(base, time_loss=0.0, thtl_delta=-30.0)] + [dict(base, time_loss=0.5, thtl_delta=0.0)] * 3}
    r = optimizar_trazada_rl([], None, precomputed_obs=early_best)["corners"][0]
    assert r["optimal_execution"]["exit"] == "early"
    assert r["recommendations"] == ["Apply throttle earlier"]


# ── 3. degradation rule ──────────────────────────────────────────────────────

def _deg(**kw):
    d = {"available": True, "tasa_s_per_lap": 0.15, "degradation_s_per_lap": 0.15,
         "fuel_effect_s_per_lap": 0.0, "r_squared": 0.9, "low_confidence": False, "n_laps_used": 15}
    d.update(kw)
    return d


def _deg_keys(deg, **kw):
    return [r["problem_key"] for r in sa._analyse_degradacion_ritmo(deg, **kw)]


def test_high_degradation_rule_reachable_at_the_clamped_slope():
    assert _deg_keys(_deg(tasa_s_per_lap=0.15, degradation_s_per_lap=0.15)) == ["setup_problem_degradation_high"]


def test_degradation_uses_net_rate_without_fuel():
    # Gross slope 0.0 looks like "no degradation" but fuel burn (-0.10) hides 0.10 s/lap of real wear.
    deg = _deg(tasa_s_per_lap=0.0, degradation_s_per_lap=0.14, fuel_effect_s_per_lap=-0.14)
    assert _deg_keys(deg) == ["setup_problem_degradation_high"]
    # Gross slope looks large but it is all track/fuel-independent ... net ~0 -> no advice
    assert _deg_keys(_deg(tasa_s_per_lap=0.10, degradation_s_per_lap=0.01, fuel_effect_s_per_lap=0.09)) == []


def test_degradation_falls_back_to_gross_when_net_field_missing():
    d = _deg(tasa_s_per_lap=0.13)
    del d["degradation_s_per_lap"]
    assert _deg_keys(d) == ["setup_problem_degradation_high"]


def test_degradation_ignored_with_insufficient_sample_or_wear_off():
    assert _deg_keys(_deg(low_confidence=True)) == []
    assert _deg_keys(_deg(n_laps_used=3)) == []
    assert _deg_keys(_deg(), wear_active=False) == []
    assert _deg_keys(_deg(), wear_active=True) == ["setup_problem_degradation_high"]


def test_moderate_degradation_band():
    assert _deg_keys(_deg(tasa_s_per_lap=0.09, degradation_s_per_lap=0.09, r_squared=0.6)) == \
        ["setup_problem_degradation_moderate"]


# ── 4. lap vs session coherence ──────────────────────────────────────────────

_CAMBER_REDUCE = {"setup_rec_camber_reduce", "setup_rec_camber_excess"}
_CAMBER_ADD = {"setup_rec_camber_add", "setup_rec_camber_insufficient"}
_P_RAISE = {"setup_rec_pressure_raise"}
_P_LOWER = {"setup_rec_pressure_lower"}


def _lap_tyre(inner, middle, outer, status="optima", surf=85.0):
    return {"tyre_analysis": {"available": True, "lap_a": {"corners": [
        {"corner": "FL", "inner": inner, "middle": middle, "outer": outer,
         "window_status": status, "surface_mean": surf}]}}}


def _lap_keys(res):
    return {r["rec_key"] for r in sa._analyse_tyres(res)}


def _ses_keys(tyre):
    return {r["rec_key"] for r in sa._analyse_tyres_sesion({"tyre": {"FL": tyre}})}


def test_camber_inner_hotter_means_reduce_negative_camber_in_both_modes():
    lap = _lap_keys(_lap_tyre(100, 90, 70))
    ses = _ses_keys({"mean_temp": 90.0, "camber_gradient": 30.0, "inner_mean": 100.0, "outer_mean": 70.0})
    assert lap & _CAMBER_REDUCE and not lap & _CAMBER_ADD
    assert ses & _CAMBER_REDUCE and not ses & _CAMBER_ADD


def test_camber_outer_hotter_means_add_negative_camber_in_both_modes():
    lap = _lap_keys(_lap_tyre(70, 85, 100))
    ses = _ses_keys({"mean_temp": 90.0, "camber_gradient": -30.0, "inner_mean": 70.0, "outer_mean": 100.0})
    assert lap & _CAMBER_ADD and not lap & _CAMBER_REDUCE
    assert ses & _CAMBER_ADD and not ses & _CAMBER_REDUCE


def test_pressure_direction_is_the_same_in_both_modes():
    lap_hot = _lap_keys(_lap_tyre(100, 100, 100, status="sobrecalentada", surf=125.0))
    ses_hot = _ses_keys({"mean_temp": 125.0})
    assert lap_hot & _P_RAISE and not lap_hot & _P_LOWER
    assert ses_hot & _P_RAISE and not ses_hot & _P_LOWER
    lap_cold = _lap_keys(_lap_tyre(60, 60, 60, status="fria", surf=60.0))
    ses_cold = _ses_keys({"mean_temp": 60.0})
    assert lap_cold & _P_LOWER and not lap_cold & _P_RAISE
    assert ses_cold & _P_LOWER and not ses_cold & _P_RAISE


def test_overheated_centre_hot_tyre_gets_pressure_lowered():
    keys = _lap_keys(_lap_tyre(100, 125, 100, status="sobrecalentada", surf=125.0))
    assert keys & _P_LOWER and not keys & _P_RAISE


# ── 5. lang argument ─────────────────────────────────────────────────────────

def test_lang_argument_selects_language_regardless_of_context():
    res = _lap_tyre(100, 90, 70)
    try:
        i18n.set_language("es")
        en = sa.analizar_setup(res, lang="en")
        i18n.set_language("en")
        es = sa.analizar_setup(res, lang="es")
        # context is left untouched by the call
        assert i18n.get_language() == "en"
    finally:
        i18n.set_language("en")
    en_txt = " ".join(r["recommendation"] + r["problem"] for r in en["recommendations"])
    es_txt = " ".join(r["recommendation"] + r["problem"] for r in es["recommendations"])
    assert "hotter than outer" in en_txt and "hotter than outer" not in es_txt
    assert "más caliente que exterior" in es_txt and "más caliente" not in en_txt
    assert en["recommendations"][0]["category"] != es["recommendations"][0]["category"]
    assert en["areas_status"][0]["label"] != es["areas_status"][0]["label"]


def test_lang_none_keeps_using_context_language():
    res = _lap_tyre(100, 90, 70)
    try:
        i18n.set_language("es")
        a = sa.analizar_setup(res)
        b = sa.analizar_setup(res, lang="es")
    finally:
        i18n.set_language("en")
    assert a["recommendations"][0]["category"] == b["recommendations"][0]["category"]


def test_session_advisor_respects_lang():
    cs = {"available": True, "corners": []}
    tel = {"tyre": {"FL": {"mean_temp": 125.0}}}
    try:
        i18n.set_language("es")
        en = sa.analizar_setup_sesion(cs, {}, tel, lang="en")
    finally:
        i18n.set_language("en")
    es = sa.analizar_setup_sesion(cs, {}, tel, lang="es")
    assert en["recommendations"][0]["problem"] != es["recommendations"][0]["problem"]
    assert "overheated" in en["recommendations"][0]["problem"]
