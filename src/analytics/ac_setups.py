"""
Assetto Corsa setup integration.

Finds the setups saved by the game (``<Documents>/Assetto Corsa/setups/<car>/<track>/*.ini``),
parses them, and links their parameters with the Setup Advisor recommendations
("current -> suggested").

Security model
--------------
* Car / track names come from the client (CSV header) and are never joined blindly:
  they are validated against a strict character set and then *matched against the
  real directory listing*; the resolved path must stay inside the setups folder.
* Only ``.ini`` / ``.sp`` files, regular files, <= MAX_SETUP_BYTES, are ever read.

Units
-----
The game stores "clicks" in the .ini. Real units are only claimed where they are
certain (tyre pressure in psi, front brake bias and brake power in %, fuel in litres).
Everything else is shown raw. Min/max/step are only attached when the car's
unpacked ``data/setup.ini`` is available (most cars ship it inside an encrypted
``data.acd``, which is deliberately NOT opened).
"""

from __future__ import annotations

import os
import re
import sys
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.i18n import _l

logger = logging.getLogger(__name__)

MAX_SETUP_BYTES = 256 * 1024
MAX_SECTIONS = 2000
ALLOWED_EXT = (".ini", ".sp")
_NAME_RE = re.compile(r"^[\w .\-+()]{1,128}$", re.UNICODE)
_WHEELS = ("LF", "RF", "LR", "RR")  # display order FL FR RL RR
_POS_TO_WHEEL = {"FL": "LF", "FR": "RF", "RL": "LR", "RR": "RR"}
_WHEEL_TO_POS = {v: k for k, v in _POS_TO_WHEEL.items()}


class SetupError(ValueError):
    """Invalid input (bad names, oversized or unreadable file)."""


# ── Locating the AC setups folder ─────────────────────────────────────────────

def _windows_known_documents() -> Optional[Path]:
    """Documents folder via SHGetKnownFolderPath (respects OneDrive / redirections)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        guid = GUID.from_buffer_copy(
            uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7").bytes_le)  # FOLDERID_Documents
        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p)]
        shell32.SHGetKnownFolderPath.restype = ctypes.HRESULT
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        buf = ctypes.c_wchar_p()
        shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(buf))
        try:
            return Path(buf.value) if buf.value else None
        finally:
            ole32.CoTaskMemFree(buf)
    except Exception as exc:  # pragma: no cover - platform specific
        logger.debug("SHGetKnownFolderPath failed: %s", exc)
        return None


def documents_candidates() -> list[Path]:
    """Possible 'Documents' folders, most reliable first (no duplicates)."""
    out: list[Path] = []

    def add(p: Optional[Path]):
        if p and p not in out:
            out.append(p)

    add(_windows_known_documents())
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        add(Path(userprofile) / "Documents")
    try:
        add(Path.home() / "Documents")
    except RuntimeError:  # pragma: no cover
        pass
    return out


def resolve_setups_dir() -> tuple[Optional[Path], bool]:
    """
    Returns (path, exists).
    ``AC_SETUPS_DIR`` is an explicit override. Otherwise the first existing
    ``<Documents>/Assetto Corsa/setups`` wins; if none exists the first expected
    location is returned with exists=False (None when there is no candidate at all).
    """
    override = os.environ.get("AC_SETUPS_DIR", "").strip()
    if override:
        p = Path(override).expanduser()
        return p, p.is_dir()
    first: Optional[Path] = None
    for docs in documents_candidates():
        p = docs / "Assetto Corsa" / "setups"
        first = first or p
        try:
            if p.is_dir():
                return p, True
        except OSError:
            continue
    return first, False


# ── Safe path helpers ─────────────────────────────────────────────────────────

def _check_name(name: str, what: str = "name") -> str:
    if not isinstance(name, str) or not name.strip():
        raise SetupError(f"empty {what}")
    name = name.strip()
    if ".." in name or not _NAME_RE.match(name):
        raise SetupError(f"invalid {what}")
    return name


def _inside(base: Path, p: Path) -> bool:
    try:
        p.resolve().relative_to(base.resolve())
        return True
    except (ValueError, OSError):
        return False


def _child_dir(parent: Path, name: str) -> Optional[Path]:
    """Existing sub-directory of ``parent`` named ``name`` (case-insensitive), or None."""
    name = _check_name(name)
    direct = parent / name
    try:
        if direct.is_dir() and _inside(parent, direct):
            return direct
        for entry in os.listdir(parent):
            if entry.lower() == name.lower():
                cand = parent / entry
                if cand.is_dir() and _inside(parent, cand):
                    return cand
    except OSError:
        return None
    return None


def _check_filename(fname: str) -> str:
    fname = _check_name(fname, "file name")
    if fname != os.path.basename(fname) or not fname.lower().endswith(ALLOWED_EXT):
        raise SetupError("invalid file name")
    return fname


def _read_limited(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SetupError("cannot read file") from exc
    if size > MAX_SETUP_BYTES:
        raise SetupError("file too large")
    with open(path, "rb") as f:
        return decode_bytes(f.read(MAX_SETUP_BYTES + 1))


def decode_bytes(raw: bytes) -> str:
    if len(raw) > MAX_SETUP_BYTES:
        raise SetupError("file too large")
    if b"\x00" in raw:
        raise SetupError("not a text file")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SetupError("cannot decode file")  # pragma: no cover


# ── INI parsing + parameter catalogue ─────────────────────────────────────────

# base name -> (group, unit). Unit only where certain; None = raw game value.
_CATALOG: dict[str, tuple[str, Optional[str]]] = {
    "PRESSURE": ("tyres", "psi"), "CAMBER": ("tyres", None), "TYRES": ("tyres", None),
    "TOE_OUT": ("suspension", None), "SPRING_RATE": ("suspension", None),
    "ARB_FRONT": ("suspension", None), "ARB_REAR": ("suspension", None),
    "ROD_LENGTH": ("suspension", None), "DAMP_BUMP": ("suspension", None),
    "DAMP_FAST_BUMP": ("suspension", None), "DAMP_REBOUND": ("suspension", None),
    "DAMP_FAST_REBOUND": ("suspension", None), "BUMP_STOP_RATE": ("suspension", None),
    "BUMP_STOP_UP": ("suspension", None), "BUMP_STOP_DN": ("suspension", None),
    "PACKER_RANGE": ("suspension", None), "HEAVE_SPRING": ("suspension", None),
    "HEAVE_PACKER": ("suspension", None), "STEER_LOCK": ("suspension", None),
    "STEER_RATIO": ("suspension", None), "SUSP_HEIGHT": ("suspension", None),
    "FRONT_BIAS": ("brakes", "%"), "BRAKE_POWER_MULT": ("brakes", "%"),
    "ABS": ("brakes", None), "HANDBRAKE_TORQUE": ("brakes", None),
    "BRAKE_DUCT": ("brakes", None),
    "DIFF_POWER": ("diff", None), "DIFF_COAST": ("diff", None),
    "DIFF_PRELOAD": ("diff", None), "DIFF_LOCK": ("diff", None),
    "TORQUE_SPLIT": ("diff", None),
    "TRACTION_CONTROL": ("electronics", None), "ENGINE_LIMITER": ("electronics", None),
    "TURBO_BOOST": ("electronics", None), "STABILITY_CONTROL": ("electronics", None),
    "FUEL": ("other", "L"), "FINAL_GEAR_RATIO": ("other", None),
}
_GROUP_ORDER = ("aero", "tyres", "suspension", "brakes", "diff", "electronics", "other")
_SPECIAL_SECTIONS = {"CAR", "__EXT_PATCH", "HEADER", "VERSION"}


def parse_ini_text(text: str) -> dict[str, dict[str, str]]:
    """Minimal tolerant INI reader (AC files use ';' and '//' comments, no quoting)."""
    sections: dict[str, dict[str, str]] = {}
    current: Optional[dict[str, str]] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "//", "#")):
            continue
        if line.startswith("[") and "]" in line:
            name = line[1:line.index("]")].strip().upper()
            if len(sections) >= MAX_SECTIONS:
                raise SetupError("too many sections")
            current = sections.setdefault(name, {})
            continue
        if current is None or "=" not in line:
            continue
        key, _sep, value = line.partition("=")
        value = re.split(r"\s*(?:;|//)", value, maxsplit=1)[0].strip()
        current[key.strip().upper()] = value
    return sections


def _num(v: str):
    try:
        f = float(v.replace(",", "."))
    except (ValueError, AttributeError):
        return v
    return int(f) if f.is_integer() and re.fullmatch(r"[+-]?\d+", v.strip()) else f


def _split_section(name: str) -> tuple[str, Optional[str]]:
    for w in _WHEELS:
        if name.endswith("_" + w):
            return name[: -len(w) - 1], w
    return name, None


def _classify(base: str) -> tuple[str, Optional[str]]:
    if base in _CATALOG:
        return _CATALOG[base]
    if re.fullmatch(r"WING_\d+", base):
        return "aero", None
    if base.startswith(("DIFF_", "DAMP_", "BUMP_STOP", "PACKER", "HEAVE")):
        return ("diff" if base.startswith("DIFF_") else "suspension"), None
    return "other", None


def _label(base: str, wheel: Optional[str], lang: str) -> str:
    key = "setups_p_" + base.lower()
    label = _l(lang, key)
    if label == key:
        m = re.fullmatch(r"WING_(\d+)", base)
        if m:
            label = _l(lang, "setups_p_wing", n=m.group(1))
        else:
            label = base.replace("_", " ").capitalize()
    return f"{label} {_WHEEL_TO_POS[wheel]}" if wheel else label


# ── Car data (optional ranges) ────────────────────────────────────────────────

def _ac_roots() -> list[Path]:
    roots: list[Path] = []
    for env in ("AC_ROOT", "AC_INSTALL_DIR"):
        v = os.environ.get(env, "").strip()
        if v:
            roots.append(Path(v))
    libs: list[Path] = []
    if sys.platform == "win32":
        steam = None
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
        except Exception:
            pass
        for cand in (steam, Path(r"C:\Program Files (x86)\Steam")):
            if cand and cand.is_dir():
                libs.append(cand)
                vdf = cand / "steamapps" / "libraryfolders.vdf"
                try:
                    for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(errors="ignore")):
                        libs.append(Path(m.group(1).replace("\\\\", "\\")))
                except OSError:
                    pass
    else:
        libs += [Path.home() / ".steam" / "steam", Path.home() / ".local" / "share" / "Steam"]
    for lib in libs:
        roots.append(lib / "steamapps" / "common" / "assettocorsa")
    seen, out = set(), []
    for r in roots:
        if str(r) not in seen:
            seen.add(str(r))
            out.append(r)
    return out


def load_car_ranges(vehicle: str, roots: Optional[list[Path]] = None) -> tuple[dict, str]:
    """
    Returns ({SECTION: {min,max,step}}, source) where source is
    'car_data' | 'encrypted' | 'not_found'.
    Only an unpacked ``content/cars/<car>/data/setup.ini`` is read.
    """
    try:
        vehicle = _check_name(vehicle, "vehicle")
    except SetupError:
        return {}, "not_found"
    encrypted = False
    for root in (roots if roots is not None else _ac_roots()):
        cars = root / "content" / "cars"
        try:
            if not cars.is_dir():
                continue
            car = _child_dir(cars, vehicle)
            if not car:
                continue
            ini = car / "data" / "setup.ini"
            if ini.is_file() and _inside(cars, ini):
                secs = parse_ini_text(_read_limited(ini))
                ranges = {}
                for name, kv in secs.items():
                    r = {k.lower(): _num(kv[k]) for k in ("MIN", "MAX", "STEP") if k in kv}
                    r = {k: v for k, v in r.items() if isinstance(v, (int, float))}
                    if r:
                        ranges[name] = r
                if ranges:
                    return ranges, "car_data"
            if (car / "data.acd").is_file():
                encrypted = True
        except (OSError, SetupError):
            continue
    return {}, "encrypted" if encrypted else "not_found"


# ── Parsed setup ──────────────────────────────────────────────────────────────

def parse_setup(text: str, name: str = "setup.ini", lang: str = "en",
                mtime: Optional[float] = None, ranges: Optional[dict] = None,
                ranges_source: str = "not_found") -> dict:
    sections = parse_ini_text(text)
    params: dict[str, dict] = {}
    for sec, kv in sections.items():
        if sec in _SPECIAL_SECTIONS or "VALUE" not in kv:
            continue
        base, wheel = _split_section(sec)
        group, unit = _classify(base)
        p = {
            "section": sec, "base": base, "wheel": _WHEEL_TO_POS.get(wheel) if wheel else None,
            "group": group, "label": _label(base, wheel, lang), "unit": unit,
            "value": _num(kv["VALUE"]),
        }
        r = (ranges or {}).get(sec)
        if r:
            p.update({k: r[k] for k in ("min", "max", "step") if k in r})
        params[sec] = p
    if not params:
        raise SetupError("no setup parameters found")

    groups = []
    for gid in _GROUP_ORDER:
        items = [k for k, p in params.items() if p["group"] == gid]
        if items:
            groups.append({"id": gid, "label": _l(lang, "setups_group_" + gid), "items": items})
    return {
        "name": name,
        "car_model": (sections.get("CAR") or {}).get("MODEL"),
        "ext_patch": (sections.get("__EXT_PATCH") or {}).get("VERSION"),
        "mtime": mtime,
        "n_params": len(params),
        "params": params,
        "groups": groups,
        "summary": summarize(params, lang),
        "ranges_source": ranges_source,
    }


def _fmt(v) -> str:
    return f"{v:g}" if isinstance(v, float) else str(v)


def summarize(params: dict, lang: str = "en") -> list[dict]:
    """A few headline chips for lists / headers: pressures, ARB, brake bias, fuel."""
    def vals(base, order):
        out = []
        for w in order:
            p = params.get(f"{base}_{w}")
            if p is None:
                return None
            out.append(_fmt(p["value"]))
        return out

    chips = []
    pr = vals("PRESSURE", _WHEELS)
    if pr:
        chips.append({"key": "pressures", "label": _l(lang, "setups_sum_pressures"),
                      "value": " / ".join(pr) + " psi"})
    af, ar = params.get("ARB_FRONT"), params.get("ARB_REAR")
    if af and ar:
        chips.append({"key": "arb", "label": _l(lang, "setups_sum_arb"),
                      "value": f"{_fmt(af['value'])} / {_fmt(ar['value'])}"})
    cf, cr = params.get("CAMBER_LF"), params.get("CAMBER_LR")
    if cf and cr:
        chips.append({"key": "camber", "label": _l(lang, "setups_sum_camber"),
                      "value": f"{_fmt(cf['value'])} / {_fmt(cr['value'])}"})
    fb = params.get("FRONT_BIAS")
    if fb:
        chips.append({"key": "bias", "label": _l(lang, "setups_sum_bias"),
                      "value": f"{_fmt(fb['value'])} %"})
    fu = params.get("FUEL")
    if fu:
        chips.append({"key": "fuel", "label": _l(lang, "setups_sum_fuel"),
                      "value": f"{_fmt(fu['value'])} L"})
    return chips


# ── Candidates ────────────────────────────────────────────────────────────────

def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _file_entry(path: Path, kind: str, lang: str) -> Optional[dict]:
    try:
        st = path.stat()
        parsed = parse_setup(_read_limited(path), path.name, lang, st.st_mtime)
    except (OSError, SetupError) as exc:
        logger.info("Skipping setup %s: %s", path, exc)
        return None
    return {
        "id": f"{kind}:{path.name}", "name": path.name, "mtime": st.st_mtime,
        "mtime_iso": _iso(st.st_mtime), "n_params": parsed["n_params"],
        "summary": parsed["summary"], "car_model": parsed["car_model"],
    }


def find_candidates(vehicle: Optional[str], venue: Optional[str], lang: str = "en",
                    base: Optional[Path] = None) -> dict:
    """
    Resolution flow:
      track_setups -> several / one setup for that exact car+track (ask which one was used)
      generic_only -> only <car>/generic/last.ini (ask whether it was the one used)
      none         -> nothing found (offer upload)
      no_access    -> server cannot see an AC setups folder (Docker / Linux / macOS)
    """
    if base is None:
        base, exists = resolve_setups_dir()
    else:
        exists = base.is_dir()
    result = {
        "ac_setups_dir": str(base) if base else None, "found_dir": bool(exists),
        "vehicle": vehicle, "venue": venue, "track_setups": [], "generic_last": None,
        "needs_confirmation": False, "state": "none", "reason": "",
    }
    if not exists:
        result.update(state="no_access", reason=_l(lang, "setups_reason_no_access"))
        return result
    if not vehicle:
        result["reason"] = _l(lang, "setups_reason_no_vehicle")
        return result

    car_dir = _child_dir(base, vehicle)
    if car_dir is None:
        result["reason"] = _l(lang, "setups_reason_no_car", vehicle=vehicle)
        return result

    if venue:
        track_dir = _child_dir(car_dir, venue)
        if track_dir is not None:
            entries = []
            for fname in os.listdir(track_dir):
                fp = track_dir / fname
                if fname.lower().endswith(".ini") and fp.is_file() and _inside(base, fp):
                    e = _file_entry(fp, "track", lang)
                    if e:
                        entries.append(e)
            entries.sort(key=lambda e: e["mtime"], reverse=True)
            result["track_setups"] = entries

    generic = car_dir / "generic" / "last.ini"
    try:
        if generic.is_file() and _inside(base, generic):
            result["generic_last"] = _file_entry(generic, "generic", lang)
    except OSError:
        pass

    if result["track_setups"]:
        n = len(result["track_setups"])
        result.update(state="track_setups", needs_confirmation=True,
                      reason=_l(lang, "setups_reason_track_many" if n > 1 else "setups_reason_track_one",
                                n=n, venue=venue))
    elif result["generic_last"]:
        result.update(state="generic_only", needs_confirmation=True,
                      reason=_l(lang, "setups_reason_generic_only", venue=venue or "?"))
    else:
        result["reason"] = _l(lang, "setups_reason_none", vehicle=vehicle, venue=venue or "?")
    return result


def read_setup_by_id(vehicle: str, venue: Optional[str], setup_id: str, lang: str = "en",
                     base: Optional[Path] = None) -> dict:
    if base is None:
        base, exists = resolve_setups_dir()
        if not exists:
            raise SetupError("setups folder not available")
    kind, _sep, fname = (setup_id or "").partition(":")
    fname = _check_filename(fname)
    car_dir = _child_dir(base, vehicle)
    if car_dir is None:
        raise SetupError("car folder not found")
    if kind == "generic":
        folder = car_dir / "generic"
    elif kind == "track":
        folder = _child_dir(car_dir, venue or "")
        if folder is None:
            raise SetupError("track folder not found")
    else:
        raise SetupError("invalid setup id")
    path = folder / fname
    if not path.is_file() or not _inside(base, path):
        raise SetupError("setup not found")
    ranges, source = load_car_ranges(vehicle)
    return parse_setup(_read_limited(path), fname, lang, path.stat().st_mtime, ranges, source)


def parse_upload(filename: str, raw: bytes, vehicle: Optional[str] = None,
                 lang: str = "en") -> dict:
    name = os.path.basename(filename or "setup.ini")
    if not name.lower().endswith(ALLOWED_EXT):
        raise SetupError("only .ini / .sp files are accepted")
    ranges, source = load_car_ranges(vehicle) if vehicle else ({}, "not_found")
    return parse_setup(decode_bytes(raw), name[:128], lang, None, ranges, source)


# ── Recommendation -> parameter mapping ───────────────────────────────────────
#
# action = (base, target, direction, step_mult, alt)
#   target: "pos" (wheel of the recommendation), "front"/"rear" axle, "bias_pos"
#   direction: +1 / -1 in the .ini's own value
#   alt: True when the advisor offers it as an alternative / mechanical fix
# Keyed by the language independent ``rec_key`` the advisor now exports.

_MAP: dict[str, list[tuple]] = {
    "setup_rec_camber_add":          [("CAMBER", "pos", -1, 1, False)],
    "setup_rec_camber_insufficient": [("CAMBER", "pos", -1, 1, False)],
    "setup_rec_camber_reduce":       [("CAMBER", "pos", +1, 1, False)],
    "setup_rec_camber_excess":       [("CAMBER", "pos", +1, 1, False)],
    "setup_rec_pressure_raise":      [("PRESSURE", "pos", +1, 1, False)],
    "setup_rec_temp_cold":           [("PRESSURE", "pos", +1, 1, False)],
    "setup_rec_pressure_lower":      [("PRESSURE", "pos", -1, 1, False)],
    "setup_rec_temp_overheat":       [("PRESSURE", "pos", -1, 1, False)],
    "setup_rec_thermal_front":       [("ARB_FRONT", None, -1, 1, False)],
    "setup_rec_thermal_rear":        [("ARB_REAR", None, -1, 1, False)],
    "setup_rec_arb_front":           [("ARB_FRONT", None, +1, 1, False)],
    "setup_rec_roll_front_session":  [("ARB_FRONT", None, +1, 2, False)],
    "setup_rec_arb_rear":            [("ARB_REAR", None, +1, 1, False)],
    "setup_rec_roll_rear_session":   [("ARB_REAR", None, +1, 2, False)],
    "setup_rec_understeer":          [("ARB_FRONT", None, -1, 1, True)],
    "setup_rec_understeer_session":  [("ARB_FRONT", None, -1, 1, True)],
    "setup_rec_oversteer":           [("ARB_FRONT", None, +1, 1, True)],
    "setup_rec_oversteer_session":   [("ARB_FRONT", None, +1, 1, True)],
    "setup_rec_mild_understeer":     [("PRESSURE", "front", -1, 1, False), ("ARB_FRONT", None, -1, 1, True)],
    "setup_rec_mild_understeer_session": [("PRESSURE", "front", -1, 1, False), ("ARB_FRONT", None, -1, 1, True)],
    "setup_rec_front_hotter":        [("FRONT_BIAS", None, -1, 1, False)],
    "setup_rec_brake_temp":          [("FRONT_BIAS", "bias_pos", -1, 1, False)],
    "setup_rec_pitch":               [("SPRING_RATE", "front", +1, 1, False)],
    "setup_rec_pitch_session":       [("SPRING_RATE", "front", +1, 1, False)],
    "setup_rec_nervous_mid_freq":    [("SPRING_RATE", "all", -1, 1, False)],
    "setup_rec_mid_freq_steer":      [("SPRING_RATE", "all", -1, 1, False)],
    "setup_rec_springs":             [("SPRING_RATE", "rear", -1, 1, False)],
    "setup_rec_springs_session":     [("SPRING_RATE", "all", -1, 1, False)],
}

# Parameters worth showing next to a recommendation when no safe change can be derived.
_RELATED: dict[str, list[str]] = {
    "setup_rec_ride_height": ["ROD_LENGTH", "SPRING_RATE"],
    "setup_rec_bottoming_session": ["ROD_LENGTH", "SPRING_RATE"],
    "setup_rec_asymmetry": ["PRESSURE"],
    "setup_rec_lateral_asymmetry": ["PRESSURE", "CAMBER"],
    "setup_rec_rear_hotter": ["PRESSURE"],
    "setup_rec_late_throttle": ["TOE_OUT", "ARB_REAR"],
    "setup_rec_nervous_general": ["PRESSURE", "ARB_FRONT", "ARB_REAR"],
    "setup_rec_medium_nervous": ["PRESSURE", "ARB_FRONT", "ARB_REAR"],
    "setup_rec_mechanical": ["PRESSURE", "ARB_FRONT", "ARB_REAR", "TOE_OUT"],
    "setup_rec_mechanical_session": ["PRESSURE", "ARB_FRONT", "ARB_REAR"],
    "setup_rec_brake_early": ["BRAKE_POWER_MULT", "FRONT_BIAS", "ABS"],
    "setup_rec_degradation_high": ["PRESSURE", "CAMBER"],
    "setup_rec_degradation_moderate": ["PRESSURE"],
    "setup_rec_slow_apex": ["ARB_FRONT", "ARB_REAR", "PRESSURE"],
}

# Bounds that hold for every car (checked in addition to the car's own MIN/MAX).
_HARD_BOUNDS = {"ARB_FRONT": (0, None), "ARB_REAR": (0, None), "FRONT_BIAS": (0, 100),
                "PRESSURE": (0, None)}
# Step is only assumed to be 1 for these (the game's click = 1 for them).
_UNIT_STEP_OK = {"PRESSURE", "ARB_FRONT", "ARB_REAR", "FRONT_BIAS"}


def _targets(setup_params: dict, base: str, target: Optional[str], pos: Optional[str]) -> list[str]:
    if target is None:
        return [base] if base in setup_params else []
    if target == "pos":
        w = _POS_TO_WHEEL.get(pos or "")
        return [f"{base}_{w}"] if w and f"{base}_{w}" in setup_params else []
    if target == "bias_pos":
        return [base] if base in setup_params else []
    wheels = {"front": ("LF", "RF"), "rear": ("LR", "RR"), "all": _WHEELS}[target]
    return [f"{base}_{w}" for w in wheels if f"{base}_{w}" in setup_params]


def _bounds(p: dict) -> tuple[Optional[float], Optional[float]]:
    lo_h, hi_h = _HARD_BOUNDS.get(p["base"], (None, None))
    lo, hi = p.get("min", lo_h), p.get("max", hi_h)
    if "min" in p and lo_h is not None:
        lo = max(p["min"], lo_h)
    if "max" in p and hi_h is not None:
        hi = min(p["max"], hi_h)
    return lo, hi


def _build_action(p: dict, direction: int, mult: int, alt: bool, lang: str) -> dict:
    cur = p["value"]
    step = p.get("step")
    step_known = isinstance(step, (int, float)) and step > 0
    if not step_known and p["base"] in _UNIT_STEP_OK:
        step, step_known = 1, True
    lo, hi = _bounds(p)
    act = {
        "param": p["section"], "label": p["label"], "unit": p.get("unit"),
        "current": cur, "suggested": None, "delta": None,
        "direction": "up" if direction > 0 else "down",
        "status": "direction_only", "alternative": alt, "note": "",
    }
    if not isinstance(cur, (int, float)):
        act["note"] = _l(lang, "setups_note_non_numeric")
        return act
    # Already at the limit in the direction the advisor wants -> incoherent advice.
    if direction < 0 and lo is not None and cur <= lo:
        act.update(status="at_limit", note=_l(lang, "setups_note_at_min", value=_fmt(cur)))
        return act
    if direction > 0 and hi is not None and cur >= hi:
        act.update(status="at_limit", note=_l(lang, "setups_note_at_max", value=_fmt(cur)))
        return act
    if not step_known:
        act["note"] = _l(lang, "setups_note_step_unknown")
        return act
    new = cur + direction * step * mult
    if lo is not None:
        new = max(new, lo)
    if hi is not None:
        new = min(new, hi)
    new = round(new, 4)
    new = int(new) if float(new).is_integer() else new
    act.update(suggested=new, delta=round(new - cur, 4), status="ok")
    if p.get("step") is None:
        act["note"] = _l(lang, "setups_note_step_assumed")
    return act


def annotate_recommendations(setup: dict, recommendations: list, lang: str = "en") -> dict:
    """Decorate advisor recommendations with current/suggested setup values."""
    params = (setup or {}).get("params") or {}
    if not isinstance(params, dict) or not params:
        raise SetupError("setup has no parameters")
    # Re-derive structure defensively: never trust client-provided labels blindly.
    clean: dict[str, dict] = {}
    for sec, p in params.items():
        if not isinstance(p, dict) or "value" not in p or not isinstance(sec, str):
            continue
        base, wheel = _split_section(sec.upper())
        q = {"section": sec.upper(), "base": base, "value": p["value"],
             "wheel": _WHEEL_TO_POS.get(wheel) if wheel else None,
             "unit": _classify(base)[1], "group": _classify(base)[0],
             "label": _label(base, wheel, lang)}
        for k in ("min", "max", "step"):
            if isinstance(p.get(k), (int, float)):
                q[k] = p[k]
        clean[q["section"]] = q

    decorated, all_actions = [], []
    n_linked = 0
    for rec in recommendations or []:
        if not isinstance(rec, dict):
            continue
        out = dict(rec)
        key = rec.get("rec_key") or ""
        pos = rec.get("pos")
        actions: list[dict] = []
        for base, target, direction, mult, alt in _MAP.get(key, []):
            d = direction
            if target == "bias_pos":
                # "reduce brake bias toward the hot axle": front axle hot -> bias back.
                d = -1 if pos in ("FL", "FR") else +1
            for sec in _targets(clean, base, target, pos):
                actions.append(_build_action(clean[sec], d, mult, alt, lang))
        related = []
        if not actions:
            for rb in _RELATED.get(key, []):
                for sec, p in clean.items():
                    if p["base"] == rb:
                        related.append({"param": sec, "label": p["label"], "value": p["value"],
                                        "unit": p.get("unit")})
        if actions or related:
            n_linked += 1
            out["setup_link"] = {"actions": actions, "related": related}
        all_actions += actions
        decorated.append(out)

    # Contradictory advice across recommendations for the same parameter.
    by_param: dict[str, set] = {}
    for a in all_actions:
        if not a["alternative"]:
            by_param.setdefault(a["param"], set()).add(a["direction"])
    conflicts = [{"param": k, "label": clean[k]["label"]} for k, v in by_param.items() if len(v) > 1]

    return {
        "recommendations": decorated,
        "n_linked": n_linked,
        "conflicts": conflicts,
        "summary": summarize(clean, lang),
    }


# ── MoTeC CSV header ──────────────────────────────────────────────────────────

def parse_motec_header(raw: bytes) -> dict:
    """Driver / Vehicle / Venue from the first lines of a MoTeC CSV export."""
    text = raw[:65536].decode("utf-8", errors="ignore")
    meta = {"driver": None, "vehicle": None, "venue": None}
    keys = {"Driver": "driver", "Vehicle": "vehicle", "Venue": "venue"}
    for line in text.splitlines()[:20]:
        clean = line.replace('"', "").strip()
        for raw_key, field in keys.items():
            if clean.startswith(raw_key + ","):
                parts = [p.strip() for p in clean.split(",")]
                if len(parts) >= 2 and parts[1]:
                    meta[field] = parts[1]
    return meta
