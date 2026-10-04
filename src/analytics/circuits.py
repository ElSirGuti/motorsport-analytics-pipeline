"""
Known circuits and corner names.

Recognises the circuit from the telemetry "Venue" metadata (Assetto Corsa / MoTeC
track id, or an iRacing track display name), confirms it against the measured lap
length and assigns official corner names to the apexes detected in a lap.

Honesty rules:
  * the database (src/data/circuits.json) only holds corner tables whose order and
    positions were verified; every other circuit is recognition-only;
  * a venue whose measured length does not fit the circuit (default +-4 %) is flagged
    low confidence and NO corner names are assigned (it is probably another layout);
  * an apex without a tabulated corner within tolerance keeps its plain number.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "circuits.json"
GEOMETRY_DIR = Path(__file__).resolve().parents[1] / "data" / "track_geometry"
GEOMETRY_WARN_M = 250.0   # a tabulated corner farther than this from any geometric corner is suspicious

LENGTH_TOLERANCE = 0.04        # relative tolerance between measured and nominal lap length
APEX_TOLERANCE_FRACTION = 0.025  # of the lap length ...
APEX_TOLERANCE_MIN_M = 120.0     # ... but never below this ...
APEX_TOLERANCE_MAX_M = 180.0     # ... nor above this (long circuits)

CONFIDENCE_LEVELS = ("high", "medium")
_PREFIX_RE = re.compile(r"^(ks|fn|acu|zw|sx|rt|ac)_")


# ── Database ───────────────────────────────────────────────────────────────────

def normalize_venue(value) -> str:
    """Canonical comparison key: ascii-folded, lower-case, punctuation collapsed to '_'."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return s


def get_track_geometry(circuit_id: Optional[str]) -> Optional[dict]:
    """
    Geometric corners of a circuit (src/data/track_geometry/<id>.json, derived from the Assetto
    Corsa racing line by scripts/ac_track_reference.py) or None when there is no file.

    Positions are fractions of the lap, independent of the car. The result is cached; do not
    mutate it.
    """
    if not circuit_id or not isinstance(circuit_id, str) or not re.fullmatch(r"[a-z0-9_]+", circuit_id):
        return None
    return _load_geometry(circuit_id)


@lru_cache(maxsize=64)
def _load_geometry(circuit_id: str) -> Optional[dict]:
    path = GEOMETRY_DIR / f"{circuit_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("circuits: cannot read %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) and isinstance(data.get("corners"), list) else None


def _warn_geometry(circuit: dict) -> None:
    """Soft check (log only, never an error): tabulated corners far from every geometric corner."""
    cid = circuit.get("id")
    corners = circuit.get("corners")
    if not corners or not isinstance(cid, str):
        return
    geo = get_track_geometry(cid)
    if not geo:
        return
    try:
        length = float(circuit["length_m"])
        fracs = []
        for g in geo["corners"]:
            fracs.append(float(g["apex_fraction"]))
            fracs += [float(a["fraction"]) for a in g.get("sub_apexes") or []]
        if not fracs:
            return
        for k in corners:
            f = float(k["apex_fraction"])
            d = min(min(abs(f - x), 1.0 - abs(f - x)) for x in fracs) * length
            if d > GEOMETRY_WARN_M:
                logger.warning("circuits: %s corner %r is %.0f m from the nearest geometric corner",
                               cid, k.get("name"), d)
    except (KeyError, TypeError, ValueError):
        return


def validate_database(data) -> list:
    """Return a list of human-readable problems (empty = valid)."""
    errors: list = []
    if not isinstance(data, dict) or not isinstance(data.get("circuits"), list):
        return ["root must be an object with a 'circuits' list"]
    seen_ids: set = set()
    seen_aliases: dict = {}
    for n, c in enumerate(data["circuits"]):
        cid = c.get("id") if isinstance(c, dict) else None
        tag = f"circuit[{n}]({cid})"
        if not isinstance(c, dict):
            errors.append(f"{tag}: not an object")
            continue
        if not isinstance(cid, str) or not re.fullmatch(r"[a-z0-9_]+", cid or ""):
            errors.append(f"{tag}: invalid id")
        elif cid in seen_ids:
            errors.append(f"{tag}: duplicated id")
        seen_ids.add(cid)
        if not isinstance(c.get("name"), str) or not c["name"].strip():
            errors.append(f"{tag}: missing name")
        if "short_name" in c and not (isinstance(c["short_name"], str) and c["short_name"].strip()):
            errors.append(f"{tag}: short_name must be a non-empty string")
        if not (isinstance(c.get("country"), str) and re.fullmatch(r"[A-Z]{2}", c["country"])):
            errors.append(f"{tag}: country must be an ISO 3166-1 alpha-2 code")
        ln = c.get("length_m")
        if not isinstance(ln, (int, float)) or isinstance(ln, bool) or not 500 <= ln <= 30000:
            errors.append(f"{tag}: length_m out of range")
        if c.get("confidence") not in CONFIDENCE_LEVELS:
            errors.append(f"{tag}: confidence must be one of {CONFIDENCE_LEVELS}")
        if not isinstance(c.get("source"), str) or not c["source"].strip():
            errors.append(f"{tag}: missing source")
        if not isinstance(c.get("notes"), str):
            errors.append(f"{tag}: missing notes")
        aliases = c.get("aliases")
        if not isinstance(aliases, list) or not aliases or not all(isinstance(a, str) and a.strip() for a in aliases):
            errors.append(f"{tag}: aliases must be a non-empty list of strings")
        else:
            for a in aliases:
                key = normalize_venue(a)
                if not key:
                    errors.append(f"{tag}: empty alias {a!r}")
                elif key in seen_aliases and seen_aliases[key] != cid:
                    errors.append(f"{tag}: alias {a!r} already used by {seen_aliases[key]}")
                seen_aliases.setdefault(key, cid)
        if "apex_tolerance_m" in c:
            at = c["apex_tolerance_m"]
            if not isinstance(at, (int, float)) or isinstance(at, bool) or not 30 <= at <= APEX_TOLERANCE_MAX_M:
                errors.append(f"{tag}: apex_tolerance_m must be between 30 and {APEX_TOLERANCE_MAX_M:g}")
        corners = c.get("corners")
        if not isinstance(corners, list):
            errors.append(f"{tag}: corners must be a list")
            continue
        names: set = set()
        last_f, last_o = -1.0, 0
        for m, k in enumerate(corners):
            ktag = f"{tag}.corners[{m}]"
            if not isinstance(k, dict):
                errors.append(f"{ktag}: not an object")
                continue
            nm = k.get("name")
            if not isinstance(nm, str) or not nm.strip():
                errors.append(f"{ktag}: missing name")
            elif nm.casefold() in names:
                errors.append(f"{ktag}: duplicated name {nm!r}")
            else:
                names.add(nm.casefold())
            f = k.get("apex_fraction")
            if not isinstance(f, (int, float)) or isinstance(f, bool) or not 0.0 <= f < 1.0:
                errors.append(f"{ktag}: apex_fraction must be in [0, 1)")
            else:
                if f <= last_f:
                    errors.append(f"{ktag}: corners must be strictly ordered by apex_fraction")
                last_f = float(f)
            o = k.get("order")
            if not isinstance(o, int) or isinstance(o, bool) or o <= last_o:
                errors.append(f"{ktag}: order must be a strictly increasing integer")
            else:
                last_o = o
        _warn_geometry(c)
    return errors


@lru_cache(maxsize=1)
def _load() -> tuple:
    """(circuits_by_id, alias_index) — invalid entries are dropped with a warning."""
    try:
        data = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("circuits: cannot read %s: %s", DB_PATH, exc)
        return {}, {}
    problems = validate_database(data)
    if problems:
        logger.warning("circuits: database has %d problem(s), e.g. %s", len(problems), problems[0])
    by_id: dict = {}
    index: dict = {}
    for c in data.get("circuits", []) if isinstance(data, dict) else []:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        by_id[c["id"]] = c
        for a in c.get("aliases") or []:
            index.setdefault(normalize_venue(a), c["id"])
        index.setdefault(normalize_venue(c["id"]), c["id"])
    return by_id, index


def load_circuits() -> dict:
    """All circuits keyed by canonical id (cached)."""
    return _load()[0]


def get_circuit(circuit_id: Optional[str]) -> Optional[dict]:
    return load_circuits().get(circuit_id) if circuit_id else None


def find_circuit(venue) -> Optional[dict]:
    """Circuit entry for a venue string, via alias normalisation (None if unknown)."""
    key = normalize_venue(venue)
    if not key:
        return None
    by_id, index = _load()
    cid = index.get(key)
    if cid is None:
        stripped = _PREFIX_RE.sub("", key)
        if stripped != key:
            cid = index.get(stripped)
    return by_id.get(cid) if cid else None


# ── Recognition ────────────────────────────────────────────────────────────────

def _empty_circuit(measured_length_m: Optional[float] = None) -> dict:
    return {
        "id": None, "name": None, "short_name": None, "country": None, "length_m": None,
        "recognized": False, "matched": False, "confidence": None,
        "named_corners": 0,
        "measured_length_m": round(float(measured_length_m), 1) if measured_length_m else None,
        "length_deviation_pct": None,
    }


def recognize(venue, measured_length_m: Optional[float] = None,
              tolerance: float = LENGTH_TOLERANCE) -> dict:
    """
    API circuit object for a venue + measured lap length.

    matched    True when the venue is known AND the measured length fits (or could not be
               measured): corner names may be used.
    confidence 'high' | 'medium' from the database; 'low' when the length does not fit
               (known venue, probably another layout); None for unknown venues.
    A known venue whose length cannot be measured is matched but capped at 'medium'.
    """
    entry = find_circuit(venue)
    out = _empty_circuit(measured_length_m)
    if entry is None:
        return out
    nominal = float(entry["length_m"])
    out.update({
        "id": entry["id"], "name": entry["name"],
        "short_name": entry.get("short_name") or entry["name"], "country": entry.get("country"),
        "length_m": nominal, "recognized": True,
        "named_corners": len(entry.get("corners") or []),
    })
    try:
        measured = float(measured_length_m) if measured_length_m is not None else None
    except (TypeError, ValueError):
        measured = None
    if measured is None or not (measured > 0):
        out["matched"] = True
        out["confidence"] = "medium" if entry["confidence"] == "high" else entry["confidence"]
        return out
    dev = measured / nominal - 1.0
    out["length_deviation_pct"] = round(dev * 100.0, 2)
    if abs(dev) <= tolerance:
        out["matched"] = True
        out["confidence"] = entry["confidence"]
    else:
        out["matched"] = False
        out["confidence"] = "low"
    return out


# ── Corner naming ──────────────────────────────────────────────────────────────

def apex_tolerance_m(lap_length_m: float, circuit: Optional[dict] = None) -> float:
    """Matching tolerance (m); a circuit may tighten it with `apex_tolerance_m` (long circuits with close corners)."""
    override = circuit.get("apex_tolerance_m") if isinstance(circuit, dict) else None
    if isinstance(override, (int, float)) and not isinstance(override, bool) and 30 <= override <= APEX_TOLERANCE_MAX_M:
        return float(override)
    return min(APEX_TOLERANCE_MAX_M, max(APEX_TOLERANCE_MIN_M, APEX_TOLERANCE_FRACTION * lap_length_m))


def assign_names(circuit: Optional[dict], apexes: Iterable, lap_length_m: Optional[float] = None) -> dict:
    """
    Assign corner names to detected apexes.

    Args:
        circuit:       database entry (find_circuit / get_circuit) or None.
        apexes:        iterable of (key, distance_m) — key is anything hashable that
                       identifies the apex to the caller (corner number, index...).
        lap_length_m:  measured lap length; defaults to the nominal length.

    Returns {key: {"name", "order", "delta_m"}} only for apexes that were named.
    Matching is one-to-one (a name is never used twice) and order preserving: it maximises
    the number of named apexes and then minimises the total distance error.
    """
    if not circuit:
        return {}
    corners = sorted(circuit.get("corners") or [], key=lambda k: k["apex_fraction"])
    pts = []
    for key, d in apexes:
        try:
            d = float(d)
        except (TypeError, ValueError):
            continue
        if d == d and d >= 0:
            pts.append((d, key))
    pts.sort(key=lambda p: p[0])
    if not corners or not pts:
        return {}
    length = float(lap_length_m) if lap_length_m and lap_length_m > 0 else float(circuit["length_m"])
    tol = apex_tolerance_m(length, circuit)

    n, m = len(pts), len(corners)
    cost = [[None] * m for _ in range(n)]
    for i, (d, _k) in enumerate(pts):
        for j, k in enumerate(corners):
            gap = abs(d - k["apex_fraction"] * length)
            if gap <= tol:
                cost[i][j] = gap

    # dp[i][j] = best (matches, -total_cost) using apexes[:i] and corners[:j]
    NEG = (0, 0.0)
    dp = [[NEG] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best, how = dp[i - 1][j], "up"
            if dp[i][j - 1] > best:
                best, how = dp[i][j - 1], "left"
            c = cost[i - 1][j - 1]
            if c is not None:
                cand = (dp[i - 1][j - 1][0] + 1, dp[i - 1][j - 1][1] - c)
                if cand > best:
                    best, how = cand, "diag"
            dp[i][j], back[i][j] = best, how
    out: dict = {}
    i, j = n, m
    while i > 0 and j > 0:
        how = back[i][j]
        if how == "diag":
            k = corners[j - 1]
            out[pts[i - 1][1]] = {"name": k["name"], "order": k.get("order"), "delta_m": round(cost[i - 1][j - 1], 1)}
            i, j = i - 1, j - 1
        elif how == "up":
            i -= 1
        else:
            j -= 1
    return out


def annotate_corners(circuit_info: Optional[dict], corners: list, distance_key: str,
                     lap_length_m: Optional[float] = None) -> list:
    """
    Add `corner_name` (None when unnamed) to every corner dict, in place.

    `distance_key` is the field holding the apex distance in metres. Names are only
    assigned when circuit_info['matched'] is true (venue known and length confirmed).
    Returns `corners` for chaining.
    """
    for c in corners or []:
        if isinstance(c, dict):
            c.setdefault("corner_name", None)
    if not corners or not circuit_info or not circuit_info.get("matched"):
        return corners
    entry = get_circuit(circuit_info.get("id"))
    if not entry:
        return corners
    pts = [(idx, c.get(distance_key)) for idx, c in enumerate(corners)
           if isinstance(c, dict) and c.get(distance_key) is not None]
    names = assign_names(entry, pts, lap_length_m or circuit_info.get("measured_length_m"))
    for idx, info in names.items():
        corners[idx]["corner_name"] = info["name"]
    return corners


def name_for_distance(circuit_info: Optional[dict], distance_m, lap_length_m: Optional[float] = None) -> Optional[str]:
    """Name of the tabulated corner closest to a distance (None if outside tolerance)."""
    if distance_m is None or not circuit_info or not circuit_info.get("matched"):
        return None
    entry = get_circuit(circuit_info.get("id"))
    if not entry:
        return None
    res = assign_names(entry, [(0, distance_m)], lap_length_m or circuit_info.get("measured_length_m"))
    return res[0]["name"] if 0 in res else None


def median_lap_length(lengths: Iterable) -> Optional[float]:
    vals = sorted(float(v) for v in lengths if v is not None and v == v and float(v) > 0)
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


# ── Result enrichment (additive: only adds `circuit`, `corner_name` and friends) ──

def _numeric_distances(rows: list, key: str) -> list:
    return [(i, r.get(key)) for i, r in enumerate(rows) if isinstance(r, dict) and r.get(key) is not None]


def enrich_compare(result: dict, venue, lap_length_m: Optional[float] = None) -> dict:
    """
    Pairwise comparison payloads (compare-laps, compare-session-laps, telemetry/*).

    Adds result['circuit'], `corner_name` on every corner and on every detected apex
    (plus `corner_number`), and from/to corner numbers + names on the sector rows.
    """
    info = recognize(venue, lap_length_m)
    result["circuit"] = info
    entry = get_circuit(info["id"]) if info["matched"] else None
    length = lap_length_m or info.get("length_m")

    apexes = result.get("apexes")
    apexes = apexes if isinstance(apexes, list) else []
    apex_names: dict = {}
    if entry and apexes:
        apex_names = assign_names(entry, _numeric_distances(apexes, "Distance"), length)
    for i, a in enumerate(apexes):
        if isinstance(a, dict):
            a["corner_number"] = i + 1
            a["corner_name"] = apex_names[i]["name"] if i in apex_names else None

    corners = result.get("corners")
    if isinstance(corners, list) and corners:
        dkey = next((k for k in ("apex_distance", "ref_apex_distance")
                     if any(isinstance(c, dict) and c.get(k) is not None for c in corners)), None)
        for c in corners:
            if isinstance(c, dict):
                c.setdefault("corner_name", None)
        if dkey and entry:
            if apexes:
                # reuse the apex naming so corners, apexes and sectors always agree
                for c in corners:
                    if not isinstance(c, dict) or c.get(dkey) is None:
                        continue
                    for i, a in enumerate(apexes):
                        if isinstance(a, dict) and a.get("Distance") is not None \
                                and abs(float(a["Distance"]) - float(c[dkey])) <= 1.0:
                            c["corner_name"] = apex_names[i]["name"] if i in apex_names else None
                            break
                    else:
                        c["corner_name"] = name_for_distance(info, c[dkey], length)
            else:
                annotate_corners(info, corners, dkey, length)

    sectors = result.get("sectores")
    if apexes and isinstance(sectors, list):
        n = len(apexes)
        for s in sectors:
            if not isinstance(s, dict) or not isinstance(s.get("sector"), int):
                continue
            k = s["sector"]            # sector k runs from apex k-1 to apex k (1-based apexes)
            frm, to = k - 1, k
            s["from_corner_number"] = frm if 1 <= frm <= n else None
            s["to_corner_number"] = to if 1 <= to <= n else None
            s["from_corner_name"] = apex_names[frm - 1]["name"] if (frm - 1) in apex_names else None
            s["to_corner_name"] = apex_names[to - 1]["name"] if (to - 1) in apex_names else None
    return result


def enrich_session(result: dict, venue) -> dict:
    """analyze-session payload: circuit from the median length of the racing laps."""
    laps = result.get("laps") or []
    lengths = [l.get("lap_distance") for l in laps
               if isinstance(l, dict) and not l.get("is_pit_lap") and l.get("lap_distance")]
    result["circuit"] = recognize(venue, median_lap_length(lengths))
    return result


def enrich_stint(result: dict, venue, lap_length_m: Optional[float]) -> dict:
    """stint payload: names the session corners and the racing-line corners."""
    info = recognize(venue, lap_length_m)
    result["circuit"] = info
    cs = result.get("curvas_sesion")
    by_number: dict = {}
    if isinstance(cs, dict) and isinstance(cs.get("corners"), list):
        annotate_corners(info, cs["corners"], "apex_distance", lap_length_m)
        by_number = {c.get("corner_number"): c.get("corner_name") for c in cs["corners"]
                     if isinstance(c, dict) and c.get("corner_name")}
        # re-title descriptions: "Corner 4 (Tamburello): late braking ..."
        from src.analytics.session_corner_analysis import describe_with_name
        for c in cs["corners"]:
            if isinstance(c, dict) and c.get("corner_name") and c.get("description_parts") is not None                     and c.get("corner_number") is not None:
                c["description"] = describe_with_name(
                    c["corner_number"], c["description_parts"], c["corner_name"])
    rl = result.get("racing_line_rl")
    if isinstance(rl, dict) and isinstance(rl.get("corners"), list):
        for c in rl["corners"]:
            if isinstance(c, dict):
                c["corner_name"] = by_number.get(c.get("corner_number"))
    return result


def enrich_optimal_lap(result: dict, venue) -> dict:
    """optimal-lap payload: names corners and loss zones."""
    if not isinstance(result, dict) or not result.get("available"):
        return result
    L = result.get("track_length_m")
    info = recognize(venue, L)
    result["circuit"] = info
    corners = result.get("corners") or []
    annotate_corners(info, corners, "apex_distance", L)
    by_number = {c.get("corner_number"): c.get("corner_name") for c in corners
                 if isinstance(c, dict) and c.get("corner_name")}
    for z in result.get("top_zones") or []:
        if isinstance(z, dict):
            z["corner_name"] = by_number.get(z.get("corner_number"))
    return result


def lap_length_of(df) -> Optional[float]:
    """Measured length (m) of a single-lap frame from its Distance channel."""
    try:
        d = df["Distance"].dropna()
        return float(d.max() - d.min()) if len(d) > 1 else None
    except Exception:
        return None
