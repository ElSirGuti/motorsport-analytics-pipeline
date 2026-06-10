"""Tests para src/telemetry/metrics.py."""

import numpy as np
import pandas as pd
import pytest

from src.telemetry.metrics import (
    BRAKE_THRESHOLD_PCT,
    APEX_MIN_DISTANCE_M,
    detect_braking_points,
    detect_apex_points,
    detect_full_throttle_points,
    segment_corners,
)


class TestDetectBrakingPoints:
    def test_detects_single_braking_event(self, lap_df):
        braking = detect_braking_points(lap_df)
        assert isinstance(braking, list)
        assert all("distance" in b and "brake_pressure" in b for b in braking)

    def test_no_braking_when_brake_is_zero(self):
        df = pd.DataFrame({
            "Distance": np.linspace(0, 1000, 100),
            "Brake": np.zeros(100),
            "Speed": np.full(100, 150.0),
            "Throttle": np.full(100, 100.0),
        })
        assert detect_braking_points(df) == []

    def test_threshold_respected(self):
        df = pd.DataFrame({
            "Distance": np.linspace(0, 100, 10),
            "Brake": [0, 0, 3, 3, 3, 0, 0, 90, 90, 0],
            "Speed": np.full(10, 100.0),
            "Throttle": np.full(10, 0.0),
        })
        points = detect_braking_points(df, threshold=BRAKE_THRESHOLD_PCT)
        pressures = [p["brake_pressure"] for p in points]
        assert all(p >= BRAKE_THRESHOLD_PCT for p in pressures)

    def test_returns_sorted_by_distance(self, lap_df):
        braking = detect_braking_points(lap_df)
        distances = [b["distance"] for b in braking]
        assert distances == sorted(distances)


class TestDetectApexPoints:
    def test_detects_apexes_in_lap_with_corners(self, lap_df):
        apexes = detect_apex_points(lap_df)
        assert len(apexes) > 0

    def test_apex_speed_below_threshold(self, lap_df):
        apexes = detect_apex_points(lap_df)
        mean_speed = lap_df["Speed"].mean()
        for apex in apexes:
            assert apex["speed"] < mean_speed

    def test_minimum_distance_between_apexes(self, lap_df):
        apexes = detect_apex_points(lap_df, min_distance_between=APEX_MIN_DISTANCE_M)
        for i in range(1, len(apexes)):
            gap = apexes[i]["distance"] - apexes[i - 1]["distance"]
            assert gap >= APEX_MIN_DISTANCE_M - 1  # margen de 1m por redondeo

    def test_no_apexes_on_straight(self, lap_df_short):
        apexes = detect_apex_points(lap_df_short)
        assert len(apexes) == 0


class TestDetectFullThrottlePoints:
    def test_detects_full_throttle_transitions(self, lap_df):
        points = detect_full_throttle_points(lap_df)
        assert isinstance(points, list)
        assert all("distance" in p and "throttle" in p for p in points)

    def test_constant_full_throttle_returns_empty(self):
        df = pd.DataFrame({
            "Distance": np.linspace(0, 500, 50),
            "Throttle": np.full(50, 100.0),
            "Speed": np.full(50, 150.0),
            "Brake": np.zeros(50),
        })
        points = detect_full_throttle_points(df)
        assert len(points) == 0


class TestSegmentCorners:
    def test_returns_list_of_corners(self, lap_df):
        corners = segment_corners(lap_df)
        assert isinstance(corners, list)

    def test_corner_has_required_keys(self, lap_df):
        corners = segment_corners(lap_df)
        for c in corners:
            assert "corner_number" in c
            assert "braking_point" in c
            assert "apex" in c
            assert "full_throttle" in c

    def test_corner_numbers_are_sequential(self, lap_df):
        corners = segment_corners(lap_df)
        for i, c in enumerate(corners, start=1):
            assert c["corner_number"] == i

    def test_event_order_within_corner(self, lap_df):
        corners = segment_corners(lap_df)
        for c in corners:
            bp = c["braking_point"]["distance"]
            ap = c["apex"]["distance"]
            ft = c["full_throttle"]["distance"]
            assert bp < ap
            assert ap < ft
