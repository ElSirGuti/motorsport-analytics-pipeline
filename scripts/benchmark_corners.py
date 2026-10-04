#!/usr/bin/env python
"""Banco de pruebas de la deteccion de curvas y su asignacion de nombres.

Mide, sobre telemetria real, cuanto de la tabla de curvas de ``src/data/circuits.json`` recupera cada
detector del proyecto, por separado:

  * ``speed``     metrics.detect_apex_points (minimos locales de velocidad)
  * ``geometry``  geometry.detectar_apexes_perfectos (curvatura de la trazada)
  * ``segmenter`` metrics.segment_corners (curvas completas frenada+apice+gas; las usan
                  stint, session_corner_analysis y la comparacion), sobre la vuelta remuestreada por
                  distancia como hace el pipeline
  * ``union``     union de los tres con deduplicacion por proximidad (DEDUP_M)

Verdad de referencia: SOLO las curvas tabuladas (apex_fraction) y la tolerancia de
``circuits.apex_tolerance_m``. Una deteccion cuenta como acierto cuando ``circuits.assign_names`` la
empareja con una curva tabulada (uno a uno, respetando el orden). Las detecciones sin curva tabulada
son 'extras': ruido o curvas reales no tabuladas, no un error por si solas.

Uso:
    python scripts/benchmark_corners.py CARPETA_O_ARCHIVO [...] [--circuit ID] [--out r.json] [--md r.md]

Acepta .csv, .csv.gz, .ibt y .ld (recorre carpetas de forma recursiva). No modifica nada salvo --out/--md.
No cambia ningun detector: solo los ejecuta y compara con la tabla.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import gzip
import json
import logging
import os
import shutil
import sys
import warnings
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
logging.disable(logging.CRITICAL)
warnings.filterwarnings("ignore", category=RuntimeWarning)

import numpy as np  # noqa: E402

from src.analytics import circuits as C  # noqa: E402
from src.analytics.geometry import detectar_apexes_perfectos, procesar_geometria_pista_perfecta  # noqa: E402
from src.analytics.stint import segmentar_vueltas_desde_csv  # noqa: E402
from src.io.header_meta import read_header  # noqa: E402
from src.io.loaders import load_telemetry_data, read_motec_metadata  # noqa: E402
from src.processing.alignment import align_by_distance  # noqa: E402
from src.telemetry.metrics import detect_apex_points, segment_corners  # noqa: E402

EXTS = (".csv", ".csv.gz", ".ibt", ".ld")
BASE_DETECTORS = ("speed", "geometry", "segmenter")
DETECTORS = BASE_DETECTORS + ("union",)
DEDUP_M = 60.0          # detecciones de distintos detectores a menos de esto se funden en una
MIN_LAP_M = 800.0       # vueltas mas cortas no se consideran (como inventory_telemetry)
LAP_LEN_TOL = 0.04      # vuelta completa = longitud a +-4 % de la mediana (como circuit_apexes)


# ── Deteccion ─────────────────────────────────────────────────────────────────

def clean_laps(df):
    """Vueltas completas limpias (misma logica que scripts/circuit_apexes.py), sin imprimir avisos."""
    try:
        laps = segmentar_vueltas_desde_csv(df)
    except ValueError:
        laps = [df]  # archivo de una sola vuelta
    lengths = [float(l["Distance"].max() - l["Distance"].min()) for l in laps]
    keep = [(l, n) for l, n in zip(laps, lengths) if n >= MIN_LAP_M]
    if not keep:
        return []
    med = float(np.median([n for _, n in keep]))
    return [l.reset_index(drop=True) for l, n in keep if abs(n - med) <= LAP_LEN_TOL * med]


def detect_all(lap) -> tuple[dict, dict, float]:
    """({detector: [distancias en m desde el inicio de la vuelta]}, {detector: error}, longitud)."""
    d0 = float(lap["Distance"].iloc[0])
    length = float(lap["Distance"].iloc[-1]) - d0
    out: dict = {}
    errors: dict = {}

    def run(name, fn):
        try:
            out[name] = sorted(float(x) for x in fn() if np.isfinite(x))
        except Exception as exc:  # noqa: BLE001 - un detector roto no debe abortar el banco
            out[name] = []
            errors[name] = type(exc).__name__

    def _speed():
        return [a["distance"] - d0 for a in detect_apex_points(lap)]

    def _geometry():
        g = procesar_geometria_pista_perfecta(lap)
        return [float(r["Distance"]) - d0 for _, r in detectar_apexes_perfectos(g).iterrows()]

    def _segmenter():
        cols = [c for c in ("Distance", "Speed", "Brake", "Throttle") if c in lap.columns]
        al = align_by_distance(lap[cols])
        return [c["apex"]["distance"] - d0 for c in segment_corners(al)]

    run("speed", _speed)
    run("geometry", _geometry)
    run("segmenter", _segmenter)
    out["union"] = union_dedup([(d, k) for k in BASE_DETECTORS for d in out[k]])
    return out, errors, length


def union_dedup(points, tol: float = DEDUP_M) -> list:
    """Funde detecciones (distancia, detector) a menos de ``tol`` m: devuelve la posicion media de cada grupo."""
    groups: list = []
    for d, _k in sorted(points):
        if groups and d - groups[-1][-1] <= tol:
            groups[-1].append(d)
        else:
            groups.append([d])
    return [float(np.mean(g)) for g in groups]


def match_lap(circuit: dict, dists: list, length: float) -> dict:
    """{nombre de curva: distancia detectada} para las detecciones emparejadas con la tabla."""
    res = C.assign_names(circuit, list(enumerate(dists)), length)
    return {info["name"]: dists[i] for i, info in res.items()}


# ── Agregacion ────────────────────────────────────────────────────────────────

def summarise(circuit: dict, laps: list) -> dict:
    """Metricas por detector para una lista de vueltas [{'dists','length'}]."""
    names = [k["name"] for k in sorted(circuit["corners"], key=lambda k: k["apex_fraction"])]
    n_tab = len(names)
    out = {}
    for det in DETECTORS:
        recalls, extras, counts = [], [], []
        pos = collections.defaultdict(list)
        for lap in laps:
            dists = lap["dists"][det]
            m = match_lap(circuit, dists, lap["length"])
            recalls.append(len(m) / n_tab)
            extras.append(len(dists) - len(m))
            counts.append(len(dists))
            for nm, d in m.items():
                pos[nm].append(d)
        per_corner = {}
        for nm in names:
            p = pos.get(nm, [])
            per_corner[nm] = {
                "share": round(len(p) / len(laps), 3),
                "mean_m": round(float(np.mean(p)), 1) if p else None,
                "std_m": round(float(np.std(p)), 1) if len(p) >= 2 else None,
            }
        stds = [v["std_m"] for v in per_corner.values() if v["std_m"] is not None]
        shares = [v["share"] for v in per_corner.values()]
        out[det] = {
            "recall": round(float(np.mean(recalls)), 3),
            "extras_per_lap": round(float(np.mean(extras)), 2),
            "detections_per_lap": round(float(np.mean(counts)), 2),
            "stability_std_m": round(float(np.mean(stds)), 1) if stds else None,
            "appearance_pct": round(100.0 * float(np.mean(shares)), 1),
            "never_detected": [nm for nm in names if per_corner[nm]["share"] == 0.0],
            "per_corner": per_corner,
        }
    return out


def _lap_weighted(items: list, key: str):
    """Media ponderada por vueltas de una metrica de detector sobre [(n_laps, summary)]."""
    vals = [(n, s[key]) for n, s in items if s.get(key) is not None]
    tot = sum(n for n, _ in vals)
    return round(sum(n * v for n, v in vals) / tot, 3) if tot else None


# ── Entrada ───────────────────────────────────────────────────────────────────

def collect_files(inputs: list) -> list:
    files = []
    for p in inputs:
        if os.path.isdir(p):
            for root, _d, names in os.walk(p):
                files += [os.path.join(root, n) for n in names if n.lower().endswith(EXTS)]
        elif os.path.isfile(p):
            files.append(p)
    return sorted(set(files))


def process_file(path: str) -> dict:
    """Carga un archivo y devuelve su metadato y las detecciones por vuelta (o el motivo de omision)."""
    tmp = None
    real = path
    info = {"file": os.path.basename(path).replace("_&_Andres Gutierrez_&_", "_&_piloto_&_")}
    try:
        if path.lower().endswith(".gz"):
            tmp = tempfile.mkdtemp(prefix="bench_corners_")
            real = os.path.join(tmp, os.path.basename(path)[:-3])
            with gzip.open(path, "rb") as a, open(real, "wb") as b:
                shutil.copyfileobj(a, b)
        head = {}
        try:
            head = read_header(real) or {}
        except Exception:  # noqa: BLE001
            pass
        venue = head.get("venue") or head.get("circuit")
        if not venue:
            try:
                venue = (read_motec_metadata(real) or {}).get("venue")
            except Exception:  # noqa: BLE001
                venue = None
        info["venue"] = venue or "?"
        info["vehicle"] = head.get("vehicle") or head.get("car") or "?"
        circuit = C.find_circuit(venue) if venue else None
        if not circuit:
            info["skip"] = "circuito no esta en la tabla"
            return info
        if not circuit.get("corners"):
            info["circuit"] = circuit["id"]
            info["skip"] = "circuito reconocido pero sin curvas tabuladas"
            return info
        info["circuit"] = circuit["id"]
        df = load_telemetry_data(real)
        laps = clean_laps(df)
        if not laps:
            info["skip"] = "sin vueltas completas"
            return info
        median_len = float(np.median([l["Distance"].iloc[-1] - l["Distance"].iloc[0] for l in laps]))
        rec = C.recognize(venue, median_len)
        if not rec["matched"]:
            info["skip"] = (f"longitud medida {median_len:.0f} m no encaja con la tabla "
                            f"({circuit['length_m']:.0f} m): otro trazado")
            return info
        records, errors = [], collections.Counter()
        for lap in laps:
            dists, errs, length = detect_all(lap)
            records.append({"dists": dists, "length": length})
            errors.update(errs)
        info["laps"] = len(records)
        info["records"] = records
        info["detector_errors"] = dict(errors)
        return info
    except Exception as exc:  # noqa: BLE001
        info["skip"] = f"error al procesar: {type(exc).__name__}: {str(exc)[:80]}"
        return info
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


# ── Informe ───────────────────────────────────────────────────────────────────

def run_benchmark(inputs: list, circuit_filter: str | None = None) -> dict:
    files = collect_files(inputs)
    processed = [process_file(p) for p in files]
    used, skipped = [], []
    for p in processed:
        if circuit_filter and p.get("circuit") not in (None, circuit_filter):
            continue  # otro circuito: no es de este banco
        if "skip" in p:
            skipped.append({"file": p["file"], "reason": p["skip"]})
        else:
            used.append(p)

    by_circuit: dict = collections.defaultdict(list)
    for p in used:
        by_circuit[p["circuit"]].append(p)

    circuits_out: dict = {}
    total_items = {d: [] for d in DETECTORS}
    for cid, plist in sorted(by_circuit.items()):
        circuit = C.get_circuit(cid)
        all_laps = [r for p in plist for r in p["records"]]
        tol = C.apex_tolerance_m(float(np.median([r["length"] for r in all_laps])), circuit)
        det = summarise(circuit, all_laps)
        cars = {}
        by_car = collections.defaultdict(list)
        for p in plist:
            by_car[p["vehicle"]].append(p)
        for car, cl in sorted(by_car.items()):
            laps = [r for p in cl for r in p["records"]]
            cars[car] = {"n_files": len(cl), "n_laps": len(laps),
                         "files": [p["file"] for p in cl], "detectors": summarise(circuit, laps)}
        corners = sorted(circuit["corners"], key=lambda k: k["apex_fraction"])
        # Nunca detectada por NINGUN detector (union) en ningun archivo del circuito
        never = [{"name": k["name"], "apex_fraction": k["apex_fraction"]} for k in corners
                 if k["name"] in det["union"]["never_detected"]]
        circuits_out[cid] = {
            "name": circuit["name"], "length_m": circuit["length_m"], "tolerance_m": round(tol, 1),
            "n_files": len(plist), "n_laps": len(all_laps), "n_tabulated": len(corners),
            "detectors": det, "never_detected": never,
            "never_detected_by_detector": {d: det[d]["never_detected"] for d in BASE_DETECTORS},
            "cars": cars,
        }
        for d in DETECTORS:
            total_items[d].append((len(all_laps), det[d]))
    total = {"n_files": len(used), "n_laps": sum(c["n_laps"] for c in circuits_out.values()), "detectors": {}}
    for d in DETECTORS:
        total["detectors"][d] = {
            "recall": _lap_weighted(total_items[d], "recall"),
            "extras_per_lap": _lap_weighted(total_items[d], "extras_per_lap"),
            "detections_per_lap": _lap_weighted(total_items[d], "detections_per_lap"),
            "stability_std_m": _lap_weighted(total_items[d], "stability_std_m"),
            "appearance_pct": _lap_weighted(total_items[d], "appearance_pct"),
        }
    return {
        "generated": datetime.date.today().isoformat(),
        "dedup_m": DEDUP_M,
        "detectors": list(DETECTORS),
        "files_used": [{"file": p["file"], "circuit": p["circuit"], "vehicle": p["vehicle"], "laps": p["laps"],
                        "detector_errors": p["detector_errors"]} for p in used],
        "files_skipped": skipped,
        "circuits": circuits_out,
        "total": total,
    }


def _fmt(v, suffix=""):
    return "-" if v is None else f"{round(v, 2)}{suffix}"


def to_markdown(r: dict) -> str:
    L = []
    L.append("# Banco de pruebas de curvas: linea base")
    L.append("")
    L.append(f"Fecha: {r['generated']}. Generado con `python scripts/benchmark_corners.py` "
             "(no modifica ningun detector; solo los ejecuta y compara con la tabla de `circuits.json`).")
    L.append("")
    L.append("Detectores: `speed` (metrics.detect_apex_points), `geometry` (geometry.detectar_apexes_perfectos), "
             "`segmenter` (metrics.segment_corners, el que usan stint/sesion/comparacion) y `union` "
             f"(los tres, deduplicados a {r['dedup_m']:.0f} m).")
    L.append("")
    L.append("Metricas: **recall** = curvas tabuladas con una deteccion emparejada dentro de tolerancia / curvas "
             "tabuladas (media por vuelta); **extras** = detecciones por vuelta sin curva tabulada; **std m** = "
             "desviacion tipica de la posicion de cada curva entre vueltas (media de curvas con >= 2 apariciones); "
             "**aparece %** = porcentaje medio de vueltas en que cada curva tabulada es detectada.")
    L.append("")
    t = r["total"]
    L.append("## Total")
    L.append("")
    L.append(f"{t['n_files']} archivos utilizados, {t['n_laps']} vueltas completas.")
    L.append("")
    L.append("| Detector | Recall | Detecciones/vuelta | Extras/vuelta | Std (m) | Aparece % |")
    L.append("|---|---|---|---|---|---|")
    for d in DETECTORS:
        x = t["detectors"][d]
        L.append(f"| {d} | {_fmt(x['recall'])} | {_fmt(x['detections_per_lap'])} | {_fmt(x['extras_per_lap'])} | "
                 f"{_fmt(x['stability_std_m'])} | {_fmt(x['appearance_pct'])} |")
    L.append("")
    L.append("## Por circuito y coche")
    L.append("")
    L.append("Cada fila: recall / extras por vuelta / std en m. Std '-' = menos de 2 apariciones de cualquier curva.")
    L.append("")
    L.append("| Circuito | Coche | Vueltas | Tab. | Tol. (m) | speed | geometry | segmenter | union |")
    L.append("|---|---|---|---|---|---|---|---|---|")

    def cell(s):
        return f"{s['recall']:.2f} / {s['extras_per_lap']:.1f} / {_fmt(s['stability_std_m'])}"

    for cid, c in r["circuits"].items():
        d = c["detectors"]
        L.append(f"| **{c['name']}** (total) | todos | {c['n_laps']} | {c['n_tabulated']} | {c['tolerance_m']:.0f} | "
                 + " | ".join(cell(d[k]) for k in DETECTORS) + " |")
        for car, cc in c["cars"].items():
            warn = " (pocas vueltas)" if cc["n_laps"] < 3 else ""
            L.append(f"| {c['name']} | {car}{warn} | {cc['n_laps']} | {c['n_tabulated']} | {c['tolerance_m']:.0f} | "
                     + " | ".join(cell(cc["detectors"][k]) for k in DETECTORS) + " |")
    L.append("")
    L.append("## Consistencia entre detectores")
    L.append("")
    L.append("Detecciones medias por vuelta (cuantas curvas ve cada detector en la misma vuelta) frente a las "
             "curvas tabuladas.")
    L.append("")
    L.append("| Circuito | Tabuladas | speed | geometry | segmenter | union |")
    L.append("|---|---|---|---|---|---|")
    for c in r["circuits"].values():
        d = c["detectors"]
        L.append(f"| {c['name']} | {c['n_tabulated']} | " + " | ".join(str(d[k]["detections_per_lap"]) for k in DETECTORS) + " |")
    L.append("")
    L.append("## Curvas nunca detectadas")
    L.append("")
    L.append("Curvas tabuladas sin ninguna deteccion emparejada (en ningun detector, ninguna vuelta, ningun archivo "
             "del circuito): candidatas a 'curva a fondo' o a posicion mal tabulada.")
    L.append("")
    any_never = False
    for cid, c in r["circuits"].items():
        for k in c["never_detected"]:
            any_never = True
            L.append(f"- {c['name']}: {k['name']} (fraccion de vuelta {k['apex_fraction']:.3f})")
    if not any_never:
        L.append("- Ninguna.")
    L.append("")
    L.append("Nunca detectadas por cada detector (aunque otro si las vea):")
    L.append("")
    for cid, c in r["circuits"].items():
        parts = [f"{d}: {', '.join(c['never_detected_by_detector'][d]) or 'ninguna'}" for d in BASE_DETECTORS]
        L.append(f"- {c['name']}: " + "; ".join(parts))
    L.append("")
    L.append("## Archivos utilizados")
    L.append("")
    for f in r["files_used"]:
        L.append(f"- {f['file']} ({f['circuit']}, {f['vehicle']}, {f['laps']} vueltas)")
    L.append("")
    L.append("## Archivos omitidos")
    L.append("")
    if r["files_skipped"]:
        for f in r["files_skipped"]:
            L.append(f"- {f['file']}: {f['reason']}")
    else:
        L.append("- Ninguno.")
    L.append("")
    L.append("## Limitaciones")
    L.append("")
    L.append("- La verdad de referencia son SOLO las curvas tabuladas en `circuits.json`; las curvas reales no "
             "tabuladas cuentan como 'extras', que por tanto mezclan ruido y curvas reales.")
    L.append("- Un acierto exige una deteccion a menos de la tolerancia del circuito; no valida el nombre mas alla "
             "de la posicion y el orden (emparejamiento uno a uno de `circuits.assign_names`).")
    L.append("- Los fixtures del repo son recortes de archivos que tambien pueden estar en la carpeta de descargas, "
             "asi que algunas vueltas pueden contarse dos veces.")
    L.append("- Circuitos y coches con pocas vueltas dan metricas de estabilidad poco fiables (marcados en la tabla).")
    L.append("- El detector `segmenter` se ejecuta sobre la vuelta remuestreada a 1 m; los demas sobre la vuelta cruda.")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="carpetas o archivos (.csv, .csv.gz, .ibt, .ld)")
    ap.add_argument("--circuit", help="solo este circuito (id de circuits.json)")
    ap.add_argument("--out", help="ruta del JSON de resultados")
    ap.add_argument("--md", help="ruta del informe Markdown")
    a = ap.parse_args()

    r = run_benchmark(a.inputs, a.circuit)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
            f.write("\n")
    md = to_markdown(r)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
