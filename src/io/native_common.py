"""
Utilidades comunes a los loaders de formatos nativos (iRacing .ibt, MoTeC .ld).

ESTADO: EXPERIMENTAL. Los formatos se implementaron a partir de su documentacion
publica y se validaron con archivos reales del autor (ver tests/test_formats.py y
docs/USER_GUIDE.md), pero cubren una muestra pequena de coches/simuladores.

Contrato de salida (igual que el camino CSV tras ``load_telemetry_data``):
  - Nombres canonicos de ``COLUMN_ALIASES`` (Speed, Throttle, Brake, Distance...).
  - Unidades ya normalizadas: Speed km/h, Throttle/Brake 0-100 %, SteerAngle deg,
    LateralG/LongitudinalG en g, YawRate deg/s, presiones en bar, suspension en mm,
    temperaturas en C, Distance en m (acumulada de sesion).
  - ``df.attrs['format']``, ``df.attrs['experimental']``, ``df.attrs['metadata']``.

CONVENCION INTERNA DE LateralG (documentada en ``normalize_lateral_sign``):
  LateralG tiene el MISMO signo que YawRate en curva estacionaria (ay ~ r*V), es decir
  corr(LateralG, YawRate*Speed) > 0. Con el YawRate de iRacing (positivo = giro a la
  izquierda) eso significa LateralG positivo = giro a la izquierda. Las fuentes cuya
  convencion difiere (p. ej. ACTI/Assetto Corsa .ld: LateralG negativo al girar a la
  izquierda, corr ~ -0.95) se invierten en el loader nativo; ``df.attrs['lateral_g_flipped']``
  lo registra. Los CSV de Assetto Corsa NO se tocan (ver ``loaders.load_telemetry_data``).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from src.i18n import _ as _tr

logger = logging.getLogger(__name__)

NATIVE_EXTENSIONS = (".ibt", ".ld")
G0 = 9.80665

try:
    MAX_NATIVE_ROWS = max(10_000, int(os.getenv("NATIVE_MAX_ROWS", "2000000")))
except ValueError:
    MAX_NATIVE_ROWS = 2_000_000


# ── Deteccion de formato ──────────────────────────────────────────────────────
def detect_format(filepath: str) -> str:
    """Devuelve 'ibt', 'ld' o 'csv'. La extension manda; si el nombre no es
    concluyente (p. ej. la API guarda las subidas como 'session.csv') se mira
    la firma binaria del archivo."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".ibt":
        return "ibt"
    if ext == ".ld":
        return "ld"
    try:
        with open(filepath, "rb") as f:
            head = f.read(144)
    except OSError:
        return "csv"
    return sniff_bytes(head) or "csv"


def sniff_bytes(head: bytes) -> Optional[str]:
    import struct
    if len(head) >= 16 and head[:4] == b"\x40\x00\x00\x00" and head[4:8] == b"\x00\x00\x00\x00":
        meta_ptr, data_ptr = struct.unpack_from("<II", head, 8)
        if 0 < meta_ptr < data_ptr:
            return "ld"
    if len(head) >= 40:
        ver, _status, tick, _siu, sil, sio, nvars, vho, nbuf, buflen = struct.unpack_from("<10i", head, 0)
        if ver in (1, 2) and 1 <= tick <= 1000 and 0 < nvars < 20000 and 0 < buflen < 10_000_000 \
                and sil >= 0 and sio > 0 and vho > 0 and 1 <= nbuf <= 4:
            return "ibt"
    return None


# ── Modelo intermedio ─────────────────────────────────────────────────────────
@dataclass
class RawChannel:
    """Un canal tal y como esta en disco (sin escalar si es posible)."""
    name: str
    unit: str
    freq: float                      # Hz
    n: int                           # numero de muestras
    reader: Callable[[], np.ndarray]  # devuelve float64 ya escalado a la unidad ``unit``
    discrete: bool = False           # entero/enumerado: se mantiene el ultimo valor al remuestrear

    def values(self) -> np.ndarray:
        return self.reader()


# ── Alias extra (nombres nativos que COLUMN_ALIASES no cubre) ─────────────────
# Se anaden DESPUES de los alias del loader CSV; los nombres nativos de iRacing
# tienen prioridad porque vienen primero en las listas por-formato.
EXTRA_ALIASES: Dict[str, List[str]] = {
    "Distance":      ["LapDist", "Lap Distance"],
    "LateralG":      ["LatAccel", "G Force Lat"],
    "LongitudinalG": ["LongAccel", "G Force Long"],
    "LapTime":       ["LapCurrentLapTime"],
    "SessionLapCount": ["Lap Number", "LapCompleted"],
    "Gear":          ["Gear"],
    "FuelLevel":     ["FuelLevel", "Fuel Level", "Fuel"],
    "WaterTemp":     ["WaterTemp", "Engine Temp"],
    "OilTemp":       ["OilTemp", "Eng Oil Temp"],
    "RPM":           ["RPM", "Engine RPM"],
    "AirTemp":       ["AirTemp", "Air Temp"],
    "RoadTemp":      ["TrackTemp", "Road Temp"],
    "InPit":         ["OnPitRoad", "In Pit", "InPit"],
}

# canal canonico -> tipo de conversion
KINDS: Dict[str, str] = {
    "Speed": "speed",
    "Brake": "pedal", "Throttle": "pedal", "Clutch": "pedal",
    "SteerAngle": "angle_deg",
    "LateralG": "accel_g", "LongitudinalG": "accel_g",
    "YawRate": "rate_degs",
    "WindSpeed": "wind_kmh", "WindDir": "angle_deg",
    "BrakeBias": "fraction_pct",
    **{f"TyrePress{p}": "pressure_bar" for p in ("FL", "FR", "RL", "RR")},
    **{f"TyrePressCold{p}": "pressure_bar" for p in ("FL", "FR", "RL", "RR")},
    **{f"SuspTravel{p}": "length_mm" for p in ("FL", "FR", "RL", "RR")},
}

# canales que se copian tal cual si existen (nombre original) porque el
# pipeline los busca con ese nombre (geometria iRacing, deposito AC, GPS)
PASSTHROUGH = ("Lat", "Lon", "Alt", "YawNorth", "VelocityX", "VelocityY", "Max Fuel")

# canales discretos (se mantiene el ultimo valor al remuestrear)
DISCRETE = {"Gear", "SessionLapCount", "InPit", "TCActive", "ABSActive", "LapInvalid", "TrackSurface"}

# canales cuya presencia se requiere para que el pipeline funcione
_ESSENTIAL = ("Speed", "Brake", "Throttle")


def _norm_unit(u: str) -> str:
    u = (u or "").strip().lower().replace(" ", "").replace("²", "2").replace("^", "")
    return u


def convert(kind: str, values: np.ndarray, unit: str, *, fraction_pedals: Optional[bool] = None) -> np.ndarray:
    """Convierte ``values`` (en ``unit``) a la unidad canonica del ``kind``."""
    u = _norm_unit(unit)
    v = np.asarray(values, dtype=np.float64)
    if kind == "speed":
        if u in ("m/s", "ms", ""):
            return v * 3.6
        if u in ("mph", "mi/h"):
            return v * 1.609344
        return v                                   # km/h
    if kind == "pedal":
        finite = v[np.isfinite(v)]
        mx = float(finite.max()) if finite.size else 0.0
        frac = fraction_pedals if fraction_pedals is not None else (0 < mx <= 1.05)
        return v * 100.0 if frac else v
    if kind == "angle_deg":
        return np.rad2deg(v) if u == "rad" else v
    if kind == "accel_g":
        if u in ("m/s2", "ms2"):
            return v / G0
        return v                                   # ya en g
    if kind == "wind_kmh":
        return v * 3.6 if u in ("m/s", "ms") else v
    if kind == "rate_degs":
        return np.rad2deg(v) if u in ("rad/s", "rads") else v
    if kind == "pressure_bar":
        if u == "kpa":
            return v / 100.0
        if u == "psi":
            return v / 14.5038
        if u == "pa":
            return v / 1e5
        if u == "bar":
            return v
        finite = v[np.isfinite(v)]                 # unidad desconocida: misma heuristica que el CSV
        mx = float(finite.max()) if finite.size else 0.0
        return v * 0.01 if mx > 100 else (v / 14.5038 if mx > 10 else v)
    if kind == "length_mm":
        return v * 1000.0 if u == "m" else v
    if kind == "fraction_pct":
        finite = v[np.isfinite(v)]
        return v * 100.0 if finite.size and float(finite.max()) <= 1.05 else v
    return v


# ── Seleccion de canales ──────────────────────────────────────────────────────
def _alias_table() -> Dict[str, List[str]]:
    from src.io.loaders import COLUMN_ALIASES  # import perezoso (evita ciclo)
    table: Dict[str, List[str]] = {k: list(v) for k, v in COLUMN_ALIASES.items()}
    for canon, extra in EXTRA_ALIASES.items():
        lst = table.setdefault(canon, [])
        for a in extra:
            if a not in lst:
                lst.append(a)
    return table


def pick_channels(available: Dict[str, List[RawChannel]], native_first: List[str] | None = None
                  ) -> Dict[str, RawChannel]:
    """Devuelve {nombre_columna_de_salida: RawChannel}. ``available`` mapea nombre
    de canal -> candidatos (hay nombres duplicados en algunos .ld); se toma el
    primero con datos."""
    table = _alias_table()
    chosen: Dict[str, RawChannel] = {}

    def first_usable(name: str) -> Optional[RawChannel]:
        for ch in available.get(name, []):
            if ch.n > 1:
                return ch
        return None

    # Temperaturas de neumatico de iRacing: se usan las de SUPERFICIE (PtempL/M/R), que son las
    # que varian en pista (las de carcasa CL/CM/CR solo se actualizan en boxes). El mapeo
    # interior/exterior replica el export MoTeC de iRacing: en los neumaticos izquierdos
    # R es el interior; en los derechos lo es L.
    for pre, corner, left in (("LF", "FL", True), ("RF", "FR", False), ("LR", "RL", True), ("RR", "RR", False)):
        mapping = {"Middle": "M", "Inner": "R" if left else "L", "Outer": "L" if left else "R"}
        for zone, suffix in mapping.items():
            ch = first_usable(f"{pre}temp{suffix}")
            if ch is not None:
                chosen[f"TyreTemp{zone}{corner}"] = ch

    for canon, aliases in table.items():
        if canon in chosen:
            continue
        order = list(aliases)
        if native_first:
            order = [a for a in native_first if a in aliases] + [a for a in order if a not in native_first]
        if canon in available and first_usable(canon):
            order.insert(0, canon)
        for a in order:
            ch = first_usable(a)
            if ch is not None:
                chosen[canon] = ch
                break
    for name in PASSTHROUGH:
        ch = first_usable(name)
        if ch is not None and name not in chosen:
            chosen[name] = ch
    return chosen


# ── Convencion de signo de LateralG ───────────────────────────────────────────
def normalize_lateral_sign(df: pd.DataFrame) -> bool:
    """Fuerza la convencion interna LateralG ~ +YawRate*Speed (in place).

    Detecta la convencion de la fuente con ``slip_angle.lateral_sign_convention``
    (correlacion LateralG vs YawRate*Speed a > 10 m/s) y, si es negativa, invierte
    LateralG. Sin LateralG, YawRate o Speed (o sin datos suficientes) no hace nada.
    Devuelve True si se invirtio y lo anota en ``df.attrs['lateral_g_flipped']``.
    """
    flipped = False
    if all(c in df.columns for c in ("LateralG", "YawRate", "Speed")):
        from src.analytics.slip_angle import lateral_sign_convention, _yaw_to_rad
        ay = pd.to_numeric(df["LateralG"], errors="coerce")
        yaw = _yaw_to_rad(pd.to_numeric(df["YawRate"], errors="coerce").fillna(0))
        vx = pd.to_numeric(df["Speed"], errors="coerce").fillna(0) / 3.6
        if lateral_sign_convention(ay.fillna(0) * G0, yaw, vx) < 0:
            df["LateralG"] = -ay
            flipped = True
    df.attrs["lateral_g_flipped"] = flipped
    return flipped


# ── Remuestreo a rejilla comun ────────────────────────────────────────────────
def resample(values: np.ndarray, freq: float, grid_hz: float, n_out: int, discrete: bool) -> np.ndarray:
    if len(values) == 0:
        return np.full(n_out, np.nan)
    if abs(freq - grid_hz) < 1e-9 and len(values) == n_out:
        return values
    t_out = np.arange(n_out) / grid_hz
    if discrete:
        idx = np.minimum((t_out * freq + 1e-9).astype(np.int64), len(values) - 1)
        return values[idx]
    t_in = np.arange(len(values)) / freq
    return np.interp(t_out, t_in, values)


# ── Montaje del DataFrame canonico ────────────────────────────────────────────
def build_frame(chosen: Dict[str, RawChannel], *, fmt: str, time_s: Optional[np.ndarray] = None,
                grid_hz: Optional[float] = None, fraction_pedals: Optional[bool] = None,
                available_names: Optional[List[str]] = None, metadata: Optional[dict] = None,
                lap_dist_unwrap: bool = True) -> pd.DataFrame:
    """Remuestrea los canales elegidos a una rejilla comun, convierte unidades,
    sintetiza Distance si hace falta y valida los canales esenciales."""
    from src.io.loaders import DataLoaderException, _synthesize_distance

    missing = [c for c in _ESSENTIAL if c not in chosen]
    if "Speed" in missing:
        raise DataLoaderException(_tr("fmt_no_speed_channel", fmt=fmt.upper(),
                                      available=", ".join((available_names or [])[:40])))
    if missing:
        raise DataLoaderException(_tr("loader_missing_channels", missing=missing,
                                      available=(available_names or [])[:40]))

    freqs = [ch.freq for ch in chosen.values() if ch.freq > 0]
    if not freqs:
        raise DataLoaderException(_tr("fmt_no_data", fmt=fmt.upper()))
    hz = float(grid_hz or max(freqs))
    n_out = int(max(int(round(ch.n * hz / ch.freq)) for ch in chosen.values() if ch.freq > 0))
    if time_s is not None:
        n_out = len(time_s)
    if n_out < 2:
        raise DataLoaderException(_tr("fmt_no_data", fmt=fmt.upper()))
    if n_out > MAX_NATIVE_ROWS:
        raise DataLoaderException(_tr("fmt_too_many_samples", fmt=fmt.upper(), n=n_out, max=MAX_NATIVE_ROWS))

    cols: Dict[str, np.ndarray] = {}
    t = time_s if time_s is not None else np.arange(n_out) / hz
    cols["Time"] = np.asarray(t, dtype=np.float64) - float(t[0]) if len(t) else t
    for name, ch in chosen.items():
        vals = ch.values()
        discrete = ch.discrete or name in DISCRETE
        out = resample(vals, ch.freq, hz, n_out, discrete)
        kind = KINDS.get(name)
        if kind:
            out = convert(kind, out, ch.unit, fraction_pedals=fraction_pedals)
        cols[name] = out

    df = pd.DataFrame(cols)
    normalize_lateral_sign(df)

    # Distance: LapDist (por vuelta) -> acumulada de sesion
    if "Distance" in df.columns:
        d = df["Distance"].to_numpy(dtype=np.float64)
        if lap_dist_unwrap:
            d = unwrap_lap_distance(d, hz)
        df["Distance"] = d

    if "LapTime" in df.columns and chosen["LapTime"].name == "LapCurrentLapTime":
        df["LapTime"] = fix_lap_timer(df["LapTime"].to_numpy(dtype=np.float64),
                                      df["SessionLapCount"].to_numpy() if "SessionLapCount" in df.columns else None,
                                      df["Time"].to_numpy(dtype=np.float64))

    # Gear: iRacing usa -1 marcha atras, 0 punto muerto (se conserva)
    for c in ("Gear", "SessionLapCount"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round()

    dist_max = float(np.nanmax(np.abs(df["Distance"]))) if "Distance" in df.columns and df["Distance"].notna().any() else 0.0
    if "Distance" not in df.columns or not dist_max > 10.0:
        df = _synthesize_distance(df)

    for ch in _ESSENTIAL:
        if df[ch].isnull().all():
            raise DataLoaderException(_tr("loader_channel_not_numeric", ch=ch))

    base = [c for c in (*_ESSENTIAL, "Distance") if c in df.columns]
    if df[base].isnull().any().any():
        df[base] = df[base].interpolate(method="linear").ffill().bfill()

    df.attrs["format"] = fmt
    df.attrs["experimental"] = True
    df.attrs.setdefault("lateral_g_flipped", False)
    df.attrs["metadata"] = dict(metadata or {})
    df.attrs["sample_rate_hz"] = hz
    return df


def unwrap_lap_distance(d: np.ndarray, hz: float = 60.0) -> np.ndarray:
    """LapDist reinicia a ~0 en cada vuelta: la convierte en distancia acumulada
    de sesion sumando el salto de cada reinicio."""
    d = np.asarray(d, dtype=np.float64).copy()
    if len(d) < 2 or not np.isfinite(d).any():
        return d
    d = pd.Series(d).ffill().bfill().to_numpy()
    step = np.diff(d, prepend=d[0])
    mx = float(np.nanmax(d))
    wrap = step < -0.5 * max(mx, 1.0)
    # En un reinicio el avance real es el valor nuevo (distancia desde la linea).
    step = np.where(wrap, d, step)
    step = np.where(step < 0, 0.0, step)       # retrocesos (reset a boxes, etc.)
    # saltos imposibles (>150 m/s) = discontinuidad del registro (p. ej. primer muestreo basura)
    step = np.where(step > 150.0 / max(hz, 1.0) + 5.0, 0.0, step)
    return np.cumsum(step)


# ── Despacho ──────────────────────────────────────────────────────────────────
def load_native(filepath: str, fmt: str) -> pd.DataFrame:
    """Carga un archivo nativo ('ibt' | 'ld'). Cualquier fallo inesperado de
    parseo se convierte en un DataLoaderException traducido."""
    from src.io.loaders import DataLoaderException
    logger.info("Formato nativo EXPERIMENTAL detectado: %s", fmt)
    try:
        if fmt == "ibt":
            from src.io.ibt_loader import load_ibt
            return load_ibt(filepath)
        from src.io.ld_loader import load_ld
        return load_ld(filepath)
    except DataLoaderException:
        raise
    except (OSError, ValueError, KeyError, IndexError, MemoryError) as e:
        logger.exception("Error leyendo %s", fmt)
        raise DataLoaderException(_tr("fmt_unreadable", fmt=fmt.upper(), err=str(e)))
    except Exception as e:  # struct.error, etc.
        logger.exception("Error leyendo %s", fmt)
        raise DataLoaderException(_tr("fmt_unreadable", fmt=fmt.upper(), err=str(e)))


def read_native_metadata(filepath: str, fmt: str) -> dict:
    if fmt == "ibt":
        from src.io.ibt_loader import read_ibt_metadata
        return read_ibt_metadata(filepath)
    from src.io.ld_loader import read_ld_metadata
    return read_ld_metadata(filepath)


def fix_lap_timer(lap_time: np.ndarray, lap: Optional[np.ndarray], time_s: np.ndarray) -> np.ndarray:
    """LapCurrentLapTime de iRacing sigue contando la vuelta anterior ~2 s despues de
    cruzar meta (el contador de vueltas ya cambio) y luego salta al valor real. Eso
    rompe la duracion de cada vuelta. Se reconstruye el cronometro por vuelta como
    tiempo transcurrido desde el cambio del contador (error <= 1 muestra)."""
    t = np.asarray(lap_time, dtype=np.float64).copy()
    t[t < 0] = np.nan
    t = pd.Series(t).ffill().bfill().to_numpy()
    if lap is None or len(t) < 3:
        return t
    lap = np.asarray(lap)
    starts = np.concatenate(([0], np.flatnonzero(np.diff(lap) != 0) + 1))
    out = np.empty_like(t)
    bounds = np.append(starts, len(t))
    for a, b in zip(bounds[:-1], bounds[1:]):
        out[a:b] = time_s[a:b] - time_s[a]
    return out
