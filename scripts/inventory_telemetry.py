#!/usr/bin/env python
"""Inventario de archivos de telemetría: circuito, coche, nº de vueltas completas y longitud.

Sirve para ver de un vistazo qué datos reales hay para probar la detección de curvas (y qué falta).

Uso:
    python scripts/inventory_telemetry.py CARPETA [CARPETA ...] [--min-lap-m 800]

Recorre las carpetas de forma recursiva (.csv, .ibt, .ld). No modifica nada.
"""
from __future__ import annotations

import argparse
import collections
import logging
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
logging.disable(logging.CRITICAL)

import numpy as np  # noqa: E402

from src.analytics import circuits as C  # noqa: E402
from src.analytics.stint import segmentar_vueltas_desde_csv  # noqa: E402
from src.io.header_meta import read_header  # noqa: E402
from src.io.loaders import load_telemetry_data  # noqa: E402

EXTS = (".csv", ".ibt", ".ld")


def inspect(path: str, min_lap_m: float) -> dict:
    row = {"file": path, "venue": "?", "vehicle": "?", "laps": 0, "length": float("nan"), "note": ""}
    try:
        head = read_header(path) or {}
        row["venue"] = head.get("venue") or head.get("circuit") or "?"
        row["vehicle"] = head.get("vehicle") or head.get("car") or "?"
    except Exception as exc:  # noqa: BLE001
        row["note"] = f"header: {type(exc).__name__}"
    try:
        df = load_telemetry_data(path)
        try:
            laps = segmentar_vueltas_desde_csv(df)
        except ValueError:
            laps = [df]  # archivo de una sola vuelta
        lengths = [float(l["Distance"].max() - l["Distance"].min()) for l in laps]
        lengths = [n for n in lengths if n >= min_lap_m]
        if lengths:
            med = float(np.median(lengths))
            full = [n for n in lengths if abs(n - med) <= 0.04 * med]
            row["laps"], row["length"] = len(full), med
    except Exception as exc:  # noqa: BLE001
        row["note"] = (row["note"] + " load: " + type(exc).__name__).strip()
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--min-lap-m", type=float, default=800.0, help="longitud mínima para contar una vuelta")
    a = ap.parse_args()

    files = []
    for folder in a.folders:
        for root, _dirs, names in os.walk(folder):
            files += [os.path.join(root, n) for n in names if n.lower().endswith(EXTS)]
    rows = [inspect(p, a.min_lap_m) for p in sorted(files)]

    by_venue = collections.defaultdict(list)
    for r in rows:
        by_venue[str(r["venue"])].append(r)

    print(f"{len(rows)} archivos en {len(by_venue)} circuitos\n")
    print(f"{'circuito':<26}{'en tabla':<13}{'coche':<42}{'vueltas':>8}{'longitud':>10}  archivo")
    print("-" * 125)
    for venue in sorted(by_venue):
        circ = C.find_circuit(venue) if venue != "?" else None
        label = ("con nombres" if circ and circ.get("corners") else "solo reconoc.") if circ else "NO"
        for r in sorted(by_venue[venue], key=lambda x: str(x["vehicle"])):
            length = f"{r['length']:.0f} m" if r["length"] == r["length"] else "-"
            print(f"{venue[:25]:<26}{label:<13}{str(r['vehicle'])[:41]:<42}{r['laps']:>8}{length:>10}  "
                  f"{os.path.basename(r['file'])[:34]} {r['note']}")
    print("\nResumen por circuito (coches distintos / vueltas completas en total):")
    for venue in sorted(by_venue):
        cars = {str(r["vehicle"]) for r in by_venue[venue]}
        print(f"  {venue[:30]:<32}{len(cars):>3} coches  {sum(r['laps'] for r in by_venue[venue]):>4} vueltas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
