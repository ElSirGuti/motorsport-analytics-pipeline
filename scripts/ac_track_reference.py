#!/usr/bin/env python
"""Curvas geometricas de un circuito de Assetto Corsa (verdad de referencia independiente del coche).

Lee ``content/tracks/<pista>/[<layout>/]ai/fast_lane.ai`` (solo lectura) y calcula donde hay curvas
segun la geometria de la linea de la IA: fraccion de vuelta, metros, radio minimo, direccion y clase
(slow < 60 m, medium 60-150 m, fast 150-400 m). Una curva 'fast' puede ser a fondo para un coche con
mucho apoyo: la clase describe la pista, no lo que hace un coche.

Uso:
    python scripts/ac_track_reference.py TRACK_ID [--layout NOMBRE] [--compare] [--export]
    python scripts/ac_track_reference.py --list-layouts TRACK_ID
    python scripts/ac_track_reference.py --export-all        # regenera src/data/track_geometry/*.json

--compare   contrasta con la tabla de src/data/circuits.json (circuito por alias del TRACK_ID o --circuit):
            distancia en metros de cada curva tabulada a la curva geometrica mas cercana, curvas
            geometricas sin curva tabulada y curvas tabuladas sin pico geometrico.
--export    escribe src/data/track_geometry/<circuit_id>.json (pequeno, versionado; la app lo lee en
            Docker/Kubernetes, donde no existe el juego). Con --export-all se eligen los layouts
            automaticamente: longitud oficial dentro del +-3 % de circuits.json, la mas
            cercana (empate: el primero de EXPORT_PLAN). Un circuito sin layout que cuadre NO se exporta.

El juego se localiza con AC_CONTENT_DIR / AC_INSTALL_DIR o en las rutas habituales de Steam.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
logging.disable(logging.CRITICAL)

from src.analytics import ac_track_geometry as G  # noqa: E402
from src.analytics import circuits as C  # noqa: E402

LENGTH_MATCH = 0.03   # |oficial / circuits.json - 1|
FAR_M = 250.0

# circuit_id -> candidatos (track_id, layout). Se prueban todos; manda la longitud y la tabla.
EXPORT_PLAN = {
    "imola": [("imola", ""), ("fn_imola", "")],
    "spa_francorchamps": [("spa", "")],
    "silverstone": [("ks_silverstone", "gp")],
    "monaco": [("monaco_2020", ""), ("monaco", "")],
    "le_mans": [("sx_lemans", "24h_2024"), ("sx_lemans", "chicane"), ("lemans_2017", "lights"),
                ("lemans_2017", "no_lights")],
    "mugello": [("mugello", "")],
    "brands_hatch": [("ks_brands_hatch", "gp")],
    "monza": [("monza", "")],
    "red_bull_ring": [("ks_red_bull_ring", "layout_gp")],
    "barcelona": [("ks_barcelona", "layout_gp"), ("ks_barcelona", "layout_gp_2023")],
    "laguna_seca": [("ks_laguna_seca", "")],
    "zandvoort": [("ks_zandvoort", ""), ("zandvoort2020", "2020"), ("zandvoort2023", "2023")],
    "vallelunga": [("ks_vallelunga", "classic_circuit"), ("ks_vallelunga", "extended_circuit")],
    "magione": [("magione", "")],
    "sepang": [("sepang", ""), ("acu_sepang", "")],
    "nordschleife": [("ks_nordschleife", "endurance"), ("ks_nordschleife", "nordschleife")],
}


def _corner_dicts(geo):
    return [c.to_dict() for c in geo.corners]


def print_corners(geo, official_m, scale_m):
    print(f"Linea: {geo.length_line_m:.0f} m  oficial: {official_m or '?'} m  "
          f"{'circuito cerrado (' + str(geo.direction) + ')' if geo.closed else 'NO cerrada'}  "
          f"hueco de cierre {geo.closure_gap_m:.1f} m")
    print(f"{len(geo.corners)} curvas geometricas (metros = fraccion x {scale_m:.0f} m)\n")
    print(f"{'#':>3} {'fraccion':>8} {'metros':>7} {'R min':>7} {'dir':<6} {'clase':<7} {'tipo':<9} sub-apices (fraccion:radio)")
    for c in geo.corners:
        subs = " ".join(f"{a.fraction:.3f}:{a.radius_m:.0f}{a.direction[0].upper()}" for a in c.sub_apexes) \
            if c.is_complex else ""
        print(f"{c.index:>3} {c.apex_fraction:>8.3f} {c.apex_fraction * scale_m:>7.0f} {c.min_radius_m:>7.0f} "
              f"{c.direction:<6} {c.severity:<7} {c.kind:<9} {subs}")


def contrast(circuit, geo, scale_m):
    res = G.compare_with_table(circuit, _corner_dicts(geo), scale_m)
    rows = res["rows"]
    print(f"\nContraste con circuits.json: {circuit['id']} ({len(rows)} curvas tabuladas)")
    print(f"{'curva tabulada':<24} {'fraccion':>8} {'dist m':>7} {'signo':>6} {'en tramo':>8}  curva geometrica (R min, clase)")
    for r in rows:
        extra = f"#{r['geo_index']} ({r['min_radius_m']:.0f} m, {r['severity']})" if r["geo_index"] else "-"
        print(f"{r['name']:<24} {r['fraction']:>8.3f} {r['nearest_m'] if r['nearest_m'] is not None else '-':>7} "
              f"{r['delta_m'] if r['delta_m'] is not None else '-':>6} {'si' if r['inside_extent'] else 'no':>8}  {extra}")
    d = [r["nearest_m"] for r in rows if r["nearest_m"] is not None]
    if d:
        print(f"distancia media {sum(d) / len(d):.1f} m, maxima {max(d):.1f} m "
              f"(signo + = la tabla queda despues del apice geometrico; 'en tramo' = dentro de inicio-fin de la curva)")
    free = res["geometric_without_table"]
    print(f"\nCurvas geometricas sin curva tabulada ({len(free)}):")
    for c in free:
        print(f"  #{c['index']:<3} fraccion {c['apex_fraction']:.3f} ({c['apex_fraction'] * scale_m:.0f} m) "
              f"R {c['min_radius_m']:.0f} m {c['direction']} {c['severity']}")
    miss = res["table_without_peak"]
    print(f"\nCurvas tabuladas sin pico geometrico a menos de {FAR_M:.0f} m ({len(miss)}):")
    for r in miss:
        print(f"  {r['name']} (fraccion {r['fraction']:.3f})")
    return res


def _write(circuit_id, track_id, layout, geo, lane, official):
    out = G.build_export(circuit_id, track_id, layout, geo, lane, official)
    G.TRACK_GEOMETRY_DIR.mkdir(parents=True, exist_ok=True)
    path = G.TRACK_GEOMETRY_DIR / f"{circuit_id}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


def export_all(tracks_dir):
    circuits = C.load_circuits()
    summary = []
    for cid, cands in EXPORT_PLAN.items():
        circ = circuits.get(cid)
        if not circ:
            print(f"[{cid}] no esta en circuits.json: omitido")
            continue
        nominal = float(circ["length_m"])
        best = None
        order: list = []
        for track_id, layout in cands:
            try:
                geo, lane, off = G.analyze_track(track_id, layout, tracks_dir)
            except G.FastLaneError as exc:
                print(f"[{cid}] {track_id}/{layout or '-'}: {exc}")
                continue
            if not off or abs(off / nominal - 1.0) > LENGTH_MATCH:
                print(f"[{cid}] {track_id}/{layout or '-'}: longitud oficial {off} m no cuadra con {nominal:.0f} m (+-3 %)")
                continue
            if not geo.closed:
                print(f"[{cid}] {track_id}/{layout or '-'}: linea no cerrada, descartada")
                continue
            res = G.compare_with_table(circ, _corner_dicts(geo), nominal)
            d = [r["nearest_m"] for r in res["rows"] if r["nearest_m"] is not None]
            score = (sum(d) / len(d)) if d else None
            key = (round(abs(off / nominal - 1.0), 4), len(order))
            order.append(1)
            if best is None or key < best[0]:
                best = (key, track_id, layout, geo, lane, off, score, max(d) if d else None)
        if best is None:
            print(f"[{cid}] NINGUN layout cuadra: no se exporta")
            summary.append((cid, None))
            continue
        _, track_id, layout, geo, lane, off, mean_d, max_d = best
        path = _write(cid, track_id, layout, geo, lane, off)
        print(f"[{cid}] {track_id}/{layout or '-'}  linea {geo.length_line_m:.0f} m  oficial {off:.0f} m  "
              f"{len(geo.corners)} curvas  -> {os.path.relpath(path, ROOT)}"
              + (f"  tabla: media {mean_d:.1f} m, max {max_d:.1f} m" if mean_d is not None else ""))
        summary.append((cid, (track_id, layout, mean_d, max_d)))
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("track_id", nargs="?", help="carpeta de la pista en content/tracks (p. ej. imola, ks_silverstone)")
    ap.add_argument("--layout", default="", help="subcarpeta del layout (p. ej. gp, layout_gp); por defecto la raiz de la pista")
    ap.add_argument("--circuit", help="id de circuits.json (por defecto se deduce del track_id)")
    ap.add_argument("--compare", action="store_true", help="contrasta con la tabla de circuits.json")
    ap.add_argument("--export", action="store_true", help="escribe src/data/track_geometry/<circuit_id>.json")
    ap.add_argument("--export-all", action="store_true", help="exporta todos los circuitos de AC de circuits.json")
    ap.add_argument("--list-layouts", action="store_true", help="lista los layouts con fast_lane.ai de la pista")
    a = ap.parse_args()

    tracks = G.find_ac_tracks_dir()
    if tracks is None:
        print("No se encuentra la carpeta del juego (define AC_CONTENT_DIR o AC_INSTALL_DIR).", file=sys.stderr)
        return 2
    if a.export_all:
        export_all(tracks)
        return 0
    if not a.track_id:
        ap.error("falta TRACK_ID")
    if a.list_layouts:
        for lay in G.list_layouts(a.track_id, tracks):
            off = G.official_length_m(a.track_id, lay, tracks)
            print(f"{lay or '(raiz)':<28} oficial: {off if off else '?'} m")
        return 0
    try:
        geo, lane, off = G.analyze_track(a.track_id, a.layout, tracks)
    except G.FastLaneError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    circ = C.get_circuit(a.circuit) if a.circuit else C.find_circuit(a.track_id)
    scale = off or (circ and circ["length_m"]) or geo.length_line_m
    print(f"{a.track_id}/{a.layout or '(raiz)'}  fast_lane.ai v{lane.version}, {len(lane.x)} puntos")
    print_corners(geo, off, scale)
    if a.compare:
        if circ:
            contrast(circ, geo, float(circ["length_m"]))
        else:
            print("\nEl circuito no esta en circuits.json: nada que contrastar.")
    if a.export:
        if not circ:
            print("--export necesita un circuito de circuits.json (usa --circuit).", file=sys.stderr)
            return 1
        if not off or abs(off / float(circ["length_m"]) - 1.0) > LENGTH_MATCH:
            print(f"Longitud oficial {off} m no cuadra con {circ['length_m']} m (+-3 %): no se exporta.", file=sys.stderr)
            return 1
        print("\nEscrito", _write(circ["id"], a.track_id, a.layout, geo, lane, off))
    return 0


if __name__ == "__main__":
    sys.exit(main())
