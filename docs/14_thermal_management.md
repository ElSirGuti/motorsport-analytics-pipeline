# 14 — Thermal Management Analysis

## Overview

The thermal management module (`src/analytics/thermal_management.py`) provides a unified, sim-agnostic analysis layer for the four thermal domains that most directly affect lap time and reliability in a racing context: engine fluid temperatures (coolant and oil), brake temperatures at each corner, tyre operating pressures, and brake bias distribution. The module is invoked at the stint level through `analizar_termica`, which receives one telemetry `DataFrame` per lap, aggregates results across all laps, and returns a single structured dictionary that the rest of the pipeline can surface through the API or the session dashboard.

Thermal management is arguably the highest-leverage area for a race engineer between sessions. A 10 °C deviation in brake temperature from the optimal window does not merely affect feel; it shifts friction coefficient by a measurable amount, accelerates pad and rotor wear, and increases the probability of fluid vaporisation under heavy braking. Similarly, a tyre starting at the wrong cold inflation pressure will build heat unevenly across the carcass, degrading contact-patch geometry and altering the effective load sensitivity of the tyre in ways that make classical setup adjustments less predictable. The module encodes established engineering thresholds derived from endurance and GT racing practice and translates raw telemetry numbers into explicit, actionable recommendations — whether that is closing a brake duct by one position, lowering a cold tyre pressure by 0.08 bar, or reducing front brake bias by 2 %.

The module supports two primary simulator data sources. **iRacing** exports coolant temperature (`WaterTemp`), oil temperature (`OilTemp`), all four tyre pressures in **kPa** (e.g. `LFpressure` at roughly 170–250 kPa), and brake bias as a fraction via `dcBrakeBias` (e.g. `0.57` meaning 57 % front). **Assetto Corsa (AC)** exports brake temperatures at each corner (`BrakeTempFL` etc.) in degrees Celsius and tyre pressures in **PSI** (typically 20–40 PSI). The module uses automatic unit detection for all pressure channels so that neither the calling code nor the user needs to configure the source simulator explicitly.

---

## Algorithm / Methodology

### Fluid Temperature Analysis

The `_analyse_fluid` function is a generic routine that handles both coolant and oil temperature channels. It iterates over the per-lap DataFrames, resolves the correct channel name from a ranked list of candidates (e.g. `["WaterTemp", "Water Temp", "Engine Temp", "CoolantTemp"]`), and computes the mean temperature for each lap. If at least three laps are available, it fits a first-degree polynomial to the per-lap means and reports the slope as `trend_c_per_lap` — the rate at which fluid temperature is rising or falling across the stint.

**Coolant (water) thresholds:**

| Status | Condition |
|--------|-----------|
| `normal` | Peak lap mean < 105 °C |
| `warning` | Peak lap mean ≥ 105 °C and < 115 °C |
| `critical` | Peak lap mean ≥ 115 °C |

**Oil thresholds:**

| Status | Condition |
|--------|-----------|
| `normal` | Peak lap mean < 130 °C |
| `warning` | Peak lap mean ≥ 130 °C and < 140 °C |
| `critical` | Peak lap mean ≥ 140 °C |

The `warning` band is intentionally wide so the engineer receives advance notice before temperatures climb into the range where thermal protection mechanisms (oil viscosity breakdown, coolant boiling) become relevant. A `critical` status generates an explicit `alert` string in the output.

The trend coefficient is the primary indicator of whether a session is thermally stable. A positive trend greater than ~0.5 °C/lap on a high-count stint signals a cooling system that is undersized for the ambient conditions, or a driving style that is loading the engine harder across the stint. A negative trend suggests the car is warming up and will stabilise, which is normal in the first three laps.

### Brake Temperature Zones

The `_analyse_brake_temps` function resolves per-corner channel names and computes, for each corner and each lap, both the mean and the peak temperature. The corner-level mean is then classified against four boundaries:

| Zone | Temperature Range | Status Code | Engineering Implication |
|------|-------------------|-------------|-------------------------|
| Cold | < 200 °C | `too_cold` | Resin binders not activated; glazing risk; reduced friction coefficient |
| Sub-optimal | 200–300 °C | `suboptimal` | Pad warming but not at rated friction |
| Optimal | 300–700 °C | `optimal` | Full friction coefficient; predictable modulation |
| Hot | 700–800 °C | `hot` | Approaching fluid boil threshold; wear accelerating |
| Critical | > 800 °C | `critical` | Risk of brake fluid vapour lock; immediate action required |

After classifying individual corners, the function computes a **thermal balance** by averaging front mean temperatures and rear mean temperatures separately, and calculating the front-to-rear ratio (`ratio_f_r`). A ratio above 1.30 indicates the front braking system is absorbing disproportionate energy relative to the rear — consistent with a bias that is too far forward. A ratio below 0.75 indicates the inverse. This balance metric feeds directly into the brake bias recommendation.

**Duct recommendations** are generated for every corner in `too_cold`, `hot`, or `critical` states:

- `too_cold` → `close` the duct to trap heat and build the brake into the operating window.
- `hot` or `critical` → `open` the duct to increase cooling air flow. Priority is `alta` for `critical`.

### Tyre Pressure Analysis

The `_analyse_tyre_pressure` function handles the most complex unit-conversion logic in the module. The internal helper `_to_bar` applies automatic unit detection based on the maximum observed value in the series:

```python
if max_value > 100:   # kPa  — iRacing range: ~170-250 kPa
    return series * 0.01
elif max_value > 10:  # PSI  — AC range: ~20-40 PSI
    return series * (1 / 14.5038)
else:                 # already in bar
    return series
```

This means the same analysis code handles both simulators transparently. All internal computations and all output values are expressed in **bar**, with a parallel `psi` field provided at every pressure output for display convenience.

For each lap, the function computes `hot_bar` (mean live pressure during the lap) and `cold_bar` (either from a dedicated cold-pressure channel such as `LFcoldPressure`, or estimated from the first 5 % of lap samples as a proxy for the pre-heat state). The **delta** (`hot_bar − cold_bar`) is the primary setup diagnostic:

| Delta Range | Status Code | Interpretation |
|-------------|-------------|----------------|
| < 0.05 bar | `low_delta` | Cold pressure set too high; tyre runs near its nitrogen build-up limit; carcass flex reduced |
| 0.05–0.28 bar | `ok` | Normal build-up; contact patch geometry within design intent |
| > 0.28 bar | `high_delta` | Cold pressure too low; excessive carcass deflection, heat generation accelerating degradation |

The target midpoint is **0.15 bar** (`_DP_MID`). When the average delta differs from this midpoint by more than 0.03 bar, the module computes a `target_cold` pressure and emits a recommendation with the direction (`raise` or `lower`), the magnitude in both bar and PSI, and the current versus target values. The safety floor of 0.8 bar prevents recommendations that would result in a structurally unsafe cold inflation.

### Brake Bias Normalisation

iRacing reports `dcBrakeBias` as a decimal fraction (e.g. `0.570`), while other sources report it as an already-scaled percentage (e.g. `57.0`). The helper `_to_pct_bias` normalises both conventions:

```python
if series.max() <= 1.05:
    return series * 100.0   # fraction → percent
return series               # already percent
```

The threshold of `1.05` is intentionally above `1.00` to absorb floating-point noise or sensors that report `1.00` as maximum fraction. Once normalised, the brake bias analysis follows a two-level logic:

1. **Thermal evidence (primary):** if brake temperatures are available and the front-to-rear ratio indicates imbalance (ratio > 1.30 or < 0.75), the module recommends a 2 % front bias adjustment toward the cooler axle. The adjustment is capped at the soft-limit boundaries (52 %–63 % front) to prevent recommendations that would cause obvious instability.

2. **Range check (secondary):** if the current bias sits outside the 52–63 % typical range regardless of temperature evidence, an `out_of_range` warning is emitted. This flag is advisory — race cars with unusual weight distributions may intentionally operate outside this range.

---

## Input Telemetry Channels

### iRacing

| Domain | Channel Name(s) | Unit | Notes |
|--------|----------------|------|-------|
| Coolant temperature | `WaterTemp` | °C | Available on all cars |
| Oil temperature | `OilTemp`, `Eng Oil Temp` | °C | Available on most cars |
| Tyre pressure (hot) | `LFpressure`, `RFpressure`, `LRpressure`, `RRpressure` | kPa | Always present |
| Cold tyre pressure | `LFcoldPressure`, `RFcoldPressure`, `LRcoldPressure`, `RRcoldPressure` | kPa | Available when iRacing exposes setup data |
| Brake bias | `dcBrakeBias` | fraction (0–1) | Available on cars with adjustable bias |
| Brake temperatures | Not typically exported | — | Not used; fluid temps substitute |

### Assetto Corsa

| Domain | Channel Name(s) | Unit | Notes |
|--------|----------------|------|-------|
| Brake temperature | `BrakeTempFL`, `BrakeTempFR`, `BrakeTempRL`, `BrakeTempRR` | °C | Available via AC Shared Memory or MoTeC export |
| Tyre pressure (hot) | `TyrePressFL`, `TyrePressFR`, `TyrePressRL`, `TyrePressRR` | PSI | Also accepted as `Tyre Pres FL` etc. |
| Coolant / oil temps | `Engine Temp`, `CoolantTemp` | °C | Car-dependent; not all mods export these |
| Brake bias | `BrakeBias`, `Brake Bias` | % | Car-dependent |

All channel lookups resolve the **first matching name** from the candidate list. If no candidate is found in the DataFrame, the sub-analysis returns `{"available": false}` and is silently omitted from the output without raising an exception.

---

## Output Schema

The top-level return value of `analizar_termica` is a dictionary with the following structure:

```json
{
  "available": true,
  "n_recommendations": 3,

  "water_temp": {
    "available": true,
    "channel": "Water",
    "per_lap": [
      { "lap": 1, "mean_c": 92.4 },
      { "lap": 2, "mean_c": 94.1 }
    ],
    "mean_c": 93.2,
    "max_c": 94.1,
    "trend_c_per_lap": 0.85,
    "status": "normal",
    "warn_threshold_c": 105,
    "crit_threshold_c": 115
  },

  "oil_temp": { "...same structure as water_temp..." },

  "brake_temps": {
    "available": true,
    "optimal_range_c": [300, 700],
    "corners": {
      "FL": {
        "mean_c": 312.5,
        "max_c": 489.0,
        "status": "optimal",
        "per_lap": [
          { "lap": 1, "mean_c": 305.2, "max_c": 471.0 }
        ]
      },
      "FR": { "..." },
      "RL": { "..." },
      "RR": { "..." }
    },
    "balance": {
      "front_mean_c": 315.0,
      "rear_mean_c": 280.0,
      "ratio_f_r": 1.13
    },
    "duct_recs": [
      {
        "corner": "RL",
        "action": "close",
        "reason": "175°C — under optimal range, close brake duct to build heat",
        "priority": "media"
      }
    ]
  },

  "tyre_pressure": {
    "available": true,
    "delta_target": { "bar": 0.15, "psi": 2.2 },
    "delta_window": {
      "low":  { "bar": 0.05, "psi": 0.7 },
      "high": { "bar": 0.28, "psi": 4.1 }
    },
    "corners": {
      "FL": {
        "hot":   { "bar": 1.87, "psi": 27.1 },
        "cold":  { "bar": 1.65, "psi": 23.9 },
        "delta": { "bar": 0.22, "psi": 3.2 },
        "status": "ok",
        "per_lap": [
          {
            "lap": 1,
            "hot_bar": 1.871,
            "hot_max_bar": 1.903,
            "cold_bar": 1.650,
            "delta_bar": 0.221
          }
        ]
      }
    },
    "recommendations": [
      {
        "corner": "RR",
        "direction": "raise",
        "delta_bar": 0.09,
        "delta_psi": 1.3,
        "current_cold": { "bar": 1.60, "psi": 23.2 },
        "target_cold":  { "bar": 1.69, "psi": 24.5 },
        "current_hot":  { "bar": 1.94, "psi": 28.1 },
        "reason": "Hot-cold delta 0.34 bar (4.9 PSI) — target is 0.15 bar (2.2 PSI). Raise cold pressure by 0.09 bar (1.3 PSI).",
        "priority": "baja"
      }
    ]
  },

  "brake_bias": {
    "available": true,
    "current_pct": 57.3,
    "per_lap": [
      { "lap": 1, "bias_pct": 57.1 },
      { "lap": 2, "bias_pct": 57.5 }
    ],
    "typical_range": [52.0, 63.0],
    "out_of_range": null,
    "recommendation": null
  }
}
```

Fields set to `null` or `{"available": false}` indicate that the telemetry channel was absent in the uploaded data; all other sub-analyses proceed normally.

---

## Interpretation Guide

**Reading fluid temperatures:** Start with `status`. A `normal` status with a `trend_c_per_lap` of 0.0–0.3 is ideal: the car is at equilibrium and there is no concern. A `warning` status where `max_c` is within 2–3 °C of the `warn_threshold_c` and the trend is near-zero is also acceptable — the car is running warm but stable. The concern is a `warning` status combined with a positive trend (> 0.5 °C/lap) over a long stint, which suggests temperatures will eventually cross into `critical`. In a real session this pattern should prompt the engineer to check radiator blanking, oil cooler configuration, or fuel map richness.

**Reading brake temperatures:** Check all four corners. The ideal pattern is all four in `optimal` with a `ratio_f_r` between 0.90 and 1.20 — front and rear axles sharing thermal load in proportion to their respective brake force. A ratio above 1.30 with fronts clearly hotter than rears usually indicates a front-biased setup on a circuit where the rear tyres are doing relatively more work; this is where the bias recommendation becomes meaningful. Do not act on a single lap of data — the `per_lap` array is provided precisely so the engineer can distinguish a transient heavy-braking lap from a persistent trend.

**Reading tyre pressures:** The `delta` field is the primary number. Targets vary by tyre manufacturer, but 0.15 bar is a broadly applicable midpoint for modern GT and prototype compounds. A corner showing `high_delta` consistently across multiple laps is not working at the right cold inflation; the `recommendations` array will already have computed the target. When a `cold_bar` estimate is derived from the early-lap proxy (because no dedicated cold-pressure channel exists), treat the delta values with wider uncertainty — they are directionally reliable but not as precise as hardware-measured cold pressures.

**Reading brake bias:** The `current_pct` represents the average front brake force share across all processed laps. The `recommendation` field is populated only when brake temperature evidence is strong enough to make a directional case — a ratio of 1.30 or above (or below 0.75) with both axles above 50 °C. Below those thresholds the module makes no recommendation, because cold brakes have poor signal-to-noise in their temperature data. `out_of_range` is a softer flag that simply notes when the bias is outside the 52–63 % range typical of rear-wheel-drive GT machinery.

**Common patterns:**

- Rears in `too_cold` at a high-speed circuit with no rear duct: normal for many cars. Close recommendation is expected. Verify whether the car has rear ducts fitted.
- Oil temperature `warning` on lap 2 of a short run: almost always transient. If it returns to `normal` by lap 4, ignore.
- All four tyres `high_delta` after a pitstop where tyre warmers were not used: expected. The cold-pressure estimate will be unreliable for that stint; weight the subsequent stints more heavily.

---

## Limitations

**No real-time capability.** The module is a post-session batch analyser. It does not stream data and cannot generate alerts during a live session. All inputs must be fully recorded before analysis begins.

**Cold-pressure estimation accuracy.** When a simulator does not export a dedicated cold-pressure channel (the most common case with AC), the module estimates cold pressure from the first 5 % of lap samples. On a lap that starts with already-warm tyres (e.g. immediately after a pitstop on worn rubber), this estimate will be elevated, causing the computed delta to be artificially compressed. In such cases `status` may show `ok` when the actual cold setup is sub-optimal.

**No tyre compound or construction awareness.** The delta thresholds (0.05–0.28 bar window, 0.15 bar target) are manufacturer-neutral approximations. Bias-ply endurance compounds typically target lower deltas; soft qualifying compounds may tolerate wider swings. The module does not ingest compound metadata and cannot adjust thresholds accordingly.

**No ambient temperature compensation.** Brake and fluid temperature thresholds are fixed regardless of track or ambient temperature. A 35 °C ambient session at Bahrain will produce systematically higher steady-state fluid temperatures than a 15 °C ambient session at Silverstone for identical driving inputs. The engineer must apply this context when interpreting `warning` statuses near the threshold.

**Brake temperature inference only in iRacing.** iRacing does not export corner-level brake temperatures in its standard telemetry output. The `brake_temps` sub-analysis will return `{"available": false}` for iRacing sessions. Brake bias recommendations fall back to the range-check path only, which is less informative.

**No circuit sectoring.** Temperatures are averaged across the entire lap. A circuit with one very slow, high-braking sector may produce elevated brake temperatures that mask cold brakes on the remaining three sectors. The `per_lap` arrays allow manual inspection but the module does not segment telemetry by track position.

**Two-lap comparative mode.** `analizar_termica_comparativa` is a convenience wrapper that calls the full stint analysis on exactly two laps. It does not compute differential metrics between the two laps — it simply tags the result with `label_a` and `label_b`. Engineers comparing setups between two reference laps must interpret the per-corner and per-fluid values themselves.
