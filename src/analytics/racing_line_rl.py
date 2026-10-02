"""
Racing line optimisation via offline Q-learning.

For each corner detected in the session, a Q-table is trained over the
historical lap observations (brake point, apex speed, throttle application).
The agent learns which execution pattern produced the least time loss, then
reports the gap between the driver's average execution and the optimal.

No external RL framework required — pure NumPy tabular Q-learning.
"""
import logging
from collections import defaultdict

import numpy as np

logger = logging.getLogger(__name__)

# ── Discretisation bins ───────────────────────────────────────────────────────
# brake_delta_meters:   negative = braked earlier than ref, positive = later
_BRAKE_BINS  = [-10.0, 10.0]   # → 3 bins: early / similar / late
# apex_speed_delta_kmh: negative = slower than ref, positive = faster
_APEX_BINS   = [-3.0,  3.0]    # → 3 bins: slow / similar / fast
# throttle_delta_meters: positive = full-throttle zone longer (earlier application)
_THTL_BINS   = [-8.0,  8.0]    # → 3 bins: late / similar / early

_BIN_LABELS_BRAKE  = ['early', 'similar', 'late']
_BIN_LABELS_APEX   = ['slow',  'similar', 'fast']
_BIN_LABELS_THTL   = ['late',  'similar', 'early']

# Q-learning hyper-parameters
_LR      = 0.4   # learning rate
_GAMMA   = 0.0   # no future discount — each corner is independent
_EPOCHS  = 30    # passes over the dataset


def _bin(val: float, edges: list) -> int:
    return int(np.digitize(val, edges))   # 0, 1, or 2


class _CornerAgent:
    """Tabular Q-agent for one corner's 3-phase execution."""

    N_BRAKE = N_APEX = N_THTL = 3

    def __init__(self):
        # Q[brake_bin, apex_bin, thtl_bin] = expected negative time-loss (higher = better)
        self.Q      = np.full((self.N_BRAKE, self.N_APEX, self.N_THTL), np.nan)
        self.counts = np.zeros((self.N_BRAKE, self.N_APEX, self.N_THTL), dtype=int)

    def update(self, bb: int, ab: int, tb: int, reward: float):
        idx = (bb, ab, tb)
        if np.isnan(self.Q[idx]):
            self.Q[idx] = reward
        else:
            self.Q[idx] += _LR * (reward - self.Q[idx])
        self.counts[idx] += 1

    def best_state(self):
        """(brake_bin, apex_bin, thtl_bin) with highest Q (NaN states ignored)."""
        masked = np.where(np.isnan(self.Q), -np.inf, self.Q)
        flat   = int(np.argmax(masked))
        return np.unravel_index(flat, self.Q.shape)

    def best_q(self) -> float:
        valid = self.Q[~np.isnan(self.Q)]
        return float(np.max(valid)) if len(valid) else 0.0


def _get_per_lap_observations(dfs: list, df_laps):
    """
    Re-run corner extraction for each flying lap and return raw per-corner
    observations: {corner_idx: [{time_loss, brake_delta, apex_delta, thtl_delta}]}
    """
    from src.processing.alignment import align_pair
    from src.telemetry.lap_comparator import _estimate_corner_time_loss
    from src.telemetry.metrics import segment_corners

    if 'is_pit_lap' in df_laps.columns:
        flying = df_laps[~df_laps['is_pit_lap'] & df_laps['lap_time_s'].notna()]
    else:
        flying = df_laps[df_laps['lap_time_s'].notna()]

    if len(flying) < 2:
        return {}

    ref_idx = int(flying['lap_time_s'].idxmin())
    ref_df  = dfs[ref_idx]

    obs: dict = defaultdict(list)

    for idx in flying.index:
        if idx == ref_idx:
            continue
        lap_df = dfs[idx]
        try:
            al_a, al_b = align_pair(ref_df, lap_df)
            corners_a  = segment_corners(al_a)
            corners_b  = segment_corners(al_b)
            n = min(len(corners_a), len(corners_b))
            for i in range(n):
                ca, cb = corners_a[i], corners_b[i]
                tl = _estimate_corner_time_loss(al_a, al_b, ca, cb)
                obs[i + 1].append({
                    "time_loss":    float(tl),
                    "brake_delta":  float(cb["braking_point"]["distance"] - ca["braking_point"]["distance"]),
                    "apex_delta":   float(cb["apex"]["speed"] - ca["apex"]["speed"]),
                    "thtl_delta":   float(cb["full_throttle"]["distance"] - ca["full_throttle"]["distance"]),
                })
        except Exception as exc:
            logger.debug("rl_obs: idx=%d: %s", idx, exc)

    return dict(obs)


def optimizar_trazada_rl(dfs: list, df_laps, precomputed_obs: dict | None = None) -> dict:
    """
    Train a Q-learning agent per corner using historical lap observations.

    Args:
        dfs:              Per-lap DataFrames.
        df_laps:          Lap metrics DataFrame.
        precomputed_obs:  If provided (from get_corner_observations), skip re-aligning.

    Returns per-corner optimal execution recommendations and the potential
    time gain if the driver executes closer to the learned optimal.
    """
    if precomputed_obs is not None:
        logger.info("racing_line_rl: using pre-computed observations (%d corners)", len(precomputed_obs))
        obs = precomputed_obs
    else:
        logger.info("racing_line_rl: extracting per-lap corner observations…")
        obs = _get_per_lap_observations(dfs, df_laps)

    if not obs:
        return {"available": False, "reason": "no corner observations extracted"}

    results = []
    total_potential = 0.0

    for corner_num in sorted(obs.keys()):
        laps = obs[corner_num]
        if len(laps) < 2:
            continue

        agent = _CornerAgent()

        for _ in range(_EPOCHS):
            for lap in laps:
                bb = _bin(lap['brake_delta'], _BRAKE_BINS)
                ab = _bin(lap['apex_delta'],  _APEX_BINS)
                tb = _bin(lap['thtl_delta'],  _THTL_BINS)
                # Reward = negative time loss (higher = better execution)
                reward = -lap['time_loss']
                agent.update(bb, ab, tb, reward)

        # ── Current driver profile (average of last 3 laps or all) ───────────
        recent = laps[-3:]
        mean_bb = int(round(np.mean([_bin(l['brake_delta'], _BRAKE_BINS) for l in recent])))
        mean_ab = int(round(np.mean([_bin(l['apex_delta'],  _APEX_BINS)  for l in recent])))
        mean_tb = int(round(np.mean([_bin(l['thtl_delta'],  _THTL_BINS)  for l in recent])))
        mean_bb = max(0, min(2, mean_bb))
        mean_ab = max(0, min(2, mean_ab))
        mean_tb = max(0, min(2, mean_tb))

        opt_bb, opt_ab, opt_tb = agent.best_state()
        opt_q     = agent.best_q()

        current_q = agent.Q[mean_bb, mean_ab, mean_tb]
        if np.isnan(current_q):
            current_q = float(np.nanmean(-np.array([l['time_loss'] for l in laps])))

        potential_gain = max(0.0, opt_q - current_q)
        total_potential += potential_gain

        # ── Build human-readable recommendation ──────────────────────────────
        recs = []
        if opt_bb != mean_bb:
            direction = 'later' if opt_bb > mean_bb else 'earlier'
            recs.append(f"Brake {direction}")
        if opt_ab != mean_ab:
            direction = 'faster' if opt_ab > mean_ab else 'slower'
            recs.append(f"Carry more apex speed" if direction == 'faster' else 'Accept lower apex speed — tighter line')
        if opt_tb != mean_tb:
            direction = 'earlier' if opt_tb > mean_tb else 'later'
            recs.append(f"Apply throttle {direction}")

        mean_loss = float(np.mean([l['time_loss'] for l in laps]))
        results.append({
            "corner_number":    corner_num,
            "n_laps":           len(laps),
            "mean_time_loss_s": round(mean_loss, 3),
            "potential_gain_s": round(potential_gain, 3),
            "current_execution": {
                "brake": _BIN_LABELS_BRAKE[mean_bb],
                "apex":  _BIN_LABELS_APEX[mean_ab],
                "exit":  _BIN_LABELS_THTL[mean_tb],
            },
            "optimal_execution": {
                "brake": _BIN_LABELS_BRAKE[int(opt_bb)],
                "apex":  _BIN_LABELS_APEX[int(opt_ab)],
                "exit":  _BIN_LABELS_THTL[int(opt_tb)],
            },
            "already_optimal": (opt_bb == mean_bb and opt_ab == mean_ab and opt_tb == mean_tb),
            "recommendations":  recs if recs else ["Execution already near optimal"],
            # Q-table as 3×3 heatmap data (brake × apex, collapsed over thtl dim)
            "q_heatmap": _build_heatmap(agent),
        })

    if not results:
        return {"available": False, "reason": "all corners had <2 observations"}

    # Sort by potential gain descending
    results.sort(key=lambda r: -r['potential_gain_s'])

    logger.info(
        "racing_line_rl: %d corners, total_potential=%.3fs",
        len(results), total_potential,
    )
    return {
        "available":             True,
        "corners":               results,
        "total_potential_gain_s": round(total_potential, 3),
        "n_corners":             len(results),
    }


def _build_heatmap(agent: _CornerAgent) -> list:
    """
    Collapse Q-table over the throttle dimension (max) and return a
    3×3 list of {brake_label, apex_label, q_value} dicts for the frontend.
    """
    heatmap = []
    for bb in range(3):
        for ab in range(3):
            q_vals = agent.Q[bb, ab, :]
            valid  = q_vals[~np.isnan(q_vals)]
            q_best = float(np.max(valid)) if len(valid) else None
            count  = int(agent.counts[bb, ab, :].sum())
            heatmap.append({
                "brake": _BIN_LABELS_BRAKE[bb],
                "apex":  _BIN_LABELS_APEX[ab],
                "q":     round(q_best, 4) if q_best is not None else None,
                "count": count,
            })
    return heatmap
