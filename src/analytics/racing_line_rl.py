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

from src.i18n import _ as _tr

logger = logging.getLogger(__name__)

# ── Discretisation bins ───────────────────────────────────────────────────────
# brake_delta_meters:   negative = braked earlier than ref, positive = later
_BRAKE_BINS  = [-10.0, 10.0]   # → 3 bins: early / similar / late
# apex_speed_delta_kmh: negative = slower than ref, positive = faster
_APEX_BINS   = [-3.0,  3.0]    # → 3 bins: slow / similar / fast
# thtl_delta: distance (m) at which full throttle is reached, versus the reference lap.
# Positive = full throttle reached LATER (further along the lap); negative = EARLIER.
_THTL_BINS   = [-8.0,  8.0]    # → 3 bins: early / similar / late (bin index grows with distance)

_BIN_LABELS_BRAKE  = ['early', 'similar', 'late']
_BIN_LABELS_APEX   = ['slow',  'similar', 'fast']
_BIN_LABELS_THTL   = ['early', 'similar', 'late']

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

    def update(self, bb: int, ab: int, tb: int, reward: float, count: bool = True):
        """Q update. ``count=False`` for repeated training epochs, so ``counts`` holds the
        number of real observations per cell and not observations x epochs."""
        idx = (bb, ab, tb)
        if np.isnan(self.Q[idx]):
            self.Q[idx] = reward
        else:
            self.Q[idx] += _LR * (reward - self.Q[idx])
        if count:
            self.counts[idx] += 1

    def best_state(self):
        """(brake_bin, apex_bin, thtl_bin) with highest Q (NaN states ignored)."""
        masked = np.where(np.isnan(self.Q), -np.inf, self.Q)
        flat   = int(np.argmax(masked))
        return np.unravel_index(flat, self.Q.shape)

    def best_q(self) -> float:
        valid = self.Q[~np.isnan(self.Q)]
        return float(np.max(valid)) if len(valid) else 0.0


def _get_per_lap_observations(dfs: list, df_laps, corner_map: dict | None = None):
    """
    Re-run corner extraction for each flying lap and return raw per-corner
    observations: {corner_idx: [{time_loss, brake_delta, apex_delta, thtl_delta}]}
    (with ``corner_map``: measured in the windows of the unified corner map, keyed by its numbers)
    """
    from src.analytics.session_corner_analysis import get_corner_observations
    return get_corner_observations(dfs, df_laps, corner_map=corner_map)


def optimizar_trazada_rl(dfs: list, df_laps, precomputed_obs: dict | None = None,
                         corner_map: dict | None = None) -> dict:
    """
    Train a Q-learning agent per corner using historical lap observations.

    Args:
        dfs:              Per-lap DataFrames.
        df_laps:          Lap metrics DataFrame.
        precomputed_obs:  If provided (from get_corner_observations), skip re-aligning.
        corner_map:       Unified corner map (used only when the observations are not precomputed).

    Returns per-corner optimal execution recommendations and the potential
    time gain if the driver executes closer to the learned optimal.
    """
    if precomputed_obs is not None:
        logger.info("racing_line_rl: using pre-computed observations (%d corners)", len(precomputed_obs))
        obs = precomputed_obs
    else:
        logger.info("racing_line_rl: extracting per-lap corner observations…")
        obs = _get_per_lap_observations(dfs, df_laps, corner_map=corner_map)

    if not obs:
        return {"available": False, "reason": "no corner observations extracted"}

    results = []
    total_potential = 0.0

    for corner_num in sorted(obs.keys()):
        laps = obs[corner_num]
        if len(laps) < 2:
            continue
        # Unified corner map: a flat_out / kink corner has no braking point, apex or throttle
        # application to optimise, so it is not trained (its time loss stays in curvas_sesion).
        if laps[0].get("kind") in ("flat_out", "kink"):
            continue
        # Deltas that could not be measured in a lap (None) count as "similar" (0.0): no information.
        laps = [{**l, **{k: (0.0 if l.get(k) is None else l[k])
                         for k in ("brake_delta", "apex_delta", "thtl_delta")}} for l in laps]

        agent = _CornerAgent()

        for epoch in range(_EPOCHS):
            for lap in laps:
                bb = _bin(lap['brake_delta'], _BRAKE_BINS)
                ab = _bin(lap['apex_delta'],  _APEX_BINS)
                tb = _bin(lap['thtl_delta'],  _THTL_BINS)
                # Reward = negative time loss (higher = better execution)
                reward = -lap['time_loss']
                agent.update(bb, ab, tb, reward, count=(epoch == 0))

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
            recs.append(_tr("rl_brake_later") if opt_bb > mean_bb else _tr("rl_brake_earlier"))
        if opt_ab != mean_ab:
            recs.append(_tr("rl_apex_faster") if opt_ab > mean_ab else _tr("rl_apex_slower"))
        if opt_tb != mean_tb:
            recs.append(_tr("rl_throttle_later") if opt_tb > mean_tb else _tr("rl_throttle_earlier"))

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
            "recommendations":  recs if recs else [_tr("rl_already_optimal")],
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
