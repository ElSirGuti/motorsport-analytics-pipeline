"""Fixtures compartidos para los tests del pipeline de telemetría."""

import numpy as np
import pandas as pd
import pytest


def _make_lap_df(n: int = 500, with_corners: bool = True) -> pd.DataFrame:
    """Genera un DataFrame de telemetría sintético con n muestras."""
    distance = np.linspace(0, 2000, n)
    speed = np.full(n, 150.0)
    brake = np.zeros(n)
    throttle = np.full(n, 100.0)

    if with_corners:
        for apex_pct in [0.15, 0.35, 0.55, 0.75]:
            apex_idx = int(apex_pct * n)
            w = n // 20
            start = max(0, apex_idx - w)
            end = min(n, apex_idx + w)

            brake_start = max(0, apex_idx - w)
            brake_end = max(0, apex_idx - w // 2)
            brake[brake_start:brake_end] = 80.0
            throttle[brake_start:brake_end] = 0.0

            for j in range(start, end):
                factor = 1 - 0.4 * np.exp(-((j - apex_idx) ** 2) / (2 * (w / 3) ** 2))
                speed[j] = 150.0 * factor

            throttle_start = apex_idx + w // 2
            throttle_end = min(n, apex_idx + w)
            throttle[throttle_start:throttle_end] = 100.0

    return pd.DataFrame({
        "Distance": distance,
        "Speed": speed,
        "Brake": brake,
        "Throttle": throttle,
        "LateralG": np.random.normal(0, 0.5, n),
        "LongitudinalG": np.random.normal(0, 0.3, n),
    })


@pytest.fixture
def lap_df():
    return _make_lap_df()


@pytest.fixture
def lap_df_fast():
    """Vuelta un 2% más rápida (velocidades levemente superiores)."""
    df = _make_lap_df()
    df["Speed"] = df["Speed"] * 1.02
    return df


@pytest.fixture
def lap_df_short(tmp_path):
    """DataFrame sin curvas (solo recta)."""
    return _make_lap_df(n=200, with_corners=False)
