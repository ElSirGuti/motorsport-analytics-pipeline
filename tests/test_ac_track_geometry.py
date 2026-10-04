"""Tests of src/analytics/ac_track_geometry.py and the exported track_geometry JSON files.

Only the tests marked with ``needs_game`` use an installed Assetto Corsa (skipped otherwise);
everything else works on synthetic files or on the JSON versioned in src/data/track_geometry.
"""
import json
import math
import struct

import numpy as np
import pytest

from src.analytics import ac_track_geometry as G
from src.analytics import circuits as C

GAME = G.find_ac_tracks_dir()
needs_game = pytest.mark.skipif(GAME is None, reason="Assetto Corsa not installed")


# -- synthetic fast_lane.ai ---------------------------------------------------------------

def make_fast_lane(xs, zs, version=7, close_gap=True):
    """Bytes of a version 7 fast_lane.ai with the given points (+ an ignored trailing block)."""
    xs, zs = np.asarray(xs, float), np.asarray(zs, float)
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xs), np.diff(zs)))])
    out = struct.pack("<4i", version, len(xs), 0, len(xs))
    for i in range(len(xs)):
        out += struct.pack("<4fi", xs[i], 0.0, zs[i], s[i], i)
    return out + b"\x00" * 64


def stadium(straight=300.0, radius=60.0, step=1.6, sign=1.0, scale=1.0):
    """Closed stadium: two straights joined by two semicircles. sign=+1 is anticlockwise in the (x, z)
    plane, which in the mirrored AC axes is a CLOCKWISE circuit with right-hand bends (the sign
    convention was checked against ui_track.json `run`); sign=-1 gives an anticlockwise circuit."""
    pts = []
    n_arc = int(math.pi * radius / step)
    for x in np.arange(0, straight, step):
        pts.append((x, -radius))
    for t in np.linspace(-math.pi / 2, math.pi / 2, n_arc, endpoint=False):
        pts.append((straight + radius * math.cos(t), radius * math.sin(t)))
    for x in np.arange(straight, 0, -step):
        pts.append((x, radius))
    for t in np.linspace(math.pi / 2, 3 * math.pi / 2, n_arc, endpoint=False):
        pts.append((radius * math.cos(t), radius * math.sin(t)))
    a = np.roll(np.array(pts), -int(straight / 2 / step), axis=0) * scale   # start mid-straight
    return a[:, 0], sign * a[:, 1]


def stadium_expected(straight=300.0, radius=60.0):
    perim = 2 * straight + 2 * math.pi * radius
    return (straight / 2 + math.pi * radius / 2) / perim, (1.5 * straight + 1.5 * math.pi * radius) / perim


def test_parse_and_analyze_stadium_right():
    xs, zs = stadium()
    lane = G.parse_fast_lane(make_fast_lane(xs, zs))
    assert lane.version == 7 and len(lane.x) == len(xs)
    geo = G.analyze_lane(lane)
    assert geo.closed and geo.direction == "clockwise"
    assert geo.length_line_m == pytest.approx(2 * 300 + 2 * math.pi * 60, rel=0.01)
    assert len(geo.corners) == 2
    f1, f2 = stadium_expected()
    for c, f in zip(geo.corners, (f1, f2)):
        # the apex of a constant-radius arc is arbitrary: the arc itself is centred on f
        assert (c.start_fraction + c.end_fraction) / 2 == pytest.approx(f, abs=0.02)
        assert c.min_radius_m == pytest.approx(60.0, rel=0.06)
        assert c.direction == "right" and c.severity == "medium" and not c.is_complex
        assert c.start_fraction < c.apex_fraction < c.end_fraction


def test_stadium_left_direction_and_anticlockwise():
    xs, zs = stadium(sign=-1.0)
    geo = G.analyze_lane(G.parse_fast_lane(make_fast_lane(xs, zs)))
    assert geo.direction == "anticlockwise"
    assert [c.direction for c in geo.corners] == ["left", "left"]


def test_fraction_is_independent_of_line_length():
    f = []
    for scale in (1.0, 1.02):
        xs, zs = stadium(scale=scale)
        geo = G.analyze_lane(G.parse_fast_lane(make_fast_lane(xs, zs)))
        f.append([(c.start_fraction + c.end_fraction) / 2 for c in geo.corners])
    assert f[0] == pytest.approx(f[1], abs=0.005)


def test_corner_across_the_start_line_is_found_once():
    # rotate the start point to the middle of the first semicircle: the corner wraps around the lap start
    xs, zs = stadium()
    k = int(300 / 1.6) + 30
    xs, zs = np.roll(xs, -k), np.roll(zs, -k)
    geo = G.analyze_lane(G.parse_fast_lane(make_fast_lane(xs, zs)))
    assert len(geo.corners) == 2
    assert all(0.0 <= c.apex_fraction < 1.0 for c in geo.corners)
    assert all(c.min_radius_m == pytest.approx(60.0, rel=0.06) for c in geo.corners)


def test_open_line_is_not_closed():
    xs = np.arange(0, 1000, 1.6)
    geo = G.analyze_lane(G.parse_fast_lane(make_fast_lane(xs, np.zeros_like(xs))))
    assert not geo.closed and geo.direction is None and geo.corners == []


def test_chicane_is_grouped_as_complex():
    # straight, left-right S of radius 50 m, straight: one 'chicane' complex with two sub-apexes
    pts = [(x, 0.0) for x in np.arange(0, 400, 1.6)]
    n = int(math.pi * 50 / 2 / 1.6)
    cx, cz = 400.0, 50.0
    for t in np.linspace(-math.pi / 2, 0, n, endpoint=False):
        pts.append((cx + 50 * math.cos(t), cz + 50 * math.sin(t)))
    cx, cz = 400.0 + 100.0, 50.0
    for t in np.linspace(math.pi, math.pi / 2, n, endpoint=False):
        pts.append((cx + 50 * math.cos(t), cz + 50 * math.sin(t)))
    last = pts[-1]
    pts += [(last[0] + x, last[1]) for x in np.arange(1.6, 400, 1.6)]
    a = np.array(pts)
    geo = G.analyze_lane(G.parse_fast_lane(make_fast_lane(a[:, 0], a[:, 1])), close=False)
    assert len(geo.corners) == 1
    c = geo.corners[0]
    assert c.kind == "chicane" and c.is_complex and len(c.sub_apexes) == 2
    assert {s.direction for s in c.sub_apexes} == {"left", "right"}


@pytest.mark.parametrize("radius,severity", [(30, "slow"), (100, "medium"), (250, "fast")])
def test_severity_classes(radius, severity):
    xs, zs = stadium(straight=600, radius=radius)
    geo = G.analyze_lane(G.parse_fast_lane(make_fast_lane(xs, zs)))
    assert geo.corners and all(c.severity == severity for c in geo.corners)


def test_corrupt_files_are_rejected_with_clear_errors(tmp_path):
    xs, zs = stadium()
    good = make_fast_lane(xs, zs)
    with pytest.raises(G.FastLaneError, match="version 6"):
        G.parse_fast_lane(make_fast_lane(xs, zs, version=6))
    with pytest.raises(G.FastLaneError, match="truncated"):
        G.parse_fast_lane(good[:200])
    with pytest.raises(G.FastLaneError, match="too short"):
        G.parse_fast_lane(b"\x07\x00")
    with pytest.raises(G.FastLaneError, match="cannot read"):
        G.parse_fast_lane(tmp_path / "missing.ai")
    nan = bytearray(good)
    struct.pack_into("<f", nan, 16, float("nan"))
    with pytest.raises(G.FastLaneError, match="non-finite"):
        G.parse_fast_lane(bytes(nan))
    empty_s = bytearray(good)
    for i in range(len(xs)):
        struct.pack_into("<f", empty_s, 16 + i * 20 + 12, 0.0)
    with pytest.raises(G.FastLaneError, match="distance"):
        G.parse_fast_lane(bytes(empty_s))
    p = tmp_path / "fast_lane.ai"
    p.write_bytes(good)
    assert len(G.parse_fast_lane(p).x) == len(xs)


# -- official length ----------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("4909", 4909.0), ("5807m", 5807.0), ("3.602", 3602.0), ("13.626km", 13626.0),
    ("3.340m", 3340.0), ("5.543m", 5543.0), (" 7004 ", 7004.0), ("3,602", 3602.0), (4909, 4909.0),
    ("20.832 km", 20832.0),
])
def test_parse_length_m(raw, expected):
    assert G.parse_length_m(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", "abc", "-5", "0", True])
def test_parse_length_m_invalid(raw):
    assert G.parse_length_m(raw) is None


# -- game folder --------------------------------------------------------------------------

def test_find_tracks_dir_from_environment(tmp_path, monkeypatch):
    tracks = tmp_path / "assettocorsa" / "content" / "tracks"
    (tracks / "mytrack" / "ai").mkdir(parents=True)
    xs, zs = stadium()
    (tracks / "mytrack" / "ai" / "fast_lane.ai").write_bytes(make_fast_lane(xs, zs))
    (tracks / "mytrack" / "ui").mkdir()
    (tracks / "mytrack" / "ui" / "ui_track.json").write_text('﻿{"name": "T", "length": "977m"}', encoding="utf-8")
    for var, val in (("AC_CONTENT_DIR", tmp_path / "assettocorsa" / "content"),
                     ("AC_INSTALL_DIR", tmp_path / "assettocorsa")):
        monkeypatch.delenv("AC_CONTENT_DIR", raising=False)
        monkeypatch.delenv("AC_INSTALL_DIR", raising=False)
        monkeypatch.setenv(var, str(val))
        assert G.find_ac_tracks_dir() == tracks
    assert G.list_layouts("mytrack", tracks) == [""]
    geo, lane, official = G.analyze_track("mytrack", "", tracks)
    assert official == 977.0 and geo.closed


# -- exported JSON (no game needed) -------------------------------------------------------

EXPECTED_EXPORTS = {
    "imola", "spa_francorchamps", "silverstone", "monaco", "le_mans", "mugello", "brands_hatch", "monza",
    "red_bull_ring", "barcelona", "laguna_seca", "zandvoort", "vallelunga", "magione", "sepang", "nordschleife",
}


def test_exported_geometry_files_exist_and_load():
    files = {p.stem for p in G.TRACK_GEOMETRY_DIR.glob("*.json")}
    assert EXPECTED_EXPORTS <= files
    for cid in files:
        assert C.get_track_geometry(cid) is not None
    assert C.get_track_geometry("oran_park_gp") is None
    assert C.get_track_geometry("../circuits") is None
    assert C.get_track_geometry(None) is None


@pytest.mark.parametrize("cid", sorted(EXPECTED_EXPORTS))
def test_exported_geometry_is_coherent(cid):
    g = C.get_track_geometry(cid)
    circ = C.get_circuit(cid)
    assert g["circuit_id"] == cid and circ is not None
    assert g["source"]["format_version"] == 7 and g["source"]["track_id"]
    assert g["closed"] is True
    assert g["extracted"]
    assert abs(g["length_official_m"] / circ["length_m"] - 1) <= 0.03
    assert abs(g["length_line_m"] / g["length_official_m"] - 1) <= 0.03
    corners = g["corners"]
    assert corners
    fr = [c["apex_fraction"] for c in corners]
    assert fr == sorted(fr) and len(set(fr)) == len(fr)
    assert all(0.0 <= f < 1.0 for f in fr)
    assert [c["index"] for c in corners] == list(range(1, len(corners) + 1))
    for c in corners:
        assert c["min_radius_m"] > 0 and c["direction"] in ("left", "right")
        assert c["severity"] in G.SEVERITIES
        r = c["min_radius_m"]
        assert c["severity"] == ("slow" if r < 60 else "medium" if r < 150 else "fast")
        assert c["complex"] == (len(c["sub_apexes"]) > 1)
        assert all(a["radius_m"] > 0 and 0.0 <= a["fraction"] < 1.0 for a in c["sub_apexes"])
        assert min(a["radius_m"] for a in c["sub_apexes"]) == pytest.approx(r, abs=0.15)


def test_exported_files_are_small_utf8():
    for p in G.TRACK_GEOMETRY_DIR.glob("*.json"):
        raw = p.read_bytes()
        assert len(raw) < 40_000
        assert not raw.startswith(b"\xef\xbb\xbf")
        raw.decode("utf-8")


def test_imola_table_against_exported_geometry():
    circ = C.get_circuit("imola")
    res = G.compare_with_table(circ, C.get_track_geometry("imola")["corners"])
    rows = {r["name"]: r for r in res["rows"]}
    assert len(rows) == 9
    # Variante Bassa is tabulated as flat_out: radius 478 m, above the export cut, so it has no geometric corner
    assert rows["Variante Bassa"]["kind"] == "flat_out"
    rows = {n: r for n, r in rows.items() if r["kind"] != "flat_out"}
    assert len(rows) == 8
    d = [r["nearest_m"] for r in rows.values()]
    assert max(d) <= 40 and sum(d) / len(d) <= 20
    assert all(r["inside_extent"] for r in rows.values())
    # radii verified against the telemetry-tabulated corners (slow/medium corners)
    assert rows["Tosa"]["min_radius_m"] < 60 and rows["Tosa"]["severity"] == "slow"
    assert res["geometric_without_table"] == [] and res["table_without_peak"] == []
    assert rows["Tosa"]["nearest_m"] <= 20 and rows["Piratella"]["nearest_m"] <= 12


def test_tabulated_corners_are_near_a_geometric_corner_everywhere():
    for circ in C.load_circuits().values():
        g = C.get_track_geometry(circ["id"])
        if not g or not circ.get("corners"):
            continue
        res = G.compare_with_table(circ, g["corners"])
        assert res["table_without_peak"] == [], circ["id"]


# -- with the game --------------------------------------------------------------------------

@needs_game
def test_game_imola_matches_exported_json():
    geo, lane, official = G.analyze_track("imola")
    assert lane.version == 7 and official == 4909.0
    assert geo.closed and geo.direction == "anticlockwise"
    assert geo.length_line_m == pytest.approx(4864, abs=5)
    exported = C.get_track_geometry("imola")["corners"]
    assert [round(c.apex_fraction, 5) for c in geo.corners] == [c["apex_fraction"] for c in exported]


@needs_game
def test_game_directions_match_ui_run_field():
    for track, layout in (("ks_silverstone", "gp"), ("ks_laguna_seca", ""), ("monza", "")):
        geo, _, _ = G.analyze_track(track, layout)
        run = str(G.read_ui_track(track, layout).get("run", "")).replace("-", "")
        if run in ("clockwise", "anticlockwise"):
            assert geo.direction == run
