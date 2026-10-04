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

y los del mapa de curvas unificado (src/analytics/corner_map.py):

  * ``corner_map``    mapa construido por consenso sobre TODAS las vueltas limpias del archivo, con la
                      plantilla de pista (geometria del juego + tabla de curvas)
  * ``map_no_table``  igual pero SIN inyectar la tabla (solo telemetria + geometria de pista); los nombres se
                      asignan despues, asi que su recall no es circular
  * ``map_telemetry`` solo consenso de telemetria (sin plantilla): aisla el efecto del consenso
  * ``single_lap``    el mapa completo construido vuelta a vuelta (una sola vuelta cada vez)
  * ``single_lap_no_table``  idem sin inyectar la tabla (no circular)

Metricas nuevas: ``recall_detectable`` (sin las curvas tabuladas con ``kind: flat_out``, comparable con la linea
base antigua) y ``spurious_per_lap`` (detecciones que no son curva tabulada NI curva geometrica de la pista:
ruido, no curvas reales sin tabular).

Verdad de referencia: SOLO las curvas tabuladas (apex_fraction) y la tolerancia de
``circuits.apex_tolerance_m``. Una deteccion cuenta como acierto cuando ``circuits.assign_names`` la
empareja con una curva tabulada (uno a uno, respetando el orden). Las detecciones sin curva tabulada
son 'extras': ruido o curvas reales no tabuladas, no un error por si solas.

Uso:
    python scripts/benchmark_corners.py CARPETA_O_ARCHIVO [...] [--circuit ID] [--out r.json] [--md r.md]
        [--compare linea_base.json] [--crossval cv.json] [--title TEXTO] [--exclude TEXTO]

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
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
logging.disable(logging.CRITICAL)
warnings.filterwarnings("ignore", category=RuntimeWarning)

import numpy as np  # noqa: E402

from src.analytics import circuits as C  # noqa: E402
from src.analytics.corner_map import build_corner_map  # noqa: E402
from src.analytics.geometry import detectar_apexes_perfectos, procesar_geometria_pista_perfecta  # noqa: E402
from src.analytics.stint import segmentar_vueltas_desde_csv  # noqa: E402
from src.io.header_meta import read_header  # noqa: E402
from src.io.loaders import load_telemetry_data, read_motec_metadata  # noqa: E402
from src.processing.alignment import align_by_distance  # noqa: E402
from src.telemetry.metrics import detect_apex_points, segment_corners  # noqa: E402

EXTS = (".csv", ".csv.gz", ".ibt", ".ld")
BASE_DETECTORS = ("speed", "geometry", "segmenter")
LEGACY_DETECTORS = BASE_DETECTORS + ("union",)
MAP_DETECTORS = ("corner_map", "map_no_table", "map_telemetry", "single_lap", "single_lap_no_table")
DETECTORS = LEGACY_DETECTORS + MAP_DETECTORS
MAP_VARIANT_OPTIONS = {
    "corner_map": {},
    "map_no_table": {"use_table": False},
    "map_telemetry": {"use_table": False, "use_geometry": False},
}
GEO_BACK_M = 80.0       # una deteccion a menos de esto de una curva geometrica de la pista no es ruido
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


def geo_atoms(circuit: dict, length: float) -> list:
    """Posiciones (m) de las curvas geometricas de la pista (radio < 400 m); [] si no hay geometria."""
    geo = C.get_track_geometry(circuit["id"])
    if not geo:
        return []
    return [float(a["fraction"]) * length for g in geo["corners"] for a in g.get("sub_apexes") or []]


def map_detections(laps: list, venue, options: dict | None = None) -> tuple:
    """({variante: [[distancias] por vuelta]}, mapa completo) de los detectores del mapa unificado."""
    out: dict = {}
    full = None
    lengths = [float(l["Distance"].iloc[-1] - l["Distance"].iloc[0]) for l in laps]
    for name, extra in MAP_VARIANT_OPTIONS.items():
        opts = dict(options or {})
        opts.update(extra)
        res = build_corner_map(laps, venue, options=opts)
        if name == "corner_map":
            full = res
        # el mismo mapa para todas las vueltas del archivo, escalado a la longitud de cada vuelta (por fraccion)
        out[name] = [sorted(c["fraction"] * n for c in res["corners"]) for n in lengths]
    out["single_lap"] = [sorted(c["apex_distance_m"] for c in build_corner_map([l], venue, options=options)["corners"])
                         for l in laps]
    nt = dict(options or {}, use_table=False)
    out["single_lap_no_table"] = [sorted(c["apex_distance_m"] for c in build_corner_map([l], venue, options=nt)["corners"])
                                  for l in laps]
    return out, full


# ── Agregacion ────────────────────────────────────────────────────────────────

def summarise(circuit: dict, laps: list) -> dict:
    """Metricas por detector para una lista de vueltas [{'dists','length'}]."""
    names = [k["name"] for k in sorted(circuit["corners"], key=lambda k: k["apex_fraction"])]
    n_tab = len(names)
    detectable = [k["name"] for k in circuit["corners"] if k.get("kind") != "flat_out"]
    out = {}
    for det in DETECTORS:
        if not all(det in lap["dists"] for lap in laps):
            continue
        recalls, recalls_det, extras, counts, spurious = [], [], [], [], []
        pos = collections.defaultdict(list)
        for lap in laps:
            dists = lap["dists"][det]
            res = C.assign_names(circuit, list(enumerate(dists)), lap["length"])
            m = {info["name"]: dists[i] for i, info in res.items()}
            atoms = geo_atoms(circuit, lap["length"])
            recalls.append(len(m) / n_tab)
            recalls_det.append(len([n for n in m if n in detectable]) / max(1, len(detectable)))
            extras.append(len(dists) - len(m))
            counts.append(len(dists))
            spurious.append(sum(1 for i, d in enumerate(dists) if i not in res
                                and not any(abs(d - a) <= GEO_BACK_M for a in atoms)))
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
            "recall_detectable": round(float(np.mean(recalls_det)), 3),
            "spurious_per_lap": round(float(np.mean(spurious)), 2),
            "extras_per_lap": round(float(np.mean(extras)), 2),
            "detections_per_lap": round(float(np.mean(counts)), 2),
            "stability_std_m": (round(float(np.mean(stds)), 1) if stds else None) if det not in MAP_DETECTORS[:3] else None,
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


def process_file(path: str, options: dict | None = None, load_only: bool = False) -> dict:
    """Carga un archivo y devuelve su metadato y las detecciones por vuelta (o el motivo de omision).

    ``load_only`` devuelve las vueltas limpias (``info["clean_laps"]``) sin ejecutar ningun detector."""
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
        if load_only:
            info["clean_laps"] = laps
            info["laps"] = len(laps)
            return info
        records, errors = [], collections.Counter()
        for lap in laps:
            dists, errs, length = detect_all(lap)
            records.append({"dists": dists, "length": length})
            errors.update(errs)
        t0 = time.perf_counter()
        maps, full = map_detections(laps, venue, options)
        info["map_seconds"] = round(time.perf_counter() - t0, 2)
        for name, per_lap in maps.items():
            for record, d in zip(records, per_lap):
                record["dists"][name] = d
        info["corner_map"] = [{"number": c["number"], "name": c["name"], "fraction": c["fraction"],
                               "kind": c["kind"], "direction": c["direction"], "min_radius_m": c["min_radius_m"],
                               "confidence": c["confidence"], "flat_out_share": c["flat_out_share"],
                               "is_complex": c["is_complex"], "sources": c["sources"]} for c in full["corners"]]
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

def run_benchmark(inputs: list, circuit_filter: str | None = None, options: dict | None = None,
                  exclude: tuple = ()) -> dict:
    files = [f for f in collect_files(inputs) if not any(x.lower() in os.path.basename(f).lower() for x in exclude)]
    processed = [process_file(p, options) for p in files]
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
            "corner_map": max(plist, key=lambda p: p["laps"])["corner_map"],
            "corner_map_file": max(plist, key=lambda p: p["laps"])["file"],
        }
        for d in DETECTORS:
            total_items[d].append((len(all_laps), det[d]))
    total = {"n_files": len(used), "n_laps": sum(c["n_laps"] for c in circuits_out.values()), "detectors": {}}
    for d in DETECTORS:
        total["detectors"][d] = {
            "recall": _lap_weighted(total_items[d], "recall"),
            "recall_detectable": _lap_weighted(total_items[d], "recall_detectable"),
            "spurious_per_lap": _lap_weighted(total_items[d], "spurious_per_lap"),
            "extras_per_lap": _lap_weighted(total_items[d], "extras_per_lap"),
            "detections_per_lap": _lap_weighted(total_items[d], "detections_per_lap"),
            "stability_std_m": _lap_weighted(total_items[d], "stability_std_m"),
            "appearance_pct": _lap_weighted(total_items[d], "appearance_pct"),
        }
    return {
        "generated": datetime.date.today().isoformat(),
        "dedup_m": DEDUP_M,
        "detectors": list(DETECTORS),
        "map_params": build_corner_map([], None)["summary"]["params"] | dict(options or {}),
        "files_used": [{"file": p["file"], "circuit": p["circuit"], "vehicle": p["vehicle"], "laps": p["laps"],
                        "map_seconds": p["map_seconds"], "detector_errors": p["detector_errors"]} for p in used],
        "files_skipped": skipped,
        "circuits": circuits_out,
        "total": total,
    }


def _fmt(v, suffix=""):
    return "-" if v is None else f"{round(v, 2)}{suffix}"


DET_LABEL = {"speed": "speed", "geometry": "geometry", "segmenter": "segmenter", "union": "union",
             "corner_map": "corner_map", "map_no_table": "map_no_table", "map_telemetry": "map_telemetry",
             "single_lap": "single_lap"}


def to_markdown(r: dict, legacy: dict | None = None, crossval: dict | None = None, title: str | None = None) -> str:
    L = []
    L.append(f"# {title or 'Banco de pruebas de curvas'}")
    L.append("")
    L.append(f"Fecha: {r['generated']}. Generado con `python scripts/benchmark_corners.py` "
             "(no modifica ningun detector; solo los ejecuta y compara con la tabla de `circuits.json`).")
    L.append("")
    L.append("Detectores existentes: `speed` (metrics.detect_apex_points), `geometry` (geometry.detectar_apexes_perfectos), "
             "`segmenter` (metrics.segment_corners, el que usan stint/sesion/comparacion) y `union` "
             f"(los tres, deduplicados a {r['dedup_m']:.0f} m).")
    L.append("")
    L.append("Mapa de curvas unificado (`src/analytics/corner_map.py`): `corner_map` (consenso sobre todas las vueltas "
             "limpias del archivo + plantilla de pista + tabla), `map_no_table` (igual pero sin inyectar la tabla: "
             "su recall NO es circular), `map_telemetry` (solo consenso de telemetria, sin plantilla) y `single_lap` "
             "(el mapa completo construido vuelta a vuelta).")
    L.append("")
    L.append("Metricas: **recall** = curvas tabuladas con una deteccion emparejada dentro de tolerancia / curvas "
             "tabuladas (media por vuelta); **recall det.** = lo mismo sin las curvas tabuladas con `kind: flat_out` "
             "(comparable con la linea base antigua, que no tenia Variante Bassa); **extras** = detecciones por vuelta "
             "sin curva tabulada (mezcla ruido y curvas reales no tabuladas); **ruido** = extras que ademas no estan a "
             f"menos de {GEO_BACK_M:.0f} m de ninguna curva geometrica de la pista (ruido casi seguro); **std m** = "
             "desviacion tipica de la posicion de cada curva entre vueltas (media de curvas con >= 2 apariciones; no "
             "definida para los mapas por consenso, que dan el mismo mapa a todas las vueltas); **aparece %** = "
             "porcentaje medio de vueltas en que cada curva tabulada es detectada.")
    L.append("")
    L.append("Atencion: `corner_map` inyecta las curvas de la tabla (curvas virtuales), asi que su recall con nombre "
             "contra esa misma tabla es alto por construccion. La medida no circular es `map_no_table` (y la "
             "validacion cruzada por circuito, que ajusta los umbrales sin mirar el circuito evaluado).")
    L.append("")
    t = r["total"]
    dets = [d for d in DETECTORS if d in t["detectors"]]
    L.append("## Total")
    L.append("")
    L.append(f"{t['n_files']} archivos utilizados, {t['n_laps']} vueltas completas.")
    L.append("")
    L.append("| Detector | Recall | Recall det. | Detecciones/vuelta | Extras/vuelta | Ruido/vuelta | Std (m) | Aparece % |")
    L.append("|---|---|---|---|---|---|---|---|")
    for d in dets:
        x = t["detectors"][d]
        L.append(f"| {d} | {_fmt(x['recall'])} | {_fmt(x.get('recall_detectable'))} | {_fmt(x['detections_per_lap'])} | "
                 f"{_fmt(x['extras_per_lap'])} | {_fmt(x.get('spurious_per_lap'))} | {_fmt(x['stability_std_m'])} | "
                 f"{_fmt(x['appearance_pct'])} |")
    L.append("")
    L.append("## Por circuito")
    L.append("")
    L.append("Cada celda: recall / recall det. / extras por vuelta / ruido por vuelta.")
    L.append("")
    L.append("| Circuito | Vueltas | Tab. | Tol. (m) | " + " | ".join(dets) + " |")
    L.append("|---|---|---|---|" + "---|" * len(dets))

    def cell(s):
        return (f"{s['recall']:.2f} / {s['recall_detectable']:.2f} / {s['extras_per_lap']:.1f} / "
                f"{s['spurious_per_lap']:.1f}")

    for cid, c in r["circuits"].items():
        d = c["detectors"]
        L.append(f"| {c['name']} | {c['n_laps']} | {c['n_tabulated']} | {c['tolerance_m']:.0f} | "
                 + " | ".join(cell(d[k]) for k in dets) + " |")
    L.append("")
    L.append("## Por circuito y coche")
    L.append("")
    L.append("Cada fila: recall / extras por vuelta / std en m. Std '-' = menos de 2 apariciones de cualquier curva.")
    L.append("")
    show = [k for k in ("segmenter", "union", "corner_map", "map_no_table", "single_lap", "single_lap_no_table") if k in dets]
    L.append("| Circuito | Coche | Vueltas | " + " | ".join(show) + " |")
    L.append("|---|---|---|" + "---|" * len(show))

    def cell2(s):
        return f"{s['recall']:.2f} / {s['extras_per_lap']:.1f} / {_fmt(s['stability_std_m'])}"

    for cid, c in r["circuits"].items():
        for car, cc in c["cars"].items():
            warn = " (pocas vueltas)" if cc["n_laps"] < 3 else ""
            L.append(f"| {c['name']} | {car}{warn} | {cc['n_laps']} | "
                     + " | ".join(cell2(cc["detectors"][k]) for k in show) + " |")
    L.append("")
    L.append("## Consistencia entre detectores")
    L.append("")
    L.append("Detecciones medias por vuelta (cuantas curvas ve cada detector en la misma vuelta) frente a las "
             "curvas tabuladas.")
    L.append("")
    L.append("| Circuito | Tabuladas | " + " | ".join(dets) + " |")
    L.append("|---|---|" + "---|" * len(dets))
    for c in r["circuits"].values():
        d = c["detectors"]
        L.append(f"| {c['name']} | {c['n_tabulated']} | " + " | ".join(str(d[k]["detections_per_lap"]) for k in dets) + " |")
    L.append("")

    if legacy:
        L.append("## Antes / despues")
        L.append("")
        L.append("'Antes' = `docs/benchmarks/corners_baseline_legacy.json` (tabla de Imola con 8 curvas, sin Variante "
                 "Bassa). 'Despues' usa el recall det. (mismas 8 curvas) para ser comparable; entre parentesis el "
                 "recall con las 9 curvas. Cada celda: recall / extras por vuelta.")
        L.append("")
        L.append("| Circuito | segmenter antes | union antes | corner_map | map_no_table | single_lap | single_lap_no_table | map_telemetry |")
        L.append("|---|---|---|---|---|---|---|---|")

        def lc(s):
            return f"{s['recall']:.2f} / {s['extras_per_lap']:.1f}"

        def nc(s):
            extra = f" ({s['recall']:.2f})" if abs(s["recall"] - s["recall_detectable"]) > 1e-9 else ""
            return f"{s['recall_detectable']:.2f}{extra} / {s['extras_per_lap']:.1f}"

        rows = list(r["circuits"].items())
        for cid, c in rows:
            lg = legacy["circuits"].get(cid)
            if not lg:
                continue
            d = c["detectors"]
            L.append(f"| {c['name']} | {lc(lg['detectors']['segmenter'])} | {lc(lg['detectors']['union'])} | "
                     f"{nc(d['corner_map'])} | {nc(d['map_no_table'])} | {nc(d['single_lap'])} | {nc(d['single_lap_no_table'])} | "
                     f"{nc(d['map_telemetry'])} |")
        tl, tn = legacy["total"]["detectors"], t["detectors"]

        def tc(x, det_=False):
            rc = x["recall_detectable"] if det_ else x["recall"]
            return f"{rc:.2f} / {x['extras_per_lap']:.2f}"

        L.append(f"| **Total** | {tc(tl['segmenter'])} | {tc(tl['union'])} | {tc(tn['corner_map'], True)} | "
                 f"{tc(tn['map_no_table'], True)} | {tc(tn['single_lap'], True)} | {tc(tn['single_lap_no_table'], True)} | "
                 f"{tc(tn['map_telemetry'], True)} |")
        L.append("")
        L.append(f"Estabilidad (std de la posicion entre vueltas, m): antes segmenter {_fmt(tl['segmenter']['stability_std_m'])}, "
                 f"union {_fmt(tl['union']['stability_std_m'])}; despues single_lap {_fmt(tn['single_lap']['stability_std_m'])}, single_lap_no_table {_fmt(tn['single_lap_no_table']['stability_std_m'])}.")
        L.append("")

    if crossval:
        L.append("## Validacion cruzada por circuito")
        L.append("")
        L.append(f"{crossval['description']}")
        L.append("")
        L.append("Cada celda: validacion cruzada (en muestra entre parentesis). Recall con nombre contra la tabla, sin "
                 "inyectarla; ruido = detecciones sin curva tabulada ni geometrica.")
        L.append("")
        L.append("| Circuito | Vueltas | Recall consenso (telemetria + geometria) | Recall vuelta a vuelta | Recall solo telemetria | Extras/vuelta | Ruido/vuelta | Parametros elegidos sin mirar el circuito |")
        L.append("|---|---|---|---|---|---|---|---|")

        def cv(f, key, d=2):
            return f"{f['heldout'][key]:.{d}f} ({f['default'][key]:.{d}f})"

        for cid, f in crossval["folds"].items():
            params = ", ".join(f"{k}={v}" for k, v in f["params"].items())
            L.append(f"| {cid} | {f['n_laps']} | {cv(f, 'recall_consensus')} | {cv(f, 'recall_single_lap')} | "
                     f"{cv(f, 'recall_telemetry_only')} | {cv(f, 'extras_per_lap', 1)} | {cv(f, 'spurious_per_lap')} | {params} |")
        a_, b_ = crossval["total_default"], crossval["total_heldout"]
        L.append(f"| **Total** | {crossval['n_laps']} | {b_['recall_consensus']:.2f} ({a_['recall_consensus']:.2f}) | "
                 f"{b_['recall_single_lap']:.2f} ({a_['recall_single_lap']:.2f}) | "
                 f"{b_['recall_telemetry_only']:.2f} ({a_['recall_telemetry_only']:.2f}) | "
                 f"{b_['extras_per_lap']:.1f} ({a_['extras_per_lap']:.1f}) | {b_['spurious_per_lap']:.2f} ({a_['spurious_per_lap']:.2f}) | |")
        L.append("")
        og = crossval["objective_grid"]
        same = sum(1 for f in crossval["folds"].values() if f["params"] == crossval["best_all_params"])
        diffs = [f"{k} {crossval['default_params'][k]:g} (optimo de la rejilla: {v:g})"
                 for k, v in crossval["best_all_params"].items() if crossval["default_params"][k] != v]
        L.append(f"Objetivo medio en la rejilla: minimo {og['min']}, mediana {og['median']}, maximo {og['max']}; "
                 f"por defecto {crossval['default_objective']}. {same} de {len(crossval['folds'])} pliegues eligen "
                 "la misma configuracion que el optimo con todos los circuitos. "
                 + ("Los valores por defecto de `corner_map` coinciden con ese optimo salvo " + "; ".join(diffs)
                    + " (se mantiene el valor razonado: la diferencia de objetivo es pequena). " if diffs else
                    "Los valores por defecto de `corner_map` son ese optimo. ")
                 + "El optimo es estable, pero la muestra son 5 circuitos de un solo simulador.")
        L.append("")
        L.append(f"Variante evaluada: `{crossval['variant']}`. Objetivo: {crossval['objective']}.")
        L.append("")

    L.append("## Mapas de curvas")
    L.append("")
    L.append("Mapa `corner_map` del archivo con mas vueltas de cada circuito. `kind`: braking / lift / flat_out / kink; "
             "`a fondo %` = porcentaje de vueltas sin minimo de velocidad ni frenada.")
    L.append("")
    for cid, c in r["circuits"].items():
        L.append(f"### {c['name']} ({c['corner_map_file']})")
        L.append("")
        L.append("| # | Nombre | Fraccion | Tipo | Dir. | Radio min (m) | Conf. | A fondo % | Compleja |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for k in c["corner_map"]:
            L.append(f"| {k['number']} | {k['name'] or '-'} | {k['fraction']:.3f} | {k['kind']} | {k['direction'] or '-'} | "
                     f"{_fmt(k['min_radius_m'])} | {k['confidence']:.2f} | {100 * k['flat_out_share']:.0f} | "
                     f"{'si' if k['is_complex'] else 'no'} |")
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
        parts += [f"{d}: {', '.join(c['detectors'][d]['never_detected']) or 'ninguna'}" for d in ("map_no_table", "single_lap_no_table")
                  if d in c["detectors"]]
        L.append(f"- {c['name']}: " + "; ".join(parts))
    L.append("")
    L.append("## Archivos utilizados")
    L.append("")
    for f in r["files_used"]:
        L.append(f"- {f['file']} ({f['circuit']}, {f['vehicle']}, {f['laps']} vueltas, mapa en {f.get('map_seconds', '-')} s "
                 "incluidas las 4 variantes y el modo vuelta a vuelta)")
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
             "tabuladas cuentan como 'extras', que por tanto mezclan ruido y curvas reales (de ahi la columna ruido).")
    L.append("- Un acierto exige una deteccion a menos de la tolerancia del circuito; no valida el nombre mas alla "
             "de la posicion y el orden (emparejamiento uno a uno de `circuits.assign_names`).")
    L.append("- Los fixtures del repo son recortes de archivos que tambien pueden estar en la carpeta de descargas, "
             "asi que algunas vueltas pueden contarse dos veces.")
    L.append("- Circuitos y coches con pocas vueltas dan metricas de estabilidad poco fiables (marcados en la tabla).")
    L.append("- El detector `segmenter` se ejecuta sobre la vuelta remuestreada a 1 m; los demas sobre la vuelta cruda.")
    L.append("- La tabla y la geometria de pista no son independientes de la telemetria: la tabla se ajusto con "
             "minimos de velocidad de estas mismas vueltas. Por eso el numero honesto es `map_no_table` y la "
             "validacion cruzada.")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="carpetas o archivos (.csv, .csv.gz, .ibt, .ld)")
    ap.add_argument("--circuit", help="solo este circuito (id de circuits.json)")
    ap.add_argument("--out", help="ruta del JSON de resultados")
    ap.add_argument("--md", help="ruta del informe Markdown")
    ap.add_argument("--compare", help="JSON de una linea base anterior: anade la comparacion antes/despues")
    ap.add_argument("--crossval", help="JSON de scripts/crossval_corner_map.py: anade la validacion cruzada")
    ap.add_argument("--title", help="titulo del informe")
    ap.add_argument("--exclude", action="append", default=[], help="omite los archivos cuyo nombre contenga este texto (repetible)")
    ap.add_argument("--map-options", help="JSON con opciones de corner_map (sobrescriben los valores por defecto)")
    a = ap.parse_args()

    options = json.loads(a.map_options) if a.map_options else None
    r = run_benchmark(a.inputs, a.circuit, options, tuple(a.exclude))
    legacy = json.load(open(a.compare, encoding="utf-8")) if a.compare else None
    crossval = json.load(open(a.crossval, encoding="utf-8")) if a.crossval else None
    if legacy:
        r["comparison_with"] = os.path.basename(a.compare)
        r["comparison"] = {cid: {"legacy": {d: {k: v for k, v in lg["detectors"][d].items() if k != "per_corner"}
                                           for d in LEGACY_DETECTORS},
                                 "now": {d: {k: v for k, v in c["detectors"][d].items() if k != "per_corner"}
                                         for d in DETECTORS}}
                           for cid, c in r["circuits"].items() for lg in [legacy["circuits"].get(cid)] if lg}
    if crossval:
        r["crossval"] = crossval
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
            f.write("\n")
    md = to_markdown(r, legacy, crossval, a.title)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)), exist_ok=True)
        with open(a.md, "w", encoding="utf-8", newline="\n") as f:
            f.write(md)
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
