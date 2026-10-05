"""Reproducible profile of the full analysis pipeline.

Usage (PYTHONUTF8=1 recommended):

    python scripts/profile_pipeline.py FILE [FILE ...] [--repeat N] [--cprofile]
                                       [--dump DIR] [--compare DIR_A DIR_B]
                                       [--skip-endpoints] [--skip-stages]

Sections printed as markdown tables:

* STAGES    : wall time of each pipeline primitive called directly (CSV read,
              filters, segmentation, session analysis, every stint module,
              data quality, optimal lap).
* ENDPOINTS : wall time of each HTTP endpoint through an in-process
              ``TestClient`` (multipart upload + analysis + JSON encode + decode),
              first in the classic mode (file sent every time) and, when
              ``POST /api/files`` exists, in ``file_id`` mode (upload once).
              Also JSON payload size and process peak RSS.
* --dump    : stores every endpoint JSON under DIR/<file-stem>/ so that two code
              versions can be compared with ``--compare DIR_A DIR_B``
              (numeric tolerance 1e-6).

Network cost is not part of the in-process numbers; measure it with a real
uvicorn (see the report in docs / PR) by pointing ``--url`` at a running server.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import logging
import math
import os
import pstats
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONUTF8", "1")
logging.disable(logging.WARNING)


def _rss_mb() -> float:
    try:
        import psutil  # type: ignore
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        try:
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                     ctypes.byref(pmc), pmc.cb)
            return pmc.PeakWorkingSetSize / 1e6
        except Exception:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


@contextmanager
def _timer(rows: list, name: str):
    t0 = time.perf_counter()
    yield
    rows.append((name, time.perf_counter() - t0))


def _print_table(title: str, rows: list, total_label: str | None = None):
    print(f"\n### {title}\n")
    print("| stage | seconds |\n|---|---:|")
    for n, s in rows:
        print(f"| {n} | {s:.3f} |")
    if total_label:
        print(f"| **{total_label}** | **{sum(s for _, s in rows):.3f}** |")


# ── Stages ───────────────────────────────────────────────────────────────────
def profile_stages(path: str, with_cprofile: bool):
    from src.io.loaders import load_telemetry_data
    from src.processing.filters import apply_standard_filters
    from src.telemetry.session_analyzer import analyze_session
    from src.analytics import stint as st
    from src.analytics.session_corner_analysis import analizar_curvas_sesion, get_corner_observations
    from src.analytics.session_telemetry_analysis import analizar_telemetria_sesion
    from src.analytics.setup_advisor import analizar_setup_sesion
    from src.analytics.thermal_management import analizar_termica
    from src.analytics.tyre_degradation import predecir_degradacion_neumatico
    from src.analytics.racing_line_rl import optimizar_trazada_rl
    from src.analytics.data_quality import safe_assess, build_meta
    from src.analytics.optimal_lap import calcular_vuelta_optima_desde_df

    rows: list = []
    prof = cProfile.Profile() if with_cprofile else None
    if prof:
        prof.enable()
    with _timer(rows, "read_csv + normalise (load_telemetry_data)"):
        df = load_telemetry_data(path)
    with _timer(rows, "apply_standard_filters"):
        dff = apply_standard_filters(df)
    with _timer(rows, "segmentar_vueltas_desde_csv (filtered)"):
        laps_f = st.segmentar_vueltas_desde_csv(dff)
    with _timer(rows, "analyze_session (raw df)"):
        sess = analyze_session(df)
    with _timer(rows, "data_quality (session)"):
        safe_assess(df, build_meta(path, os.path.basename(path), "session"), sess, "en")
    with _timer(rows, "segmentar_vueltas_desde_csv (raw, stint)"):
        dfs = st.segmentar_vueltas_desde_csv(df)
    with _timer(rows, "stint: extraer_metricas_por_vuelta"):
        dl = st.extraer_metricas_por_vuelta(dfs)
    with _timer(rows, "stint: degradacion"):
        deg = st.analizar_degradacion_stint(dl)
    with _timer(rows, "stint: combustible"):
        st.calcular_estrategia_combustible(dl, dfs=dfs)
    with _timer(rows, "stint: montecarlo"):
        st.simular_tiempos_stint(dl, deg)
    obs = {}
    cmap = None
    try:   # unified corner map (CORNER_DETECTION=map, the default); None with CORNER_DETECTION=legacy
        from src.analytics import corner_service
        from src.io.loaders import read_motec_metadata
        with _timer(rows, f"stint: corner map build (CORNER_DETECTION={corner_service.mode()})"):
            cmap = corner_service.session_corner_map(dfs, read_motec_metadata(path).get("venue"), None, dl)
    except ImportError:   # versions before the unified corner map
        pass
    with _timer(rows, "stint: corner observations"):
        obs = get_corner_observations(dfs, dl, corner_map=cmap) if cmap else get_corner_observations(dfs, dl)
    with _timer(rows, "stint: analizar_curvas_sesion"):
        cs = analizar_curvas_sesion(dfs, dl, lang="en", precomputed_obs=obs, corner_map=cmap) if cmap             else analizar_curvas_sesion(dfs, dl, lang="en", precomputed_obs=obs)
    with _timer(rows, "stint: analizar_telemetria_sesion"):
        ts = analizar_telemetria_sesion(dfs, dl)
    with _timer(rows, "stint: setup_sesion"):
        analizar_setup_sesion(cs, deg, ts, lang="en")
    with _timer(rows, "stint: termica"):
        analizar_termica(dfs, dl)
    with _timer(rows, "stint: degradacion_neumatico"):
        predecir_degradacion_neumatico(dfs, dl)
    with _timer(rows, "stint: racing_line_rl"):
        optimizar_trazada_rl(dfs, dl, precomputed_obs=obs or None)
    with _timer(rows, "stint: track_evolution"):
        st.calcular_evolucion_pista(dl)
    with _timer(rows, "optimal_lap (filtered df)"):
        calcular_vuelta_optima_desde_df(dff, microsector_m=25.0, speed_tol_kmh=3.0, lang="en",
                                        distance_synthetic=False)
    if prof:
        prof.disable()
    _print_table(f"STAGES - {os.path.basename(path)} ({len(df):,} rows x {len(df.columns)} cols, {len(laps_f)} laps)",
                 rows, "sum")
    if prof:
        s = io.StringIO()
        pstats.Stats(prof, stream=s).sort_stats("cumulative").print_stats(35)
        print("\n```\n" + s.getvalue()[:6000] + "\n```")
        s = io.StringIO()
        pstats.Stats(prof, stream=s).sort_stats("tottime").print_stats(25)
        print("\n```\n" + s.getvalue()[:5000] + "\n```")


# ── Endpoints ────────────────────────────────────────────────────────────────
def _post(client, url, path, name, data=None, params=None, file_field="session_file"):
    with open(path, "rb") as fh:
        files = {file_field: (name, fh, "text/csv")} if file_field else None
        return client.post(url, files=files, data=data or {}, params=params or {"lang": "en"})


def profile_endpoints(path: str, repeat: int, dump_dir: Path | None):
    from fastapi.testclient import TestClient
    import main

    client = TestClient(main.app)
    name = os.path.basename(path)
    has_files = any(getattr(r, "path", "") == "/api/files" for r in main.app.routes)
    dump: dict = {}
    mb = os.path.getsize(path) / 1e6

    try:
        from src.io import session_cache
    except Exception:  # pre-cache versions of the code base
        session_cache = None

    def run(label, fn):
        best = None
        resp = None
        for _ in range(repeat):
            if session_cache:
                session_cache.cache.clear()   # classic mode = cold: every call parses again (as before)
            t0 = time.perf_counter()
            resp = fn()
            dt = time.perf_counter() - t0
            best = dt if best is None else min(best, dt)
        assert resp.status_code == 200, (label, resp.status_code, resp.text[:300])
        return best, len(resp.content), resp.json()

    rows = []
    for label, url, field, extra in [
        ("analyze-session", "/api/analyze-session", "session_file", None),
        ("stint/analyze", "/api/stint/analyze", "laps", None),
        ("optimal-lap", "/api/optimal-lap", "session_file", None),
        ("compare-session-laps (auto)", "/api/compare-session-laps", "session_file", {"lap_a": "0", "lap_b": "0"}),
    ]:
        secs, size, js = run(label, lambda url=url, field=field, extra=extra: _post(
            client, url, path, name, data=extra, file_field=field))
        rows.append((f"classic: {label}  [{size/1e6:.2f} MB json]", secs))
        dump[label] = js
    _print_table(f"ENDPOINTS classic (file re-sent on every call) - {name} ({mb:.1f} MB)", rows, "sum of calls")
    classic_total = sum(s for _, s in rows[:3])

    if has_files:
        rows2 = []
        if session_cache:
            session_cache.cache.clear()
        t0 = time.perf_counter()
        r = _post(client, "/api/files", path, name, file_field="file")
        t_up = time.perf_counter() - t0
        assert r.status_code == 200, r.text
        fid = r.json()["file_id"]
        rows2.append(("POST /api/files (upload once)", t_up))
        results = {}
        for label, url, extra in [
            ("analyze-session", "/api/analyze-session", {}),
            ("stint/analyze", "/api/stint/analyze", {}),
            ("optimal-lap", "/api/optimal-lap", {}),
            ("compare-session-laps (auto)", "/api/compare-session-laps", {"lap_a": "0", "lap_b": "0"}),
        ]:
            payload = {"file_id": fid, **extra}
            if url.endswith("stint/analyze"):
                payload = {"file_id": fid}
            # first call after upload is "cold-ish"; later repeats are warm
            t0 = time.perf_counter()
            resp = client.post(url, data=payload, params={"lang": "en"})
            first = time.perf_counter() - t0
            assert resp.status_code == 200, (label, resp.status_code, resp.text[:300])
            best = first
            for _ in range(repeat - 1):
                t0 = time.perf_counter()
                resp = client.post(url, data=payload, params={"lang": "en"})
                best = min(best, time.perf_counter() - t0)
            rows2.append((f"file_id: {label} (first call / best)", first))
            if repeat > 1:
                rows2.append((f"file_id: {label} (best of {repeat})", best))
            results[label] = resp.json()
            dump[label + " [file_id]"] = results[label]
        _print_table(f"ENDPOINTS file_id mode - {name}", rows2)
        first_total = rows2[0][1] + sum(s for n, s in rows2 if "first call" in n and "compare" not in n)
        print(f"\nFlow total (upload + session + stint + optimal-lap, first calls): {first_total:.3f}s "
              f"vs classic {classic_total:.3f}s")
    print(f"\nPeak RSS of this process: {_rss_mb():.0f} MB")

    if dump_dir:
        out = dump_dir / Path(path).stem
        out.mkdir(parents=True, exist_ok=True)
        for k, v in dump.items():
            safe = "".join(c if c.isalnum() else "_" for c in k)
            (out / f"{safe}.json").write_text(json.dumps(v, sort_keys=True), encoding="utf-8")
        print(f"JSON dumped to {out}")


# ── Compare dumps ────────────────────────────────────────────────────────────
def _diff(a, b, path="", tol=1e-6, out=None):
    out = out if out is not None else []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: missing in {'A' if k not in a else 'B'}")
            else:
                _diff(a[k], b[k], f"{path}/{k}", tol, out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} != {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                _diff(x, y, f"{path}[{i}]", tol, out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if not (a == b or abs(a - b) <= tol * max(1.0, abs(a), abs(b)) or (math.isnan(a) and math.isnan(b))):
            out.append(f"{path}: {a} != {b}")
    elif a != b:
        out.append(f"{path}: {str(a)[:60]} != {str(b)[:60]}")
    return out


def compare_dirs(a: Path, b: Path):
    bad = 0
    for fa in sorted(a.rglob("*.json")):
        fb = b / fa.relative_to(a)
        if not fb.exists():
            continue
        d = _diff(json.loads(fa.read_text("utf-8")), json.loads(fb.read_text("utf-8")))
        # volatile fields
        d = [x for x in d if not any(v in x for v in ("generated_at", "elapsed", "created_at"))]
        # keys only present in B are additive features (new fields); they are not regressions
        added = [x for x in d if x.endswith("missing in A")]
        d = [x for x in d if x not in added]
        extra = f" (+{len(added)} new keys in B)" if added else ""
        print(f"{fa.relative_to(a)}: {'IDENTICAL' if not d else f'{len(d)} differences'}{extra}")
        for x in d[:8]:
            print("   ", x)
        bad += bool(d)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--cprofile", action="store_true")
    ap.add_argument("--dump", type=Path)
    ap.add_argument("--compare", nargs=2, type=Path)
    ap.add_argument("--skip-endpoints", action="store_true")
    ap.add_argument("--skip-stages", action="store_true")
    args = ap.parse_args()
    if args.compare:
        sys.exit(1 if compare_dirs(*args.compare) else 0)
    for f in args.files:
        print(f"\n## {f}")
        if not args.skip_stages:
            profile_stages(f, args.cprofile)
        if not args.skip_endpoints:
            profile_endpoints(f, args.repeat, args.dump)


if __name__ == "__main__":
    main()
