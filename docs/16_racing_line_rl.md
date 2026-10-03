# 16 - Racing Line Optimisation (Tabular Q-Learning)

[Ver en Español](./16_racing_line_rl.es.md)

**Module:** `src/analytics/racing_line_rl.py`
**Main function:** `optimizar_trazada_rl(dfs, df_laps, precomputed_obs=None)`
**Observation source:** `get_corner_observations` in `src/analytics/session_corner_analysis.py`
**Dependencies:** NumPy only (no RL framework)
**Reconciled with the code:** 2026-10-03 (EN and ES versions share the same structure)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Method](#2-method)
3. [Training Procedure](#3-training-procedure)
4. [Output Schema](#4-output-schema)
5. [Interpretation Guide](#5-interpretation-guide)
6. [Limitations](#6-limitations)
7. [Constants Reference](#7-constants-reference)
8. [Verification Status](#8-verification-status)

---

## 1. Overview

For every corner detected in a session, the module looks at how each lap executed three phases of the corner (braking point, apex speed, throttle application) relative to the session's fastest lap, and finds which discretised combination of those three phases was associated with the smallest time loss. It then compares that combination with the driver's recent execution and reports the estimated time gain and a plain-language recommendation.

Honest characterisation: the "agent" is a per-corner table of 27 cells holding an exponentially weighted average of observed rewards. Because the discount factor is 0 and the "action" is the observed execution itself, there is no sequential decision problem: it is an empirical, order-dependent, per-state running mean followed by an argmax (a contextual-bandit-style summary). Calling it "reinforcement learning" is a modelling convention, not evidence that an optimal policy is being discovered. The output must be read as "in which execution pattern was this driver fastest in this corner, in this session", not as a physical optimum.

---

## 2. Method

### 2.1 State space

Three deltas relative to the reference lap are discretised with `numpy.digitize` into three bins each (3 x 3 x 3 = 27 cells per corner):

| Dimension | Raw signal | Edges | Bin 0 / 1 / 2 labels |
|---|---|---|---|
| Brake point | `brake_delta` (m) | -10, +10 | `early`, `similar`, `late` |
| Apex speed | `apex_delta` (km/h) | -3, +3 | `slow`, `similar`, `fast` |
| Throttle application | `thtl_delta` (m) | -8, +8 | `late`, `similar`, `early` |

`digitize` semantics: value < lower edge gives bin 0; lower <= value < upper gives bin 1; value >= upper gives bin 2.

Definitions of the deltas (from `get_corner_observations`, lap minus reference):

- `brake_delta` = braking-point distance of the lap minus that of the reference (positive = braked later in the lap).
- `apex_delta` = apex speed of the lap minus reference apex speed (positive = faster).
- `thtl_delta` = full-throttle distance of the lap minus the reference's (positive = full throttle reached later).

Throttle axis (fixed 2026-10-03): `detect_full_throttle_points` returns the distance at which full throttle is first reached after a corner, so `thtl_delta` is (lap distance) minus (reference distance) and a positive value means full throttle was reached LATER. Bin 2 (positive delta) is now labelled `late` and bin 0 `early`; a higher optimal bin than the current one produces `rl_throttle_later`, a lower one `rl_throttle_earlier`. Previously the labels and both recommendations were inverted.

### 2.2 Reward and update rule

```
reward = -time_loss_s          (time_loss_s > 0: lap slower than reference in this corner)
Q[s] <- reward                         on the first visit of cell s
Q[s] <- Q[s] + 0.4 * (reward - Q[s])   on later visits
```

With `gamma = 0` the target is just the immediate reward; no successor state exists. Unvisited cells stay `NaN` and are never selected as optimal.

`time_loss_s` comes from `_estimate_corner_time_loss` (in `src/telemetry/lap_comparator.py`): between the earlier of the two braking points and the later of the two full-throttle points, it integrates `ds * (1/v_lap - 1/v_ref)` on the distance-aligned speeds (speed floor 1 m/s). It can be negative if the lap was faster than the reference in that corner.

### 2.3 Policy extraction

```
opt = argmax over visited cells of Q[brake_bin, apex_bin, thtl_bin]
```

There is no minimum visit count: a cell visited by a single lap can win.

---

## 3. Training Procedure

1. **Reference lap.** Among flying laps (not `is_pit_lap`, with `lap_time_s`), the one with the minimum time. At least 2 flying laps are required; otherwise there are no observations.
2. **Observation extraction** (skipped when `precomputed_obs` is given, which `main.py` does by passing the observations already computed for the corner analysis). For every other flying lap: only the channels `Distance`, `Speed`, `Brake`, `Throttle` are kept; the lap and the reference are aligned by distance (`align_pair`); corners are detected on each (`segment_corners`); corners of the lap are paired with those of the reference **by apex proximity** (`pair_corners`, maximum apex gap 150 m), not by index. The corner number is the 1-based index of the corner in the reference lap. Laps that raise an exception are skipped.
3. **Training per corner.** Corners with fewer than 2 observations are skipped. A fresh agent runs 30 epochs over the corner's observations in lap order, applying the update rule of 2.2. Because the replay order is fixed, each cell's value is a recency-weighted average of its observations (the most recent one in the cell weighs most).
4. **Current execution profile.** Last 3 observations (or all if fewer): the bin index of each axis is averaged over them, rounded with Python `round`, and clamped to [0, 2]. This is a rounded mean of bin indices, not a mode, and it can land in a cell that no lap actually visited.
5. **Potential gain.**

```
current_q      = Q[current cell]; if that cell is NaN: mean(-time_loss) over all the corner's observations
potential_gain = max(0, Q[opt] - current_q)
total          = sum of potential_gain over corners
```

6. **Recommendations**: per axis where the optimal bin differs from the current one, one localized message (`rl_brake_later/earlier`, `rl_apex_faster/slower`, `rl_throttle_earlier/later`); if none differ, `rl_already_optimal`.

---

## 4. Output Schema

When data are insufficient the payload is `{"available": false, "reason": "..."}` with one of two English, non-localized strings: `no corner observations extracted` (fewer than 2 flying laps or no corners paired) or `all corners had <2 observations`. A corner is silently omitted if it has fewer than 2 observations; `available` is false only when every corner is omitted.

```json
{
  "available": true,
  "n_corners": 8,
  "total_potential_gain_s": 0.412,
  "corners": [
    {
      "corner_number": 5,
      "n_laps": 18,
      "mean_time_loss_s": 0.087,
      "potential_gain_s": 0.063,
      "current_execution": {"brake": "late", "apex": "slow", "exit": "late"},
      "optimal_execution": {"brake": "similar", "apex": "similar", "exit": "early"},
      "already_optimal": false,
      "recommendations": ["Brake earlier", "Carry more apex speed", "Apply throttle earlier"],
      "q_heatmap": [{"brake": "early", "apex": "slow", "q": -0.041, "count": 90}]
    }
  ]
}
```

Top level: `available`, `n_corners` (corners with at least 2 observations), `total_potential_gain_s` (sum of per-corner gains, rounded to 3 decimals), `corners` (sorted by `potential_gain_s` descending).

Per corner: `corner_number`, `n_laps` (observations, which is at most the number of flying laps minus 1 because the reference is not compared with itself), `mean_time_loss_s`, `potential_gain_s`, `current_execution`, `optimal_execution` (labels per `brake` / `apex` / `exit`), `already_optimal`, `recommendations`, `q_heatmap`.

`q_heatmap` has 9 cells (brake x apex); `q` is the best Q over the three throttle bins (or `null` if unvisited) and `count` is the number of real observations (laps) in those cells. Fixed 2026-10-03: previously the counter was also incremented on each of the 30 training epochs, so `count` was 30 x the number of observations.

---

## 5. Interpretation Guide

- **`potential_gain_s`** is the number to act on: the estimated time recoverable at that corner by moving to the learned best pattern. Corners are sorted by it.
- **`current_execution` vs `optimal_execution`** shows the direction of the change. Remember the current profile is a rounded mean of bins.
- **`mean_time_loss_s`** gives context: a big gain with a small mean loss usually means a few outlier laps; a big mean loss with a big gain is a consistent weakness.
- **`q_heatmap`**: values are negative time loss in seconds; closer to zero is better; `null` means no evidence.
- **`total_potential_gain_s`** is an optimistic upper bound: it sums independent corners (no interaction), and the argmax over 27 noisy cells is biased upwards (a cell that was lucky once wins).

---

## 6. Limitations

- **Sparse data.** 27 cells per corner versus typically 5-30 laps: most cells are empty and winners may rest on one lap. `count` in the heatmap is the real number of observations, so a count of 1 means exactly one lap.
- **Corner pairing by apex proximity** (150 m) can still mismatch if a corner is not detected on some laps; there is no compensation for track-limit, weather or kerb changes within the session.
- **Independence between corners** (`gamma = 0`) ignores the exit-to-entry coupling of chicanes and S-sections.
- **Reference dependence.** All deltas are relative to the single fastest lap of the session; anomalies in that lap bias everything. No cross-session normalisation.
- **Coarse bins** (3 per axis) were chosen to keep the table fillable from one session.
- **No causal inference.** Fuel load, tyre state and temperature are not controlled for.
- **Offline.** Nothing updates within a stint unless the function is called again with new data.
- **Throttle axis:** `early`/`late` now follow the sign of `thtl_delta` (negative = earlier, positive = later), see 2.1.

---

## 7. Constants Reference

| Constant | Value |
|---|---|
| `_BRAKE_BINS` | [-10, 10] m |
| `_APEX_BINS` | [-3, 3] km/h |
| `_THTL_BINS` | [-8, 8] m |
| `_LR` (alpha) | 0.4 |
| `_GAMMA` | 0.0 (declared; not used in the update) |
| `_EPOCHS` | 30 |
| Minimum observations per corner | 2 |
| Recent laps for the current profile | 3 |
| `PAIR_MAX_APEX_GAP_M` (in `src/telemetry/metrics.py`) | 150 m |

---

## 8. Verification Status

Formulas, constants, keys and the `count` behaviour were checked against the code on 2026-10-03. The `count` inflation (30 per observation) and the inverted throttle-axis labels/recommendations were reproduced with synthetic tests and fixed the same day (`tests/test_advisor_rl_fixes.py`); on the real Imola/Spa logs the throttle advice flipped direction. Not verifiable from the code: the usefulness of the recommendations as coaching advice (no validation against real lap-time improvements exists in the repository).
