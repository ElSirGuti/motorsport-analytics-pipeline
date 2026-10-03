"""Stint tyre_temp_avg from canonical channels and LateralG sign convention."""
from __future__ import annotations

import glob
import gzip
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
import pytest

from src.analytics.slip_angle import lateral_sign_convention
from src.analytics.stint import extraer_metricas_por_vuelta, lap_tyre_temp_avg
from src.io.native_common import normalize_lateral_sign


def _lap(**cols):
    n = 50
    d = {"Speed": np.full(n, 150.0), "LapTime": np.linspace(0, 90, n)}
    d.update({k: np.full(n, v) for k, v in cols.items()})
    return pd.DataFrame(d)


def test_tyre_temp_uses_middle_zone():
    cols = {f"TyreTempMiddle{c}": t for c, t in zip(("FL", "FR", "RL", "RR"), (80, 82, 84, 86))}
    df = _lap(TyreTempInnerFL=10.0, **cols)
    assert lap_tyre_temp_avg(df) == pytest.approx(83.0)


def test_tyre_temp_falls_back_to_core_then_edges_then_legacy():
    core = _lap(**{f"TyreTempCore{c}": 90.0 for c in ("FL", "FR", "RL", "RR")})
    assert lap_tyre_temp_avg(core) == pytest.approx(90.0)
    assert lap_tyre_temp_avg(_lap(TyreTempInnerFL=70.0, TyreTempOuterFL=80.0)) == pytest.approx(75.0)
    assert lap_tyre_temp_avg(_lap(TyreTemp_FL=60.0)) == pytest.approx(60.0)


def test_tyre_temp_missing_or_zero_is_nan():
    assert np.isnan(lap_tyre_temp_avg(_lap()))
    assert np.isnan(lap_tyre_temp_avg(_lap(TyreTempMiddleFL=0.0)))


def test_metrics_per_lap_report_tyre_temp():
    laps = [_lap(TyreTempMiddleFL=80.0 + i) for i in range(3)]
    out = extraer_metricas_por_vuelta(laps)
    assert out["tyre_temp_avg"].tolist() == [80.0, 81.0, 82.0]


def _synthetic(sign):
    t = np.linspace(0, 60, 3000)
    yaw_deg = 40 * np.sin(t / 3)
    v = np.full_like(t, 144.0)
    ay_g = np.deg2rad(yaw_deg) * (v / 3.6) / 9.80665
    return pd.DataFrame({"Speed": v, "YawRate": yaw_deg, "LateralG": sign * ay_g})


def test_positive_convention_untouched():
    df = _synthetic(+1)
    ref = df["LateralG"].copy()
    assert normalize_lateral_sign(df) is False
    pd.testing.assert_series_equal(df["LateralG"], ref)
    assert df.attrs["lateral_g_flipped"] is False


def test_negative_convention_is_flipped_and_idempotent():
    df = _synthetic(-1)
    assert normalize_lateral_sign(df) is True
    np.testing.assert_allclose(df["LateralG"], _synthetic(+1)["LateralG"])
    assert lateral_sign_convention(df["LateralG"] * 9.80665, np.deg2rad(df["YawRate"]), df["Speed"] / 3.6) == 1.0
    assert normalize_lateral_sign(df) is False


def test_missing_channels_is_noop():
    df = pd.DataFrame({"Speed": [1.0, 2.0], "LateralG": [0.1, 0.2]})
    assert normalize_lateral_sign(df) is False


def test_ac_csv_keeps_original_sign():
    """AC/ACTI CSV are deliberately NOT normalised (numeric equivalence of existing results)."""
    from src.io.loaders import load_telemetry_data
    src = os.path.join(os.path.dirname(__file__), "fixtures", "imola_5laps.csv.gz")
    if not os.path.exists(src):
        pytest.skip("fixture missing")
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.csv")
        with gzip.open(src, "rb") as a, open(p, "wb") as b:
            shutil.copyfileobj(a, b)
        df = load_telemetry_data(p)
    assert not df.attrs.get("lateral_g_flipped", False)
    v = df["Speed"].to_numpy() / 3.6
    r = np.deg2rad(df["YawRate"].to_numpy()) * v
    m = v > 10
    assert np.corrcoef(df["LateralG"].to_numpy()[m], r[m])[0, 1] < -0.5


_NATIVE = (glob.glob(r"C:\Users\elgut\Documents\iRacing\Telemetry\*.ibt")[:2]
           + glob.glob(r"C:\Users\elgut\Documents\iRacing\Telemetry\*.ld")[:1]
           + glob.glob(r"C:\Users\elgut\Documents\acti\telem\**\*.ld", recursive=True)[:3])


@pytest.mark.skipif(not _NATIVE, reason="real .ibt/.ld files not available")
@pytest.mark.parametrize("path", _NATIVE)
def test_real_native_files_follow_convention(path):
    from src.io.loaders import load_telemetry_data
    df = load_telemetry_data(path)
    if "LateralG" not in df.columns or "YawRate" not in df.columns:
        pytest.skip("no lateral/yaw channels")
    v = df["Speed"].to_numpy() / 3.6
    m = v > 10
    r = np.deg2rad(df["YawRate"].to_numpy()) * v
    assert np.corrcoef(df["LateralG"].to_numpy()[m], r[m])[0, 1] > 0.5, path
    assert any(c.startswith("TyreTemp") for c in df.columns)
