"""Tests de la integración de setups de Assetto Corsa (datos sintéticos)."""

import os

import pytest
from fastapi.testclient import TestClient

from src.analytics import ac_setups as ac

CAR, TRACK = "ks_test_car", "fn_testtrack"

INI = """[ABS]
VALUE=7
[ARB_FRONT]
VALUE=1
[ARB_REAR]
VALUE=0
[BRAKE_POWER_MULT]
VALUE=100
[CAMBER_LF]
VALUE=-31
[CAMBER_LR]
VALUE=-28
[CAMBER_RF]
VALUE=-31
[CAMBER_RR]
VALUE=-28
[CAR]
MODEL=ks_test_car
[FRONT_BIAS]
VALUE=68
[FUEL]
VALUE=18
[PRESSURE_LF]
VALUE=17
[PRESSURE_LR]
VALUE=18
[PRESSURE_RF]
VALUE=16
[PRESSURE_RR]
VALUE=17
[ROD_LENGTH_LF]
VALUE=9
[SPRING_RATE_LF]
VALUE=165
[SPRING_RATE_RF]
VALUE=165
[SPRING_RATE_LR]
VALUE=150
[SPRING_RATE_RR]
VALUE=150
[TOE_OUT_LR]
VALUE=110
[TRACTION_CONTROL]
VALUE=0
[TYRES]
VALUE=0
[__EXT_PATCH]
VERSION=0.3.0-preview342
"""


@pytest.fixture
def setups(tmp_path, monkeypatch):
    base = tmp_path / "setups"
    (base / CAR / TRACK).mkdir(parents=True)
    (base / CAR / "generic").mkdir(parents=True)
    monkeypatch.setenv("AC_SETUPS_DIR", str(base))
    return base


def _rec(rec_key, pos=None, **kw):
    r = {"rec_key": rec_key, "problem_key": "x", "priority": "alta", **kw}
    if pos:
        r["pos"] = pos
    return r


# ── Parsing ───────────────────────────────────────────────────────────────────

def test_parse_groups_and_values():
    s = ac.parse_setup(INI, "last.ini", "en")
    assert s["car_model"] == "ks_test_car"
    assert s["ext_patch"] == "0.3.0-preview342"
    assert s["params"]["PRESSURE_LF"]["value"] == 17
    assert s["params"]["PRESSURE_LF"]["unit"] == "psi"
    assert s["params"]["PRESSURE_LF"]["wheel"] == "FL"
    assert s["params"]["FRONT_BIAS"]["unit"] == "%"
    assert s["params"]["CAMBER_LF"]["unit"] is None  # raw clicks, no invented conversion
    ids = [g["id"] for g in s["groups"]]
    assert ids == ["tyres", "suspension", "brakes", "electronics", "other"]
    assert any(c["key"] == "pressures" and c["value"] == "17 / 16 / 18 / 17 psi" for c in s["summary"])


def test_parse_rejects_non_setup_and_binary():
    with pytest.raises(ac.SetupError):
        ac.parse_setup("[PRESET_0]\nFUEL=0\n", "last.sp")
    with pytest.raises(ac.SetupError):
        ac.decode_bytes(b"MZ\x00\x01binary")
    with pytest.raises(ac.SetupError):
        ac.decode_bytes(b"a" * (ac.MAX_SETUP_BYTES + 1))


def test_parse_upload_extension():
    assert ac.parse_upload("my.ini", INI.encode())["n_params"] > 10
    with pytest.raises(ac.SetupError):
        ac.parse_upload("evil.exe", INI.encode())


def test_header_parsing():
    raw = ('"Format","MoTeC CSV File",,,"Workbook",""\n"Venue","fn_imola",,,"Worksheet",""\n'
           '"Vehicle","ks_porsche_cayman_gt4_clubsport",,,"Vehicle Desc",""\n"Driver","A B",,,"x",""\n').encode()
    m = ac.parse_motec_header(raw)
    assert m == {"driver": "A B", "vehicle": "ks_porsche_cayman_gt4_clubsport", "venue": "fn_imola"}


# ── Path resolution + safety ──────────────────────────────────────────────────

def test_env_override(setups):
    p, exists = ac.resolve_setups_dir()
    assert p == setups and exists


def test_env_override_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("AC_SETUPS_DIR", str(tmp_path / "nope"))
    r = ac.find_candidates(CAR, TRACK, "en")
    assert r["state"] == "no_access" and r["found_dir"] is False and not r["needs_confirmation"]


def test_documents_fallbacks(monkeypatch, tmp_path):
    monkeypatch.delenv("AC_SETUPS_DIR", raising=False)
    monkeypatch.setattr(ac, "_windows_known_documents", lambda: None)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    docs = tmp_path / "Documents" / "Assetto Corsa" / "setups"
    docs.mkdir(parents=True)
    p, exists = ac.resolve_setups_dir()
    assert exists and p == docs


@pytest.mark.parametrize("bad", ["..", "../x", "a/../b", "a\\b", "C:\\Windows", "  ", "x" * 200, "a\x00b"])
def test_path_traversal_rejected(setups, bad):
    with pytest.raises(ac.SetupError):
        ac.find_candidates(bad, TRACK)
    with pytest.raises(ac.SetupError):
        ac.find_candidates(CAR, bad)


def test_setup_id_traversal_rejected(setups):
    (setups / CAR / "generic" / "last.ini").write_text(INI)
    (setups.parent / "secret.ini").write_text(INI)
    for sid in ("generic:../../secret.ini", "generic:..\\..\\secret.ini", "track:/etc/passwd",
                "generic:last.txt", "other:last.ini", "generic:"):
        with pytest.raises(ac.SetupError):
            ac.read_setup_by_id(CAR, TRACK, sid)


def test_case_insensitive_match(setups):
    (setups / CAR / TRACK / "a.ini").write_text(INI)
    r = ac.find_candidates(CAR.upper(), TRACK.upper())
    assert len(r["track_setups"]) == 1


def test_oversized_and_non_ini_files_ignored(setups):
    d = setups / CAR / TRACK
    (d / "big.ini").write_text(INI + "; " + "x" * ac.MAX_SETUP_BYTES)
    (d / "notes.txt").write_text(INI)
    (d / "garbage.ini").write_text("hello world")
    assert ac.find_candidates(CAR, TRACK)["track_setups"] == []


# ── Flows ─────────────────────────────────────────────────────────────────────

def test_flow_several_track_setups(setups):
    d = setups / CAR / TRACK
    (d / "a.ini").write_text(INI)
    (d / "b.ini").write_text(INI.replace("VALUE=17", "VALUE=19", 1))
    os.utime(d / "a.ini", (1_000_000, 1_000_000))
    (setups / CAR / "generic" / "last.ini").write_text(INI)
    r = ac.find_candidates(CAR, TRACK, "es")
    assert r["state"] == "track_setups" and r["needs_confirmation"]
    assert [e["name"] for e in r["track_setups"]] == ["b.ini", "a.ini"]  # newest first
    assert r["generic_last"] is not None
    s = ac.read_setup_by_id(CAR, TRACK, r["track_setups"][0]["id"])
    assert s["name"] == "b.ini"


def test_flow_generic_only(setups):
    (setups / CAR / "generic" / "last.ini").write_text(INI)
    r = ac.find_candidates(CAR, TRACK)
    assert r["state"] == "generic_only" and r["needs_confirmation"]
    assert r["generic_last"]["id"] == "generic:last.ini" and r["track_setups"] == []
    assert ac.read_setup_by_id(CAR, TRACK, "generic:last.ini")["n_params"] > 10


def test_flow_nothing(setups):
    r = ac.find_candidates(CAR, TRACK)
    assert r["state"] == "none" and not r["needs_confirmation"] and r["found_dir"]
    r = ac.find_candidates("unknown_car", TRACK)
    assert r["state"] == "none"


# ── Annotate ──────────────────────────────────────────────────────────────────

def _annotate(recs, ini=INI, lang="en"):
    return ac.annotate_recommendations(ac.parse_setup(ini, "t.ini", lang), recs, lang)


def test_annotate_pressure_and_camber():
    out = _annotate([_rec("setup_rec_temp_overheat", "FL"), _rec("setup_rec_camber_add", "RR")])
    a = out["recommendations"][0]["setup_link"]["actions"][0]
    assert (a["param"], a["current"], a["suggested"], a["direction"], a["unit"]) == ("PRESSURE_LF", 17, 16, "down", "psi")
    c = out["recommendations"][1]["setup_link"]["actions"][0]
    assert c["param"] == "CAMBER_RR" and c["current"] == -28
    assert c["suggested"] is None and c["status"] == "direction_only"  # camber step unverified


def test_annotate_uses_car_step_when_known():
    s = ac.parse_setup(INI, "t.ini", "en", ranges={"CAMBER_LF": {"min": -50, "max": 0, "step": 1}})
    out = ac.annotate_recommendations(s, [_rec("setup_rec_camber_add", "FL")], "en")
    a = out["recommendations"][0]["setup_link"]["actions"][0]
    assert a["suggested"] == -32 and a["status"] == "ok"


def test_annotate_at_limit_is_flagged():
    # ARB_REAR is already 0 and the advisor wants it softer.
    out = _annotate([_rec("setup_rec_thermal_rear")])
    a = out["recommendations"][0]["setup_link"]["actions"][0]
    assert a["status"] == "at_limit" and a["suggested"] is None and a["note"]
    # Pressure at the car's maximum
    s = ac.parse_setup(INI, "t.ini", "en", ranges={"PRESSURE_LF": {"min": 13, "max": 17, "step": 1}})
    a = ac.annotate_recommendations(s, [_rec("setup_rec_pressure_raise", "FL")], "en")["recommendations"][0]["setup_link"]["actions"][0]
    assert a["status"] == "at_limit"


def test_annotate_arb_bias_and_front_pressure():
    out = _annotate([_rec("setup_rec_arb_front"), _rec("setup_rec_brake_temp", "RL"),
                     _rec("setup_rec_mild_understeer")])
    arb = out["recommendations"][0]["setup_link"]["actions"][0]
    assert (arb["current"], arb["suggested"]) == (1, 2)
    bias = out["recommendations"][1]["setup_link"]["actions"][0]
    assert bias["param"] == "FRONT_BIAS" and bias["suggested"] == 69  # rear axle hot -> bias forward
    params = [a["param"] for a in out["recommendations"][2]["setup_link"]["actions"]]
    assert params == ["PRESSURE_LF", "PRESSURE_RF", "ARB_FRONT"]


def test_annotate_related_and_unmapped():
    out = _annotate([_rec("setup_rec_bottoming_session"), _rec("setup_rec_trail_braking"),
                     {"problem": "legacy rec without keys"}])
    assert [p["param"] for p in out["recommendations"][0]["setup_link"]["related"]][:1] == ["ROD_LENGTH_LF"]
    assert "setup_link" not in out["recommendations"][1]
    assert "setup_link" not in out["recommendations"][2]
    assert out["n_linked"] == 1


def test_annotate_conflicts():
    out = _annotate([_rec("setup_rec_arb_front"), _rec("setup_rec_thermal_front")])
    assert [c["param"] for c in out["conflicts"]] == ["ARB_FRONT"]


def test_annotate_ignores_missing_params():
    ini = "[ARB_FRONT]\nVALUE=3\n"
    out = _annotate([_rec("setup_rec_temp_overheat", "FL")], ini)
    assert "setup_link" not in out["recommendations"][0]


def test_advisor_exports_keys():
    from src.analytics.setup_advisor import analizar_setup_sesion
    res = analizar_setup_sesion(
        {"available": True, "corners": []}, {},
        {"tyre": {"FL": {"mean_temp": 130.0}}}, lang="en")
    rec = res["recommendations"][0]
    assert rec["rec_key"] == "setup_rec_pressure_raise" and rec["pos"] == "FL"  # unified lap/session rule
    out = _annotate(res["recommendations"])
    assert out["recommendations"][0]["setup_link"]["actions"][0]["param"] == "PRESSURE_LF"


# ── HTTP ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    import main
    return TestClient(main.app)


def test_api_flow(client, setups):
    (setups / CAR / "generic" / "last.ini").write_text(INI)
    r = client.get("/api/setups/candidates", params={"vehicle": CAR, "venue": TRACK, "lang": "es"})
    assert r.status_code == 200 and r.json()["state"] == "generic_only"
    r = client.get("/api/setups/file", params={"vehicle": CAR, "venue": TRACK, "setup_id": "generic:last.ini"})
    assert r.status_code == 200
    setup = r.json()
    r = client.post("/api/setups/annotate", json={"setup": setup, "recommendations": [_rec("setup_rec_arb_rear")]})
    assert r.status_code == 200 and r.json()["recommendations"][0]["setup_link"]["actions"]


def test_api_security_and_uploads(client, setups):
    assert client.get("/api/setups/candidates", params={"vehicle": "../..", "venue": TRACK}).status_code == 400
    assert client.get("/api/setups/file", params={"vehicle": CAR, "setup_id": "generic:../x.ini"}).status_code == 400
    r = client.post("/api/setups/parse", files={"file": ("a.ini", INI.encode())})
    assert r.status_code == 200 and r.json()["n_params"] > 10
    r = client.post("/api/setups/parse", files={"file": ("a.exe", INI.encode())})
    assert r.status_code == 400
    r = client.post("/api/setups/parse", files={"file": ("a.ini", b"x" * (ac.MAX_SETUP_BYTES + 5))})
    assert r.status_code == 413
    r = client.post("/api/setups/detect", files={"header": ("x.csv", b'"Venue","v1",,\n"Vehicle","c1",,\n')})
    assert r.json()["vehicle"] == "c1"
    assert client.post("/api/setups/annotate", json={"setup": {}, "recommendations": []}).status_code == 400
