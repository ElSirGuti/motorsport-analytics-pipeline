"""Compare CORNER_DETECTION=legacy against CORNER_DETECTION=map on the real endpoints.

Everything that is NOT a corner must be identical between the two modes (laps, times, best lap,
fuel, degradation, Monte Carlo, optimal lap, chart data, data quality...). This script runs the
endpoints in-process (FastAPI TestClient) with the switch in both positions on the same input and:

  1. reports the differences OUTSIDE the corner keys (numeric tolerance 1e-6) -> must be none;
  2. summarises what changed in the corner keys (number of corners, names, flat-out corners).

Usage (PYTHONUTF8=1 recommended):

    python scripts/compare_corner_modes.py [FILE ...] [--no-fixtures] [--no-downloads]
                                           [--endpoints analyze-session,stint,optimal-lap,compare-session-laps]
                                           [--pairs] [--tol 1e-6] [--json out.json]

Without FILE it uses tests/fixtures (imola_5laps, spa_3laps and the rbr_* single laps as pairs) and, if they
exist, the CSV of the Downloads folder (cayman_gt4_imola_assetto_corsa.csv, porsche_gt4_spa.csv,
vuelta_rapida.csv, ...). A key is a "corner key" (excluded from the identity check) when it is in CORNER_KEYS (whole block) or in
CORNER_FIELDS (a corner number / name inside another block) below. Exit code 1 when a non-corner difference exists.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
_TMP = tempfile.mkdtemp(prefix="cornermodes_")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP.replace(os.sep, '/')}/t.db")
os.environ.setdefault("STORAGE_DIR", os.path.join(_TMP, "storage"))
logging.disable(logging.WARNING)

# Blocks whose content legitimately changes with the corner detector. Matching is by key NAME anywhere in
# the JSON (a corner list inside optimal-lap, a block of the stint result, ...).
CORNER_KEYS = {
    "corner_map", "corners", "apexes", "sectores", "curvas_sesion", "racing_line_rl", "setup_sesion",
    "corner_clusters", "tiempo_potencial", "xgboost_pred", "dynamic_events", "setup_advisor", "text_report",
    # derived from the corner list / the apexes
    "telemetria",            # RDP-compressed series: it keeps the apex samples
    "apexes_detected", "num_corners_analyzed", "worst_corner", "worst_corner_loss", "corners_time_delta_s",
    "outside_corners_delta_s", "history_samples", "compression_ratio",
}
# fields dropped wherever they appear (a number / name of a corner inside an otherwise non-corner block,
# e.g. the zones of the optimal lap or the sector rows)
CORNER_FIELDS = {"corner_number", "corner_label", "corner_name", "corner_kind", "from_corner_number",
                 "to_corner_number", "from_corner_name", "to_corner_name", "descripcion"}
VOLATILE = ("generated_at", "elapsed", "created_at")

DOWNLOADS = Path.home() / "Downloads"
FIXTURES = ROOT / "tests" / "fixtures"


def _strip(obj):
    """Copy of the JSON without the corner keys."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items()
                if k not in CORNER_KEYS and k not in CORNER_FIELDS and k not in VOLATILE}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def diff(a, b, path="", tol=1e-6, out=None):
    out = out if out is not None else []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'map' if k not in a else 'legacy'}")
            else:
                diff(a[k], b[k], f"{path}/{k}", tol, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: len legacy={len(a)} map={len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diff(x, y, f"{path}[{i}]", tol, out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if not (a == b or abs(a - b) <= tol * max(1.0, abs(a), abs(b)) or (math.isnan(a) and math.isnan(b))):
            out.append(f"{path}: legacy={a} map={b}")
    elif a != b:
        out.append(f"{path}: legacy={str(a)[:50]!r} map={str(b)[:50]!r}")
    return out


def _gunzip(src: Path, dst: Path) -> Path:
    with gzip.open(src, "rb") as f, open(dst, "wb") as o:
        shutil.copyfileobj(f, o)
    return dst


def collect_inputs(args) -> tuple:
    """([(label, path)], [(label, path_a, path_b)])"""
    work = Path(_TMP) / "inputs"
    work.mkdir(parents=True, exist_ok=True)
    sessions, pairs = [], []
    if args.files:
        sessions = [(Path(f).stem, Path(f)) for f in args.files]
    else:
        if not args.no_fixtures:
            for n in ("imola_5laps", "spa_3laps"):
                src = FIXTURES / f"{n}.csv.gz"
                if src.exists():
                    sessions.append((n, _gunzip(src, work / f"{n}.csv")))
            single = {}
            for n in ("rbr_fast", "rbr_slow", "rbr_other_car"):
                src = FIXTURES / f"{n}.csv.gz"
                if src.exists():
                    single[n] = _gunzip(src, work / f"{n}.csv")
            if "rbr_fast" in single and "rbr_slow" in single:
                pairs.append(("rbr_fast vs rbr_slow", single["rbr_fast"], single["rbr_slow"]))
            if "rbr_fast" in single and "rbr_other_car" in single:
                pairs.append(("rbr_fast vs rbr_other_car", single["rbr_fast"], single["rbr_other_car"]))
        if not args.no_downloads:
            for n in ("cayman_gt4_imola_assetto_corsa.csv", "porsche_gt4_spa.csv"):
                if (DOWNLOADS / n).exists():
                    sessions.append((Path(n).stem, DOWNLOADS / n))
            if (DOWNLOADS / "vuelta_rapida.csv").exists() and (DOWNLOADS / "vuelta_lenta.csv").exists():
                pairs.append(("vuelta_rapida vs vuelta_lenta (Downloads)",
                              DOWNLOADS / "vuelta_rapida.csv", DOWNLOADS / "vuelta_lenta.csv"))
    return sessions, pairs


def _call(client, endpoint, files, data):
    t0 = time.perf_counter()
    r = client.post(endpoint, files=files, data=data, params={"lang": "en"})
    return r, time.perf_counter() - t0


def run_session(client, label, path, endpoints):
    """{endpoint: {mode: (json, seconds)}} for one session file."""
    from src.io import session_cache
    out: dict = {}
    for ep in endpoints:
        url, field, extra = {
            "analyze-session": ("/api/analyze-session", "session_file", {}),
            "stint": ("/api/stint/analyze", "laps", {}),
            "optimal-lap": ("/api/optimal-lap", "session_file", {}),
            "compare-session-laps": ("/api/compare-session-laps", "session_file", {"lap_a": "0", "lap_b": "0"}),
        }[ep]
        out[ep] = {}
        for mode in ("legacy", "map"):
            os.environ["CORNER_DETECTION"] = mode
            session_cache.cache.clear()
            session_cache.corner_map_cache.clear()
            with open(path, "rb") as fh:
                r, dt = _call(client, url, {field: (path.name, fh, "text/csv")}, extra)
            if r.status_code != 200:
                out[ep][mode] = ({"__error__": f"{r.status_code} {r.text[:160]}"}, dt)
            else:
                out[ep][mode] = (r.json(), dt)
    return out


def run_pair(client, label, a, b, endpoints=("compare-laps", "telemetry/analyze")):
    out: dict = {}
    for ep in endpoints:
        keys = ("lap_a", "lap_b") if ep == "compare-laps" else ("lap_fast", "lap_slow")
        out[ep] = {}
        for mode in ("legacy", "map"):
            os.environ["CORNER_DETECTION"] = mode
            from src.io import session_cache
            session_cache.corner_map_cache.clear()
            with open(a, "rb") as fa, open(b, "rb") as fb:
                r, dt = _call(client, f"/api/{ep}", {keys[0]: (a.name, fa, "text/csv"),
                                                    keys[1]: (b.name, fb, "text/csv")}, {})
            out[ep][mode] = (r.json() if r.status_code == 200 else {"__error__": f"{r.status_code} {r.text[:160]}"}, dt)
    return out


def corner_summary(js: dict) -> dict:
    """Corner facts of a response, whichever block carries them."""
    cm = js.get("corner_map") or {}
    corners = None
    for key in ("corners",):
        if isinstance(js.get(key), list):
            corners = js[key]
    cs = js.get("curvas_sesion")
    if isinstance(cs, dict) and cs.get("available"):
        corners = cs.get("corners")
    named = [c.get("corner_name") or c.get("name") for c in (corners or []) if isinstance(c, dict)]
    return {
        "n": len(corners) if corners is not None else None,
        "names": [n for n in named if n],
        "map_n": cm.get("n_corners"),
        "map_named": cm.get("n_named"),
        "flat": [c["number"] for c in cm.get("corners", []) if c.get("kind") in ("flat_out", "kink")],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--no-fixtures", action="store_true")
    ap.add_argument("--no-downloads", action="store_true")
    ap.add_argument("--endpoints", default="analyze-session,stint,optimal-lap,compare-session-laps")
    ap.add_argument("--no-pairs", action="store_true")
    ap.add_argument("--tol", type=float, default=1e-6)
    ap.add_argument("--json", type=Path, help="write the full report here")
    args = ap.parse_args()

    from fastapi.testclient import TestClient
    import main as app_main
    client = TestClient(app_main.app)
    sessions, pairs = collect_inputs(args)
    endpoints = [e for e in args.endpoints.split(",") if e]
    bad = 0
    report: list = []

    def handle(label, ep, res):
        nonlocal bad
        (lj, lt), (mj, mt) = res["legacy"], res["map"]
        if "__error__" in lj or "__error__" in mj:
            print(f"  {ep}: ERROR legacy={lj.get('__error__')} map={mj.get('__error__')}")
            bad += 1
            return
        d = diff(_strip(lj), _strip(mj), tol=args.tol)
        sl, sm = corner_summary(lj), corner_summary(mj)
        status = "IDENTICAL outside corner keys" if not d else f"{len(d)} DIFFERENCES"
        print(f"  {ep}: {status}   time legacy {lt:.2f}s / map {mt:.2f}s")
        print(f"      corners legacy={sl['n']} map={sm['n']}  map_n={sm['map_n']} named={sm['map_named']} flat_out={sm['flat']}")
        if sl["names"] or sm["names"]:
            print(f"      names legacy={sl['names']}\n      names map   ={sm['names']}")
        for x in d[:12]:
            print("      !", x)
        bad += bool(d)
        report.append({"input": label, "endpoint": ep, "differences": d, "legacy": sl, "map": sm,
                       "seconds": {"legacy": round(lt, 3), "map": round(mt, 3)}})

    for label, path in sessions:
        print(f"\n## {label}  ({path})")
        for ep, res in run_session(client, label, path, endpoints).items():
            handle(label, ep, res)
    if not args.no_pairs:
        for label, a, b in pairs:
            print(f"\n## {label}")
            for ep, res in run_pair(client, label, a, b).items():
                handle(label, ep, res)
    os.environ.pop("CORNER_DETECTION", None)
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(_TMP, ignore_errors=True)
    print("\nRESULT:", "all identical outside the corner keys" if not bad else f"{bad} input/endpoint with differences")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
