"""Tests para src/processing/alignment.py."""

import numpy as np
import pandas as pd
import pytest

from src.processing.alignment import align_by_distance, align_pair


class TestAlignByDistance:
    def test_output_has_uniform_distance(self, lap_df):
        aligned = align_by_distance(lap_df, distance_step=1.0)
        distances = aligned["Distance"].values
        diffs = np.diff(distances)
        assert np.allclose(diffs, 1.0, atol=1e-6)

    def test_preserves_channels(self, lap_df):
        aligned = align_by_distance(lap_df, distance_step=1.0)
        for col in ["Speed", "Brake", "Throttle"]:
            assert col in aligned.columns

    def test_raises_without_distance_column(self):
        df = pd.DataFrame({"Speed": [100.0, 110.0], "Brake": [0.0, 50.0]})
        with pytest.raises(ValueError, match="Distance"):
            align_by_distance(df)

    def test_brake_clipped_to_0_100(self, lap_df):
        lap_df["Brake"] = -10.0
        aligned = align_by_distance(lap_df)
        assert aligned["Brake"].min() >= 0

    def test_throttle_clipped_to_0_100(self, lap_df):
        lap_df["Throttle"] = 150.0
        aligned = align_by_distance(lap_df)
        assert aligned["Throttle"].max() <= 100

    def test_different_step_sizes(self, lap_df):
        for step in [0.5, 1.0, 5.0]:
            aligned = align_by_distance(lap_df, distance_step=step)
            diffs = np.diff(aligned["Distance"].values)
            assert np.allclose(diffs, step, atol=1e-4)


class TestAlignPair:
    def test_both_outputs_same_length(self, lap_df, lap_df_fast):
        a, b = align_pair(lap_df, lap_df_fast)
        assert len(a) == len(b)

    def test_both_outputs_same_distance_vector(self, lap_df, lap_df_fast):
        a, b = align_pair(lap_df, lap_df_fast)
        assert np.allclose(a["Distance"].values, b["Distance"].values, atol=1e-6)

    def test_shared_range_is_correct(self, lap_df, lap_df_fast):
        a, b = align_pair(lap_df, lap_df_fast)
        a_min, a_max = a["Distance"].min(), a["Distance"].max()
        b_min, b_max = b["Distance"].min(), b["Distance"].max()
        assert abs(a_min - b_min) < 1.0
        assert abs(a_max - b_max) < 1.0
