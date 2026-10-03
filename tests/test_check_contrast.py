"""Unit tests for scripts/check_contrast.py (WCAG maths and the light theme gate)."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_contrast.py"
spec = importlib.util.spec_from_file_location("check_contrast", SCRIPT)
cc = importlib.util.module_from_spec(spec)
sys.modules["check_contrast"] = cc
spec.loader.exec_module(cc)


def test_black_on_white_is_21():
    assert cc.contrast((0, 0, 0, 1), (255, 255, 255, 1)) == pytest.approx(21.0)


def test_identical_colors_ratio_is_1():
    assert cc.contrast((120, 130, 140, 1), (120, 130, 140, 1)) == pytest.approx(1.0)


def test_known_wcag_value():
    # #767676 on white is the classic 4.54:1 AA threshold grey
    r = cc.contrast(cc.parse_color("#767676"), cc.parse_color("#ffffff"))
    assert 4.5 <= r < 4.6


def test_parse_color_formats():
    assert cc.parse_color("#fff") == (255, 255, 255, 1.0)
    assert cc.parse_color("rgba(10, 20, 30, 0.5)") == (10, 20, 30, 0.5)
    assert cc.parse_color("var(--x)") is None


def test_composite_alpha():
    out = cc.composite((0, 0, 0, 0.5), (255, 255, 255, 1.0))
    assert out[0] == pytest.approx(127.5)


def test_light_theme_passes_all_pairs():
    light = cc.load_themes()["light"]
    failing = [(f, b, round(r, 2)) for f, b, r, _m, _w, ok in cc.check(light) if not ok]
    assert failing == []


def test_dark_theme_passes_all_pairs():
    dark = cc.load_themes()["dark"]
    failing = [(f, b, round(r, 2)) for f, b, r, _m, _w, ok in cc.check(dark) if not ok]
    assert failing == []


def test_ink_hierarchy_dark_and_light():
    for name, tokens in cc.load_themes().items():
        lum = [cc.luminance(tokens[k]) for k in ("ink-1", "ink-2", "ink-3", "ink-4")]
        surf = cc.luminance(tokens["surface-1"])
        d = [abs(x - surf) for x in lum]
        assert d == sorted(d, reverse=True), name


def test_strict_flag_exit_code_ok():
    assert cc.main(["--strict"]) == 0


def test_light_theme_defines_every_dark_token_that_matters():
    themes = cc.load_themes()
    for tok in ("surface-0", "surface-1", "ink-1", "accent", "ok", "warn", "bad", *cc.LAPS):
        assert themes["light"][tok] != themes["dark"][tok]


def test_main_exit_code_ok():
    assert cc.main([]) == 0
