"""Spin / slide / off-track detection and cause diagnosis (src/analytics/incidents.py)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
from src.analytics.incidents import detect_incidents
from src.i18n import set_language

HZ = 20
LAP_S = 60
LAP_M = 3000.0
ROOT = Path(__file__).resolve().parent.parent


def _lap(spin_at=None, throttle_in_spin=95.0, off=True, extra_dirt=False, with_body=True, steer_peak=60.0) -> pd.DataFrame:
    """A 60 s lap: three corners (steer + brake), body slip angle, yaw rate, tyre dirt. ``spin_at``: second
    in which the car spins (throttle ``throttle_in_spin`` at the loss, power-on oversteer)."""
    n = LAP_S * HZ
    t = np.arange(n) / HZ
    speed = np.full(n, 150.0)
    thr = np.full(n, 100.0)
    brk = np.zeros(n)
    steer = np.zeros(n)
    for c in (10, 30, 50):                        # corner centres in seconds
        m = np.abs(t - c) < 3
        steer[m] = steer_peak * np.cos((t[m] - c) / 3 * np.pi / 2)
        speed[m] = 150 - 50 * np.cos((t[m] - c) / 3 * np.pi / 2)
        brk[(t > c - 5) & (t < c - 3)] = 70
        thr[(t > c - 5) & (t < c - 1)] = 0
    yaw = steer * 0.5                              # deg/s
    beta = -yaw * 0.05                             # small slip in normal driving (opposite to the yaw)
    dirt = np.zeros(n)
    if spin_at is not None:
        i = int(spin_at * HZ)
        thr[i - 20:i + 40] = throttle_in_spin
        brk[i - 20:i + 40] = 0
        steer[i - 20:i + 5] = 70
        ramp = np.linspace(0, 1, 30)
        beta[i:i + 30] = -170 * ramp
        beta[i + 30:i + 50] = -170
        beta[i + 50:i + 70] = np.linspace(-170, -10, 20)
        yaw[i:i + 70] = 200
        speed[i:i + 70] = np.linspace(120, 15, 70)
        if off:
            dirt[i + 20:i + 60] = np.linspace(0, 1.4, 40)
            dirt[i + 60:] = np.linspace(1.4, 0.3, n - i - 60)
    vx = speed / 3.6 * np.cos(np.deg2rad(beta))
    vy = speed / 3.6 * np.sin(np.deg2rad(beta))
    d = pd.DataFrame({"Time": t, "Distance": np.linspace(0, LAP_M, n), "Speed": speed, "Throttle": thr, "Brake": brk,
                      "SteerAngle": steer, "YawRate": yaw, "LateralG": np.abs(steer) / 40.0,
                      "LongitudinalG": np.zeros(n), "Gear": np.full(n, 4.0), "LapTime": t})
    if with_body:
        d["BodyVelX"], d["BodyVelY"] = vx, vy
        for w in ("FL", "FR", "RL", "RR"):
            d[f"Dirt{w}"] = dirt
    return d


def _session(spin_lap=2, **kw):
    return [_lap(spin_at=45 if i + 1 == spin_lap else None, **kw) for i in range(4)]


def test_clean_session_has_no_events():
    r = detect_incidents([_lap() for _ in range(4)])
    assert r["available"] is True
    assert r["events"] == []
    assert r["summary"]["n_events"] == 0
    assert r["sources"]["slip"] == "body_velocity"


def test_spin_with_off_track_is_one_event_with_cause():
    set_language("en")
    r = detect_incidents(_session(spin_lap=2))
    assert r["summary"]["n_events"] == 1, r["events"]
    e = r["events"][0]
    assert e["lap"] == 2 and e["kind"] == "spin" and e["went_off"] is True
    assert e["severity"] in ("moderate", "major")
    assert e["peak_slip_deg"] >= 100
    assert 90 < e["distance_m"] < LAP_M
    assert e["primary_cause"] == "too_much_throttle"
    top = e["causes"][0]
    assert top["code"] == "too_much_throttle" and top["score"] >= 0.45
    assert top["label"] and top["advice"] and top["evidence"]
    assert all("{" not in ev["text"] for ev in top["evidence"])      # every placeholder was filled
    assert e["trace"]["t"][0] < 0 < e["trace"]["t"][-1] and len(e["trace"]["speed"]) == len(e["trace"]["t"])


def test_localised_texts_and_key_parity():
    set_language("es")
    try:
        e = detect_incidents(_session(spin_lap=3))["events"][0]
        assert "acelerador" in e["causes"][0]["label"].lower()
    finally:
        set_language("en")
    en = json.loads((ROOT / "src/locales/extra/incidents.en.json").read_text(encoding="utf-8"))
    es = json.loads((ROOT / "src/locales/extra/incidents.es.json").read_text(encoding="utf-8"))
    assert set(en) == set(es)
    # every cause the module can emit has label + advice, every evidence key exists
    src = (ROOT / "src/analytics/incidents.py").read_text(encoding="utf-8")
    import re
    for code in set(re.findall(r'add\("([a-z_]+)"', src)):
        assert f"inc_cause_{code}" in en and f"inc_advice_{code}" in en, code
    for key in set(re.findall(r'_ev\("(inc_ev_[a-z_]+)"', src)):
        assert key in en, key


def test_spin_in_the_other_laps_does_not_leak():
    r = detect_incidents(_session(spin_lap=4))
    assert [e["lap"] for e in r["events"]] == [4]


def test_big_slide_saved_is_not_a_spin():
    laps = _session(spin_lap=2)
    d = laps[1]
    i = int(45 * HZ)
    # shrink the slide: the car never goes beyond 60 degrees and rotates < 100 degrees
    for w in ("FL", "FR", "RL", "RR"):
        d[f"Dirt{w}"] = 0.0
    scale = 60 / 170
    vb = d["BodyVelY"].to_numpy() / np.maximum(d["BodyVelX"].to_numpy(), 1e-3)
    beta = np.arctan(vb) * 0 + np.deg2rad(np.clip(np.rad2deg(np.arctan2(d["BodyVelY"], d["BodyVelX"])), -60, 60))
    sp = d["Speed"].to_numpy() / 3.6
    d["BodyVelX"], d["BodyVelY"] = sp * np.cos(beta), sp * np.sin(beta)
    d["YawRate"] = np.where(np.arange(len(d)) < i + 70, np.minimum(d["YawRate"], 60.0), d["YawRate"])
    assert scale < 1
    r = detect_incidents(laps)
    assert [e["kind"] for e in r["events"]] == ["slide"]
    assert r["events"][0]["severity"] == "minor"


def test_off_track_only_from_tyre_dirt():
    laps = _session(spin_lap=0)
    d = laps[0]
    i = 600
    dirt = np.zeros(len(d))
    dirt[i:i + 30] = np.linspace(0, 0.9, 30)
    dirt[i + 30:] = np.linspace(0.9, 0.2, len(d) - i - 30)
    for w in ("FL", "FR", "RL", "RR"):
        d[f"Dirt{w}"] = dirt
    r = detect_incidents(laps)
    assert [(e["lap"], e["kind"]) for e in r["events"]] == [(1, "off_track")]
    assert r["events"][0]["off_track"]["wheels"] == 4
    assert r["sources"]["off_track"] == "tire_dirt"


def test_one_wheel_on_a_kerb_is_ignored():
    laps = _session(spin_lap=0)
    laps[0]["DirtFL"] = np.r_[np.zeros(600), np.linspace(0, 0.4, 10), np.full(len(laps[0]) - 610, 0.3)]
    assert detect_incidents(laps)["events"] == []


def test_no_signals_does_not_crash():
    bare = [_lap(with_body=False).drop(columns=["YawRate"]) for _ in range(3)]
    r = detect_incidents(bare)
    assert r["available"] is True and r["events"] == []
    assert detect_incidents([])["available"] is False
    assert detect_incidents([pd.DataFrame({"Speed": [1.0, 2.0]})])["available"] is False


def test_yaw_only_fallback_finds_the_spin():
    laps = [l.drop(columns=[c for c in l.columns if c.startswith(("BodyVel", "Dirt"))]) for l in _session(spin_lap=2)]
    r = detect_incidents(laps)
    assert r["sources"]["slip"] == "yaw_only"
    assert [e["kind"] for e in r["events"]] == ["spin"]


def test_hot_spot_when_the_same_corner_repeats():
    laps = [_lap(spin_at=45) for _ in range(3)] + [_lap()]
    r = detect_incidents(laps)
    assert r["summary"]["n_events"] == 3
    assert r["summary"]["hot_spots"] and r["summary"]["hot_spots"][0]["count"] == 3


def test_corner_is_named_from_the_corner_map():
    cmap = {"summary": {"lap_length_m": LAP_M},
            "corners": [{"number": 3, "name": "Test Corner", "kind": "braking",
                         "start_m": 1900.0, "end_m": 2300.0, "apex_distance_m": 2100.0}]}
    e = detect_incidents(_session(spin_lap=2), cmap)["events"][0]
    assert e["corner"] and e["corner"]["corner_name"] == "Test Corner" and e["corner"]["corner_number"] == 3


def test_ld_and_csv_channel_names_map_to_canonical():
    from src.io.loaders import COLUMN_ALIASES
    assert "Chassis Velocity X" in COLUMN_ALIASES["BodyVelX"]
    assert "Tire Dirt Level RR" in COLUMN_ALIASES["DirtRR"]
    assert "PlayerTrackSurface" in COLUMN_ALIASES["TrackSurface"]


def write_session_csv(path, spin_lap=2) -> None:
    """One CSV with four laps (a spin in ``spin_lap``) using the channel names of an ACTI export."""
    frames = _session(spin_lap=spin_lap)
    big = pd.concat(
        [f.assign(**{"Session Lap Count": i, "Time": f["Time"] + i * (LAP_S + 1)}) for i, f in enumerate(frames)],
        ignore_index=True)
    big["LapTime"] = big["Time"] - (big["Session Lap Count"] * (LAP_S + 1))
    big["Distance"] = np.concatenate([f["Distance"].to_numpy() + i * LAP_M for i, f in enumerate(frames)])
    big = big.rename(columns={"BodyVelX": "Chassis Velocity X", "BodyVelY": "Chassis Velocity Y",
                              "DirtFL": "Tire Dirt Level FL", "DirtFR": "Tire Dirt Level FR",
                              "DirtRL": "Tire Dirt Level RL", "DirtRR": "Tire Dirt Level RR"})
    big.to_csv(path, index=False)


def test_api_session_and_stint_return_incidents(tmp_path):
    path = tmp_path / "session.csv"
    write_session_csv(path)
    c = TestClient(main.app)
    for url in ("/api/analyze-session", "/api/stint/analyze"):
        with open(path, "rb") as fh:
            r = c.post(url, files={"session_file" if "session" in url else "laps": ("session.csv", fh, "text/csv")})
        assert r.status_code == 200, r.text[:300]
        inc = r.json().get("incidents")
        assert inc and inc["available"], url
        assert any(e["kind"] == "spin" for e in inc["events"]), (url, inc["events"])


@pytest.mark.skipif(not all((ROOT / "tests/fixtures" / f"{n}.csv.gz").exists() for n in ("imola_5laps", "spa_3laps")),
                    reason="real fixtures missing")
def test_real_fixtures_position_yaw_no_false_positives_and_finds_the_real_spin(tmp_path):
    """Clean Imola laps give no incident; the Spa session contains a real spin in its last lap (found from
    position + yaw rate: those CSVs have neither body velocity nor tyre dirt)."""
    import gzip
    import shutil

    from src.analytics.stint import segmentar_vueltas_desde_csv
    from src.io.loaders import load_telemetry_data

    def run(name):
        out = tmp_path / f"{name}.csv"
        with gzip.open(ROOT / "tests/fixtures" / f"{name}.csv.gz", "rb") as a, open(out, "wb") as b:
            shutil.copyfileobj(a, b)
        return detect_incidents(segmentar_vueltas_desde_csv(load_telemetry_data(str(out))))

    imola = run("imola_5laps")
    assert imola["available"] and imola["events"] == [] and imola["sources"]["slip"] == "position_yaw"
    spa = run("spa_3laps")
    spins = [e for e in spa["events"] if e["kind"] == "spin"]
    assert len(spa["events"]) == 1 and len(spins) == 1
    assert spins[0]["lap"] == 4 and 3000 < spins[0]["distance_m"] < 3400
