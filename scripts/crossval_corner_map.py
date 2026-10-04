#!/usr/bin/env python
"""Validacion cruzada por circuito (leave-one-circuit-out) de los umbrales de corner_map.

Para cada circuito con telemetria real y tabla de curvas se eligen los parametros de
``src/analytics/corner_map.py`` MIRANDO SOLO LOS OTROS circuitos y se evalua en el excluido. Asi se mide
cuanto generalizan los umbrales a un circuito que no se ha visto, no solo lo bien que ajustan en muestra.

Variantes evaluadas (sin inyectar la tabla, para que el recall no sea circular):
  * ``map_no_table``          mapa por consenso sobre todas las vueltas de cada archivo (telemetria + geometria)
  * ``single_lap_no_table``   mapa construido vuelta a vuelta
  * ``map_telemetry``         solo consenso de telemetria (circuito desconocido: aqui pesa ``min_share``)
El objetivo de un circuito es la media de las tres de:  recall - 0.10 * ruido - 0.02 * extras
(recall con nombre contra la tabla; ruido = detecciones sin curva tabulada NI curva geometrica de la
pista; extras = detecciones sin curva tabulada). Los parametros se eligen por el objetivo medio de los
circuitos de entrenamiento (cada circuito pesa igual).

Uso:
    python scripts/crossval_corner_map.py CARPETA_O_ARCHIVO [...] [--out cv.json] [--quick]

Es determinista. Tarda unos minutos (rejilla de 243 configuraciones; con --quick, 24).
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import numpy as np  # noqa: E402

import benchmark_corners as B  # noqa: E402
from src.analytics import circuits as C  # noqa: E402
from src.analytics import corner_map as CM  # noqa: E402

GRID = {
    "min_share": [0.5, 0.6, 0.75],
    "cluster_tol_min_m": [40.0, 60.0, 90.0],
    "match_pad_m": [40.0, 60.0, 90.0],
    "unbacked_min_support": [0.4, 0.6, 0.8],
    "group_gap_m": [80.0, 120.0, 160.0],
}
QUICK_GRID = {
    "min_share": [0.5, 0.6, 0.75],
    "cluster_tol_min_m": [60.0],
    "match_pad_m": [40.0, 60.0],
    "unbacked_min_support": [0.4, 0.6],
    "group_gap_m": [80.0, 120.0],
}
W_SPURIOUS, W_EXTRAS = 0.10, 0.02
VARIANTS = ("map_no_table", "single_lap_no_table", "map_telemetry")


def _memoize():
    """Memoiza la preparacion de vueltas y los candidatos por vuelta (no dependen de los umbrales que se varian)."""
    prep, cand, kap = {}, {}, {}
    orig_prep, orig_cand, orig_kap = CM._prepare_lap, CM._lap_candidates, CM._signed_curvature

    def prep_m(df, warnings, idx):
        k = id(df)
        if k not in prep:
            prep[k] = orig_prep(df, [], idx)
        return prep[k]

    def cand_m(lap, opts):
        k = (id(lap), opts["merge_detectors_m"], opts["brake_zone_search_m"])
        if k not in cand:
            cand[k] = orig_cand(lap, opts)
        return cand[k]

    def kap_m(lap):
        k = id(lap)
        if k not in kap:
            kap[k] = orig_kap(lap)
        return kap[k]

    CM._prepare_lap, CM._lap_candidates, CM._signed_curvature = prep_m, cand_m, kap_m


def evaluate(files: list, options: dict) -> dict:
    """{circuito: {variante: summary}} para unas opciones."""
    per_circuit: dict = collections.defaultdict(lambda: collections.defaultdict(list))
    for f in files:
        laps, venue = f["clean_laps"], f["venue"]
        nt = dict(options, use_table=False)
        cons = CM.build_corner_map(laps, venue, options=nt)
        fr = sorted(c["fraction"] for c in cons["corners"])
        tel = CM.build_corner_map(laps, venue, options=dict(options, use_table=False, use_geometry=False))
        frt = sorted(c["fraction"] for c in tel["corners"])
        singles = [sorted(c["apex_distance_m"] for c in CM.build_corner_map([l], venue, options=nt)["corners"])
                   for l in laps]
        for i, lap in enumerate(laps):
            length = float(lap["Distance"].iloc[-1] - lap["Distance"].iloc[0])
            per_circuit[f["circuit"]]["map_no_table"].append(
                {"dists": {"map_no_table": [x * length for x in fr]}, "length": length})
            per_circuit[f["circuit"]]["map_telemetry"].append(
                {"dists": {"map_telemetry": [x * length for x in frt]}, "length": length})
            per_circuit[f["circuit"]]["single_lap_no_table"].append(
                {"dists": {"single_lap_no_table": singles[i]}, "length": length})
    out = {}
    for cid, d in per_circuit.items():
        circuit = C.get_circuit(cid)
        out[cid] = {v: B.summarise(circuit, d[v])[v] for v in VARIANTS}
        out[cid]["n_laps"] = len(d[VARIANTS[0]])
    return out


def objective(res: dict) -> float:
    vals = [s["recall"] - W_SPURIOUS * s["spurious_per_lap"] - W_EXTRAS * s["extras_per_lap"]
            for s in (res[v] for v in VARIANTS)]
    return float(np.mean(vals))


def _metrics(res: dict) -> dict:
    return {"recall": round(float(np.mean([res[v]["recall"] for v in VARIANTS])), 3),
            "recall_consensus": res["map_no_table"]["recall"], "recall_single_lap": res["single_lap_no_table"]["recall"],
            "recall_telemetry_only": res["map_telemetry"]["recall"],
            "extras_per_lap": round(float(np.mean([res[v]["extras_per_lap"] for v in VARIANTS])), 2),
            "spurious_per_lap": round(float(np.mean([res[v]["spurious_per_lap"] for v in VARIANTS])), 2)}


def _weighted(rows: list) -> dict:
    n = sum(r[0] for r in rows)
    return {k: round(sum(r[0] * r[1][k] for r in rows) / n, 3) for k in rows[0][1]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--exclude", action="append", default=[], help="omite los archivos cuyo nombre contenga este texto")
    a = ap.parse_args()

    files = []
    for p in B.collect_files(a.inputs):
        if any(x.lower() in os.path.basename(p).lower() for x in a.exclude):
            continue
        info = B.process_file(p, load_only=True)
        if "skip" not in info:
            files.append(info)
    _memoize()
    grid = QUICK_GRID if a.quick else GRID
    keys = list(grid)
    configs = [dict(zip(keys, v)) for v in itertools.product(*[grid[k] for k in keys])]
    default = {k: CM.DEFAULTS[k] for k in keys}
    if default not in configs:
        configs.append(default)
    t0 = time.time()
    results = []
    for cfg in configs:
        results.append(evaluate(files, cfg))
    circuits = sorted(results[0])
    nlaps = {c: results[0][c]["n_laps"] for c in circuits}
    obj = [{c: objective(r[c]) for c in circuits} for r in results]
    di = configs.index(default)

    folds = {}
    held_rows, def_rows = [], []
    for h in circuits:
        train = [c for c in circuits if c != h]
        best = max(range(len(configs)), key=lambda i: (np.mean([obj[i][c] for c in train]), i == di))
        ho, df = _metrics(results[best][h]), _metrics(results[di][h])
        folds[h] = {"n_laps": nlaps[h], "params": configs[best], "heldout": ho, "default": df,
                    "train_objective": round(float(np.mean([obj[best][c] for c in train])), 4)}
        held_rows.append((nlaps[h], ho))
        def_rows.append((nlaps[h], df))
    best_all = max(range(len(configs)), key=lambda i: (np.mean([obj[i][c] for c in circuits]), i == di))
    out = {
        "description": ("Leave-one-circuit-out: los parametros de cada fila se eligieron mirando solo los otros "
                        f"{len(circuits) - 1} circuitos (rejilla de {len(configs)} configuraciones: "
                        + ", ".join(f"{k} en {grid[k]}" for k in keys)
                        + "). 'En muestra' = los parametros por defecto de corner_map (el optimo con todos los circuitos) evaluados en ese circuito."),
        "variant": "map_no_table, single_lap_no_table y map_telemetry (media)",
        "objective": f"recall - {W_SPURIOUS} * ruido - {W_EXTRAS} * extras, media de las tres variantes",
        "n_laps": sum(nlaps.values()), "n_configs": len(configs), "seconds": round(time.time() - t0, 1),
        "default_params": default, "best_all_params": configs[best_all],
        "best_all_objective": round(float(np.mean([obj[best_all][c] for c in circuits])), 4),
        "default_objective": round(float(np.mean([obj[di][c] for c in circuits])), 4),
        "objective_grid": {"min": round(float(min(np.mean(list(o.values())) for o in obj)), 4),
                           "median": round(float(np.median([np.mean(list(o.values())) for o in obj])), 4),
                           "max": round(float(max(np.mean(list(o.values())) for o in obj)), 4)},
        "folds": folds, "total_heldout": _weighted(held_rows), "total_default": _weighted(def_rows),
        "default_by_circuit_variant": {c: {v: {k: results[di][c][v][k] for k in
                                               ("recall", "recall_detectable", "extras_per_lap", "spurious_per_lap")}
                                           for v in VARIANTS} for c in circuits},
    }
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
            f.write("\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n_configs", "seconds", "default_objective", "best_all_params",
                                          "best_all_objective", "total_default", "total_heldout")}, indent=1))
    for c, f in folds.items():
        print(c, f["params"], f["heldout"], f["default"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
