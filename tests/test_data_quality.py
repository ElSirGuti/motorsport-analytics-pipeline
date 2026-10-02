"""Tests for the data-quality assessor (synthetic frames, no real CSV needed)."""
import json

import numpy as np
import pandas as pd
import pytest

from src.analytics.data_quality import assess_data_quality, safe_assess


def _frame(n=1200, hz=20.0, lap=1, extra=None, drop=(), synthetic=False, t0=0.0):
    rng = np.random.default_rng(lap)
    t = t0 + np.arange(n) / hz
    speed = 120 + 40 * np.sin(np.linspace(0, 6.28, n)) + rng.normal(0, 1, n)
    df = pd.DataFrame({
        "Speed": speed,
        "Brake": np.clip(rng.normal(10, 20, n), 0, 100),
        "Throttle": np.clip(rng.normal(60, 30, n), 0, 100),
        "Distance": np.cumsum(speed / 3.6 / hz),
        "Time": t,
        "Gear": rng.integers(2, 6, n),
        "SteerAngle": rng.normal(0, 30, n),
        "LateralG": rng.normal(0, 1, n),
        "LongitudinalG": rng.normal(0, 0.8, n),
        "YawRate": rng.normal(0, 5, n),
        "CarCoordX": np.cumsum(rng.normal(0, 1, n)),
        "CarCoordY": np.cumsum(rng.normal(0, 1, n)),
        "AirTemp": 22.0,
        "BrakeBias": 58.0,
    })
    for c in ("FL", "FR", "RL", "RR"):
        df[f"TyreTempMiddle{c}"] = 80 + rng.normal(0, 2, n)
        df[f"SuspTravel{c}"] = 30 + rng.normal(0, 5, n)
        df[f"BrakeTemp{c}"] = 350 + rng.normal(0, 30, n)
        df[f"TyrePress{c}"] = 1.9 + rng.normal(0, 0.01, n)
        df[f"TyrePressCold{c}"] = 1.8
    df["WaterTemp"] = 90 + rng.normal(0, 1, n)
    df["OilTemp"] = 100 + rng.normal(0, 1, n)
    df["Fuel Level"] = 50 - np.arange(n) * 0.001
    for k, v in (extra or {}).items():
        df[k] = v
    df = df.drop(columns=[c for c in drop if c in df.columns])
    if synthetic:
        df.attrs["distance_synthetic"] = True
    return df


def _ch(dq, key):
    return next(c for c in dq["channels"] if c["key"] == key)


def _mod(dq, key):
    return next(m for m in dq["modules"] if m["key"] == key)


def _laps(n, **kw):
    return [_frame(lap=i + 1, t0=i * 60.0, **kw) for i in range(n)]


def test_complete_data_is_good_and_json_serializable():
    dq = assess_data_quality(_laps(8), {"mode": "stint"}, lang="en")
    assert dq["available"] and dq["level"] == "good" and dq["score"] >= 80
    assert dq["source"]["sample_rate_hz"] == 20.0
    assert dq["laps"]["valid"] == 8 and dq["laps"]["sufficient"]
    assert _ch(dq, "distance")["status"] == "ok"
    json.dumps(dq)  # must be strictly serialisable


def test_constant_brake_temperature_equal_to_ambient_is_flagged():
    dfs = _laps(6, extra={"BrakeTempFL": 22.0, "BrakeTempFR": 22.0, "BrakeTempRL": 22.0, "BrakeTempRR": 22.0})
    dq = assess_data_quality(dfs, {"mode": "stint"}, lang="en")
    ch = _ch(dq, "brake_temp")
    assert ch["status"] == "constant" and ch["detail_code"] == "constant_ambient"
    assert _mod(dq, "brakes")["status"] == "degraded"
    assert _mod(dq, "thermal")["status"] == "degraded"
    fix = next(i for i in dq["improvements"] if i["channel"] == "brake_temp")
    assert "brakes" in fix["unlocks"]


def test_synthesized_distance_reports_method_and_precision():
    dfs = _laps(6, synthetic=True)
    dq = assess_data_quality(dfs, {"mode": "stint"}, lang="en")
    d = _ch(dq, "distance")
    assert d["status"] == "synthesized" and d["method"] == "speed_integration"
    assert d["clock"] == "Time" and d["precision_pct"] is not None
    assert _mod(dq, "time_delta")["status"] == "degraded"
    assert _mod(dq, "optimal_lap")["status"] == "degraded"
    top = dq["improvements"][0]
    assert top["channel"] == "distance" and top["priority"] == "high"


def test_missing_channels_make_modules_unavailable_with_reason():
    dfs = _laps(6, drop=("YawRate", "LateralG", "LongitudinalG", "CarCoordX", "CarCoordY",
                         "WaterTemp", "OilTemp", "TyrePressColdFL", "TyrePressColdFR",
                         "TyrePressColdRL", "TyrePressColdRR"))
    dq = assess_data_quality(dfs, {"mode": "stint"}, lang="en")
    assert _ch(dq, "yaw")["status"] == "missing"
    assert _mod(dq, "slip")["status"] == "unavailable"
    assert "yaw" in _mod(dq, "slip")["reason"].lower()
    assert _mod(dq, "dynamics")["status"] == "unavailable"
    assert _mod(dq, "gg")["status"] == "unavailable"
    assert _mod(dq, "thermal")["status"] == "degraded"
    assert dq["score"] < assess_data_quality(_laps(6), {"mode": "stint"}, lang="en")["score"]
    cold = next(i for i in dq["improvements"] if i["channel"] == "tyre_press_cold")
    assert "cold" in cold["detail"].lower()


def test_few_laps_limits_trend_modules():
    dq = assess_data_quality(_laps(3), {"mode": "stint"}, lang="en")
    assert dq["laps"]["valid"] == 3 and not dq["laps"]["sufficient"]
    assert _mod(dq, "tyre_wear")["status"] == "unavailable"
    assert _mod(dq, "racing_line")["status"] == "degraded"
    assert any(i["id"] == "fix_more_laps" for i in dq["improvements"])


def test_module_results_are_reused_not_recomputed():
    results = {
        "laps": [{"lap_number": i + 1, "lap_time_s": 90.0 + i * 0.1, "is_pit_lap": i == 0,
                  "is_outlier": i == 1} for i in range(8)],
        "racing_line_rl": {"available": False, "reason": "all corners had <2 observations"},
        "degradacion_neumatico": {"available": True, "low_confidence": True,
                                  "reason": "wide slope CI", "reason_code": "wide_slope_ci"},
        "thermal_analysis": {"available": True,
                             "water_temp": {"available": True},
                             "oil_temp": {"available": False, "reason": "oil sensor dead"},
                             "brake_temps": {"available": True},
                             "tyre_pressure": {"available": True},
                             "brake_bias": {"available": True}},
    }
    dq = assess_data_quality(_laps(8), {"mode": "stint"}, results, lang="en")
    assert dq["laps"]["detected"] == 8 and dq["laps"]["pit"] == 1 and dq["laps"]["outliers"] == 1
    assert dq["laps"]["valid"] == 6
    rl = _mod(dq, "racing_line")
    assert rl["status"] == "unavailable" and rl["reason"] == "all corners had <2 observations"
    assert rl["source"] == "module"
    tw = _mod(dq, "tyre_wear")
    assert tw["status"] == "degraded" and tw["reason"] == "wide slope CI"
    th = _mod(dq, "thermal")
    assert th["status"] == "degraded" and any("oil sensor dead" in d for d in th["details"])


def test_inactive_tyre_wear_is_detected():
    dfs = _laps(6, extra={"AID Tire Wear Rate": 0.0})
    dq = assess_data_quality(dfs, {"mode": "stint"}, lang="en")
    assert _ch(dq, "tyre_wear")["status"] == "inactive"
    assert _mod(dq, "tyre_wear")["status"] == "unavailable"


def test_compare_mode_hides_session_only_modules():
    dq = assess_data_quality([_frame(lap=1), _frame(lap=2)], {"mode": "compare"}, lang="en")
    keys = {m["key"] for m in dq["modules"]}
    assert "tyre_wear" not in keys and "racing_line" not in keys and "fuel_stint" not in keys
    assert "time_delta" in keys and dq["laps"]["valid"] == 2


def test_partial_segments_counted_from_lap_counter():
    parts = [_frame(n=1200, extra={"SessionLapCount": 1}),
             _frame(n=1200, extra={"SessionLapCount": 2}),
             _frame(n=1200, extra={"SessionLapCount": 3}),
             _frame(n=40, extra={"SessionLapCount": 4})]
    df = pd.concat(parts, ignore_index=True)
    results = {"laps": [{"lap_number": i, "lap_time": 60.0, "is_pit_lap": False} for i in (1, 2, 3)]}
    dq = assess_data_quality(df, {"mode": "session"}, results, lang="en")
    assert dq["laps"]["detected"] == 3 and dq["laps"]["partial_discarded"] == 1
    assert dq["laps"]["segmentation"] == "lap_counter"


def test_spanish_texts_and_safe_wrapper():
    dq = assess_data_quality(_laps(3, synthetic=True), {"mode": "stint"}, lang="es")
    assert "Sintetizada" in _ch(dq, "distance")["detail"]
    assert _ch(dq, "distance")["label"] == "Distancia"
    assert safe_assess(None) is not None and safe_assess(None)["available"] is False
    assert safe_assess("not a frame")["available"] is False


@pytest.mark.parametrize("lang", ["en", "es"])
def test_every_translation_key_exists(lang):
    from src.i18n import get_locale
    loc = get_locale(lang)
    dq = assess_data_quality(_laps(3, synthetic=True, drop=("YawRate", "WaterTemp")), {"mode": "stint"}, lang=lang)
    for c in dq["channels"]:
        assert c["label"] != f"dq_ch_{c['key']}"
    for m in dq["modules"]:
        assert m["label"] != f"dq_mod_{m['key']}"
        assert not (m["reason"] or "").startswith("dq_")
    for i in dq["improvements"]:
        assert not i["title"].startswith("dq_") and not i["detail"].startswith("dq_")
    assert "dq_fix_tyre_press_cold" in loc
