"""The unified corner map as the ONLY source of corners in every analysis endpoint (stage 2a).

Covers: same number / numbering of corners in session (stint), comparison and optimal lap; Imola names
(Tamburello ... Rivazza 2 and the flat-out Variante Bassa); flat_out corners have no braking / apex /
throttle metrics but DO have time loss; the CORNER_DETECTION=legacy|map switch; one map build per session
shared between endpoints (cache); unknown circuit; single lap and few laps; PDF mark; racing line and setup
advisor ignore flat-out corners. See docs/CORNER_DETECTION.md, section "Integration".
"""
import gzip
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from src.analytics import circuits as C
from src.analytics import corner_service
from src.io import session_cache

FIXTURES = Path(__file__).parent / "fixtures"
IMOLA_NAMES = ["Tamburello", "Villeneuve", "Tosa", "Piratella", "Acque Minerali", "Variante Alta",
               "Rivazza 1", "Rivazza 2", "Variante Bassa"]

pytestmark = pytest.mark.skipif(
    not all((FIXTURES / f"{n}.csv.gz").exists() for n in ("imola_5laps", "spa_3laps", "rbr_fast", "rbr_slow")),
    reason="real fixtures missing (run scripts/make_fixtures.py)",
)


@pytest.fixture(scope="module")
def csvs(tmp_path_factory):
    d = tmp_path_factory.mktemp("cmap_fixtures")
    out = {}
    for n in ("imola_5laps", "spa_3laps", "rbr_fast", "rbr_slow"):
        with gzip.open(FIXTURES / f"{n}.csv.gz", "rb") as src, open(d / f"{n}.csv", "wb") as dst:
            shutil.copyfileobj(src, dst)
        out[n] = d / f"{n}.csv"
    # the same Imola session under a venue the database does not know (no template, no names)
    text = out["imola_5laps"].read_bytes().replace(b"fn_imola", b"zz_unknown_track")
    (d / "unknown_5laps.csv").write_bytes(text)
    out["unknown_5laps"] = d / "unknown_5laps.csv"
    return out


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _fresh_caches():
    session_cache.cache.clear()
    session_cache.corner_map_cache.clear()
    yield
    session_cache.corner_map_cache.clear()


def _post(client, url, path, field="session_file", lang="en", **form):
    with open(path, "rb") as fh:
        r = client.post(url, files={field: (Path(path).name, fh, "text/csv")}, data=form, params={"lang": lang})
    assert r.status_code == 200, (url, r.status_code, r.text[:300])
    return r.json()


def _pair(client, url, a, b, keys, lang="en"):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        r = client.post(url, files={keys[0]: (Path(a).name, fa, "text/csv"), keys[1]: (Path(b).name, fb, "text/csv")},
                        params={"lang": lang})
    assert r.status_code == 200, (url, r.status_code, r.text[:300])
    return r.json()


@pytest.fixture(scope="module")
def imola(client, csvs):
    """All the session endpoints on the Imola fixture, CORNER_DETECTION=map (default)."""
    session_cache.corner_map_cache.clear()
    p = csvs["imola_5laps"]
    return {
        "session": _post(client, "/api/analyze-session", p),
        "stint": _post(client, "/api/stint/analyze", p, field="laps"),
        "optimal": _post(client, "/api/optimal-lap", p),
        "compare": _post(client, "/api/compare-session-laps", p, lap_a="0", lap_b="0"),
    }


# ── same corners everywhere ──────────────────────────────────────────────────────
def test_default_mode_is_map(monkeypatch):
    monkeypatch.delenv("CORNER_DETECTION", raising=False)
    assert corner_service.mode() == "map" and corner_service.use_map()
    monkeypatch.setenv("CORNER_DETECTION", "LEGACY")
    assert corner_service.mode() == "legacy" and not corner_service.use_map()
    monkeypatch.setenv("CORNER_DETECTION", "nonsense")
    assert corner_service.mode() == "map"


def test_same_number_and_numbering_in_session_compare_and_optimal_lap(imola):
    cm = imola["session"]["corner_map"]
    numbers = [c["number"] for c in cm["corners"]]
    assert numbers == list(range(1, len(numbers) + 1)) and len(numbers) >= 9
    for key in ("stint", "optimal", "compare"):
        assert imola[key]["corner_map"]["corners"] == cm["corners"], key   # the very same map object
    stint = [c["corner_number"] for c in imola["stint"]["curvas_sesion"]["corners"]]
    comp = [c["corner_number"] for c in imola["compare"]["corners"]]
    opt = [c["corner_number"] for c in imola["optimal"]["corners"]]
    apx = [a["corner_number"] for a in imola["compare"]["apexes"]]
    assert stint == comp == apx == numbers
    assert set(opt) <= set(numbers) and len(opt) >= len(numbers) - 1
    # names agree between every panel of every endpoint
    by_n = {c["number"]: c["name"] for c in cm["corners"]}
    for blk in (imola["stint"]["curvas_sesion"]["corners"], imola["compare"]["corners"], imola["compare"]["apexes"],
                imola["optimal"]["corners"]):
        for c in blk:
            assert c["corner_name"] == by_n[c["corner_number"]]
    for z in imola["optimal"]["top_zones"]:
        if z["corner_number"]:
            assert z["corner_name"] == by_n[z["corner_number"]]
    for c in imola["stint"]["racing_line_rl"]["corners"]:
        assert c["corner_name"] == by_n[c["corner_number"]]


def test_imola_names_and_kinds(imola):
    cm = imola["session"]["corner_map"]
    names = [c["name"] for c in cm["corners"] if c["name"]]
    assert names == IMOLA_NAMES
    assert cm["n_named"] == 9 and cm["circuit"]["id"] == "imola" and cm["method"] == "consensus+template"
    bassa = next(c for c in cm["corners"] if c["name"] == "Variante Bassa")
    assert bassa["kind"] == "flat_out" and bassa["flat_out_share"] > 0.5
    assert next(c for c in cm["corners"] if c["name"] == "Tamburello")["kind"] == "braking"
    # additive object: documented keys, no heavy series
    assert set(cm) >= {"circuit", "method", "params", "n_corners", "n_named", "warnings", "corners"}
    assert {"number", "name", "fraction", "apex_distance_m", "start_m", "end_m", "kind", "direction",
            "min_radius_m", "confidence", "is_complex", "sub_apexes", "flat_out_share"} <= set(cm["corners"][0])
    assert len(str(cm)) < 40_000


def test_compare_apexes_sectors_and_corners_agree(imola):
    comp = imola["compare"]
    n = len(comp["apexes"])
    assert len(comp["sectores"]) == n + 1
    for s in comp["sectores"]:
        k = s["sector"]
        assert s["from_corner_number"] == (k - 1 if k > 1 else None)
        assert s["to_corner_number"] == (k if k <= n else None)
    by_n = {a["corner_number"]: a["corner_name"] for a in comp["apexes"]}
    assert s["from_corner_name"] == by_n[n]                              # the last sector starts at the last corner
    assert comp["metadata"]["apexes_detected"] == n == len(comp["corners"])
    # UI contract kept: every field the current panels read
    for c in comp["corners"]:
        assert {"corner_number", "start_distance", "end_distance", "apex_distance", "time_loss_seconds",
                "braking_delta_meters", "apex_speed_delta_kmh", "throttle_delta_meters", "description",
                "corner_name"} <= set(c)
    for a in comp["apexes"]:
        assert {"Distance", "Curvature", "Speed", "Throttle", "corner_number", "corner_name"} <= set(a)
    # windows are disjoint: the corner losses never exceed the lap delta plus what the straights gain back
    wins = sorted((c["start_distance"], c["end_distance"]) for c in comp["corners"])
    assert all(a[1] <= b[0] + 1e-6 for a, b in zip(wins, wins[1:]))
    s = comp["summary"]
    assert abs(s["corners_time_delta_s"] + s["outside_corners_delta_s"] - s["total_time_delta"]) < 0.01


# ── flat_out ──────────────────────────────────────────────────────────────────────
def test_flat_out_has_time_loss_but_no_braking_apex_throttle(imola):
    fl = [c for c in imola["stint"]["curvas_sesion"]["corners"] if c["kind"] == "flat_out"]
    assert [c["corner_name"] for c in fl] == ["Variante Bassa"]
    c = fl[0]
    assert c["braking_available"] is False and c["apex_available"] is False and c["throttle_available"] is False
    assert c["braking_delta_meters"] == 0.0 and c["apex_speed_delta_kmh"] == 0.0 and c["throttle_delta_meters"] == 0.0
    assert isinstance(c["time_loss_seconds"], float) and isinstance(c["std_loss_seconds"], float)
    assert c["n_laps"] >= 3 and "flat out" in c["description"] and "Variante Bassa" in c["description"]
    # the same in comparison mode
    cc = next(c for c in imola["compare"]["corners"] if c["kind"] == "flat_out")
    assert cc["braking_delta_available"] is False and cc["throttle_delta_available"] is False
    assert cc["apex_delta_available"] is False and cc["apex_speed_delta_kmh"] == 0.0
    assert isinstance(cc["time_loss_seconds"], float) and cc["corner_name"] == "Variante Bassa"
    # a braking corner does measure them
    t = next(c for c in imola["stint"]["curvas_sesion"]["corners"] if c["corner_name"] == "Tamburello")
    assert t["braking_available"] and t["apex_available"] and t["throttle_available"]
    # optimal lap keeps the flat-out corner as a zone with its own gain
    o = next(c for c in imola["optimal"]["corners"] if c["corner_name"] == "Variante Bassa")
    assert o["kind"] == "flat_out" and o["gain_theoretical_s"] >= 0


def test_racing_line_and_setup_ignore_flat_out_corners(imola):
    flat = {c["number"] for c in imola["session"]["corner_map"]["corners"] if c["kind"] in ("flat_out", "kink")}
    assert flat
    rl = imola["stint"]["racing_line_rl"]
    assert rl["available"] and not flat & {c["corner_number"] for c in rl["corners"]}
    pri = imola["stint"]["setup_sesion"].get("corner_priority") or []
    assert not flat & {c["corner_number"] for c in pri}
    for c in rl["corners"]:                       # structure untouched
        assert {"corner_number", "n_laps", "mean_time_loss_s", "potential_gain_s", "current_execution",
                "optimal_execution", "recommendations", "q_heatmap"} <= set(c)


# ── the switch ────────────────────────────────────────────────────────────────────
def test_legacy_switch_restores_old_detectors(client, csvs, monkeypatch, imola):
    monkeypatch.setenv("CORNER_DETECTION", "legacy")
    p = csvs["imola_5laps"]
    stint = _post(client, "/api/stint/analyze", p, field="laps")
    comp = _post(client, "/api/compare-session-laps", p, lap_a="0", lap_b="0")
    assert "corner_map" not in stint and "corner_map" not in comp
    assert "corner_map" not in _post(client, "/api/analyze-session", p)
    legacy_names = [c["corner_name"] for c in stint["curvas_sesion"]["corners"] if c["corner_name"]]
    assert "Variante Bassa" not in legacy_names
    assert len(stint["curvas_sesion"]["corners"]) < len(imola["stint"]["curvas_sesion"]["corners"])
    assert all("kind" not in c for c in stint["curvas_sesion"]["corners"])       # old shape, untouched
    assert all("kind" not in c for c in comp["corners"])
    # what is not a corner is identical between the modes
    for k in ("laps", "degradacion", "combustible", "montecarlo", "telemetria_sesion"):
        assert stint[k] == imola["stint"][k], k
    assert comp["time_delta_series"] == imola["compare"]["time_delta_series"]
    assert comp["summary"]["total_time_delta"] == imola["compare"]["summary"]["total_time_delta"]


# ── cache ─────────────────────────────────────────────────────────────────────────
def test_map_is_built_once_and_shared_between_endpoints(client, csvs):
    session_cache.corner_map_cache.clear()
    before = session_cache.corner_map_cache.builds
    with open(csvs["imola_5laps"], "rb") as fh:
        up = client.post("/api/files", files={"file": ("imola.csv", fh, "text/csv")})
    assert up.status_code == 200
    fid = up.json()["file_id"]
    r1 = client.post("/api/analyze-session", data={"file_id": fid}, params={"lang": "en"})
    r2 = client.post("/api/stint/analyze", data={"file_id": fid}, params={"lang": "en"})
    r3 = client.post("/api/optimal-lap", data={"file_id": fid}, params={"lang": "en"})
    r4 = client.post("/api/compare-session-laps", data={"file_id": fid, "lap_a": "0", "lap_b": "0"},
                     params={"lang": "en"})
    assert all(r.status_code == 200 for r in (r1, r2, r3, r4))
    assert session_cache.corner_map_cache.builds - before == 1
    assert session_cache.corner_map_cache.hits >= 3
    maps = [r.json()["corner_map"]["corners"] for r in (r1, r2, r3, r4)]
    assert maps[0] == maps[1] == maps[2] == maps[3]
    # uploading the same bytes again (classic mode) is the same SHA-256: still no new build
    _post(client, "/api/stint/analyze", csvs["imola_5laps"], field="laps")
    assert session_cache.corner_map_cache.builds - before == 1


def test_cache_key_and_lru(monkeypatch):
    c = session_cache.CornerMapCache()
    monkeypatch.setenv("CORNER_MAP_CACHE_MAX", "2")
    calls = []

    def builder(tag):
        def f():
            calls.append(tag)
            return {"tag": tag}
        return f

    assert c.get_or_build(("a",), builder("a")) == {"tag": "a"}
    assert c.get_or_build(("a",), builder("a2")) == {"tag": "a"}      # hit
    c.get_or_build(("b",), builder("b"))
    c.get_or_build(("c",), builder("c"))                                # evicts the least recently used
    assert len(c._data) == 2 and calls == ["a", "b", "c"]
    c.get_or_build(("a",), builder("a3"))
    assert calls[-1] == "a3"
    got = c.get_or_build(("a",), builder("x"))
    got["tag"] = "mutated"                                              # callers get a copy
    assert c.get_or_build(("a",), builder("y")) == {"tag": "a3"}
    assert c.get_or_build(("n",), lambda: None) is None                 # a failed build is not cached
    assert c.builds >= 4


# ── unknown circuit, few laps, one lap ─────────────────────────────────────────────
def test_unknown_circuit_uses_telemetry_consensus(client, csvs):
    stint = _post(client, "/api/stint/analyze", csvs["unknown_5laps"], field="laps")
    cm = stint["corner_map"]
    assert cm["circuit"] is None and cm["method"] == "consensus" and cm["n_named"] == 0
    assert cm["n_corners"] >= 5 and any("unknown circuit" in w for w in cm["warnings"])
    cs = stint["curvas_sesion"]
    assert cs["available"] and len(cs["corners"]) == cm["n_corners"]
    assert all(c["corner_name"] is None for c in cs["corners"])
    assert not stint["circuit"]["recognized"]
    comp = _post(client, "/api/compare-session-laps", csvs["unknown_5laps"], lap_a="0", lap_b="0")
    assert len(comp["corners"]) == cm["n_corners"] and comp["circuit"]["recognized"] is False
    opt = _post(client, "/api/optimal-lap", csvs["unknown_5laps"])
    assert opt["available"] and len(opt["corners"]) >= cm["n_corners"] - 1


def test_three_lap_session_works(client, csvs):
    spa = _post(client, "/api/stint/analyze", csvs["spa_3laps"], field="laps")
    cm = spa["corner_map"]
    assert spa["curvas_sesion"]["available"] and cm["n_corners"] >= 10 and cm["n_laps"] == 3
    assert [c["name"] for c in cm["corners"] if c["name"]][:3] == ["La Source", "Eau Rouge / Raidillon", "Les Combes"]
    assert [c["corner_number"] for c in spa["curvas_sesion"]["corners"]] == [c["number"] for c in cm["corners"]]
    assert spa["racing_line_rl"]["available"] is False or all(c["n_laps"] >= 2 for c in spa["racing_line_rl"]["corners"])


def test_single_lap_and_two_laps(client, csvs):
    from src.io.loaders import load_telemetry_data
    from src.processing.filters import apply_standard_filters
    df = apply_standard_filters(load_telemetry_data(str(csvs["rbr_fast"])))
    from src.analytics.corner_map import build_corner_map
    one = build_corner_map([df], "ks_red_bull_ring")
    assert one["summary"]["n_laps"] == 1 and one["summary"]["n_corners"] >= 6
    assert any("relaxed" in w for w in one["summary"]["warnings"])
    assert all(c["confidence"] <= 0.9 for c in one["corners"])
    # two single-lap files through the comparison endpoints: same map in both, relaxed warning
    a, b = csvs["rbr_fast"], csvs["rbr_slow"]
    basic = _pair(client, "/api/compare-laps", a, b, ("lap_a", "lap_b"))
    adv = _pair(client, "/api/telemetry/analyze", a, b, ("lap_fast", "lap_slow"))
    for js in (basic, adv):
        cm = js["corner_map"]
        assert cm["n_laps"] == 2 and any("relaxed" in w for w in cm["warnings"])
        assert {c["corner_number"] for c in js["corners"]} <= {c["number"] for c in cm["corners"]}
        assert len(js["corners"]) >= cm["n_corners"] - 1                      # a corner window needs >= 10 samples
    assert [c["corner_number"] for c in basic["corners"]] == [c["corner_number"] for c in adv["corners"]]
    assert [a_["corner_number"] for a_ in adv["apexes"]] == [c["number"] for c in adv["corner_map"]["corners"]]
    assert basic["summary"]["num_corners_analyzed"] == len(basic["corners"])


def test_pair_endpoints_share_one_map_build(client, csvs):
    session_cache.corner_map_cache.clear()
    before = session_cache.corner_map_cache.builds
    a, b = csvs["rbr_fast"], csvs["rbr_slow"]
    _pair(client, "/api/compare-laps", a, b, ("lap_a", "lap_b"))
    _pair(client, "/api/telemetry/analyze", a, b, ("lap_fast", "lap_slow"))
    assert session_cache.corner_map_cache.builds - before == 1


def test_select_map_laps_handles_short_stints():
    import numpy as np
    import pandas as pd

    def lap(n_m):
        return pd.DataFrame({"Distance": np.arange(0.0, n_m, 1.0), "Speed": 100.0})

    laps = [lap(1366), lap(1638), lap(1638), lap(1496)]
    df_laps = pd.DataFrame({"lap_time_s": [56.3, 48.2, 46.7, 49.9], "is_pit_lap": [False] * 4})
    sel = corner_service.select_map_laps(laps, df_laps)
    assert [len(x) for x in sel] == [1638, 1638]                         # the usual length wins, not the median
    df_laps["is_pit_lap"] = [True, False, False, True]
    assert len(corner_service.select_map_laps(laps, df_laps)) == 2
    # a full lap and a short trailing segment (the file of a single flying lap): the full lap, not the
    # "fastest" 9 s fragment
    frag = [lap(3261), lap(235)]
    sel = corner_service.select_map_laps(frag, pd.DataFrame({"lap_time_s": [99.8, 9.35], "is_pit_lap": [False, False]}))
    assert [len(x) for x in sel] == [3261]


# ── names from the map in circuits.py ──────────────────────────────────────────────
def test_circuits_map_path_keeps_map_names():
    cmap = {"corners": [{"number": 1, "name": "Alpha"}, {"number": 2, "name": None}]}
    rows = [{"corner_number": 1}, {"corner_number": 2}, {"corner_number": 3}]
    C.annotate_corners_from_map(cmap, rows)
    assert [r["corner_name"] for r in rows] == ["Alpha", None, None]
    res = {"corner_map": cmap, "corners": [{"corner_number": 1, "apex_distance": 99999.0}],
           "apexes": [{"Distance": 1.0, "corner_number": 1}]}
    C.enrich_compare(res, "fn_imola", 4909.0)
    assert res["corners"][0]["corner_name"] == "Alpha" and res["apexes"][0]["corner_name"] == "Alpha"
    old = {"corners": [{"corner_number": 1, "apex_distance": 713.0}]}
    C.enrich_compare(old, "fn_imola", 4909.0)                            # no map: distance matching as before
    assert old["corners"][0]["corner_name"] == "Tamburello"


# ── PDF ───────────────────────────────────────────────────────────────────────────
def test_pdf_marks_flat_out_corner(imola):
    fitz = pytest.importorskip("pymupdf")
    from src.io.pdf_exporter import export_session_report_pdf
    for lang, mark in (("en", "flat out"), ("es", "a fondo")):
        pdf = export_session_report_pdf(imola["session"], imola["stint"], lang=lang)
        doc = fitz.open(stream=pdf, filetype="pdf")
        text = "\n".join(p.get_text() for p in doc)
        assert "Variante Bassa" in text and mark in text.lower()
        assert re.search(r"\b10\b", text)
