"""
Incident detection: spins, big slides and off-track excursions, with the likely cause of each.

Works on the per-lap frames the stint / session analysis already produces. Uses the best signal the
log offers and degrades gracefully:

* slip angle: body velocity (``BodyVelX/Y``, ACTI) > position + yaw (``CarCoord`` or ``Lat/Lon``) > yaw only
* off-track: tyre dirt (``Dirt*``, ACTI) > track surface (``TrackSurface``, iRacing) > geometric deviation
  from the line the other laps drove (needs position)

Every cause is an INFERENCE from the driver inputs and the car state before the event, scored 0..1 and
shown with the numbers that support it. What the logs cannot tell (contact with other cars, a wind
direction in an unknown frame, a damp patch) is never claimed.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.i18n import _ as _tr

logger = logging.getLogger(__name__)

# ── thresholds ───────────────────────────────────────────────────────────────────────────
MIN_SPEED_KMH = 30.0         # speed at the onset for a slide / spin to count (excludes standstill artefacts)
SLIDE_DEG = 45.0             # peak body slip angle of a "big slide" (saved)
SPIN_ROTATION_DEG = 150.0    # a slide that turned the car this much is a spin even if its peak slip angle stayed lower
SPIN_DEG = 100.0             # peak body slip angle of a spin (car pointing backwards)
BETA_MIN_SPEED_MS = 5.0      # below this speed the slip angle is noise
MERGE_GAP_S = 1.0            # samples of one event closer than this are the same event
PRE_S = 3.0                  # window before the onset the causes are read from
LINK_S = 3.0                 # a spin and an off-track closer than this are one event
DIRT_ON = 0.25               # tyre dirt level that means a wheel left the track
DIRT_MAJOR = 0.8
GEO_MIN_OFFSET_M = 6.0       # geometric off-track: minimum lateral deviation from the usual line
GEO_MIN_S = 0.5
TRACE_PRE_S, TRACE_POST_S, TRACE_POINTS = 4.0, 4.0, 90
WHEELS = ("FL", "FR", "RL", "RR")


# ── helpers ──────────────────────────────────────────────────────────────────────────────
def _col(df: pd.DataFrame, name: str) -> Optional[np.ndarray]:
    if name not in df.columns:
        return None
    v = pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)
    return v if np.isfinite(v).any() else None


def _filled(a: Optional[np.ndarray], default: float = 0.0) -> Optional[np.ndarray]:
    if a is None:
        return None
    return np.nan_to_num(a, nan=default, posinf=default, neginf=default)


def _runs(mask: np.ndarray, gap: int = 0) -> List[tuple]:
    """[(first, last)] index runs of True, merging runs separated by <= ``gap`` samples."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(idx) > gap + 1) + 1
    return [(int(g[0]), int(g[-1])) for g in np.split(idx, cuts)]


def _sign_corr(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 20 or np.std(a[ok]) < 1e-9 or np.std(b[ok]) < 1e-9:
        return 1.0
    c = float(np.corrcoef(a[ok], b[ok])[0, 1])
    return 1.0 if not np.isfinite(c) or c >= 0 else -1.0


def _yaw_deg_s(df: pd.DataFrame) -> Optional[np.ndarray]:
    y = _col(df, "YawRate")
    if y is None:
        return None
    y = _filled(y)
    # rad/s when its magnitude never exceeds ~6 (a car does not yaw at 340 deg/s)
    return np.rad2deg(y) if np.abs(y).max() < 6.0 else y


def _course_deg(df: pd.DataFrame) -> Optional[np.ndarray]:
    """Unwrapped course (direction of travel, degrees) from the position channels."""
    xs = ys = None
    cx, cy, cz = (_col(df, c) for c in ("CarCoordX", "CarCoordY", "CarCoordZ"))
    if cx is not None and cy is not None and cz is not None:
        rng = {k: np.nanmax(v) - np.nanmin(v) for k, v in (("x", cx), ("y", cy), ("z", cz))}
        top = sorted(rng, key=rng.get, reverse=True)[:2]
        pick = {"x": cx, "y": cy, "z": cz}
        xs, ys = pick[top[0]], pick[top[1]]
    elif cx is not None and cy is not None:
        xs, ys = cx, cy
    else:
        lat, lon = _col(df, "Lat"), _col(df, "Lon")
        if lat is not None and lon is not None and np.nanstd(lat) > 0:
            lat0 = np.nanmedian(lat)
            ys = (lat - lat0) * 111_320.0
            xs = (lon - np.nanmedian(lon)) * 111_320.0 * np.cos(np.deg2rad(lat0))
    if xs is None:
        return None
    xs, ys = _filled(xs), _filled(ys)
    k = 5
    ker = np.ones(k) / k
    xs = np.convolve(np.pad(xs, k // 2, mode="edge"), ker, "valid")        # edge padding: zeros would fake a jump
    ys = np.convolve(np.pad(ys, k // 2, mode="edge"), ker, "valid")
    dx, dy = np.gradient(xs), np.gradient(ys)
    return np.rad2deg(np.unwrap(np.arctan2(dy, dx)))


class _Lap:
    """Signals of one lap, ready for the detectors."""

    def __init__(self, df: pd.DataFrame, number: int):
        self.df = df.reset_index(drop=True)
        self.number = number
        d = self.df
        t = _col(d, "Time")
        if t is None or len(t) < 3:
            t = np.arange(len(d)) / 20.0
        self.t = np.nan_to_num(t - np.nanmin(t))
        dt = np.diff(self.t)
        dt = dt[dt > 0]
        self.hz = float(1.0 / np.median(dt)) if dt.size else 20.0
        self.n = len(d)
        spd = _filled(_col(d, "Speed"))
        self.speed = spd if spd is not None else np.zeros(self.n)
        dist = _col(d, "Distance")
        if dist is not None:
            dist = _filled(dist)
            self.dist = dist - dist[0]
        else:
            self.dist = np.cumsum(self.speed / 3.6 * np.gradient(self.t))
        self.length = float(self.dist[-1] - self.dist[0]) if self.n > 1 else 0.0
        for name, key in (("Throttle", "throttle"), ("Brake", "brake"), ("SteerAngle", "steer"),
                          ("LateralG", "latg"), ("LongitudinalG", "long_g"), ("Gear", "gear"), ("RPM", "rpm"),
                          ("VerticalG", "vert_g")):
            setattr(self, key, _filled(_col(d, name)))
        self.yaw = _yaw_deg_s(d)
        pit = _col(d, "InPit")
        self.in_pit = _filled(pit) > 0 if pit is not None else np.zeros(self.n, bool)
        self.lap_time = None
        lt = _col(d, "LapTime")
        if lt is not None and np.isfinite(lt[-1]) and 20 < np.nanmax(lt) < 1200:
            self.lap_time = float(np.nanmax(lt))
        elif self.t[-1] > 20:
            self.lap_time = float(self.t[-1])

    def idx_at(self, t: float) -> int:
        return int(np.clip(np.searchsorted(self.t, t), 0, self.n - 1))


def _position_excess(lap: _Lap, course: np.ndarray) -> Optional[np.ndarray]:
    """Rotation of the car (integrated yaw) that the path does not explain, in degrees over a 2 s window.
    None when position and yaw rate disagree (units or signs differ between loggers; it self-calibrates)."""
    W = max(3, int(round(2.0 * lap.hz)))
    yaw_int = np.cumsum(lap.yaw / lap.hz)
    dy = yaw_int[W:] - yaw_int[:-W]
    dc = course[W:] - course[:-W]
    ok = (lap.speed[W:] / 3.6 > BETA_MIN_SPEED_MS) & (np.abs(dc) > 30)
    if ok.sum() < 20:
        return None
    ratio = dy[ok] / dc[ok]
    scale = float(np.median(ratio))
    spread = float(np.percentile(np.abs(ratio - scale), 75))
    if not (0.2 < abs(scale) < 5.0) or spread > 0.25 * abs(scale):
        return None
    excess = np.zeros(lap.n)
    excess[W:] = np.abs(dy - scale * dc)
    return np.where(lap.speed / 3.6 < BETA_MIN_SPEED_MS, 0.0, excess)


# ── slip angle ───────────────────────────────────────────────────────────────────────────
def _slip_signal(lap: _Lap, k_steer_beta: dict) -> tuple:
    """(beta_deg or None, source). ``beta`` is the body slip angle normalised so that positive values
    mean the nose points to the inside of the turn, in the direction of the yaw."""
    d = lap.df
    vx, vy = _col(d, "BodyVelX"), _col(d, "BodyVelY")
    if vx is not None and vy is not None:
        vx, vy = _filled(vx), _filled(vy)
        beta = np.degrees(np.arctan2(vy, vx))
        beta = np.where(np.hypot(vx, vy) < BETA_MIN_SPEED_MS, 0.0, beta)
        return beta, "body_velocity"
    course = _course_deg(d)
    if course is not None and lap.yaw is not None:
        excess = _position_excess(lap, course)
        if excess is not None:
            return excess, "position_yaw"
    if lap.yaw is not None:
        W = max(3, int(round(2.5 * lap.hz)))
        yaw_int = np.cumsum(lap.yaw / lap.hz)
        rot = np.zeros(lap.n)
        rot[W:] = np.abs(yaw_int[W:] - yaw_int[:-W])
        v0 = np.zeros(lap.n)
        v0[W:] = lap.speed[:-W]
        collapsed = lap.speed < 0.5 * np.maximum(v0, 1.0)
        fast_yaw = np.abs(lap.yaw) > 90.0
        rot = np.where((collapsed | fast_yaw) & (rot > 120.0), rot, 0.0)
        return rot, "yaw_only"
    return None, "none"


def _normalise_beta_sign(lap: _Lap, beta: np.ndarray, source: str) -> np.ndarray:
    """Body slip: flip so that it co-varies positively with the yaw rate (nose-inside = positive)."""
    if source != "body_velocity" or lap.yaw is None:
        return beta
    ok = (lap.speed > 40) & (np.abs(lap.yaw) > 5)
    if ok.sum() < 20:
        return beta
    return beta * _sign_corr(beta[ok], lap.yaw[ok])


# ── detectors ────────────────────────────────────────────────────────────────────────────
def _detect_slides(lap: _Lap, beta: np.ndarray, source: str) -> List[dict]:
    if beta is None:
        return []
    slide_deg = SLIDE_DEG if source != "yaw_only" else 120.0
    mag = np.abs(beta)
    big = (mag >= slide_deg) & (lap.speed >= 18.0)
    out = []
    for a, b in _runs(big, gap=int(MERGE_GAP_S * lap.hz)):
        peak_i = a + int(np.argmax(mag[a:b + 1]))
        onset = a
        floor = 12.0 if source == "body_velocity" else 25.0
        lim = max(0, a - int(2.0 * lap.hz))
        while onset > lim and mag[onset - 1] > floor:
            onset -= 1
        if lap.speed[onset] < MIN_SPEED_KMH or lap.in_pit[onset]:
            continue
        peak = float(mag[peak_i])
        spin_deg = SPIN_DEG if source == "body_velocity" else 150.0
        end = min(lap.n - 1, b + int(1.0 * lap.hz))
        out.append({"kind": "spin" if peak >= spin_deg else "slide", "onset": onset, "peak": peak_i, "end": end,
                    "peak_slip_deg": round(peak, 1)})
    return out


def _detect_offtrack(lap: _Lap, ref_line: Optional[dict]) -> tuple:
    """([events], source)."""
    d = lap.df
    dirt_cols = [c for c in (f"Dirt{w}" for w in WHEELS) if c in d.columns]
    if dirt_cols:
        dirt = np.stack([_filled(_col(d, c)) for c in dirt_cols])
        peak = dirt.max(axis=0)
        rising = np.convolve((np.gradient(peak) > 0.004).astype(float), np.ones(max(3, int(0.5 * lap.hz))), "same") > 0
        on = (peak >= DIRT_ON) & rising     # the level only rises while a wheel is on the grass; it decays slowly afterwards
        out = []
        for a, b in _runs(on, gap=int(3.0 * lap.hz)):
            seg = dirt[:, a:b + 1]
            wheels = int((seg.max(axis=1) >= DIRT_ON).sum())
            pk = float(seg.max())
            if wheels < 2 and pk < 0.6:        # one wheel brushing a kerb is not an excursion
                continue
            out.append({"onset": a, "peak": a + int(np.argmax(peak[a:b + 1])), "end": b,
                        "peak_dirt": round(pk, 2), "wheels": wheels,
                        "duration_s": round((b - a + 1) / lap.hz, 2)})
        return out, "tire_dirt"
    surf = _col(d, "TrackSurface")
    if surf is not None:
        off = _filled(surf, 3.0) == 0
        out = [{"onset": a, "peak": a, "end": b, "peak_dirt": None, "wheels": None,
                "duration_s": round((b - a + 1) / lap.hz, 2)}
               for a, b in _runs(off, gap=int(0.5 * lap.hz)) if (b - a + 1) / lap.hz >= 0.3]
        return out, "track_surface"
    if ref_line is not None:
        off_m = _lateral_offset(lap, ref_line)
        if off_m is not None:
            lim = max(GEO_MIN_OFFSET_M, ref_line["limit_m"])
            out = []
            for a, b in _runs(off_m > lim, gap=int(0.3 * lap.hz)):
                if (b - a + 1) / lap.hz >= GEO_MIN_S:
                    out.append({"onset": a, "peak": a + int(np.argmax(off_m[a:b + 1])), "end": b,
                                "peak_dirt": None, "wheels": None, "peak_offset_m": round(float(off_m[a:b + 1].max()), 1),
                                "duration_s": round((b - a + 1) / lap.hz, 2)})
            return out, "geometry"
    return [], "none"


def _xy(lap: _Lap) -> Optional[tuple]:
    d = lap.df
    cx, cy, cz = (_col(d, c) for c in ("CarCoordX", "CarCoordY", "CarCoordZ"))
    if cx is not None and cy is not None and cz is not None:
        rng = {"x": np.nanmax(cx) - np.nanmin(cx), "y": np.nanmax(cy) - np.nanmin(cy), "z": np.nanmax(cz) - np.nanmin(cz)}
        top = sorted(rng, key=rng.get, reverse=True)[:2]
        pick = {"x": cx, "y": cy, "z": cz}
        return _filled(pick[top[0]]), _filled(pick[top[1]])
    if cx is not None and cy is not None:
        return _filled(cx), _filled(cy)
    return None


def _build_ref_line(laps: List[_Lap]) -> Optional[dict]:
    """Median racing line (per lap-fraction bin) and the lateral spread the laps normally have."""
    pts = [(lap, _xy(lap)) for lap in laps if lap.length > 500]
    pts = [(lap, xy) for lap, xy in pts if xy is not None]
    if len(pts) < 3:
        return None
    nb = 400
    gx, gy = [], []
    for lap, (x, y) in pts:
        f = np.clip(lap.dist / max(lap.length, 1.0), 0, 1)
        b = np.minimum((f * nb).astype(int), nb - 1)
        bx, by = np.full(nb, np.nan), np.full(nb, np.nan)
        for k in range(nb):
            m = b == k
            if m.any():
                bx[k], by[k] = x[m].mean(), y[m].mean()
        gx.append(bx), gy.append(by)
    mx, my = np.nanmedian(np.array(gx), axis=0), np.nanmedian(np.array(gy), axis=0)
    ok = np.isfinite(mx) & np.isfinite(my)
    if ok.sum() < nb * 0.8:
        return None
    mx = np.interp(np.arange(nb), np.flatnonzero(ok), mx[ok])
    my = np.interp(np.arange(nb), np.flatnonzero(ok), my[ok])
    ref = {"x": mx, "y": my, "nb": nb, "limit_m": GEO_MIN_OFFSET_M}
    offs = []
    for lap, _ in pts:
        o = _lateral_offset(lap, ref)
        if o is not None:
            offs.append(np.nanpercentile(o, 95))
    if offs:
        ref["limit_m"] = float(max(GEO_MIN_OFFSET_M, 2.0 * np.median(offs)))
    return ref


def _lateral_offset(lap: _Lap, ref: dict) -> Optional[np.ndarray]:
    xy = _xy(lap)
    if xy is None or lap.length < 500:
        return None
    x, y = xy
    nb = ref["nb"]
    f = np.clip(lap.dist / max(lap.length, 1.0), 0, 1)
    k = np.minimum((f * nb).astype(int), nb - 1)
    # search +-3 bins for the closest reference point
    best = np.full(lap.n, np.inf)
    for s in range(-3, 4):
        kk = np.clip(k + s, 0, nb - 1)
        best = np.minimum(best, np.hypot(x - ref["x"][kk], y - ref["y"][kk]))
    return best


# ── references (what the other laps did at the same place) ───────────────────────────────
def _ref_stats(laps: List[_Lap], skip: _Lap, dist_m: float, half_m: float = 25.0) -> Optional[dict]:
    rows = []
    frac = dist_m / max(skip.length, 1.0)
    for other in laps:
        if other is skip or other.length < 500:
            continue
        c = frac * other.length
        m = (other.dist >= c - half_m) & (other.dist <= c + half_m) & ~other.in_pit
        if m.sum() < 3:
            continue
        rows.append({"speed": float(np.mean(other.speed[m])), "min_speed": float(np.min(other.speed[m])),
                     "steer": float(np.mean(np.abs(other.steer[m]))) if other.steer is not None else None,
                     "throttle": float(np.mean(other.throttle[m])) if other.throttle is not None else None,
                     "brake": float(np.max(other.brake[m])) if other.brake is not None else None,
                     "latg": float(np.max(np.abs(other.latg[m]))) if other.latg is not None else None})
    if len(rows) < 2:
        return None
    return {k: (float(np.median([r[k] for r in rows if r[k] is not None])) if any(r[k] is not None for r in rows) else None)
            for k in rows[0]}


# ── causes ───────────────────────────────────────────────────────────────────────────────
def _ev(key: str, **values) -> dict:
    return {"key": key, "values": values}


def _grip_context(laps: List[_Lap]) -> dict:
    """Median tyre temperature of the session (to tell cold tyres from normal ones)."""
    temps = []
    for lap in laps:
        for pref in ("TyreTempCore", "TyreTempMiddle"):
            cols = [c for c in (f"{pref}{w}" for w in WHEELS) if c in lap.df.columns]
            if cols:
                temps.append(np.nanmean([np.nanmean(_filled(_col(lap.df, c))) for c in cols]))
                break
    return {"median_tyre_temp": float(np.median(temps)) if temps else None}


def _tyre_temp_at(lap: _Lap, i0: int, i1: int) -> Optional[float]:
    for pref in ("TyreTempCore", "TyreTempMiddle"):
        cols = [c for c in (f"{pref}{w}" for w in WHEELS) if c in lap.df.columns]
        if cols:
            return float(np.nanmean([np.nanmean(_filled(_col(lap.df, c))[i0:i1 + 1]) for c in cols]))
    return None


def _avg_cols(lap: _Lap, prefix: str, wheels, i0: int, i1: int, absval: bool = False) -> Optional[float]:
    vals = []
    for w in wheels:
        a = _col(lap.df, f"{prefix}{w}")
        if a is not None:
            seg = _filled(a)[i0:i1 + 1]
            vals.append(np.mean(np.abs(seg)) if absval else np.mean(seg))
    return float(np.mean(vals)) if vals else None


def _diagnose(lap: _Lap, ev: dict, beta: Optional[np.ndarray], source: str, ref: Optional[dict],
              gctx: dict, all_laps: List[_Lap]) -> tuple:
    """(causes, context) for one event. Scores are additive evidence, clipped to 1."""
    on = ev["onset"]
    hz = lap.hz
    i0 = max(0, on - int(PRE_S * hz))
    ip = max(0, on - int(1.0 * hz))           # last second before the onset
    i1 = min(lap.n - 1, on + int(1.2 * hz))   # first moments of the event
    causes: Dict[str, dict] = {}

    def add(code, score, *evidence):
        if score <= 0:
            return
        c = causes.setdefault(code, {"code": code, "score": 0.0, "evidence": []})
        c["score"] = min(1.0, c["score"] + score)
        c["evidence"].extend(e for e in evidence if e)

    thr, brk, steer, latg = lap.throttle, lap.brake, lap.steer, lap.latg
    speed_on = float(lap.speed[on])
    thr_on = float(np.mean(thr[max(0, on - 2):on + 1])) if thr is not None else None
    brk_on = float(np.mean(brk[max(0, on - 2):on + 1])) if brk is not None else None
    brk_pre = float(np.max(brk[i0:on + 1])) if brk is not None else None
    steer_on = float(np.mean(np.abs(steer[max(0, on - 2):on + 1]))) if steer is not None else None
    latg_on = float(np.max(np.abs(latg[ip:on + 1]))) if latg is not None else None
    context = {"speed_kmh": round(speed_on, 1),
               "throttle_pct": None if thr_on is None else round(thr_on, 0),
               "brake_pct": None if brk_on is None else round(brk_on, 0),
               "steer_deg": None if steer_on is None else round(steer_on, 0),
               "lat_g": None if latg_on is None else round(latg_on, 2),
               "gear": None if lap.gear is None else int(lap.gear[on])}
    kind = ev["kind"]
    is_rotation = kind in ("spin", "slide")

    # slip balance: front vs rear tyre slip angle in the pre-event window (ACTI)
    sa_f = _avg_cols(lap, "SlipAngle", ("FL", "FR"), ip, i1, absval=True)
    sa_r = _avg_cols(lap, "SlipAngle", ("RL", "RR"), ip, i1, absval=True)
    sr_rear = _avg_cols(lap, "SlipRatio", ("RL", "RR"), max(0, on - int(0.3 * hz)), i1)
    if sa_f is not None and sa_r is not None:
        context["slip_front_deg"], context["slip_rear_deg"] = round(sa_f, 1), round(sa_r, 1)
    rear_led = sa_r is not None and sa_f is not None and sa_r > sa_f * 1.15
    front_led = sa_r is not None and sa_f is not None and sa_f > sa_r * 1.15

    # 1. throttle: power oversteer / wheelspin
    if thr is not None and thr_on is not None and is_rotation:
        d_thr = float(thr[on] - thr[max(0, on - int(0.7 * hz))])
        score = 0.0
        ev_ = []
        if thr_on >= 35:
            score += 0.25 + 0.25 * min(1.0, (thr_on - 35) / 50)
            ev_.append(_ev("inc_ev_throttle_on", pct=round(thr_on)))
        if d_thr >= 15:
            score += 0.15
            ev_.append(_ev("inc_ev_throttle_rising", delta=round(d_thr)))
        if ref and ref.get("throttle") is not None and thr_on > ref["throttle"] + 15:
            score += 0.15
            ev_.append(_ev("inc_ev_throttle_vs_ref", pct=round(thr_on), ref=round(ref["throttle"])))
        if sr_rear is not None and sr_rear > 8:
            score += 0.2
            ev_.append(_ev("inc_ev_wheelspin", pct=round(sr_rear)))
        if rear_led:
            score += 0.1
            ev_.append(_ev("inc_ev_rear_slip", rear=round(sa_r, 1), front=round(sa_f, 1)))
        if thr_on >= 35 and (brk_on or 0) < 10:
            add("too_much_throttle", score, *ev_)

    # 2. lift-off oversteer
    if thr is not None and is_rotation:
        w = max(1, int(0.6 * hz))
        seg = thr[max(0, on - int(1.5 * hz)):on + 1]
        if seg.size > w:
            drop = float(np.max(seg[:-w] - seg[w:])) if seg.size > w else 0.0
            if drop >= 35 and (brk_on or 0) < 15 and (latg_on or 0) >= 0.6:
                add("lift_off", 0.35 + 0.3 * min(1.0, (drop - 35) / 50) + (0.15 if rear_led else 0),
                    _ev("inc_ev_lift", drop=round(drop)), _ev("inc_ev_latg", g=round(latg_on or 0, 2)))

    # 3. braking: too much brake with steering / rear lock
    if brk is not None and is_rotation and (brk_pre or 0) >= 20:
        score = 0.2 + 0.25 * min(1.0, ((brk_on or 0)) / 60)
        ev_ = [_ev("inc_ev_brake_on", pct=round(brk_on or 0), peak=round(brk_pre or 0))]
        if steer_on is not None and steer_on >= 25:
            score += 0.2
            ev_.append(_ev("inc_ev_trail_brake", steer=round(steer_on)))
        wr = _avg_cols(lap, "WheelSpeed", ("RL", "RR"), ip, on)
        wf = _avg_cols(lap, "WheelSpeed", ("FL", "FR"), ip, on)
        if wr is not None and wf is not None and wf > 5 and wr < 0.8 * wf:
            score += 0.25
            ev_.append(_ev("inc_ev_rear_lock", ratio=round(wr / wf * 100)))
        if ref and ref.get("brake") is not None and (brk_pre or 0) > ref["brake"] + 15:
            score += 0.1
            ev_.append(_ev("inc_ev_brake_vs_ref", pct=round(brk_pre or 0), ref=round(ref["brake"])))
        if (brk_on or 0) >= 10 or (brk_pre or 0) >= 40:
            add("braking_instability", score, *ev_)

    # 4. too much steering (or sudden steering) before the loss
    if steer is not None and steer_on is not None:
        rate = np.abs(np.gradient(steer, 1.0 / hz))[ip:on + 1]
        peak_rate = float(rate.max()) if rate.size else 0.0
        score, ev_ = 0.0, []
        if ref and ref.get("steer") is not None and ref["steer"] > 3 and steer_on > ref["steer"] * 1.25 + 3:
            score += 0.3 + 0.2 * min(1.0, (steer_on / ref["steer"] - 1.25) / 0.75)
            ev_.append(_ev("inc_ev_steer_vs_ref", deg=round(steer_on), ref=round(ref["steer"])))
        if peak_rate >= 250:
            score += 0.25 + 0.15 * min(1.0, (peak_rate - 250) / 400)
            ev_.append(_ev("inc_ev_steer_rate", dps=round(peak_rate)))
        if front_led and is_rotation:
            score += 0.1
        if score:
            add("too_much_steering", score, *ev_)

    # 5. correction after the loss (needs slip angle with sign)
    if is_rotation and beta is not None and steer is not None and lap.yaw is not None and source == "body_velocity":
        k = _sign_corr(steer[(lap.speed > 40) & (np.abs(lap.yaw) > 5)], lap.yaw[(lap.speed > 40) & (np.abs(lap.yaw) > 5)])
        win = slice(on, min(lap.n, on + int(1.5 * hz)))
        b = beta[win]
        if b.size > 3:
            yaw_dir = np.sign(np.median(lap.yaw[win])) or 1.0
            counter = -yaw_dir * k * steer[win]          # >0 = steering against the rotation
            peak_i = int(np.argmax(np.abs(b)))
            lag = next((i for i, c in enumerate(counter) if c > 10), None)
            amp = float(np.max(counter[:max(2, peak_i + 1)])) if counter.size else 0.0
            if lag is None or lag / hz > 0.45:
                add("late_correction", 0.35 + (0.25 if lag is None else 0.1),
                    _ev("inc_ev_no_countersteer") if lag is None else _ev("inc_ev_countersteer_lag", s=round(lag / hz, 2)))
            elif amp < 25 and ev["kind"] == "spin":
                add("late_correction", 0.3, _ev("inc_ev_small_countersteer", deg=round(amp)))
            seg3 = beta[on:min(lap.n, on + int(3 * hz))]
            if seg3.size and float(seg3.max()) > 30 and float(-seg3.min()) > 30:
                add("overcorrection", 0.45, _ev("inc_ev_pendulum"))

    # 6. entry speed too high vs the other laps
    if ref and ref.get("speed"):
        i_entry = max(0, on - int(1.0 * hz))
        v_in = float(np.mean(lap.speed[max(0, i_entry - 2):i_entry + 1]))
        gap = v_in - ref["speed"]
        if gap >= 4 or (gap >= 2 and gap / ref["speed"] >= 0.03):
            add("entry_too_fast", 0.3 + 0.4 * min(1.0, gap / 15) + (0.1 if kind == "off_track" and front_led else 0),
                _ev("inc_ev_speed_vs_ref", kmh=round(v_in), ref=round(ref["speed"]), diff=round(gap)))

    # 7. grip: cold tyres, dirt on the tyres, lower grip usage than usual
    t_ev = _tyre_temp_at(lap, i0, on)
    med_t = gctx.get("median_tyre_temp")
    if t_ev is not None and med_t is not None and t_ev < med_t - 10:
        add("low_grip", 0.3 + 0.2 * min(1.0, (med_t - t_ev - 10) / 25),
            _ev("inc_ev_cold_tyres", temp=round(t_ev), ref=round(med_t)))
    if lap.number <= 1 or (lap.lap_time is not None and np.median([l.lap_time for l in all_laps if l.lap_time] or [0]) > 0
                           and lap.lap_time > 1.12 * np.median([l.lap_time for l in all_laps if l.lap_time])):
        if t_ev is not None and med_t is not None and t_ev < med_t - 4:
            add("low_grip", 0.1, _ev("inc_ev_early_lap"))
    dirt_pre = _avg_cols(lap, "Dirt", WHEELS, max(0, on - int(2 * hz)), on)
    if dirt_pre is not None and dirt_pre > 0.1 and kind != "off_track":
        add("low_grip", 0.25, _ev("inc_ev_dirty_tyres", lvl=round(dirt_pre, 2)))
    sg = _col(lap.df, "SurfaceGrip")
    if sg is not None and np.nanmin(sg[max(0, on - 5):on + 1]) < 95:
        add("low_grip", 0.3, _ev("inc_ev_surface_grip", pct=round(float(np.nanmin(sg[max(0, on - 5):on + 1])))))
    if ref and ref.get("latg") and latg_on is not None and is_rotation and latg_on < 0.85 * ref["latg"] and ref["latg"] > 0.6:
        add("low_grip", 0.25, _ev("inc_ev_less_latg", g=round(latg_on, 2), ref=round(ref["latg"], 2)))

    # 8. kerb / bump
    vg = lap.vert_g
    if vg is not None:
        base = np.nanmedian(np.abs(vg))
        spike = float(np.max(np.abs(vg[ip:i1 + 1] - np.median(vg))))
        if spike > max(0.9, 6 * base + 0.5):
            add("kerb_or_bump", 0.35 + 0.2 * min(1.0, (spike - 0.9) / 1.5), _ev("inc_ev_vert_spike", g=round(spike, 2)))
    else:
        for pref in ("SuspTravel",):
            cols = [c for c in (f"{pref}{w}" for w in WHEELS) if c in lap.df.columns]
            if cols:
                rate = np.max([np.abs(np.gradient(_filled(_col(lap.df, c)), 1.0 / hz)) for c in cols], axis=0)
                p99 = float(np.percentile(rate, 99.5))
                pk = float(rate[ip:i1 + 1].max())
                if p99 > 0 and pk >= p99 and pk > 400:
                    add("kerb_or_bump", 0.3, _ev("inc_ev_susp_spike", mms=round(pk)))

    # 9. downshift (engine braking) on the rear axle
    if lap.gear is not None and is_rotation:
        g = lap.gear[max(0, on - int(0.8 * hz)):on + 1]
        if g.size > 2 and g[0] > g[-1] >= 1 and (thr_on or 0) < 15 and (brk_on or 0) < 15:
            add("downshift", 0.4, _ev("inc_ev_downshift", a=int(g[0]), b=int(g[-1])))

    # 10. wind: only its strength is known (direction frames differ between sims)
    ws = _col(lap.df, "WindSpeed")
    if ws is not None:
        w = float(np.nanmedian(ws[max(0, on - 5):on + 1]))
        context["wind_kmh"] = round(w, 0)
        if w >= 15 and speed_on >= 150 and (latg_on or 0) < 0.8:
            add("wind", 0.15 + 0.2 * min(1.0, (w - 15) / 30), _ev("inc_ev_wind", kmh=round(w), speed=round(speed_on)))

    # off-track by understeer: front-led with no rotation
    if kind == "off_track" and front_led:
        add("understeer_off", 0.4, _ev("inc_ev_front_slip", front=round(sa_f, 1), rear=round(sa_r or 0, 1)))
    if kind == "off_track" and steer_on is not None and latg_on is not None and ref and ref.get("latg"):
        if latg_on >= 0.9 * ref["latg"]:
            add("understeer_off", 0.2, _ev("inc_ev_grip_limit", g=round(latg_on, 2), ref=round(ref["latg"], 2)))

    out = sorted(causes.values(), key=lambda c: c["score"], reverse=True)
    return out, context


def _confidence(score: float, margin: float) -> str:
    if score >= 0.7 and margin >= 0.15:
        return "high"
    return "medium" if score >= 0.45 else "low"


def _localize(causes: List[dict]) -> List[dict]:
    res = []
    for i, c in enumerate(causes[:4]):
        if c["score"] < 0.25:
            continue
        nxt = causes[i + 1]["score"] if i + 1 < len(causes) else 0.0
        res.append({
            "code": c["code"], "score": round(c["score"], 2),
            "confidence": _confidence(c["score"], c["score"] - nxt),
            "label": _tr(f"inc_cause_{c['code']}"),
            "advice": _tr(f"inc_advice_{c['code']}"),
            "evidence": [{"text": _tr(e["key"], **e["values"]), **e["values"]} for e in c["evidence"]],
        })
    return res


# ── assembly ─────────────────────────────────────────────────────────────────────────────
def _corner_at(cmap: Optional[dict], dist_m: float, lap_len: float) -> Optional[dict]:
    if not cmap or not cmap.get("corners"):
        return None
    L = (cmap.get("summary") or {}).get("lap_length_m") or lap_len
    scale = lap_len / L if L else 1.0
    best, best_d = None, 1e9
    for c in cmap["corners"]:
        a, b, ap = c.get("start_m"), c.get("end_m"), c.get("apex_distance_m")
        if a is None or b is None or ap is None:
            continue
        a, b, ap = a * scale, b * scale, ap * scale
        if a - 40 <= dist_m <= b + 40:
            d = abs(dist_m - ap)
            if d < best_d:
                best, best_d = c, d
    if best is None:
        return None
    return {"number": best.get("number"), "name": best.get("name"), "kind": best.get("kind")}


def _trace(lap: _Lap, onset: int, beta: Optional[np.ndarray]) -> dict:
    i0 = max(0, onset - int(TRACE_PRE_S * lap.hz))
    i1 = min(lap.n, onset + int(TRACE_POST_S * lap.hz))
    idx = np.unique(np.linspace(i0, i1 - 1, min(TRACE_POINTS, i1 - i0)).astype(int))
    t0 = lap.t[onset]

    def pick(a, nd=1):
        return None if a is None else [round(float(x), nd) for x in a[idx]]
    return {"t": [round(float(x), 2) for x in (lap.t[idx] - t0)], "speed": pick(lap.speed), "throttle": pick(lap.throttle, 0),
            "brake": pick(lap.brake, 0), "steer": pick(lap.steer, 0), "slip": pick(beta), "lat_g": pick(lap.latg, 2)}


def _severity(ev: dict) -> str:
    if ev["kind"] == "spin":
        return "major" if (ev.get("min_speed_kmh", 99) < 10 or ev.get("rotation_deg", 0) > 270) else "moderate"
    if ev["kind"] == "slide":
        return "minor"
    pk = ev.get("off_track", {}).get("peak_dirt")
    dur = ev.get("off_track", {}).get("duration_s", 0)
    if pk is None:
        return "major" if dur >= 3 else "moderate" if dur >= 1.2 else "minor"
    return "major" if (pk >= DIRT_MAJOR and dur >= 2) else "moderate" if (pk >= 0.5 or dur >= 1.5) else "minor"


def detect_incidents(laps: List[pd.DataFrame], cmap: Optional[dict] = None, lap_numbers: Optional[List[int]] = None) -> dict:
    """Detect spins, big slides and off-track excursions in a session and diagnose them.

    ``laps``: the per-lap frames (as segmented by the stint analysis). ``lap_numbers``: 1-based number of
    each frame in the session (default: position + 1). Never raises: returns ``{"available": False}``."""
    try:
        return _detect(laps, cmap, lap_numbers)
    except Exception as exc:  # incident analysis must never break a session analysis
        logger.warning("incidents: %s", exc, exc_info=True)
        return {"available": False}


def _detect(frames: List[pd.DataFrame], cmap: Optional[dict], lap_numbers: Optional[List[int]]) -> dict:
    frames = [f for f in frames if f is not None and len(f) > 20]
    if not frames:
        return {"available": False}
    nums = lap_numbers or list(range(1, len(frames) + 1))
    laps = [_Lap(f, n) for f, n in zip(frames, nums)]
    ref_line = _build_ref_line(laps)
    gctx = _grip_context(laps)
    sources = {"slip": "none", "off_track": "none"}
    raw_events: List[tuple] = []
    betas: Dict[int, Optional[np.ndarray]] = {}

    for lap in laps:
        beta, src = _slip_signal(lap, {})
        if beta is not None:
            beta = _normalise_beta_sign(lap, beta, src)
        betas[lap.number] = beta
        if sources["slip"] == "none" or src == "body_velocity":
            sources["slip"] = src if beta is not None else sources["slip"]
        slides = _detect_slides(lap, beta, src)
        offs, osrc = _detect_offtrack(lap, ref_line)
        if osrc != "none":
            sources["off_track"] = osrc
        for s in slides:
            raw_events.append((lap, src, s, "rot"))
        for o in offs:
            raw_events.append((lap, src, o, "off"))

    # merge a rotation and an off-track of the same lap that are close in time
    events: List[dict] = []
    by_lap: Dict[int, list] = {}
    for item in raw_events:
        by_lap.setdefault(item[0].number, []).append(item)
    for number, items in by_lap.items():
        lap = items[0][0]
        rots = [i for i in items if i[3] == "rot"]
        offs = [i for i in items if i[3] == "off"]
        used = set()
        for lp, src, r, _ in rots:
            ev = {"lap_obj": lp, "src": src, "kind": r["kind"], "onset": r["onset"], "peak": r["peak"], "end": r["end"],
                  "peak_slip_deg": r["peak_slip_deg"]}
            for k, (_, _, o, _) in enumerate(offs):
                if k in used:
                    continue
                if o["onset"] <= r["end"] + LINK_S * lp.hz and o["end"] >= r["onset"] - LINK_S * lp.hz:
                    used.add(k)
                    ev["off_track"] = {kk: o[kk] for kk in ("peak_dirt", "wheels", "duration_s") if kk in o}
                    ev["end"] = max(ev["end"], o["end"])
            events.append(ev)
        for k, (lp, src, o, _) in enumerate(offs):
            if k in used:
                continue
            events.append({"lap_obj": lp, "src": src, "kind": "off_track", "onset": o["onset"], "peak": o["peak"], "end": o["end"],
                           "off_track": {kk: o[kk] for kk in ("peak_dirt", "wheels", "duration_s", "peak_offset_m") if kk in o}})

    events.sort(key=lambda e: (e["lap_obj"].number, e["onset"]))
    merged: List[dict] = []
    for e in events:
        prev = merged[-1] if merged else None
        if (prev is not None and e["kind"] == "off_track" and e["lap_obj"].number == prev["lap_obj"].number + 1
                and prev["end"] >= prev["lap_obj"].n - 1 - LINK_S * prev["lap_obj"].hz and e["onset"] <= LINK_S * e["lap_obj"].hz):
            o, n = prev.get("off_track"), e["off_track"]       # the excursion crosses the start/finish line
            prev["off_track"] = n if o is None else {
                **o, "duration_s": round(o.get("duration_s", 0) + n.get("duration_s", 0), 2),
                "peak_dirt": max(o.get("peak_dirt") or 0, n.get("peak_dirt") or 0) or None,
                "wheels": max(o.get("wheels") or 0, n.get("wheels") or 0) or None}
            continue
        merged.append(e)
    events = merged
    clean_times = [l.lap_time for l in laps if l.lap_time and not any(e["lap_obj"] is l for e in events)]
    median_clean = float(np.median(clean_times)) if clean_times else None
    out = []
    for ev in sorted(events, key=lambda e: (e["lap_obj"].number, e["onset"])):
        lap = ev["lap_obj"]
        beta = betas.get(lap.number)
        on, end = ev["onset"], ev["end"]
        if ev["kind"] != "off_track" and lap.yaw is not None:
            ev["rotation_deg"] = round(float(abs(np.sum(lap.yaw[on:ev["peak"] + int(1.5 * lap.hz)]) / lap.hz)), 0)
            if ev["kind"] == "slide" and ev["rotation_deg"] >= SPIN_ROTATION_DEG:
                ev["kind"] = "spin"
        ev["min_speed_kmh"] = round(float(lap.speed[on:end + 1].min()), 1)
        dist = float(lap.dist[on])
        ref = _ref_stats(laps, lap, dist)
        causes, context = _diagnose(lap, ev, beta, ev["src"], ref, gctx, laps)
        loc = _corner_at(cmap, dist, lap.length)
        went_off = "off_track" in ev
        sev = _severity({**ev, "off_track": ev.get("off_track", {})})
        if ev["kind"] == "slide" and went_off:
            sev = "moderate"
        inv = _col(lap.df, "LapInvalid")
        delta = None
        if lap.lap_time and median_clean:
            delta = round(lap.lap_time - median_clean, 2)
            delta = delta if delta > 0 else None      # a spin lap cannot be faster than a clean one: the reference is not usable
        loc_name = (loc or {}).get("name")
        primary = causes[0]["code"] if causes else None
        loc_ref = ({"corner_number": loc.get("number"), "corner_name": loc_name, "corner_kind": loc.get("kind")}
                   if loc else {})
        out.append({
            "id": f"L{lap.number}-{on}", "lap": lap.number, "kind": ev["kind"], "went_off": went_off,
            "severity": sev, "t_s": round(float(lap.t[on]), 2), "distance_m": round(dist, 0),
            "fraction": round(dist / lap.length, 4) if lap.length else None,
            "duration_s": round(float((lap.t[end] - lap.t[on])), 2),
            "peak_slip_deg": ev.get("peak_slip_deg"), "rotation_deg": ev.get("rotation_deg"),
            "min_speed_kmh": ev["min_speed_kmh"], "off_track": ev.get("off_track"),
            "lap_time_s": lap.lap_time, "lap_delta_s": delta,
            "lap_invalidated": bool(inv is not None and np.nanmax(inv) > 0),
            "corner": loc_ref or None, "context": context,
            "primary_cause": primary, "causes": _localize(_with_codes(causes)),
            "trace": _trace(lap, on, beta),
        })

    out_summary = _summary(out, laps, sources)
    return {"available": True, "events": out, "summary": out_summary, "sources": sources}


def _with_codes(causes: List[dict]) -> List[dict]:
    return causes


def _summary(events: List[dict], laps: List[_Lap], sources: dict) -> dict:
    kinds: Dict[str, int] = {}
    codes: Dict[str, int] = {}
    corners: Dict[str, dict] = {}
    for e in events:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        if e["causes"]:
            codes[e["causes"][0]["code"]] = codes.get(e["causes"][0]["code"], 0) + 1
        c = e.get("corner")
        key = (f"{c['corner_number']}" if c and c.get("corner_number") is not None else f"d{int(e['distance_m'] // 100) * 100}")
        slot = corners.setdefault(key, {"corner": c, "distance_m": e["distance_m"], "count": 0, "laps": []})
        slot["count"] += 1
        slot["laps"].append(e["lap"])
    hot = sorted((v for v in corners.values() if v["count"] >= 2), key=lambda v: -v["count"])
    laps_with = sorted({e["lap"] for e in events})
    return {"n_events": len(events), "by_kind": kinds, "top_causes": codes, "hot_spots": hot[:5],
            "n_laps": len(laps), "n_laps_with_incident": len(laps_with), "laps_with_incident": laps_with,
            "slip_source": sources["slip"], "off_track_source": sources["off_track"],
            "wind_logged": any(_col(l.df, "WindSpeed") is not None for l in laps)}
