# Racing Line Optimization via Reinforcement Learning

## Overview

This module applies offline tabular Q-learning to discover the corner execution pattern — brake point, apex speed, and throttle application — that minimizes lap time contribution for each detected corner in a session. Rather than relying on a physics model or expert annotation, the agent learns empirically from the driver's own historical lap data: it searches across every observed execution variant and converges on the combination that consistently produced the smallest time loss relative to a reference lap.

The approach is deliberately minimal. No external RL framework is required; the entire algorithm is implemented in NumPy. Because each corner is treated as an independent, single-step decision problem (no inter-corner carry-over), the discount factor γ is set to zero and the Bellman equation reduces to a straightforward incremental mean.

Entry point: `src/analytics/racing_line_rl.py`, function `optimizar_trazada_rl`.

---

## Reinforcement Learning Framework

### Problem Formulation

The problem is modeled as a finite, discrete Markov Decision Process (MDP) with a single-step horizon. For corner *c* and lap *k*, the agent observes a state *s* and receives a scalar reward *r* with no successor state:

```
s  = (brake_bin, apex_bin, throttle_bin)   ∈ {0,1,2}³
a  = implicit — the state IS the action taken by the driver
r  = −time_loss_s(k, c)
```

Because the driver's execution is already encoded in the three bins, the "action" and "state" collapse to a single tuple. The agent's task is to identify which tuple achieves the highest expected reward across the observed distribution of laps.

### State Space

Three telemetry deltas are computed relative to the session reference lap (fastest non-pit lap) and then discretized into three bins each, yielding a 3 × 3 × 3 = 27-state space per corner.

| Dimension | Raw signal | Bin edges | Bin labels |
|---|---|---|---|
| Brake point | `brake_delta` (m) | −10, +10 | `early`, `similar`, `late` |
| Apex speed | `apex_delta` (km/h) | −3, +3 | `slow`, `similar`, `fast` |
| Throttle application | `thtl_delta` (m) | −8, +8 | `late`, `similar`, `early` |

Sign conventions:
- **brake_delta > 0** — driver braked later than the reference (deeper into the corner).
- **apex_delta > 0** — driver carried more speed through the apex than the reference.
- **thtl_delta > 0** — the full-throttle zone is longer, meaning throttle was applied earlier.

Discretization uses `numpy.digitize` with the two edges above, producing bin indices 0, 1, 2.

```python
def _bin(val: float, edges: list) -> int:
    return int(np.digitize(val, edges))   # edges=[lo, hi] → bins 0,1,2
```

### Q-Table

The Q-table is a 3 × 3 × 3 array initialized to NaN. NaN serves as a sentinel for unvisited states — it ensures that unobserved execution combinations are never selected as optimal.

```
Q : R^{3×3×3},  Q[b, a, t] = E[reward | brake=b, apex=a, throttle=t]
```

Initial value: `NaN` (unvisited).

### Reward Function

```
r(k, c) = −time_loss_s(k, c)
```

`time_loss_s` is the estimated time delta between the driver lap and the reference lap over corner *c* (positive = slower than reference). Negating it converts "less time lost" into "higher reward", so the agent maximizes reward by minimizing time loss.

### Update Rule

Standard incremental Q-learning with no future discounting (γ = 0):

```
Q[s] ← Q[s] + α · (r − Q[s])
```

With α = 0.4 and γ = 0, this simplifies to an exponentially-weighted moving average of observed rewards for each state. The target value is purely the immediate reward:

```
target = r + γ · max_{s'} Q[s']
       = r + 0 · (·)
       = r
```

This is valid because there is no meaningful causal chain between sequential corners from a learning perspective — corner 3 execution does not constrain corner 4 state in a way that should be discounted.

### Policy Extraction

After training, the optimal policy π* is extracted via argmax over the Q-table, masking NaN states:

```
π*(c) = argmax_{(b,a,t)} Q_c[b, a, t]   subject to Q_c[b,a,t] ≠ NaN
```

In code:

```python
masked = np.where(np.isnan(self.Q), -np.inf, self.Q)
flat   = int(np.argmax(masked))
(opt_b, opt_a, opt_t) = np.unravel_index(flat, self.Q.shape)
```

The resulting triple `(opt_b, opt_a, opt_t)` identifies the execution pattern the agent has learned produces the best outcome, and its human-readable labels are reported as the recommendation.

---

## Training Procedure

Training is offline: the agent never interacts with a live simulation. It replays the session's historical lap observations repeatedly.

**Step 1 — Reference lap selection.**
The flying lap with the minimum recorded `lap_time_s` is designated the reference. All deltas are computed relative to this lap.

**Step 2 — Per-lap observation extraction.**
For each non-reference flying lap:
1. Align the lap's telemetry to the reference via `align_pair` (distance-based resampling).
2. Detect corners in both aligned DataFrames using `segment_corners`.
3. For each matched corner pair *(ref, lap)*:
   - Estimate `time_loss_s` via `_estimate_corner_time_loss`.
   - Compute the three deltas: `brake_delta`, `apex_delta`, `thtl_delta`.
4. Append the observation to the corner's list.

**Step 3 — Q-table training (per corner).**
A fresh `_CornerAgent` is instantiated for each corner. The agent runs 30 epochs over the observation list:

```
for epoch in range(30):
    for lap_obs in corner_observations:
        b = bin(brake_delta)
        a = bin(apex_delta)
        t = bin(thtl_delta)
        r = −time_loss_s
        Q[b,a,t] ← Q[b,a,t] + 0.4 · (r − Q[b,a,t])
```

With 30 epochs and α = 0.4, the per-state estimate converges to within ~1% of the true mean in roughly `log(0.01) / log(1 − 0.4) ≈ 9` visits to that state. For typical session sizes (10–30 laps), this is adequate.

**Step 4 — Current driver profile.**
The driver's recent execution style is estimated from the last three laps (or all laps if fewer):

```
mean_b = round(mean([bin(brake_delta) for lap in recent_laps]))
mean_a = round(mean([bin(apex_delta)  for lap in recent_laps]))
mean_t = round(mean([bin(thtl_delta)  for lap in recent_laps]))
```

Values are clamped to `[0, 2]`.

**Step 5 — Potential gain calculation.**
The potential gain is the Q-value gap between the optimal state and the driver's current state:

```
potential_gain = max(0,  Q[opt_b, opt_a, opt_t] − Q[mean_b, mean_a, mean_t])
```

If the driver's current state was never visited (Q = NaN), the fallback is the session mean reward across all observed laps.

---

## Output Schema

`optimizar_trazada_rl` returns a dictionary with the following structure:

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
      "current_execution": {
        "brake": "late",
        "apex":  "slow",
        "exit":  "late"
      },
      "optimal_execution": {
        "brake": "similar",
        "apex":  "similar",
        "exit":  "early"
      },
      "already_optimal": false,
      "recommendations": [
        "Brake earlier",
        "Accept lower apex speed — tighter line",
        "Apply throttle earlier"
      ],
      "q_heatmap": [
        {"brake": "early",   "apex": "slow",    "q": -0.041, "count": 3},
        {"brake": "early",   "apex": "similar", "q": -0.031, "count": 2},
        ...
      ]
    }
  ]
}
```

**Top-level fields:**

| Field | Type | Description |
|---|---|---|
| `available` | bool | False if fewer than 2 observations were found for any corner |
| `n_corners` | int | Number of corners with sufficient data |
| `total_potential_gain_s` | float | Sum of per-corner potential gains (seconds) |
| `corners` | array | Per-corner results, sorted by `potential_gain_s` descending |

**Per-corner fields:**

| Field | Type | Description |
|---|---|---|
| `corner_number` | int | Corner index (1-based, matched across laps by position) |
| `n_laps` | int | Number of lap observations used for this corner |
| `mean_time_loss_s` | float | Average time loss vs. reference (s) |
| `potential_gain_s` | float | Estimated time saving if driver adopts optimal execution (s) |
| `current_execution` | object | Driver's modal execution in each phase |
| `optimal_execution` | object | Q-table argmax execution in each phase |
| `already_optimal` | bool | True when current and optimal bins coincide on all three axes |
| `recommendations` | array | Human-readable action items; `["Execution already near optimal"]` when no gap |
| `q_heatmap` | array | 9-element 3×3 grid (brake × apex axes, throttle collapsed by max) |

**Q-heatmap fields:**

| Field | Type | Description |
|---|---|---|
| `brake` | string | Brake bin label for this cell |
| `apex` | string | Apex bin label for this cell |
| `q` | float \| null | Best Q-value across the throttle dimension; null if unvisited |
| `count` | int | Number of observations that fell in this (brake, apex) cell |

When `available` is `false`, the payload contains only `available` and `reason` (string).

---

## Interpretation Guide

**`potential_gain_s`** is the most actionable number. It answers: "how much time could this driver reclaim at this corner if they consistently hit the learned optimal execution?" Corners are sorted by this value descending, so the first entry in `corners` is the highest-priority coaching target.

**`current_execution` vs `optimal_execution`** shows the directional gap. A driver showing `brake: "late"` with an optimal of `brake: "earlier"` is habitually over-committing to late braking at a corner where earlier, lighter braking has historically yielded less time loss.

**`mean_time_loss_s`** provides context: a corner with a large potential gain but a small mean time loss suggests occasional poor laps skew the distribution. A corner with a large mean time loss and a large potential gain is a consistent weakness.

**Q-heatmap interpretation:** Values are on the reward scale (negative time loss in seconds). Cells closer to zero represent executions where the driver was close to the reference. More negative values indicate consistently slower execution. Null cells are unvisited — the agent has no evidence about those combinations.

**`total_potential_gain_s`** is an optimistic upper bound. It assumes every corner's optimal is achievable simultaneously without interaction effects. In practice, inter-corner compromises (e.g., exit angle from one corner constrains entry to the next) reduce the realizable gain.

---

## Limitations

**Sparse data.** The Q-table has 27 cells per corner. A 15-lap session distributes observations unevenly: only the driver's habitual execution style accumulates enough visits for a stable estimate. Cells outside the driver's typical range may hold values from one or two laps and should not be treated as reliable. The `count` field in the heatmap exposes this directly — any cell with `count < 3` should be interpreted with caution.

**Corner geometry changes.** The corner index is positional: corner 5 in lap 3 is matched to corner 5 in lap 15 by sequence number, not by world coordinates. If the track limit, weather, or a kerb condition changes mid-session, the observations conflate two different geometric situations. The module has no mechanism to detect or compensate for this.

**Single-step MDP assumption.** Setting γ = 0 decouples corners. This is a reasonable simplification for most circuits, but on tracks with chicanes or fast S-sections, the exit conditions of one corner are the entry conditions of the next. In those cases, the independent-corner model may recommend conflicting strategies on adjacent segments.

**Reference lap dependence.** All deltas are relative to the session's fastest lap. If the fastest lap contains anomalies (e.g., a traffic-affected sector that nonetheless produced the best total time), the deltas are systematically biased. There is no cross-session normalization.

**Discretization resolution.** The three-bin encoding is coarse by design — it keeps the state space small enough to populate from a single session. Finer bins (e.g., five bins per axis) would require substantially more laps to achieve stable Q-estimates and are not recommended below ~50 observations per corner.

**No causal inference.** A high Q-value for `(similar, fast, early)` means that in laps where the driver hit that combination, time loss was low. It does not mean the driver *caused* the low time loss by executing that way — confounders such as track temperature, tyre state, or fuel load are not controlled for. In short sessions with varying conditions this correlation can be misleading.

**Offline-only.** The agent cannot adapt within a stint. The recommendation reflects the best pattern observed across the session so far; it does not update lap-by-lap during a race or qualifying run unless the function is called again with updated data.
