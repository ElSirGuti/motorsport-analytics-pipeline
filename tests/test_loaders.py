"""Tests para src/io/loaders.py."""

import io
import os
import textwrap
import pytest
import pandas as pd

from src.io.loaders import load_telemetry_data, DataLoaderException, ESSENTIAL_CHANNELS


def _write_csv(tmp_path, content: str, filename: str = "lap.csv") -> str:
    path = tmp_path / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(path)


class TestLoadTelemetryData:
    def test_loads_valid_csv(self, tmp_path):
        path = _write_csv(tmp_path, """
            Distance,Speed,Brake,Throttle
            0,100,0,100
            1,105,0,100
            2,110,0,100
        """)
        df = load_telemetry_data(path)
        assert len(df) == 3
        assert all(col in df.columns for col in ESSENTIAL_CHANNELS)

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(DataLoaderException, match="No se encontró"):
            load_telemetry_data(str(tmp_path / "nonexistent.csv"))

    def test_raises_on_empty_file(self, tmp_path):
        path = _write_csv(tmp_path, "")
        with pytest.raises(DataLoaderException):
            load_telemetry_data(path)

    def test_raises_when_essential_columns_missing(self, tmp_path):
        path = _write_csv(tmp_path, """
            Distance,Speed
            0,100
            1,105
        """)
        with pytest.raises(DataLoaderException, match="Faltan canales esenciales"):
            load_telemetry_data(path)

    def test_resolves_column_aliases(self, tmp_path):
        path = _write_csv(tmp_path, """
            Dist,SpeedKmh,BrakeInput,Gas
            0,100,0,100
            1,105,0,100
        """)
        df = load_telemetry_data(path)
        assert "Distance" in df.columns
        assert "Speed" in df.columns
        assert "Brake" in df.columns
        assert "Throttle" in df.columns

    def test_handles_semicolon_separator(self, tmp_path):
        path = _write_csv(tmp_path, """
            Distance;Speed;Brake;Throttle
            0;100;0;100
            1;105;0;100
        """)
        df = load_telemetry_data(path)
        assert len(df) == 2
        assert "Speed" in df.columns

    def test_nan_interpolation_in_essential_channels(self, tmp_path):
        path = _write_csv(tmp_path, """
            Distance,Speed,Brake,Throttle
            0,100,0,100
            1,,0,100
            2,110,0,100
        """)
        df = load_telemetry_data(path)
        assert df["Speed"].isna().sum() == 0

    def test_essential_channels_are_numeric(self, tmp_path):
        path = _write_csv(tmp_path, """
            Distance,Speed,Brake,Throttle
            0,100,0,100
            1,105,0,100
        """)
        df = load_telemetry_data(path)
        for ch in ESSENTIAL_CHANNELS:
            assert pd.api.types.is_numeric_dtype(df[ch])
