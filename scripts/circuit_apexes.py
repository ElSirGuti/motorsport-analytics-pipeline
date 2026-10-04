#!/usr/bin/env python
"""Lista los ápices de un circuito a partir de telemetría real, para añadir/validar curvas en
``src/data/circuits.json``.

Detecta los ápices con el detector de geometría (curvatura de la trazada) y con el de velocidad
(mínimos locales) en TODAS las vueltas completas del archivo, los agrupa por posición en la vuelta y
solo conserva los que aparecen en una fracción mínima de las vueltas (consenso: un ápice espurio de
una sola vuelta no cuenta). Para cada uno muestra la ``apex_fraction`` que va en el JSON y, si el
circuito ya está en la tabla, la curva con nombre más cercana.

Uso:
    python scripts/circuit_apexes.py ARCHIVO.csv [--min-share 0.6] [--tol 0.012] [--json]

ARCHIVO puede ser .csv (MoTeC), .ibt (iRacing) o .ld (MoTeC). Para cada circuito conviene usar al menos
2 archivos o 2 coches distintos antes de dar la confianza por 'high' (ver README, "Known circuits").

Importante: la lista es de CANDIDATOS. El nombre y el orden de las curvas los tienes que poner tú (con
el trazado oficial delante); esta herramienta solo dice DÓNDE hay un ápice medible. Una curva que el
coche toma a fondo (p. ej. Variante Bassa en Imola con un GT4) no genera ápice y no aparecerá aquí.
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

import numpy as np  # noqa: E402

from src.analytics import circuits as C  # noqa: E402
from src.analytics.geometry import detectar_apexes_perfectos, procesar_geometria_pista_perfecta  # noqa: E402
from src.analytics.stint import segmentar_vueltas_desde_csv  # noqa: E402
from src.io.loaders import load_telemetry_data, read_motec_metadata  # noqa: E402
from src.telemetry.metrics import detect_apex_points  # noqa: E402


def _clean_laps(df):
    """Vueltas completas: longitud cercana a la mediana (descarta salidas de pit y vueltas parciales)."""
    try:
        laps = segmentar_vueltas_desde_csv(df)
    except ValueError:
        # Archivo de UNA sola vuelta (lo habitual al empezar con un circuito nuevo): se usa entero.
        print("Aviso: no se detectaron varias vueltas; se usa el archivo completo como una sola vuelta "
              "(sin consenso: confirma los ápices con otra vuelta u otro coche).\n")
        laps = [df]
    lengths = [float(l["Distance"].max() - l["Distance"].min()) for l in laps]
    if not lengths:
        return []
    med = float(np.median(lengths))
    return [l.reset_index(drop=True) for l, n in zip(laps, lengths) if abs(n - med) <= 0.04 * med]


def _apexes_of(lap):
    """(fracción de vuelta, velocidad, método) de cada ápice detectado en una vuelta."""
    d = lap["Distance"].to_numpy(dtype=float)
    d = d - d[0]
    length = float(d[-1]) or 1.0
    found = []
    try:
        g = procesar_geometria_pista_perfecta(lap)
        for _, r in detectar_apexes_perfectos(g).iterrows():
            found.append((float(r["Distance"]) / length, float(r.get("Speed", np.nan)), "geometry"))
    except Exception:
        pass
    try:
        for a in detect_apex_points(lap):
            found.append((float(a["distance"]) / length, float(a["speed"]), "speed"))
    except Exception:
        pass
    return found, length


def _cluster(points, tol):
    """Agrupa fracciones cercanas (<= tol). Devuelve [{frac, n_laps, speed, methods}] ordenado."""
    points = sorted(points, key=lambda p: p[0])
    clusters = []
    for frac, spd, method, lap_id in points:
        if clusters and frac - clusters[-1]["fracs"][-1] <= tol:
            c = clusters[-1]
        else:
            c = {"fracs": [], "speeds": [], "methods": set(), "laps": set()}
            clusters.append(c)
        c["fracs"].append(frac)
        c["speeds"].append(spd)
        c["methods"].add(method)
        c["laps"].add(lap_id)
    return clusters


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="telemetría (.csv, .ibt o .ld)")
    ap.add_argument("--min-share", type=float, default=0.6,
                    help="fracción mínima de vueltas en las que debe aparecer el ápice (por defecto 0.6)")
    ap.add_argument("--tol", type=float, default=0.012,
                    help="tolerancia de agrupación, como fracción de vuelta (por defecto 0.012 = ~60 m en 5 km)")
    ap.add_argument("--json", action="store_true", help="imprime también el bloque 'corners' para circuits.json")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # la salida lleva tildes: en Windows seria cp1252

    df = load_telemetry_data(a.file)
    try:
        venue = (read_motec_metadata(a.file) or {}).get("venue")
    except Exception:
        venue = None
    laps = _clean_laps(df)
    if not laps:
        print("No se encontraron vueltas completas en el archivo.")
        return 1

    points, lengths = [], []
    for i, lap in enumerate(laps):
        found, length = _apexes_of(lap)
        lengths.append(length)
        points += [(f, s, m, i) for f, s, m in found]
    clusters = _cluster(points, a.tol)
    need = max(1, int(np.ceil(a.min_share * len(laps))))
    kept = [c for c in clusters if len(c["laps"]) >= need]

    length = float(np.median(lengths))
    circuit = C.find_circuit(venue) if venue else None
    print(f"Archivo: {os.path.basename(a.file)}")
    print(f"Circuito (cabecera): {venue!r} -> {'reconocido: ' + circuit['name'] if circuit else 'NO está en la tabla'}")
    print(f"Vueltas completas usadas: {len(laps)}   longitud mediana: {length:.0f} m"
          + (f"   (tabla: {circuit['length_m']} m)" if circuit else ""))
    print(f"Ápices que aparecen en >= {need} de {len(laps)} vueltas (tolerancia {a.tol}):\n")
    print(f"{'#':>3} {'apex_fraction':>13} {'distancia':>10} {'vel km/h':>9} {'vueltas':>8}  {'método':<15} nombre en la tabla")
    rows = []
    for k, c in enumerate(kept, 1):
        frac = float(np.median(c["fracs"]))
        name = ""
        if circuit:
            n = C.name_for_distance(C.recognize(venue, length), frac * length, length)
            name = n or ""
        spd = float(np.nanmedian(c["speeds"])) if np.isfinite(c["speeds"]).any() else float("nan")
        print(f"{k:>3} {frac:>13.3f} {frac * length:>8.0f} m {spd:>9.0f} {len(c['laps']):>4}/{len(laps):<3}  "
              f"{'+'.join(sorted(c['methods'])):<15} {name}")
        rows.append({"order": k, "name": name or "?", "apex_fraction": round(frac, 3)})
    dropped = len(clusters) - len(kept)
    if dropped:
        print(f"\n({dropped} candidatos descartados por aparecer en pocas vueltas)")
    if a.json:
        print("\nBloque para 'corners' (rellena los nombres '?' con el trazado oficial delante):")
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
