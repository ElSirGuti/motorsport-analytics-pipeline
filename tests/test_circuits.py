"""Known circuits and corner names (src/analytics/circuits.py + src/data/circuits.json)."""
from __future__ import annotations

import copy
import gzip
import json
import os
import shutil

import pytest

from src.analytics import circuits as C

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


# ── database ──────────────────────────────────────────────────────────────────
def _raw_db() -> dict:
    return json.loads(C.DB_PATH.read_text(encoding="utf-8"))


def test_database_is_valid():
    assert C.validate_database(_raw_db()) == []


def test_database_content_policy():
    circuits = C.load_circuits()
    assert {"imola", "spa_francorchamps"} <= set(circuits)
    for c in circuits.values():
        assert c["confidence"] in ("high", "medium")
        assert c["source"].strip()
        # a corner table is only published for circuits validated against telemetry
        if c["corners"]:
            assert c["confidence"] == "high", c["id"]
    assert [k["name"] for k in circuits["imola"]["corners"]][:7] == [
        "Tamburello", "Villeneuve", "Tosa", "Piratella", "Acque Minerali", "Variante Alta", "Rivazza 1"]
    names = [k["name"] for k in circuits["spa_francorchamps"]["corners"]]
    for expected in ("La Source", "Eau Rouge / Raidillon", "Les Combes", "Malmedy", "Rivage", "Pouhon",
                     "Fagnes", "Stavelot", "Blanchimont", "Bus Stop"):
        assert expected in names


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d["circuits"].append(copy.deepcopy(d["circuits"][0])), "duplicated id"),
    (lambda d: d["circuits"][0].update(confidence="certain"), "confidence"),
    (lambda d: d["circuits"][0].update(country="Italy"), "country"),
    (lambda d: d["circuits"][0].update(length_m=12), "length_m"),
    (lambda d: d["circuits"][0]["corners"][1].update(apex_fraction=0.01), "strictly ordered"),
    (lambda d: d["circuits"][0]["corners"][1].update(apex_fraction=1.2), "apex_fraction"),
    (lambda d: d["circuits"][0]["corners"][1].update(name=d["circuits"][0]["corners"][0]["name"]), "duplicated name"),
    (lambda d: d["circuits"][1]["aliases"].append("fn_imola"), "alias"),
    (lambda d: d["circuits"][0].pop("source"), "source"),
])
def test_validator_rejects_bad_entries(mutate, fragment):
    data = _raw_db()
    mutate(data)
    errors = C.validate_database(data)
    assert errors and any(fragment in e for e in errors), errors


def test_load_is_cached():
    assert C.load_circuits() is C.load_circuits()


# ── recognition ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("venue,cid", [
    ("fn_imola", "imola"), ("imola", "imola"), ("Imola", "imola"), ("  IMOLA ", "imola"),
    ("ks_imola", "imola"), ("Autodromo Enzo e Dino Ferrari", "imola"),
    ("spa", "spa_francorchamps"), ("ks_spa", "spa_francorchamps"), ("Spa-Francorchamps", "spa_francorchamps"),
    ("Circuit de Spa-Francorchamps", "spa_francorchamps"),
    ("ks_red_bull_ring", "red_bull_ring"), ("ks_silverstone", "silverstone"), ("monaco_2020", "monaco"),
    ("ks_nordschleife", "nordschleife"), ("Oran Park Raceway (Grand Prix)", "oran_park_gp"),
    ("Oran Park Raceway (South)", "oran_park_south"), ("Lime Rock Park (Grand Prix)", "lime_rock_gp"),
    ("acu_sepang", "sepang"), ("sx_lemans", "le_mans"), ("Nürburgring Nordschleife", "nordschleife"),
])
def test_recognition_by_alias(venue, cid):
    assert C.find_circuit(venue)["id"] == cid
    info = C.recognize(venue)
    assert info["recognized"] and info["id"] == cid and info["matched"]


def test_generic_prefix_fallback():
    assert C.find_circuit("zw_imola")["id"] == "imola"


@pytest.mark.parametrize("venue", [None, "", "   ", "unknown_track", "el capitan", "ks_monza66_unknown"])
def test_unknown_venue(venue):
    info = C.recognize(venue, 4900)
    assert info["id"] is None and not info["recognized"] and not info["matched"]
    assert info["confidence"] is None and info["name"] is None


def test_length_tolerance():
    ok = C.recognize("imola", 4909 * 1.039)
    assert ok["matched"] and ok["confidence"] == "high"
    ok = C.recognize("imola", 4909 * 0.961)
    assert ok["matched"]
    bad = C.recognize("imola", 4909 * 1.06)
    assert bad["recognized"] and not bad["matched"] and bad["confidence"] == "low"
    assert bad["id"] == "imola"  # still reported as a recognised venue, but flagged
    assert C.recognize("imola", 2500)["confidence"] == "low"


def test_unmeasured_length_caps_confidence():
    info = C.recognize("imola", None)
    assert info["matched"] and info["confidence"] == "medium"


def test_low_confidence_gets_no_names():
    info = C.recognize("imola", 2900)          # a partial lap
    corners = [{"corner_number": 1, "apex_distance": 720.0}]
    C.annotate_corners(info, corners, "apex_distance", 2900)
    assert corners[0]["corner_name"] is None


# ── name assignment (synthetic apexes) ────────────────────────────────────────
IMOLA = C.get_circuit("imola")
L = 4865.0


def _at(*fractions):
    return [(i, f * L) for i, f in enumerate(fractions)]


def test_assigns_names_in_order():
    res = C.assign_names(IMOLA, _at(0.15, 0.30, 0.355, 0.48), L)
    assert [res[i]["name"] for i in range(4)] == ["Tamburello", "Villeneuve", "Tosa", "Piratella"]


def test_never_duplicates_a_name():
    # three apexes around Tamburello: only the closest one gets the name
    res = C.assign_names(IMOLA, [("a", 0.140 * L), ("b", 0.149 * L), ("c", 0.158 * L)], L)
    assert [v["name"] for v in res.values()].count("Tamburello") == 1
    assert list(res) == ["b"]
    names = [v["name"] for v in C.assign_names(IMOLA, _at(*[k["apex_fraction"] for k in IMOLA["corners"]]), L).values()]
    assert len(names) == len(set(names)) == len(IMOLA["corners"])


def test_unmatched_apex_stays_unnamed():
    res = C.assign_names(IMOLA, _at(0.40, 0.65, 0.99), L)   # between corners
    assert res == {}


def test_tolerance_boundaries():
    tol = C.apex_tolerance_m(L)
    assert 120.0 <= tol <= 180.0
    f = IMOLA["corners"][2]["apex_fraction"] * L            # Tosa
    assert C.assign_names(IMOLA, [(0, f + tol - 1)], L)
    assert not C.assign_names(IMOLA, [(0, f + tol + 1)], L)


def test_assignment_is_order_preserving():
    # an extra apex squeezed between Villeneuve and Tosa must not steal or swap names
    res = C.assign_names(IMOLA, _at(0.294, 0.323, 0.352), L)
    assert res[0]["name"] == "Villeneuve" and res[2]["name"] == "Tosa" and 1 not in res
    orders = [res[i]["order"] for i in sorted(res)]
    assert orders == sorted(orders)


def test_assign_handles_garbage_input():
    assert C.assign_names(None, _at(0.1), L) == {}
    assert C.assign_names(IMOLA, [], L) == {}
    assert C.assign_names(IMOLA, [(0, None), (1, "x"), (2, float("nan"))], L) == {}
    assert C.assign_names({"length_m": 1000, "corners": []}, _at(0.1), L) == {}


def test_uses_measured_length_for_fractions():
    # on a lap measured 2 % short the same corner sits 2 % closer to the line
    short = L * 0.98
    res = C.assign_names(IMOLA, [(0, 0.352 * short)], short)
    assert res[0]["name"] == "Tosa"


def test_name_for_distance():
    info = C.recognize("imola", L)
    assert C.name_for_distance(info, 0.352 * L, L) == "Tosa"
    assert C.name_for_distance(info, 0.65 * L, L) is None
    assert C.name_for_distance(C.recognize("unknown"), 100, L) is None


# ── payload enrichment ───────────────────────────────────────────────────────
def test_enrich_compare_is_additive_and_consistent():
    apexes = [{"Distance": f * L, "Curvature": 0.02} for f in (0.15, 0.30, 0.40, 0.355)]
    apexes.sort(key=lambda a: a["Distance"])
    corners = [{"corner_number": i + 1, "apex_distance": a["Distance"], "time_loss_seconds": 0.1}
               for i, a in enumerate(apexes)]
    sectors = [{"sector": i + 1, "descripcion": f"s{i}"} for i in range(len(apexes) + 1)]
    result = {"apexes": apexes, "corners": corners, "sectores": sectors, "summary": {"x": 1}}
    C.enrich_compare(result, "fn_imola", L)
    assert result["circuit"]["id"] == "imola" and result["circuit"]["matched"]
    assert result["summary"] == {"x": 1}
    assert [c["corner_name"] for c in corners] == ["Tamburello", "Villeneuve", "Tosa", None]
    assert [a["corner_name"] for a in apexes] == [c["corner_name"] for c in corners]
    assert sectors[1]["from_corner_name"] == "Tamburello" and sectors[1]["to_corner_name"] == "Villeneuve"
    assert sectors[0]["from_corner_number"] is None and sectors[0]["to_corner_name"] == "Tamburello"
    assert sectors[-1]["to_corner_number"] is None
    assert all(s["descripcion"].startswith("s") for s in sectors)  # existing fields untouched


def test_enrich_compare_unknown_venue_adds_none_names():
    result = {"corners": [{"corner_number": 1, "ref_apex_distance": 700.0}], "apexes": []}
    C.enrich_compare(result, "somewhere", L)
    assert result["circuit"]["id"] is None and not result["circuit"]["matched"]
    assert result["corners"][0]["corner_name"] is None


def test_enrich_compare_basic_corners_without_apexes():
    result = {"corners": [{"corner_number": 1, "ref_apex_distance": 0.352 * L}]}
    C.enrich_compare(result, "imola", L)
    assert result["corners"][0]["corner_name"] == "Tosa"


def test_enrich_stint_names_racing_line_corners():
    result = {
        "curvas_sesion": {"available": True, "corners": [
            {"corner_number": 1, "apex_distance": 0.15 * L}, {"corner_number": 2, "apex_distance": 0.31 * L},
            {"corner_number": 3, "apex_distance": 0.40 * L}]},
        "racing_line_rl": {"available": True, "corners": [{"corner_number": 3}, {"corner_number": 1}]},
    }
    C.enrich_stint(result, "imola", L)
    assert [c["corner_name"] for c in result["curvas_sesion"]["corners"]] == ["Tamburello", "Villeneuve", None]
    assert [c["corner_name"] for c in result["racing_line_rl"]["corners"]] == [None, "Tamburello"]


def test_enrich_session_uses_median_racing_lap_length():
    laps = [{"lap_distance": 4860, "is_pit_lap": False}, {"lap_distance": 4870, "is_pit_lap": False},
            {"lap_distance": 900, "is_pit_lap": True}, {"lap_distance": 4866, "is_pit_lap": False}]
    res = C.enrich_session({"laps": laps}, "fn_imola")
    assert res["circuit"]["matched"] and res["circuit"]["measured_length_m"] == 4866


# ── regression on the real fixtures (Imola / Spa) ─────────────────────────────
_NAMES = ("imola_5laps", "spa_3laps")
real = pytest.mark.skipif(
    not all(os.path.exists(os.path.join(FIXTURES, f"{n}.csv.gz")) for n in _NAMES),
    reason="real fixtures missing")


@pytest.fixture(scope="module")
def raw_csv(tmp_path_factory):
    d = tmp_path_factory.mktemp("circuits_real")
    out = {}
    for n in _NAMES:
        p = d / f"{n}.csv"
        if os.path.exists(os.path.join(FIXTURES, f"{n}.csv.gz")):
            with gzip.open(os.path.join(FIXTURES, f"{n}.csv.gz"), "rb") as s, open(p, "wb") as o:
                shutil.copyfileobj(s, o)
            out[n] = p.read_bytes()
    return out


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)


def _post(client, path, name, raw_csv):
    field = "laps" if path.endswith("stint/analyze") else "session_file"
    r = client.post(path, files={field: (f"{name}.csv", raw_csv[name], "text/csv")})
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _check_named(items, circuit_id, length):
    """Names must be unique, be in lap order and sit within tolerance of the table."""
    entry = C.get_circuit(circuit_id)
    table = {k["name"]: k for k in entry["corners"]}
    named = [(c["apex_distance"], c["corner_name"]) for c in items if c.get("corner_name")]
    assert named, "no corner was named"
    labels = [n for _, n in named]
    assert len(labels) == len(set(labels))
    tol = C.apex_tolerance_m(length)
    for d, n in named:
        assert n in table
        assert abs(d - table[n]["apex_fraction"] * length) <= tol + 1e-6
    orders = [table[n]["order"] for _, n in sorted(named)]
    assert orders == sorted(orders)


@real
@pytest.mark.parametrize("name,cid,expected", [
    ("imola_5laps", "imola", {"Tamburello", "Villeneuve", "Tosa", "Piratella", "Acque Minerali", "Variante Alta"}),
    ("spa_3laps", "spa_francorchamps", {"La Source", "Les Combes", "Stavelot", "Bus Stop"}),
])
def test_real_session_stint_and_compare(client, raw_csv, name, cid, expected):
    sess = _post(client, "/api/analyze-session", name, raw_csv)
    assert sess["circuit"]["id"] == cid and sess["circuit"]["matched"] and sess["circuit"]["confidence"] == "high"
    assert abs(sess["circuit"]["length_deviation_pct"]) < 2.0

    stint = _post(client, "/api/stint/analyze", name, raw_csv)
    assert stint["circuit"]["id"] == cid
    corners = stint["curvas_sesion"]["corners"]
    _check_named(corners, cid, stint["circuit"]["measured_length_m"])
    assert expected <= {c["corner_name"] for c in corners}
    by_num = {c["corner_number"]: c["corner_name"] for c in corners}
    for c in stint["racing_line_rl"].get("corners", []):
        assert c["corner_name"] == by_num.get(c["corner_number"])

    cmp_ = _post(client, "/api/compare-session-laps", name, raw_csv)
    assert cmp_["circuit"]["id"] == cid
    _check_named(cmp_["corners"], cid, cmp_["circuit"]["measured_length_m"])
    # corners, apexes and sectors agree on the names
    for c in cmp_["corners"]:
        a = cmp_["apexes"][c["corner_number"] - 1]
        assert a["corner_name"] == c["corner_name"]
    for s in cmp_["sectores"]:
        k = s["sector"]
        if s["to_corner_number"]:
            assert s["to_corner_name"] == cmp_["apexes"][k - 1]["corner_name"]
    # original fields intact
    assert all("corner_number" in c and "time_loss_seconds" in c for c in cmp_["corners"])


@real
def test_real_optimal_lap_names(client, raw_csv):
    res = _post(client, "/api/optimal-lap", "imola_5laps", raw_csv)
    assert res["circuit"]["id"] == "imola"
    _check_named([c for c in res["corners"] if c.get("apex_distance") is not None],
                 "imola", res["circuit"]["measured_length_m"])
    by_num = {c["corner_number"]: c["corner_name"] for c in res["corners"]}
    for z in res["top_zones"]:
        assert z["corner_name"] == by_num.get(z["corner_number"])


# ── library & PDF ─────────────────────────────────────────────────────────────
def test_library_filters_by_canonical_circuit(client):
    payload = {"stint": {"laps": [{"lap_number": i, "lap_time_s": 100.0 + i, "is_pit_lap": False}
                                   for i in range(1, 4)], "n_laps": 3}}
    ids = []
    for venue, sha in (("fn_imola", "a" * 64), ("imola", "b" * 64), ("spa", "c" * 64), (None, "d" * 64)):
        r = client.post("/api/library", json={"venue": venue, "file_sha256": sha, "payload": payload,
                                              "title": f"t-{venue}"})
        assert r.status_code == 200, r.text
        ids.append(r.json()["session"]["id"])
    try:
        got = client.get("/api/library", params={"circuit": "imola"}).json()
        assert {i["venue"] for i in got["items"]} == {"fn_imola", "imola"}
        assert all(i["circuit"]["id"] == "imola" for i in got["items"])
        assert client.get("/api/library", params={"circuit": "monza"}).json()["total"] == 0
        facets = client.get("/api/library/facets").json()
        assert {"imola", "spa_francorchamps"} <= {c["id"] for c in facets["circuits"]}
        assert next(c for c in facets["circuits"] if c["id"] == "imola")["count"] >= 2
        spa = client.get("/api/library", params={"circuit": "spa_francorchamps"}).json()["items"]
        assert spa and spa[0]["circuit"]["name"].startswith("Circuit de Spa")
    finally:
        for i in ids:
            client.delete(f"/api/library/{i}")


def test_pdf_corner_label():
    from src.io import pdf_exporter as P
    assert P._clabel({"n": 4, "name": "Tamburello"}) == "4 · Tamburello"
    assert P._clabel({"n": 4, "name": None}) == "4"
    assert P._clabel({"n": 4, "name": "A&B"}) == "4 · A&amp;B"
    assert P._name_of(2, [{"n": 2, "name": "Tosa"}]) == "2 · Tosa"
    assert P._name_of(9, [{"n": 2, "name": "Tosa"}]) == "9"
