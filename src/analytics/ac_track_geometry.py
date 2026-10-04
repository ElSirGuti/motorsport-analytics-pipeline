"""
Geometric ground truth of where the corners of a circuit are, read from the racing
line of the AI in an installed Assetto Corsa (read-only).

Why: a corner detector working on telemetry only sees a corner if the car slows down
for it. The geometry of the track does not depend on the car, so it gives a
car-independent reference ("there is a bend of radius R here, even if a GT takes it
flat out").

Source file: ``<tracks>/<track>/[<layout>/]ai/fast_lane.ai`` (format version 7)::

    header   4 x int32 little endian: version, detail_count, lap_time, sample_count
    records  detail_count x 20 bytes: x f32, y f32, z f32, s f32 (cumulative distance), id i32
    ...      other blocks that are NOT needed (ignored)

The horizontal plane is (x, z); samples are ~1.6 m apart. The game folder is only ever
read, never written. Deployments (Docker / Kubernetes) do not see the game, so the
derived corners are exported to ``src/data/track_geometry/<circuit_id>.json``
(see ``scripts/ac_track_reference.py``) and read with
``src.analytics.circuits.get_track_geometry``.

Method (all thresholds are module constants):
  1. the line is resampled every ``RESAMPLE_M`` metres and x, z are smoothed with a
     Savitzky-Golay filter (window ``SMOOTH_WINDOW_M`` metres, cubic polynomial), which
     also gives x', z', x'', z''. Signed curvature k = (x'z'' - z'x'') / (x'^2+z'^2)^1.5
     (positive = left turn, negative = right turn; checked against the ``run`` field).
  2. if the line is a closed circuit (end within ``CLOSE_GAP_M`` of the start) the lap is
     treated as periodic. Positions are normalised to a FRACTION OF THE LAP (distance /
     closed line length): the line differs ~1 % in length from the official figure, and
     ``circuits.json`` also stores fractions.
  3. peaks of |k| (minimum radius up to 400 m, prominence 1/600 m^-1, 40 m apart) are apexes;
     each gets start / end where |k| falls below max(1/600, 20 % of its peak).
  4. apexes closer than ``COMPLEX_GAP_M`` or of opposite sign closer than
     ``CHICANE_GAP_M`` are grouped into one "complex" with sub-apexes.
  5. severity from the minimum radius: slow < 60 m, medium 60-150 m, fast 150-400 m.
     A "fast" bend can still be flat out for a car with a lot of downforce; the class
     describes the geometry, not what a given car does.
"""
from __future__ import annotations

import json
import math
import os
import re
import struct
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np

FAST_LANE_VERSION = 7
HEADER_BYTES = 16
RECORD_BYTES = 20

# -- parameters --------------------------------------------------------------------
RESAMPLE_M = 2.0              # uniform spacing of the resampled line
SMOOTH_WINDOW_M = 62.0        # Savitzky-Golay window (31 samples at 2 m), cubic
CLOSE_GAP_M = 25.0            # end-to-start gap below which the line is a closed circuit
PEAK_MIN_CURVATURE = 1.0 / 400.0   # corners with a minimum radius up to 400 m
PEAK_PROMINENCE = 1.0 / 600.0
PEAK_DISTANCE_M = 40.0
EDGE_CURVATURE = 1.0 / 600.0  # corner extent: |k| above this ...
EDGE_PEAK_SHARE = 0.20        # ... or above 20 % of its peak, whichever is larger
COMPLEX_GAP_M = 120.0         # apexes closer than this form one complex
CHICANE_GAP_M = 200.0         # opposite-sign apexes closer than this form a chicane
SLOW_RADIUS_M = 60.0
MEDIUM_RADIUS_M = 150.0
FAST_RADIUS_M = 400.0

SEVERITIES = ("slow", "medium", "fast")


class FastLaneError(ValueError):
    """The fast_lane.ai file is missing, truncated, corrupt or of an unsupported version."""


# -- data classes -------------------------------------------------------------------

@dataclass
class FastLane:
    """Parsed racing line."""
    x: np.ndarray
    z: np.ndarray
    s: np.ndarray            # cumulative distance of the file (m)
    version: int = FAST_LANE_VERSION
    lap_time: int = 0
    sample_count: int = 0

    @property
    def length_m(self) -> float:
        return float(self.s[-1])


@dataclass
class SubApex:
    fraction: float
    distance_m: float        # metres along the line
    radius_m: float
    direction: str           # 'left' | 'right'


@dataclass
class GeometricCorner:
    index: int
    start_fraction: float
    apex_fraction: float
    end_fraction: float
    apex_m: float            # metres along the line (not rescaled to the official length)
    start_m: float
    end_m: float
    min_radius_m: float
    direction: str           # direction of the tightest sub-apex
    severity: str            # slow | medium | fast
    kind: str                # single | chicane (opposite signs) | compound (same sign)
    sub_apexes: List[SubApex] = field(default_factory=list)

    @property
    def is_complex(self) -> bool:
        return len(self.sub_apexes) > 1

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_fraction": round(self.start_fraction, 5),
            "apex_fraction": round(self.apex_fraction, 5),
            "end_fraction": round(self.end_fraction, 5),
            "apex_m": round(self.apex_m, 1),
            "min_radius_m": round(self.min_radius_m, 1),
            "direction": self.direction,
            "severity": self.severity,
            "kind": self.kind,
            "complex": self.is_complex,
            "sub_apexes": [
                {"fraction": round(a.fraction, 5), "distance_m": round(a.distance_m, 1),
                 "radius_m": round(a.radius_m, 1), "direction": a.direction}
                for a in self.sub_apexes
            ],
        }


@dataclass
class Geometry:
    """Curvature profile + corners of one racing line."""
    length_line_m: float     # closed length when the line is a circuit
    closed: bool
    ds: float
    distance_m: np.ndarray   # position of each profile sample (m along the line)
    curvature: np.ndarray    # signed, 1/m (positive = left)
    corners: List[GeometricCorner]
    closure_gap_m: float = 0.0
    turning_deg: float = 0.0  # total signed heading change (+360 anticlockwise circuit)

    @property
    def direction(self) -> Optional[str]:
        """'anticlockwise' / 'clockwise' for a closed circuit, else None."""
        if not self.closed:
            return None
        return "anticlockwise" if self.turning_deg > 0 else "clockwise"


# -- parsing ------------------------------------------------------------------------

def parse_fast_lane(source) -> FastLane:
    """
    Parse a fast_lane.ai (path or bytes). Raises FastLaneError with a clear message when the
    file is unreadable, not version 7, truncated or holds invalid numbers.
    """
    if isinstance(source, (bytes, bytearray, memoryview)):
        raw, name = bytes(source), "<bytes>"
    else:
        p = Path(source)
        name = str(p)
        try:
            raw = p.read_bytes()
        except OSError as exc:
            raise FastLaneError(f"{name}: cannot read file ({exc})") from exc
    if len(raw) < HEADER_BYTES:
        raise FastLaneError(f"{name}: file too short for a fast_lane.ai header ({len(raw)} bytes)")
    version, detail, lap_time, samples = struct.unpack_from("<4i", raw, 0)
    if version != FAST_LANE_VERSION:
        raise FastLaneError(f"{name}: unsupported fast_lane.ai version {version} (expected {FAST_LANE_VERSION})")
    if not 10 <= detail <= 5_000_000:
        raise FastLaneError(f"{name}: implausible record count {detail}")
    need = HEADER_BYTES + detail * RECORD_BYTES
    if len(raw) < need:
        raise FastLaneError(f"{name}: truncated ({len(raw)} bytes, {need} needed for {detail} records)")
    rec = np.frombuffer(raw, dtype=np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                                              ("s", "<f4"), ("id", "<i4")]),
                        count=detail, offset=HEADER_BYTES)
    x = rec["x"].astype(float)
    z = rec["z"].astype(float)
    s = rec["s"].astype(float)
    if not (np.isfinite(x).all() and np.isfinite(z).all() and np.isfinite(s).all()):
        raise FastLaneError(f"{name}: non-finite coordinates (corrupt file)")
    if s[-1] <= 0:
        raise FastLaneError(f"{name}: cumulative distance column is empty (all zero): variant not supported")
    if np.any(np.diff(s) < 0) or s[-1] > 200_000:
        raise FastLaneError(f"{name}: distance column is not monotonic or out of range (corrupt file)")
    step = np.hypot(np.diff(x), np.diff(z))
    if step.size and float(np.median(step)) > 20.0:
        raise FastLaneError(f"{name}: sample spacing implausible (median {np.median(step):.1f} m)")
    return FastLane(x=x, z=z, s=s, version=version, lap_time=int(lap_time), sample_count=int(samples))


# -- curvature ----------------------------------------------------------------------

def _closure_gap(lane: FastLane) -> float:
    return float(math.hypot(lane.x[-1] - lane.x[0], lane.z[-1] - lane.z[0]))


def curvature_profile(lane: FastLane, close: Optional[bool] = None, ds: float = RESAMPLE_M,
                      window_m: float = SMOOTH_WINDOW_M):
    """
    (distance_m, signed curvature 1/m, closed, line_length_m, gap_m, x, z).

    The line is resampled every `ds` m and smoothed with Savitzky-Golay (cubic, window
    `window_m`). A closed circuit is wrapped (no edge effects at the start/finish line).
    """
    from scipy.signal import savgol_filter

    gap = _closure_gap(lane)
    closed = (gap <= CLOSE_GAP_M) if close is None else bool(close)
    keep = np.concatenate([[True], np.diff(lane.s) > 1e-6])
    s, x, z = lane.s[keep], lane.x[keep], lane.z[keep]
    if closed:
        s = np.append(s, s[-1] + gap)
        x = np.append(x, x[0])
        z = np.append(z, z[0])
        length = float(s[-1])
        n = max(8, int(round(length / ds)))
        grid = np.arange(n) * (length / n)
        step = length / n
    else:
        length = float(s[-1] - s[0])
        n = max(8, int(round(length / ds)) + 1)
        grid = np.linspace(s[0], s[-1], n)
        step = length / (n - 1)
    gx = np.interp(grid, s, x)
    gz = np.interp(grid, s, z)
    win = int(round(window_m / step)) | 1
    win = max(5, min(win, (n // 2) * 2 - 1))
    mode = "wrap" if closed else "interp"
    kw = dict(polyorder=3, delta=step, mode=mode)
    dx = savgol_filter(gx, win, deriv=1, **kw)
    dz = savgol_filter(gz, win, deriv=1, **kw)
    ddx = savgol_filter(gx, win, deriv=2, **kw)
    ddz = savgol_filter(gz, win, deriv=2, **kw)
    den = np.power(dx * dx + dz * dz, 1.5)
    k = np.divide(dz * ddx - dx * ddz, den, out=np.zeros_like(den), where=den > 1e-12)
    return grid - grid[0], k, closed, length, gap, step


def _segment(dist: np.ndarray, k: np.ndarray, closed: bool, length: float, step: float) -> List[GeometricCorner]:
    from scipy.signal import find_peaks

    n = len(k)
    ak = np.abs(k)
    if closed:
        ext = np.concatenate([ak, ak, ak])
    else:
        ext = ak
    pk, _ = find_peaks(ext, height=PEAK_MIN_CURVATURE, prominence=PEAK_PROMINENCE,
                       distance=max(1, int(round(PEAK_DISTANCE_M / step))))
    if closed:
        pk = pk[(pk >= n) & (pk < 2 * n)] - n
    if pk.size == 0:
        return []

    def at(i):  # periodic or clamped access
        return ak[i % n] if closed else ak[min(max(i, 0), n - 1)]

    # valleys between consecutive apexes bound the extent of each corner
    peaks = list(map(int, pk))
    m = len(peaks)
    valleys = []
    for a in range(m):
        i0 = peaks[a]
        i1 = peaks[a + 1] if a + 1 < m else (peaks[0] + n if closed else None)
        if i1 is None:
            valleys.append(None)
            continue
        seg = np.array([at(i) for i in range(i0, i1 + 1)])
        valleys.append(i0 + int(np.argmin(seg)))

    def bound(a, side):
        if side > 0:
            v = valleys[a]
            return v if v is not None else (n - 1 if not closed else peaks[a] + n // 2)
        prev = valleys[a - 1] if a > 0 else (valleys[-1] - n if closed else None)
        return prev if prev is not None else 0

    def extent(a):
        i = peaks[a]
        sign = 1.0 if k[i] >= 0 else -1.0
        edge = max(EDGE_CURVATURE, EDGE_PEAK_SHARE * ak[i])
        lo, hi = bound(a, -1), bound(a, +1)
        j = i
        while j > lo and (k[j % n] * sign) >= edge:
            j -= 1
        s0 = j
        j = i
        while j < hi and (k[j % n] * sign) >= edge:
            j += 1
        return s0, j

    sub = []
    for a in range(m):
        i = peaks[a]
        s0, s1 = extent(a)
        sub.append({"i": i, "s0": s0, "s1": s1, "sign": 1.0 if k[i] >= 0 else -1.0,
                    "radius": 1.0 / float(ak[i]), "d": float(dist[i])})

    # group into complexes (chain: each apex against the previous one)
    groups: list = [[sub[0]]]
    for cur in sub[1:]:
        prev = groups[-1][-1]
        gap_m = (cur["i"] - prev["i"]) * step
        if gap_m < COMPLEX_GAP_M or (cur["sign"] != prev["sign"] and gap_m < CHICANE_GAP_M):
            groups[-1].append(cur)
        else:
            groups.append([cur])
    if closed and len(groups) > 1:   # the last and first groups may touch across the start line
        first, last = groups[0][0], groups[-1][-1]
        gap_m = (first["i"] + n - last["i"]) * step
        if gap_m < COMPLEX_GAP_M or (first["sign"] != last["sign"] and gap_m < CHICANE_GAP_M):
            merged = groups.pop()
            for g in groups[0]:
                g["_wrapped"] = True
            groups[0] = merged + groups[0]

    corners: List[GeometricCorner] = []
    for g in groups:
        idx = [e["i"] + (n if e.get("_wrapped") else 0) for e in g]
        tight = min(g, key=lambda e: e["radius"])
        t_i = tight["i"]
        s0 = g[0]["s0"] + (n if g[0].get("_wrapped") else 0)
        s1 = g[-1]["s1"] + (n if g[-1].get("_wrapped") else 0)
        kind = "single"
        if len(g) > 1:
            kind = "chicane" if len({e["sign"] for e in g}) > 1 else "compound"
        subs = [SubApex(fraction=(e["i"] % n) * step / length if closed else e["d"] / length,
                        distance_m=float(e["d"]), radius_m=float(e["radius"]),
                        direction="left" if e["sign"] > 0 else "right") for e in g]
        sev = ("slow" if tight["radius"] < SLOW_RADIUS_M
               else "medium" if tight["radius"] < MEDIUM_RADIUS_M else "fast")

        def frac(i):
            return ((i % n) * step / length) if closed else float(dist[min(max(i, 0), n - 1)]) / length
        corners.append(GeometricCorner(
            index=0, start_fraction=frac(s0), apex_fraction=frac(t_i), end_fraction=frac(s1),
            apex_m=float(dist[t_i % n]), start_m=float(dist[s0 % n]), end_m=float(dist[s1 % n]),
            min_radius_m=float(tight["radius"]), direction="left" if tight["sign"] > 0 else "right",
            severity=sev, kind=kind, sub_apexes=subs))
    corners.sort(key=lambda c: c.apex_fraction)
    for n_, c in enumerate(corners, 1):
        c.index = n_
    return corners


def analyze_lane(lane: FastLane, close: Optional[bool] = None) -> Geometry:
    """Curvature profile and geometric corners of a parsed racing line."""
    dist, k, closed, length, gap, step = curvature_profile(lane, close=close)
    corners = _segment(dist, k, closed, length, step)
    turning = float(np.degrees(np.sum(k) * step))
    return Geometry(length_line_m=length, closed=closed, ds=step, distance_m=dist, curvature=k,
                    corners=corners, closure_gap_m=gap, turning_deg=turning)


def min_radius_between(geo: Geometry, f0: float, f1: float) -> float:
    """Smallest radius (m) of the line between two lap fractions (wraps when f0 > f1)."""
    n = len(geo.curvature)
    i0, i1 = int(round(f0 * n)) % n, int(round(f1 * n)) % n
    idx = np.arange(i0, i1 + 1) if i0 <= i1 else np.concatenate([np.arange(i0, n), np.arange(0, i1 + 1)])
    kmax = float(np.max(np.abs(geo.curvature[idx])))
    return math.inf if kmax <= 0 else 1.0 / kmax


# -- game folder (read-only) ----------------------------------------------------------

_STEAM_ROOTS = (
    r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam", r"D:\SteamLibrary", r"D:\Steam",
    r"E:\SteamLibrary", "~/.steam/steam", "~/.local/share/Steam",
    "~/Library/Application Support/Steam",
)
_GAME_SUBPATH = Path("steamapps") / "common" / "assettocorsa"


def _tracks_from(path: Path) -> Optional[Path]:
    """Accept the install folder, its `content` folder or the `tracks` folder itself."""
    for cand in (path, path / "tracks", path / "content" / "tracks"):
        if cand.name.lower() == "tracks" and cand.is_dir():
            return cand
        if cand.is_dir() and (cand / "tracks").is_dir() and cand.name.lower() == "content":
            return cand / "tracks"
    return None


def _library_paths(root: Path) -> List[Path]:
    vdf = root / "steamapps" / "libraryfolders.vdf"
    out: List[Path] = []
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for m in re.finditer(r'"path"\s+"([^"]+)"', text):
        out.append(Path(m.group(1).replace("\\\\", "\\")))
    return out


def find_ac_tracks_dir() -> Optional[Path]:
    """
    Folder ``.../assettocorsa/content/tracks`` of the installed game, or None.
    Order: AC_CONTENT_DIR, AC_INSTALL_DIR, then Steam libraries (libraryfolders.vdf of the usual
    Steam folders) and the usual Steam paths. Never creates or writes anything.
    """
    for var in ("AC_CONTENT_DIR", "AC_INSTALL_DIR"):
        val = os.environ.get(var)
        if val:
            found = _tracks_from(Path(os.path.expanduser(val)))
            if found:
                return found
    libs: List[Path] = []
    for r in _STEAM_ROOTS:
        root = Path(os.path.expanduser(r))
        if root.is_dir():
            libs.append(root)
            libs.extend(_library_paths(root))
    seen = set()
    for lib in libs:
        key = str(lib).lower()
        if key in seen:
            continue
        seen.add(key)
        found = _tracks_from(lib / _GAME_SUBPATH / "content")
        if found:
            return found
    return None


def list_layouts(track_id: str, tracks_dir: Optional[Path] = None) -> List[str]:
    """Layout names with a fast_lane.ai ('' = the default layout directly under the track)."""
    tracks_dir = Path(tracks_dir) if tracks_dir else find_ac_tracks_dir()
    if tracks_dir is None:
        return []
    base = tracks_dir / track_id
    out: List[str] = []
    if (base / "ai" / "fast_lane.ai").is_file():
        out.append("")
    if base.is_dir():
        for d in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            if d.is_dir() and d.name.lower() != "ai" and (d / "ai" / "fast_lane.ai").is_file():
                out.append(d.name)
    return out


def fast_lane_path(track_id: str, layout: str = "", tracks_dir: Optional[Path] = None) -> Path:
    tracks_dir = Path(tracks_dir) if tracks_dir else find_ac_tracks_dir()
    if tracks_dir is None:
        raise FastLaneError("Assetto Corsa content folder not found (set AC_CONTENT_DIR or AC_INSTALL_DIR)")
    base = tracks_dir / track_id
    p = (base / layout / "ai" / "fast_lane.ai") if layout else (base / "ai" / "fast_lane.ai")
    if not p.is_file():
        raise FastLaneError(f"no fast_lane.ai for track {track_id!r} layout {layout or '(default)'!r}: {p}")
    return p


# -- official length ------------------------------------------------------------------

_LENGTH_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)*)\s*(km|kilometers?|kilometres?|m|meters?|metres?)?\s*\.?\s*$", re.I)


def parse_length_m(value) -> Optional[float]:
    """
    Lap length in metres from the free-form `length` of ui_track.json.

    Seen: '4909', '5807m', '3.602' (km), '13.626km', '3.340m' (this one is km written with an
    'm'). Rule: an explicit km unit multiplies by 1000; otherwise a number below 100 is read as
    km (no circuit is shorter than 100 m), else metres. None when it cannot be parsed.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v, unit = float(value), ""
    else:
        m = _LENGTH_RE.match(str(value))
        if not m:
            return None
        num, unit = m.group(1), (m.group(2) or "").lower()
        if num.count(",") == 1 and "." not in num:
            num = num.replace(",", ".")
        else:
            num = num.replace(",", "")
        try:
            v = float(num)
        except ValueError:
            return None
    if not math.isfinite(v) or v <= 0:
        return None
    if unit.startswith("k"):
        v *= 1000.0
    elif v < 100.0:
        v *= 1000.0
    return v


def read_ui_track(track_id: str, layout: str = "", tracks_dir: Optional[Path] = None) -> dict:
    """Parsed ui_track.json of a track/layout ({} when missing). Tolerant: BOM, raw newlines, bad JSON."""
    tracks_dir = Path(tracks_dir) if tracks_dir else find_ac_tracks_dir()
    if tracks_dir is None:
        return {}
    base = tracks_dir / track_id / "ui"
    p = (base / layout / "ui_track.json") if layout else (base / "ui_track.json")
    try:
        text = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return {}
    try:
        data = json.loads(text, strict=False)
        return data if isinstance(data, dict) else {}
    except ValueError:
        out = {}
        for key in ("name", "length", "country", "run"):
            m = re.search(r'"%s"\s*:\s*"?([^",}\n\r]*)' % key, text)
            if m:
                out[key] = m.group(1).strip()
        return out


def official_length_m(track_id: str, layout: str = "", tracks_dir: Optional[Path] = None) -> Optional[float]:
    return parse_length_m(read_ui_track(track_id, layout, tracks_dir).get("length"))


# -- export ---------------------------------------------------------------------------

TRACK_GEOMETRY_DIR = Path(__file__).resolve().parents[1] / "data" / "track_geometry"


def build_export(circuit_id: str, track_id: str, layout: str, geo: Geometry, lane: FastLane,
                 official_m: Optional[float], extracted: Optional[str] = None) -> dict:
    """The small, versioned JSON written to src/data/track_geometry/<circuit_id>.json."""
    return {
        "circuit_id": circuit_id,
        "source": {"game": "Assetto Corsa", "file": "ai/fast_lane.ai", "track_id": track_id,
                   "layout": layout or None, "format_version": lane.version},
        "extracted": extracted or date.today().isoformat(),
        "length_official_m": round(official_m, 1) if official_m else None,
        "length_line_m": round(geo.length_line_m, 1),
        "closed": geo.closed,
        "direction": geo.direction,
        "method": {"resample_m": RESAMPLE_M, "smooth_window_m": SMOOTH_WINDOW_M,
                   "min_curvature": PEAK_MIN_CURVATURE, "complex_gap_m": COMPLEX_GAP_M,
                   "chicane_gap_m": CHICANE_GAP_M,
                   "severity_radius_m": [SLOW_RADIUS_M, MEDIUM_RADIUS_M, FAST_RADIUS_M]},
        "corners": [c.to_dict() for c in geo.corners],
    }


def analyze_track(track_id: str, layout: str = "", tracks_dir: Optional[Path] = None):
    """(Geometry, FastLane, official_length_m) of an installed track/layout."""
    p = fast_lane_path(track_id, layout, tracks_dir)
    lane = parse_fast_lane(p)
    return analyze_lane(lane), lane, official_length_m(track_id, layout, tracks_dir)


def compare_with_table(circuit: dict, corners: Iterable[dict], length_m: Optional[float] = None) -> dict:
    """
    Contrast a circuits.json entry with geometric corners (dicts as exported).

    For each tabulated corner: distance (m, using fraction x length) to the nearest geometric
    corner or sub-apex. Also lists geometric corners without a tabulated corner and tabulated
    corners with no geometric peak within 250 m.
    """
    length = float(length_m or circuit.get("length_m") or 0.0)
    corners = list(corners)
    table = circuit.get("corners") or []
    rows = []
    near_used = set()
    for t in table:
        tf = float(t["apex_fraction"])
        best = None
        for c in corners:
            fr = [c["apex_fraction"]] + [a["fraction"] for a in c.get("sub_apexes", [])]
            for f in fr:
                delta = ((tf - f + 0.5) % 1.0 - 0.5) * length     # signed: + = table after geometry
                if best is None or abs(delta) < abs(best[0]):
                    best = (delta, c)
        row = {"name": t["name"], "fraction": tf, "kind": t.get("kind"), "nearest_m": None, "delta_m": None, "geo_index": None,
               "min_radius_m": None, "severity": None, "inside_extent": None}
        if best:
            c = best[1]
            a0, a1 = c["start_fraction"], c["end_fraction"]
            inside = (a0 <= tf <= a1) if a0 <= a1 else (tf >= a0 or tf <= a1)
            row.update(nearest_m=round(abs(best[0]), 1), delta_m=round(best[0], 1), geo_index=c["index"],
                       min_radius_m=c["min_radius_m"], severity=c["severity"], inside_extent=bool(inside))
            if abs(best[0]) <= 250:
                near_used.add(c["index"])
        rows.append(row)
    untabulated = [c for c in corners if c["index"] not in near_used]
    # a tabulated flat_out corner (e.g. Variante Bassa) need not have a geometric peak: its radius is above the export cut
    unmatched = [r for r in rows if (r["nearest_m"] is None or r["nearest_m"] > 250) and r["kind"] != "flat_out"]
    return {"rows": rows, "geometric_without_table": untabulated, "table_without_peak": unmatched}
