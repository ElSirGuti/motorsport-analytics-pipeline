"""Genera los fixtures reales (recortados) de tests/fixtures/ a partir de CSV MoTeC originales.

Uso (los CSV originales NO estan en el repo):

    python scripts/make_fixtures.py \
        --imola  C:/ruta/cayman_gt4_imola_assetto_corsa.csv \
        --spa    C:/ruta/porsche_gt4_spa.csv

Opciones:
    --out DIR          Directorio de salida (por defecto tests/fixtures).
    --anonymize        (por defecto) Sustituye el campo "Driver" de la cabecera por "Test Driver".
    --no-anonymize     Conserva el nombre real del piloto.
    --step N           Decimacion (1 = conserva los 20 Hz originales; por defecto 2 -> 10 Hz).

Que hace:
  * Conserva la cabecera MoTeC (metadatos, nombres de canal, fila de unidades, formato numerico
    con coma decimal si el original la usa) tal cual.
  * Recorta por vueltas completas usando el canal "Session Lap Count" (vueltas first..last).
  * Elimina canales irrelevantes para el pipeline (danos, torques, radios, viento, ERS...).
    Se conservan los canales de COLUMN_ALIASES, los de tiempo/vuelta/pit/combustible y los de
    desgaste/grip de neumatico (necesarios para detect_wear_tracking).
  * Escribe .csv.gz (NO .csv: *.csv va por Git LFS y esta en .gitignore).

Los fixtures contienen datos reales del propietario del repositorio. Por eso el piloto se
anonimiza por defecto.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Prefijos de canal que el pipeline usa (alias en src/io/loaders.py + tiempo/vuelta/pit/grip).
KEEP_PREFIXES = (
    "Ground Speed", "Brake Pos", "Throttle Pos", "Brake Bias", "Brake Temp", "Steering Angle",
    "CG Accel Lateral", "CG Accel Longitudinal", "Engine RPM", "Gear", "Car Coord", "Car Pos Norm",
    "Chassis Yaw Rate", "Fuel Level", "Max Fuel", "In Pit", "Lap Invalidated", "Lap Time",
    "Last Lap Time", "Best Lap Time", "Session Lap Count", "Session Time Left", "Air Temp",
    "Road Temp", "Tire Temp", "Tire Pressure", "Tire Rubber Grip", "Tire Wear",
    "Suspension Travel", "Position", "AID Tire Wear Rate", "AID Fuel Rate",
)

DROP_EXACT = {"Lap Time2", "Car Coord Z", "Last Lap Time", "Best Lap Time", "Position"}  # duplicado / poco util: ahorran peso


def _find_header(rows: list[str]) -> int:
    """Indice de la fila con nombres de canal: la primera con muchas columnas y 'Speed'."""
    for i, line in enumerate(rows[:60]):
        fields = next(csv.reader([line]))
        if len(fields) > 20 and any("Speed" in f for f in fields):
            return i
    raise SystemExit("No se encontro la fila de cabecera de datos")


def _num(s: str) -> float:
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return float("nan")


def make_fixture(src: str, dst: str, first_lap: int, last_lap: int, step: int, anonymize: bool) -> None:
    with open(src, "r", encoding="utf-8", errors="ignore", newline="") as f:
        text = f.read()
    rows = text.splitlines()
    h = _find_header(rows)
    header = next(csv.reader([rows[h]]))
    keep_idx = [i for i, c in enumerate(header) if c.startswith(KEEP_PREFIXES) and c not in DROP_EXACT]
    lap_i = header.index("Session Lap Count")

    # filas: cabecera de datos h, unidades h+1, vacias, luego muestras
    units = next(csv.reader([rows[h + 1]]))
    first_data = h + 2
    while first_data < len(rows) and not rows[first_data].strip():
        first_data += 1

    meta = []
    for line in rows[:h]:
        if anonymize and re.match(r'^"?Driver"?,', line):
            line = re.sub(r'^("?Driver"?,)"[^"]*"', r'\g<1>"Test Driver"', line)
        meta.append(line)

    out = io.StringIO(newline="")
    w = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    for line in meta:
        out.write(line + "\r\n")
    out.write("\r\n")
    w.writerow([header[i] for i in keep_idx])
    w.writerow([units[i] if i < len(units) else "" for i in keep_idx])
    out.write("\r\n")

    n = 0
    for k, line in enumerate(rows[first_data:]):
        if not line.strip():
            continue
        fields = next(csv.reader([line]))
        if len(fields) <= lap_i:
            continue
        lap = _num(fields[lap_i])
        if not (first_lap <= lap <= last_lap):
            continue
        if n % step == 0:
            w.writerow([fields[i] for i in keep_idx])
        n += 1

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with gzip.GzipFile(dst, "wb", compresslevel=9, mtime=0) as gz:  # mtime=0 -> reproducible
        gz.write(out.getvalue().encode("utf-8"))
    print(f"{os.path.basename(dst)}: {n // step} filas, {len(keep_idx)} canales, "
          f"{os.path.getsize(dst) / 1024:.0f} KB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--imola", help="CSV MoTeC original de Imola (Assetto Corsa, 21 vueltas)")
    ap.add_argument("--spa", help="CSV MoTeC original de Spa (desgaste inactivo)")
    ap.add_argument("--lap-fast", help="CSV de UNA vuelta rapida (Red Bull Ring, Cayman GT4)")
    ap.add_argument("--lap-slow", help="CSV de UNA vuelta lenta (mismo coche y circuito)")
    ap.add_argument("--lap-other-car", help="CSV de UNA vuelta con otro coche (Maserati GT MC GT4)")
    ap.add_argument("--out", default=os.path.join(ROOT, "tests", "fixtures"))
    ap.add_argument("--step", type=int, default=2)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--anonymize", dest="anonymize", action="store_true", default=True)
    g.add_argument("--no-anonymize", dest="anonymize", action="store_false")
    a = ap.parse_args()
    singles = {"rbr_fast": a.lap_fast, "rbr_slow": a.lap_slow, "rbr_other_car": a.lap_other_car}
    if not (a.imola or a.spa or any(singles.values())):
        ap.error("indica --imola, --spa y/o --lap-fast/--lap-slow/--lap-other-car")
    for name, src in singles.items():  # archivos de una sola vuelta: se conservan todas las filas
        if src:
            make_fixture(src, os.path.join(a.out, f"{name}.csv.gz"), -1e9, 1e9, a.step, a.anonymize)
    if a.imola:  # vueltas 1..5 (la 1 es lenta: salida/primera vuelta)
        make_fixture(a.imola, os.path.join(a.out, "imola_5laps.csv.gz"), 1, 5, a.step, a.anonymize)
    if a.spa:    # vueltas 0..3 (la 3 es parcial: la sesion termina a mitad de vuelta)
        make_fixture(a.spa, os.path.join(a.out, "spa_3laps.csv.gz"), 0, 3, a.step, a.anonymize)
    return 0


if __name__ == "__main__":
    sys.exit(main())
