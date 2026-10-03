# 14 - Thermal Management Analysis

[Ver en Español](./14_thermal_management.es.md)

**Module:** `src/analytics/thermal_management.py`
**Main functions:** `analizar_termica(dfs, df_laps)`, `analizar_termica_comparativa(df_a, df_b, label_a, label_b)`
**Reconciled with the code:** 2026-10-03 (EN and ES versions share the same structure)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Algorithm](#2-algorithm)
3. [Input Channels](#3-input-channels)
4. [Output Schema](#4-output-schema)
5. [Interpretation Guide](#5-interpretation-guide)
6. [Limitations](#6-limitations)
7. [Constants Reference](#7-constants-reference)
8. [Verification Status](#8-verification-status)

---

## 1. Overview

The module offers a simulator-agnostic analysis of five thermal signals that matter for lap time and reliability: coolant (water) temperature, oil temperature, brake temperature per corner, tyre pressure (hot, and hot-minus-cold delta) and brake bias. `analizar_termica` receives one telemetry DataFrame per lap (`dfs`), computes each sub-analysis independently, and returns a single dictionary with per-sub-analysis results, recommendations and alerts. `df_laps` is accepted for API symmetry but is not used.

Each sub-analysis is optional: when its channels are missing the sub-analysis returns `{"available": false, "reason": ...}` and the others continue. If none is available the overall result is `{"available": false}`.

All thresholds in the module are fixed heuristics (see section 7). They are not derived from the telemetry nor tuned per car, compound or ambient temperature, and they are not sourced from a published standard; treat them as engineering rules of thumb.

The module is called from `main.py` for the whole session (`analizar_termica(dfs, df_laps)`), for the single-lap view (`analizar_termica(laps, pd.DataFrame())`) and, through `analizar_termica_comparativa`, for lap comparison.

Lap numbering in the outputs (`"lap": 1, 2, ...`) is the **position** of the DataFrame in `dfs` plus one, not the simulator lap number.

---

## 2. Algorithm

### 2.1 Fluid temperatures (`_analyse_fluid`)

One generic routine serves water (`"Water"`) and oil (`"Oil"`). For every lap it resolves the first matching channel name from the candidate list and takes the lap mean; laps without the channel are skipped.

- `mean_c`: mean of the lap means; `max_c`: **maximum of the lap means** (not the instantaneous peak).
- `trend_c_per_lap`: slope of a first-degree fit of the lap means versus lap position, only with at least 3 laps (otherwise `null`).
- Status from `max_c`: `critical` if `>= crit`, `warning` if `>= warn`, else `normal`.

| Fluid | `warning` from | `critical` from |
|---|---|---|
| Water | 105 degC | 115 degC |
| Oil | 130 degC | 140 degC |

`warning` and `critical` also add a localized `alert` string. The status uses lap means, so a short instantaneous spike inside a lap does not trigger it.

### 2.2 Brake temperatures (`_analyse_brake_temps`)

For each corner (FL, FR, RL, RR) and lap the mean, max and min of the channel are stored. Two guards precede the classification:

- No brake-temperature channel at all: `available: false` (`thermal_brake_no_channel`).
- **Constant channel guard:** if the spread across all corners and laps (largest max minus smallest min) is below 1 degC, the channel is treated as a placeholder the simulator did not fill in (for example pinned at ambient) and the sub-analysis returns `available: false` (`thermal_brake_constant`). Otherwise every brake would be flagged as too cold.

The mean over the laps of each corner is classified:

| Corner mean | Status |
|---|---|
| < 200 degC | `too_cold` |
| 200 to < 300 degC | `suboptimal` |
| 300 to 700 degC (inclusive) | `optimal` |
| > 700 to 800 degC (inclusive) | `hot` |
| > 800 degC | `critical` |

**Thermal balance:** mean of the front corners and mean of the rear corners (those that exist) and `ratio_f_r = front / rear` (`null` if the rear mean is not positive). The balance is computed only if both axles have data.

**Duct recommendations** (priority strings are the Spanish literals `media` / `alta`, not localized):

- `too_cold` gives `close` (priority `media`).
- `hot` gives `open` (`media`); `critical` gives `open` (`alta`).
- `suboptimal` and `optimal` produce no recommendation.

The output also carries `optimal_range_c: [300, 700]`.

### 2.3 Tyre pressures (`_analyse_tyre_pressure`)

**Unit detection (`_to_bar`)**, per channel, from the maximum observed value:

```
max > 100  -> kPa, multiply by 0.01
max > 10   -> PSI, multiply by 1/14.5038
else       -> already bar
```

All internal values and outputs are in bar, and each output also carries `psi` (`{bar, psi}` objects, bar rounded to 2 decimals, PSI to 1). The heuristic misclassifies a pressure series whose values are below 10 PSI, or a bar series above 10.

**Hot pressure** per lap: mean of the live pressure channel (and its maximum, `hot_max_bar`).

**Cold pressure** comes only from a dedicated cold-pressure channel (`LFcoldPressure` etc.). There is no estimation from the beginning of the lap: in a continuous stint the start of a lap is already hot, and using it gave a delta near 0 and false "raise pressure" advice (this proxy was removed). Without a cold channel, `cold` and `delta` are absent, the corner `status` is `ok`, a `note` explains why, and no pressure recommendation is made for that corner.

**Delta** = hot mean minus cold mean per lap; the corner delta is the mean over laps.

| Mean delta | `status` |
|---|---|
| < 0.05 bar | `low_delta` (little build-up: cold pressure may be too high) |
| 0.05 to 0.28 bar | `ok` |
| > 0.28 bar | `high_delta` (large build-up: cold pressure may be too low) |

**Recommendation** (only with cold and delta available):

```
target_cold  = max(0.8, cold - (delta - 0.15))
delta_adjust = target_cold - cold
emit if |delta_adjust| >= 0.03 bar
direction    = "lower" if delta_adjust < 0 else "raise"
priority     = "media" if |delta_adjust| > 0.1 else "baja"
```

The recommendation is emitted whenever the adjustment reaches 0.03 bar, even if `status` is `ok` (the target is the 0.15 bar midpoint, not the window).

### 2.4 Brake bias (`_analyse_brake_bias`)

`_to_pct_bias` converts a fraction to percent when the maximum is <= 1.05 (iRacing `dcBrakeBias`), otherwise leaves it unchanged. The per-lap means and their average (`current_pct`) are reported.

1. **Thermal evidence** (needs available brake temperatures with a balance, a non-null ratio and both axle means above 50 degC): ratio **> 1.30** gives `reduce` with `suggested = max(52, current - 2)`; ratio **< 0.75** gives `increase` with `suggested = min(63, current + 2)`. Priority `media`.
2. **Range check:** `out_of_range` text if `current_pct < 52` or `> 63` (advisory).

---

## 3. Input Channels

Each lookup resolves the first matching name that exists in the DataFrame.

| Signal | Accepted channel names | Expected unit |
|---|---|---|
| Water | `WaterTemp`, `Water Temp`, `Engine Temp`, `CoolantTemp`, `Coolant Temp`, `Eng Coolant Temp` | degC |
| Oil | `OilTemp`, `Oil Temp`, `Eng Oil Temp`, `Engine Oil Temp`, `EngOilTemp` | degC |
| Brake temp | `BrakeTemp{FL,FR,RL,RR}`, `Brake Temp {FL..}`, `BrakeTemp{FrontLeft,...}` | degC |
| Hot tyre pressure | `TyrePress{FL..}`, `Tire Pressure {FL..}`, `Tyre Pres {FL..}`, iRacing `LFpressure`, `RFpressure`, `LRpressure`, `RRpressure` | kPa / PSI / bar (auto) |
| Cold tyre pressure | `LFcoldPressure`, `RFcoldPressure`, `LRcoldPressure`, `RRcoldPressure`, `TyrePressCold{FL..}` | kPa / PSI / bar (auto) |
| Brake bias | `BrakeBias`, `dcBrakeBias`, `Brake Bias`, `brake_bias` | fraction (0-1) or % |

Simulator notes (typical behaviour, not enforced by the code): iRacing exposes water/oil temperature, pressures in kPa and `dcBrakeBias` as a fraction; Assetto Corsa exposes brake temperatures and pressures in PSI. Whether each simulator or export tool provides a given channel depends on the car and the exporter; the module only reports what is present.

---

## 4. Output Schema

```json
{
  "available": true,
  "n_recommendations": 3,
  "water_temp": {
    "available": true, "channel": "Water",
    "per_lap": [{"lap": 1, "mean_c": 92.4}],
    "mean_c": 93.2, "max_c": 94.1, "trend_c_per_lap": 0.85, "status": "normal",
    "warn_threshold_c": 105, "crit_threshold_c": 115
  },
  "oil_temp": {"...": "same structure as water_temp"},
  "brake_temps": {
    "available": true, "optimal_range_c": [300, 700],
    "corners": {"FL": {"mean_c": 312.5, "max_c": 489.0, "status": "optimal",
                        "per_lap": [{"lap": 1, "mean_c": 305.2, "max_c": 471.0, "min_c": 120.0}]}},
    "balance": {"front_mean_c": 315.0, "rear_mean_c": 280.0, "ratio_f_r": 1.13},
    "duct_recs": [{"corner": "RL", "action": "close", "reason": "...", "priority": "media"}]
  },
  "tyre_pressure": {
    "available": true,
    "delta_target": {"bar": 0.15, "psi": 2.2},
    "delta_window": {"low": {"bar": 0.05, "psi": 0.7}, "high": {"bar": 0.28, "psi": 4.1}},
    "corners": {"FL": {"hot": {"bar": 1.87, "psi": 27.1}, "cold": {"bar": 1.65, "psi": 23.9},
                        "delta": {"bar": 0.22, "psi": 3.2}, "status": "ok",
                        "per_lap": [{"lap": 1, "hot_bar": 1.871, "hot_max_bar": 1.903,
                                     "cold_bar": 1.65, "delta_bar": 0.221}]}},
    "recommendations": [{"corner": "RR", "direction": "raise", "delta_bar": 0.09, "delta_psi": 1.3,
                         "current_cold": {"bar": 1.60, "psi": 23.2},
                         "target_cold": {"bar": 1.69, "psi": 24.5},
                         "current_hot": {"bar": 1.94, "psi": 28.1},
                         "reason": "...", "priority": "baja"}]
  },
  "brake_bias": {
    "available": true, "current_pct": 57.3,
    "per_lap": [{"lap": 1, "bias_pct": 57.1}],
    "typical_range": [52.0, 63.0], "out_of_range": null, "recommendation": null
  }
}
```

Notes:

- Without a cold channel a corner entry has `hot`, `per_lap` (with `cold_bar`/`delta_bar` null), `status: "ok"` and `note`; it has no `cold` or `delta` keys.
- `n_recommendations` = duct recommendations + pressure recommendations + (1 if a bias recommendation) + (1 if a water alert) + (1 if an oil alert). The bias `out_of_range` text is not counted.
- Fluid `alert` is present only for `warning`/`critical`. Texts (`reason`, `alert`, `out_of_range`) are localized (ES/EN) through `src/i18n.py` (keys `thermal_*`); the `priority` values are fixed Spanish literals.
- `analizar_termica_comparativa` runs the same analysis over two laps and adds `label_a` and `label_b`; it computes no differential between the laps.

---

## 5. Interpretation Guide

- **Fluids:** `normal` with a small trend is the goal. `warning` with a clearly positive trend over a long stint is the pattern to watch, since the peak can drift into `critical`. The trend is a lap-mean slope, so it is noisy with few laps; 3 laps is only the minimum for it to exist. Values such as "0.5 degC/lap is concerning" are rules of thumb, not coded thresholds.
- **Brakes:** check all four corners, and compare front and rear through `ratio_f_r`. The code only acts on ratios above 1.30 or below 0.75; a balanced ratio around 1 is the intuitive ideal (an interpretation, not a coded threshold). Use `per_lap` to tell a transient heavy-braking lap from a consistent pattern.
- **Tyre pressures:** the `delta` is the number to read, and only exists with a cold channel. The 0.15 bar target and the 0.05-0.28 bar window are generic approximations; compound and tyre manufacturer targets differ, so use the recommendation as a direction and magnitude estimate to be checked against the tyre supplier's guidance.
- **Brake bias:** `recommendation` appears only with strong thermal evidence; `out_of_range` is a soft warning against a 52-63 % window that assumes typical GT-like cars.
- **Common patterns (experience-based, not verified by the code):** cold rear brakes on cars without rear ducts, a transient oil `warning` on lap 2 of a short run, and `high_delta` on all corners after a tyre change without warmers.

---

## 6. Limitations

- **Post-session batch analysis.** No streaming or live alerts.
- **Cold pressure needs a dedicated channel.** Without it the delta-based advice is skipped (by design, after removing the unreliable lap-start proxy).
- **Fluid peak is a lap mean.** A short spike within a lap is averaged away.
- **No compound, ambient or circuit awareness.** All thresholds are fixed and not sourced from a standard.
- **Unit auto-detection by maximum** can misfire at the boundaries (see 2.3).
- **Whole-lap averages.** No sectoring: one heavy-braking zone can mask the rest of the lap.
- **Brake channel availability depends on the simulator/export.** If a simulator does not export brake temperatures, or exports a constant placeholder, `brake_temps` is unavailable and the bias recommendation falls back to the range check only.
- **Lap indices are positional**, not simulator lap numbers.
- **Priorities are fixed Spanish strings**, not localized.

---

## 7. Constants Reference

| Constant | Value |
|---|---|
| Brake: cold / optimal low / optimal high / hot limit | 200 / 300 / 700 / 800 degC |
| Constant brake channel spread | < 1 degC |
| Water warn / crit | 105 / 115 degC |
| Oil warn / crit | 130 / 140 degC |
| Fluid trend minimum laps | 3 |
| Pressure delta low / high / target | 0.05 / 0.28 / 0.15 bar |
| Pressure recommendation threshold / floor | 0.03 bar / 0.8 bar |
| Pressure priority split | 0.1 bar |
| Bias ratio thresholds | > 1.30 reduce, < 0.75 increase |
| Bias step / limits | 2.0 points / 52-63 % |
| Minimum axle temperature for bias evidence | 50 degC |
| Unit conversion | 1 bar = 14.5038 PSI = 100 kPa |

---

## 8. Verification Status

Algorithms, thresholds and keys were read from `thermal_management.py` on 2026-10-03; the removal of the lap-start cold-pressure proxy and the constant-brake-channel guard are present in the current code and were missing from earlier versions of this document. Not verifiable from the code: the engineering justification of the thresholds (200/300/700/800 degC, 0.05-0.28 bar, 52-63 %), the claim of which channels each simulator exports, and the "common patterns" in section 5.
