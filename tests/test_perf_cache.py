"""Upload-once / cache / parse-speed tests (synthetic data only).

Covers: POST /api/files + ``file_id`` on the analysis endpoints (same JSON as sending the file),
410 handling, parse-once under concurrency, LRU/TTL/lock behaviour of the frame cache, upload
cleanup, and numerical equivalence of the optimised code paths with reference implementations.
"""
from __future__ import annotations

import io
import json
import math
import threading
import time

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from src.io import session_cache as sc  # noqa: E402


# ── synthetic MoTeC-like export ───────────────────────────────────────────────
def _motec_csv(n_laps: int = 5, hz: int = 20, lap_s: float = 80.0, decimal: str = ".",
               units: bool = True, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    rows = []
    for lap in range(n_laps):
        ls = lap_s + (0.0, 1.2, -0.8, 2.0, 0.5)[lap % 5]       # different lap times
        n = int(ls * hz)
        t = np.arange(n) / hz
        phase = 2 * np.pi * t / ls
        speed = 130 + 55 * np.sin(4 * phase) + rng.normal(0, 0.4, n) + lap * 0.3
        brake = np.clip(-np.cos(4 * phase) * 140 - 90, 0, 100)
        throttle = np.clip(np.cos(4 * phase) * 140 + 30, 0, 100)
        dist = np.cumsum(speed / 3.6 / hz)
        rows.append(pd.DataFrame({
            "Distance": dist, "Speed": speed, "Brake": brake, "Throttle": throttle,
            "Gear": np.clip((speed // 40).astype(int), 1, 6),
            "RPM": 4000 + speed * 25,
            "Steering Angle": 40 * np.sin(4 * phase),
            "G Force Lat": 1.6 * np.sin(4 * phase), "G Force Long": -0.8 * np.cos(4 * phase),
            "Car Coord X": 300 * np.cos(phase), "Car Coord Y": 200 * np.sin(phase),
            "Fuel Level": 60 - (lap + t / ls) * 1.8,
            "Session Lap Count": float(lap), "Lap Time": t,
            "Tire Temp Core FL": 80 + 5 * np.sin(phase), "Tire Temp Core FR": 82 + 5 * np.sin(phase),
            "Tire Temp Core RL": 78 + 3 * np.sin(phase), "Tire Temp Core RR": 79 + 3 * np.sin(phase),
            "Suspension Travel FL": 40 + 20 * np.sin(8 * phase), "Suspension Travel FR": 40 + 20 * np.cos(8 * phase),
            "Suspension Travel RL": 45 + 15 * np.sin(8 * phase), "Suspension Travel RR": 45 + 15 * np.cos(8 * phase),
        }))
    df = pd.concat(rows, ignore_index=True)
    cols = list(df.columns)
    out = io.StringIO()
    out.write('"Format","MoTeC CSV File",,,"Workbook",""\n"Venue","synthetic_ring",,,"Worksheet",""\n')
    out.write('"Vehicle","test_car",,,"Vehicle Desc",""\n"Driver","Tester",,,"Engine ID",""\n\n\n')
    out.write(",".join(f'"{c}"' for c in cols) + "\n")
    if units:
        out.write(",".join('"s"' if c != "Gear" else '""' for c in cols) + "\n")
    out.write("\n")
    for rec in df.itertuples(index=False):
        vals = []
        for v in rec:
            s = f"{v:.4f}" if isinstance(v, (float, np.floating)) else str(int(v))
            vals.append(f'"{s.replace(".", decimal)}"' if decimal != "." else s)
        out.write(",".join(vals) + "\n")
    return out.getvalue().encode("utf-8")


@pytest.fixture(scope="module")
def csv_bytes() -> bytes:
    return _motec_csv()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated upload dir + empty frame cache."""
    monkeypatch.setattr(sc.store, "_dir", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    sc.cache.clear()
    sc.cache.hits = sc.cache.misses = 0
    yield tmp_path
    sc.cache.clear()


@pytest.fixture
def client(env):
    return TestClient(main.app)


def _upload(client, data: bytes, name="session.csv"):
    r = client.post("/api/files", files={"file": (name, data, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def _strip_volatile(o):
    if isinstance(o, dict):
        return {k: _strip_volatile(v) for k, v in o.items() if k not in ("generated_at",)}
    if isinstance(o, list):
        return [_strip_volatile(v) for v in o]
    return o


def _assert_close(a, b, path="", tol=1e-6):
    if isinstance(a, dict) and isinstance(b, dict):
        assert a.keys() == b.keys(), (path, set(a) ^ set(b))
        for k in a:
            _assert_close(a[k], b[k], f"{path}/{k}", tol)
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _assert_close(x, y, f"{path}[{i}]", tol)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        assert a == b or abs(a - b) <= tol * max(1.0, abs(a), abs(b)), (path, a, b)
    else:
        assert a == b, (path, a, b)


# ── POST /api/files ───────────────────────────────────────────────────────────
def test_upload_returns_sha256_and_metadata(client, csv_bytes):
    import hashlib
    meta = _upload(client, csv_bytes, "ring.csv")
    assert meta["file_id"] == hashlib.sha256(csv_bytes).hexdigest()
    assert meta["filename"] == "ring.csv" and meta["size_bytes"] == len(csv_bytes)
    assert meta["venue"] == "synthetic_ring" and meta["vehicle"] == "test_car" and meta["format"] == "csv"
    assert _upload(client, csv_bytes)["file_id"] == meta["file_id"]      # idempotent


def test_upload_respects_max_upload(client, monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1000)
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 3)
    r = client.post("/api/files?lang=es", files={"file": ("a.csv", b"x" * 5000, "text/csv")})
    assert r.status_code == 413 and "3 MB" in r.json()["detail"]
    assert not list(sc.store.dir.glob("*.part")), "partial upload must be removed"


def test_empty_upload_rejected(client):
    r = client.post("/api/files", files={"file": ("a.csv", b"", "text/csv")})
    assert r.status_code == 400


def test_unknown_or_malformed_file_id(client):
    r = client.post("/api/analyze-session?lang=es", data={"file_id": "a" * 64})
    assert r.status_code == 410 and "vuelve a subirlo" in r.json()["detail"].lower()
    r = client.post("/api/analyze-session?lang=en", data={"file_id": "b" * 64})
    assert r.status_code == 410 and "upload it again" in r.json()["detail"]
    assert client.post("/api/analyze-session", data={"file_id": "../../etc/passwd"}).status_code == 422
    assert client.post("/api/analyze-session").status_code == 422        # neither file nor id
    assert client.get("/api/files/" + "c" * 64).status_code == 410


def test_file_status_endpoint(client, csv_bytes):
    fid = _upload(client, csv_bytes)["file_id"]
    r = client.get(f"/api/files/{fid}")
    assert r.status_code == 200 and r.json()["file_id"] == fid


# ── file_id endpoints return the same JSON as the classic upload ─────────────
def test_endpoints_equivalent_file_id_vs_classic(client, csv_bytes):
    fid = _upload(client, csv_bytes, "ring.csv")["file_id"]
    f = {"session_file": ("ring.csv", csv_bytes, "text/csv")}

    sc.cache.clear()
    a = client.post("/api/analyze-session", files=f).json()
    b = client.post("/api/analyze-session", data={"file_id": fid}).json()
    _assert_close(_strip_volatile(a), _strip_volatile(b))
    assert a["total_laps"] == 5

    sc.cache.clear()
    a = client.post("/api/stint/analyze", files={"laps": ("ring.csv", csv_bytes, "text/csv")})
    b = client.post("/api/stint/analyze", data={"file_id": fid})
    assert a.status_code == b.status_code == 200, (a.text[:200], b.text[:200])
    _assert_close(_strip_volatile(a.json()), _strip_volatile(b.json()))

    sc.cache.clear()
    a = client.post("/api/optimal-lap", files=f, data={"lang": "en"})
    b = client.post("/api/optimal-lap", data={"file_id": fid, "lang": "en"})
    assert a.status_code == b.status_code == 200
    _assert_close(_strip_volatile(a.json()), _strip_volatile(b.json()))

    sc.cache.clear()
    a = client.post("/api/compare-session-laps", files=f, data={"lap_a": "0", "lap_b": "0"})
    b = client.post("/api/compare-session-laps", data={"file_id": fid, "lap_a": "0", "lap_b": "0"})
    assert a.status_code == b.status_code == 200, (a.text[:200], b.text[:200])
    _assert_close(_strip_volatile(a.json()), _strip_volatile(b.json()))


def test_setups_detect_accepts_file_id(client, csv_bytes):
    fid = _upload(client, csv_bytes)["file_id"]
    r = client.post("/api/setups/detect", data={"file_id": fid})
    assert r.status_code == 200
    classic = client.post("/api/setups/detect", files={"header": ("h.csv", csv_bytes[:32768], "text/csv")})
    assert r.json() == classic.json()


def test_telemetry_analyze_accepts_file_ids(client):
    one = _motec_csv(n_laps=1, seed=1)
    two = _motec_csv(n_laps=1, seed=2)
    a = client.post("/api/telemetry/analyze", files={"lap_fast": ("a.csv", one, "text/csv"),
                                                     "lap_slow": ("b.csv", two, "text/csv")})
    ida, idb = _upload(client, one, "a.csv")["file_id"], _upload(client, two, "b.csv")["file_id"]
    b = client.post("/api/telemetry/analyze", data={"lap_fast_id": ida, "lap_slow_id": idb})
    assert a.status_code == b.status_code == 200, (a.text[:300], b.text[:300])
    ja, jb = a.json(), b.json()
    for k in ("metadata", "xgboost_pred", "tiempo_potencial", "data_quality"):
        ja.pop(k, None), jb.pop(k, None)           # history-dependent / volatile
    _assert_close(ja, jb)


def test_classic_mode_still_validates_input(client):
    r = client.post("/api/analyze-session", files={"session_file": ("x.csv", b"not,a,telemetry\n1,2,3\n", "text/csv")})
    assert r.status_code == 400


# ── parse once, even concurrently / across replicas ──────────────────────────
def _count_parses(monkeypatch):
    from src.io import loaders
    calls = {"n": 0}
    real = loaders.load_telemetry_data

    def counting(path, *a, **k):
        calls["n"] += 1
        time.sleep(0.05)               # widen the race window
        return real(path, *a, **k)

    monkeypatch.setattr(loaders, "load_telemetry_data", counting)
    return calls


def test_file_is_parsed_once_across_endpoints(client, csv_bytes, monkeypatch):
    calls = _count_parses(monkeypatch)
    fid = _upload(client, csv_bytes)["file_id"]
    for url in ("/api/analyze-session", "/api/stint/analyze", "/api/optimal-lap", "/api/compare-session-laps"):
        assert client.post(url, data={"file_id": fid}).status_code == 200, url
    assert calls["n"] == 1
    assert sc.cache.stats()["hits"] > 0


def test_classic_uploads_share_the_parse_via_sha(client, csv_bytes, monkeypatch):
    calls = _count_parses(monkeypatch)
    f = {"session_file": ("ring.csv", csv_bytes, "text/csv")}
    client.post("/api/analyze-session", files=f)
    client.post("/api/optimal-lap", files=f)
    assert calls["n"] == 1


def test_concurrent_requests_parse_once(client, csv_bytes, monkeypatch):
    calls = _count_parses(monkeypatch)
    fid = _upload(client, csv_bytes)["file_id"]
    out = []

    def go(url):
        out.append(client.post(url, data={"file_id": fid}).status_code)

    ts = [threading.Thread(target=go, args=(u,)) for u in
          ("/api/analyze-session", "/api/stint/analyze", "/api/optimal-lap", "/api/analyze-session")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out == [200] * 4
    assert calls["n"] == 1


def test_other_replica_reloads_from_disk_then_410_when_gone(client, csv_bytes, monkeypatch):
    calls = _count_parses(monkeypatch)
    fid = _upload(client, csv_bytes)["file_id"]
    assert client.post("/api/analyze-session", data={"file_id": fid}).status_code == 200
    sc.cache.clear()                                   # = another pod: no memory, same volume
    assert client.post("/api/analyze-session", data={"file_id": fid}).status_code == 200
    assert calls["n"] == 2
    (sc.store.dir / f"{fid}.csv").unlink()             # = uploads purged / pod without the volume
    sc.cache.clear()
    r = client.post("/api/analyze-session?lang=en", data={"file_id": fid})
    assert r.status_code == 410


def test_cached_frames_are_private_copies(env, csv_bytes):
    stored = sc.store.save_stream(io.BytesIO(csv_bytes), "a.csv", 10**9)
    a = sc.raw_frame(stored.file_id, stored.path)
    a["Speed"] = -1.0
    a.loc[:, "Brake"] = 99.0
    b = sc.raw_frame(stored.file_id, stored.path)
    assert (b["Speed"] > 0).all() and (b["Brake"] != 99.0).any()
    fa = sc.filtered_frame(stored.file_id, stored.path)
    fa.loc[:, "Throttle"] = -5.0
    assert (sc.filtered_frame(stored.file_id, stored.path)["Throttle"] > -5.0).all()
    assert (sc.raw_frame(stored.file_id, stored.path)["Throttle"] > -5.0).all()   # raw shares nothing with it


# ── frame cache mechanics ────────────────────────────────────────────────────
def _frame(n_rows: int) -> pd.DataFrame:
    return pd.DataFrame({"a": np.zeros(n_rows)})      # 8 bytes / row


def test_lru_evicts_by_bytes(monkeypatch):
    c = sc.FrameCache()
    monkeypatch.setenv("SESSION_CACHE_MAX_MB", "1")
    one_mb_third = (1024 * 1024 - 4096) // 8 // 3              # three frames fit, four do not
    for k in "abcd":
        c.get_or_load((k,), lambda: _frame(one_mb_third))
    assert c.stats()["entries"] == 3
    loads = {"n": 0}

    def loader():
        loads["n"] += 1
        return _frame(one_mb_third)

    c.get_or_load(("a",), loader)                    # evicted (oldest) -> reload
    assert loads["n"] == 1


def test_value_larger_than_budget_is_not_cached(monkeypatch):
    c = sc.FrameCache()
    monkeypatch.setenv("SESSION_CACHE_MAX_MB", "1")
    n = {"n": 0}

    def loader():
        n["n"] += 1
        return _frame(1024 * 1024)                   # 8 MB

    c.get_or_load(("big",), loader)
    c.get_or_load(("big",), loader)
    assert n["n"] == 2 and c.stats()["entries"] == 0


def test_ttl_expiry(monkeypatch):
    c = sc.FrameCache()
    monkeypatch.setenv("SESSION_CACHE_TTL_MIN", "0.01")      # 0.6 s
    n = {"n": 0}

    def loader():
        n["n"] += 1
        return _frame(10)

    c.get_or_load(("k",), loader)
    c.get_or_load(("k",), loader)
    assert n["n"] == 1
    time.sleep(0.8)
    c.get_or_load(("k",), loader)
    assert n["n"] == 2


def test_loader_failure_is_not_cached():
    c = sc.FrameCache()
    n = {"n": 0}

    def loader():
        n["n"] += 1
        raise ValueError("boom")

    for _ in range(2):
        with pytest.raises(ValueError):
            c.get_or_load(("bad",), loader)
    assert n["n"] == 2


# ── upload store ─────────────────────────────────────────────────────────────
def test_store_limit_and_cleanup(env, monkeypatch):
    store = sc.UploadStore(env / "u2")
    with pytest.raises(sc.UploadTooLarge):
        store.save_stream(io.BytesIO(b"x" * 100), "a.csv", 10)
    assert not list((env / "u2").glob("*.part"))
    f = store.save_stream(io.BytesIO(b"hello,world\n1,2\n"), "a.csv", 1000)
    assert store.get(f.file_id).filename == "a.csv"
    assert store.get("zz") is None and store.get("0" * 64) is None
    monkeypatch.setenv("UPLOAD_TTL_HOURS", "0.01")            # 36 s
    old = time.time() - 3600
    import os
    for p in (env / "u2").iterdir():
        os.utime(p, (old, old))
    assert store.clean_now() >= 2
    assert store.get(f.file_id) is None


def test_cleanup_runs_in_background_thread(env, monkeypatch):
    store = sc.UploadStore(env / "u3")
    store.CLEAN_EVERY_S = 0.0
    before = threading.active_count()
    store.save_stream(io.BytesIO(b"a,b\n1,2\n"), "a.csv", 1000)      # triggers maybe_clean()
    time.sleep(0.2)
    assert threading.active_count() <= before + 1


def test_upload_dir_resolution(monkeypatch, tmp_path):
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    monkeypatch.setenv("TEMP_DIR", str(tmp_path / "t"))
    monkeypatch.delenv("STORAGE_DIR", raising=False)
    assert sc.upload_dir() == tmp_path / "t" / "uploads"
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "s"))
    assert sc.upload_dir() == tmp_path / "s" / "uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "x"))
    assert sc.upload_dir() == tmp_path / "x"


# ── parser: fast path == reference normalisation ─────────────────────────────
@pytest.mark.parametrize("decimal", [".", ","])
@pytest.mark.parametrize("units", [True, False])
def test_loader_fast_path_matches_reference(tmp_path, decimal, units):
    from src.io.loaders import load_telemetry_data
    raw = _motec_csv(n_laps=2, decimal=decimal, units=units)
    p = tmp_path / "s.csv"
    p.write_bytes(raw)
    df = load_telemetry_data(str(p))

    # reference: everything as text -> drop units row -> comma->dot -> to_numeric (the old slow path)
    lines = raw.decode("utf-8").splitlines()
    hdr = next(i for i, l in enumerate(lines) if l.startswith('"Distance"'))
    ref = pd.read_csv(io.StringIO("\n".join(lines[hdr:])), dtype=str, skip_blank_lines=True)
    if units:
        ref = ref.iloc[1:]
    assert len(df) == len(ref)
    for col in ("Distance", "Speed", "Steering Angle", "G Force Lat"):
        want = pd.to_numeric(ref[col].str.replace(",", ".", regex=False), errors="coerce").to_numpy(float)
        got_col = {"Steering Angle": "SteerAngle", "G Force Lat": "LateralG"}.get(col, col)
        np.testing.assert_allclose(df[got_col].to_numpy(float), want, rtol=1e-12)
    assert all(df[c].dtype != object for c in ("Distance", "Speed", "Brake", "Throttle"))


# ── interpolation: batched spline == per-column interp1d ─────────────────────
def test_align_by_distance_matches_per_column_interp1d():
    from scipy.interpolate import interp1d
    from src.processing.alignment import align_by_distance
    rng = np.random.default_rng(3)
    n = 800
    d = np.cumsum(rng.uniform(0.5, 2.0, n))
    df = pd.DataFrame({
        "Distance": d, "Speed": 100 + 40 * np.sin(d / 50), "Brake": rng.uniform(0, 100, n),
        "Throttle": rng.uniform(0, 100, n), "Gear": rng.integers(1, 6, n),
        "Flag": rng.integers(0, 2, n).astype(np.int64), "Name": ["x"] * n,
    })
    df.loc[10:20, "Throttle"] = np.nan
    out = align_by_distance(df, 1.0)
    new = np.arange(np.ceil(d.min()), np.floor(d.max()) + 1.0, 1.0)
    assert list(out.columns) == ["Distance", "Speed", "Brake", "Throttle", "Gear", "Flag"]
    for col in ("Speed", "Brake", "Throttle", "Gear", "Flag"):
        kind = "nearest" if col == "Gear" else "cubic"
        ref = interp1d(d, df[col].to_numpy(float), kind=kind, bounds_error=False, fill_value="extrapolate")(new)
        if col in ("Speed", "Brake", "Throttle"):
            ref = np.clip(ref, 0, 100 if col != "Speed" else None)
        np.testing.assert_allclose(out[col].to_numpy(), ref, rtol=1e-10, atol=1e-10, equal_nan=True)
    assert np.isnan(out["Throttle"]).any() and not np.isnan(out["Speed"]).any()   # NaN stays in its column


def test_align_pair_with_precomputed_reference_is_identical():
    from src.processing.alignment import align_by_distance, align_pair
    laps = pd.read_csv(io.StringIO(_motec_csv(n_laps=2).decode().split("\n\n\n", 1)[1].replace('"x"', '0'))) \
        if False else None
    assert laps is None
    rng = np.random.default_rng(5)

    def lap(seed):
        r = np.random.default_rng(seed)
        d = np.cumsum(r.uniform(0.8, 1.2, 600))
        return pd.DataFrame({"Distance": d, "Speed": 120 + 30 * np.sin(d / 40), "Brake": r.uniform(0, 50, 600),
                             "Throttle": r.uniform(0, 100, 600)})

    a, b = lap(1), lap(2)
    x1, y1 = align_pair(a, b)
    x2, y2 = align_pair(a, b, pre_a=align_by_distance(a))
    pd.testing.assert_frame_equal(x1, x2)
    pd.testing.assert_frame_equal(y1, y2)


def test_corner_observations_slim_channels_equal_full_frame():
    """get_corner_observations only aligns the 4 channels it reads; result must not change."""
    from src.analytics import stint as st
    from src.analytics.session_corner_analysis import get_corner_observations
    from src.io.loaders import load_telemetry_data
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "s.csv")
        open(p, "wb").write(_motec_csv(n_laps=5))
        laps = st.segmentar_vueltas_desde_csv(load_telemetry_data(p))
    dl = st.extraer_metricas_por_vuelta(laps)
    slim = get_corner_observations(laps, dl)
    from src.processing.alignment import align_pair
    from src.telemetry.lap_comparator import _estimate_corner_time_loss
    from src.telemetry.metrics import segment_corners, pair_corners
    ref_idx = int(dl.loc[~dl["is_pit_lap"] & dl["lap_time_s"].notna(), "lap_time_s"].idxmin())
    full = {}
    for idx in dl.index:
        if idx == ref_idx or dl.loc[idx, "is_pit_lap"] or pd.isna(dl.loc[idx, "lap_time_s"]):
            continue
        al_a, al_b = align_pair(laps[ref_idx], laps[idx])
        ca, cb = segment_corners(al_a), segment_corners(al_b)
        for i, a, b in pair_corners(ca, cb):
            full.setdefault(i + 1, []).append({
                "time_loss": float(_estimate_corner_time_loss(al_a, al_b, a, b)),
                "brake_delta": float(b["braking_point"]["distance"] - a["braking_point"]["distance"]),
                "apex_delta": float(b["apex"]["speed"] - a["apex"]["speed"]),
                "thtl_delta": float(b["full_throttle"]["distance"] - a["full_throttle"]["distance"]),
            })
    keep = ("time_loss", "brake_delta", "apex_delta", "thtl_delta")      # other keys are additive extras
    slim = {k: [{f: o[f] for f in keep} for o in v] for k, v in slim.items()}
    assert slim and slim == full


# ── suspension: vectorised bottoming == original loop ────────────────────────
def _bottoming_reference(distance, travel, label):
    from src.analytics.suspension import BOTTOM_FRACTION, MIN_DURATION_M, SMOOTH_WINDOW_M
    ts = travel.rolling(window=SMOOTH_WINDOW_M, center=True, min_periods=1).median()
    max_t = float(ts.max())
    if max_t < 1.0:
        return []
    bottoming = ts >= max_t * BOTTOM_FRACTION
    events, in_ev, start = [], False, 0

    def add(s, e_excl, end_idx):
        sm, em = float(distance.iloc[s]), float(distance.iloc[end_idx])
        if em - sm >= MIN_DURATION_M:
            seg = float(ts.iloc[s:e_excl].max())
            events.append({"corner": label, "start_m": round(sm, 0), "end_m": round(em, 0),
                           "max_travel": round(seg, 1), "severity": round(seg / max_t, 3)})

    for i in range(len(bottoming)):
        if bottoming.iloc[i] and not in_ev:
            in_ev, start = True, i
        elif not bottoming.iloc[i] and in_ev:
            in_ev = False
            add(start, i, i - 1)
    if in_ev:
        add(start, len(bottoming), len(bottoming) - 1)
    return events


def test_bottoming_events_vectorised_equals_loop():
    from src.analytics.suspension import _bottoming_events
    rng = np.random.default_rng(11)
    for trial in range(60):
        n = int(rng.integers(5, 2500))
        travel = pd.Series(np.abs(np.cumsum(rng.normal(0, 3, n))) + rng.normal(0, 1, n))
        if trial % 5 == 0:
            travel.iloc[rng.integers(0, n, 3)] = np.nan
        dist = pd.Series(np.arange(n, dtype=float))
        assert _bottoming_events(dist, travel, "FL") == _bottoming_reference(dist, travel, "FL")
    flat = pd.Series(np.zeros(50))
    assert _bottoming_events(pd.Series(np.arange(50.0)), flat, "FL") == []


def test_standard_filters_do_not_touch_the_input():
    from src.processing.filters import apply_standard_filters
    df = pd.DataFrame({"Speed": np.r_[np.full(50, 100.0), 900.0, np.full(50, 100.0)],
                       "Brake": 0.0, "Throttle": 50.0, "LateralG": np.random.default_rng(0).normal(size=101),
                       "Other": np.arange(101.0)})
    snap = df.copy()
    out = apply_standard_filters(df)
    pd.testing.assert_frame_equal(df, snap)
    assert not out["LateralG"].equals(df["LateralG"])
    out.loc[:, "Other"] = -1.0                  # default is a fully independent copy
    pd.testing.assert_frame_equal(df, snap)
    light = apply_standard_filters(df, deep=False)      # cache mode: same values, shared unchanged arrays
    pd.testing.assert_frame_equal(light, apply_standard_filters(df))
    pd.testing.assert_frame_equal(df, snap)
