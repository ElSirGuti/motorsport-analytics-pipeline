# 15 - Tyre Degradation Model

[Ver en Español](./15_tyre_degradation.es.md)

**Module:** `src/analytics/tyre_degradation.py`
**Main functions:** `predecir_degradacion_neumatico(dfs, df_laps)`, `detect_wear_tracking(dfs)`
**Shared helpers (from `src/analytics/stint.py`):** `analizar_degradacion_stint`, `_projection_laps`, `MIN_LAPS_FOR_TREND`
**Reconciled with the code:** 2026-10-03 (EN and ES versions share the same structure)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Algorithm](#2-algorithm)
3. [Input Requirements](#3-input-requirements)
4. [Output Schema](#4-output-schema)
5. [Interpretation Guide](#5-interpretation-guide)
6. [Limitations](#6-limitations)
7. [Constants Reference](#7-constants-reference)
8. [Verification Status](#8-verification-status)

---

## 1. Overview

The module quantifies how much lap-time performance a tyre set has lost across a stint and projects how many laps remain before a performance "cliff" (a lap-time loss of 1.5 s relative to the best lap).

It does **not** fit a machine-learning model. Earlier versions of this document described a polynomial Ridge regression; that model no longer exists in the code and `scikit-learn` is not used here. The current design deliberately reuses the stint trend engine of `stint.py` so that the tyre page and the stint page can never disagree on the slope, and it follows three principles:

1. **Do not invent wear.** If the simulator was not modelling tyre wear, no degradation is computed.
2. **Do not report negative degradation.** A falling lap time is fuel burn, track evolution or noise, not "tyres getting better". It is reported separately.
3. **Do not project from too little data.** Below a minimum number of valid laps nothing is projected, and the cliff estimate is only produced when the degradation is statistically distinguishable from zero.

---

## 2. Algorithm

### 2.1 Wear-tracking detection (`detect_wear_tracking`)

Before any maths, the module checks whether the simulator was actually modelling tyre wear. It scans every column of every lap DataFrame:

- **Wear-rate channels** (exact names): `AID Tire Wear Rate`, `AID Tyre Wear Rate`, `Tire Wear Rate`, `Tyre Wear Rate`, `TyreWearRate`, `TireWearRate`. The maximum absolute value is recorded.
- **Wear/grip state channels** (case-insensitive prefix): `tire/tyre rubber grip`, `tire/tyre wear`, `tirewear`, `tyrewear`, `tire/tyre life`, `tirelife`, `tyrelife`, `tyregrip` (the loader name of `Tire Rubber Grip FL..RR`). The min and max over the whole session are recorded per channel. Since the loaders keep `Tire Rubber Grip *` (as `TyreGrip*`) and `AID Tire Wear Rate` (as `TireWearRate`) for `.ld` files too, ACTI logs are now recognised (before, the channels were dropped and the answer was `active = None`).

Decision, in this order:

| Condition | Result |
|---|---|
| A wear-rate channel exists and its maximum absolute value is <= 1e-9 | `active = False` ("... == 0 for the whole session") |
| State channels exist and **all** of them have a session range < 0.05 | `active = False` ("... constant across the session") |
| State channels exist and at least one varies | `active = True` |
| Only wear-rate channels exist, with values > 0 | `active = True` |
| No wear channel at all | `active = None` (unknown: the analysis continues, flagged as such) |

When `active` is `False` the function returns immediately with `available: False`, `wear_tracking: False`, `reason_code: "wear_inactive"`, the localized `reason` and `wear_evidence`. Nothing else is computed.

### 2.2 Lap selection

The valid laps come from `_projection_laps(df_laps)` (shared with the stint module):

1. Racing laps only: pit laps (`is_pit_lap`) and time outliers (< 70 % or > 115 % of the median lap time, applied when at least 3 laps exist) are removed, as are laps without a time.
2. Out-laps (the lap right after a pit lap) are removed when enough laps remain (at least `MIN_LAPS_FOR_TREND`).
3. The session's first lap (standing/rolling start on cold tyres) is removed when more than `MIN_LAPS_FOR_TREND` laps are available.

If fewer than `MIN_LAPS_FOR_TREND` (= 5) valid laps remain, the function returns `available: False`, `low_confidence: true`, `confidence: "low"`, `reason_code: "insufficient_sample"` and the number of laps found (`n_laps_used`).

### 2.3 Target variable

For each valid lap with time `t_i` and the best valid lap time `t_best`:

```
delta_i = t_i - t_best
```

### 2.4 Trend and degradation slope

The slope is not computed here. `analizar_degradacion_stint(df_laps)` (in `stint.py`) produces:

- `tasa_s_per_lap`: the **robust total slope** of lap time versus lap number: OLS slope shrunk (empirical Bayes, prior sd 0.05 s/lap) towards the explicit fuel-burn effect and clamped to +/-0.15 s/lap. With fewer than 5 laps it would equal the fuel effect only.
- `fuel_effect_s_per_lap`: the fuel-mass effect, `-0.035 s/L x mean fuel burned per lap` (negative = the car gets faster as the tank empties), applied only when the mean burn is at least 0.05 L/lap (otherwise 0).
- `slope_se_s_per_lap` and `slope_ci`: standard error and 95 % confidence interval of the **raw OLS** slope (the CI is not the shrunk one).
- `anchor_lap`, `anchor_time_s`: median of the last three valid laps and their mean lap number.

The tyre module then separates the tyre component:

```
total       = tasa_s_per_lap
deg         = max(0, total - fuel_effect)        # degradation_rate_s_per_lap, always >= 0
track_evo   = min(0, total - fuel_effect)        # track_evolution_s_per_lap, always <= 0
ci_lo_deg   = slope_ci[0] - fuel_effect
reliable    = (deg >= 0.01) and (ci_lo_deg > 0)  # degradation_detected
```

Because `fuel_effect` is <= 0, subtracting it adds the fuel gain back, so a car that stays flat in lap time while burning fuel shows positive tyre degradation. A negative remainder is never reported as degradation; it goes to `track_evolution_s_per_lap`.

### 2.5 Cliff projection

Projection runs 40 laps ahead of the last valid lap, anchored at the recent pace (not at the regression intercept):

```
proj(l)  = anchor_delta + deg * (l - anchor_lap)
sigma    = max( std(residuals of a linear fit of delta, ddof=2), 0.25 )
band(l)  = 1.28 * sqrt( (slope_se * (l - anchor_lap))^2 + sigma^2 )
p10(l)   = max(0, proj(l) - band(l))
p90(l)   = proj(l) + band(l)
```

where `anchor_delta = anchor_time_s - t_best`. The 1.28 factor gives an 80 % band (p10-p90). The `projection` list holds only the first 25 future laps, each with `projected`, `p10`, `p90` and `cliff`.

`remaining_laps` is produced **only when `reliable` is true**: it is the first number of laps `k` ahead of the last lap for which `proj >= 1.5 s`, or the string `">40"` if there is no crossing within 40 laps. When not reliable it is `null`.

### 2.6 Wear state (0-100 %)

Only when `reliable` is true:

```
max_scale = max(1.5, 1.2 * max(delta), 0.3)
wear_pct  = clamp( delta_last / max_scale * 100, 0, 100 ), rounded to 0.1
```

Otherwise `wear_pct` is `null`. The scale is anchored to the cliff threshold or the worst delta of the session (x1.2), whichever is larger.

### 2.7 Per-lap features and wear factors

For each valid lap whose telemetry slice exists in `dfs` (matched by the row index of `df_laps`), a feature vector is built from the first channel found in a priority list (iRacing native names such as `LFtempCM` and MoTeC-style names such as `Tyre Temp FL Centre`):

| Feature | Description |
|---|---|
| `temp_{fl,fr,rl,rr}` | Mean tyre core temperature (needs more than 5 non-null samples) |
| `stress_{pos}` | Fraction of samples outside the 75-100 degC window |
| `pres_{pos}` | Mean tyre pressure (needs more than 5 samples; units are not converted here) |
| `mean_lat_g` | Mean absolute lateral acceleration |
| `mean_brake_g` | Mean absolute longitudinal deceleration, counting only samples below -0.1 g (0 if none) |
| `mean_speed` | Mean speed (computed but excluded from the correlation ranking) |

When at least `MIN_LAPS_FOR_FACTORS` (= 6) laps have features:

- **Wear factors**: the absolute Pearson correlation of each feature (NaN imputed with the median; constant features skipped; `lap_number` and `mean_speed` excluded) with `delta_vs_best`. The six highest are returned as `top_wear_factors`. The reported `correlation` is the absolute value, so the sign is not available.
- **Axle temperature trends**: slope (degC per lap) of a first-degree fit of the mean front (`temp_fl`, `temp_fr`) and mean rear (`temp_rl`, `temp_rr`) temperature versus lap number; gaps are filled backward then forward.

With fewer than 6 laps both are skipped and `wear_factors_reason` / `temp_trend_reason` explain why. `left_mean_temp` and `right_mean_temp` are the mean of all per-lap temperatures of the left (FL, RL) and right (FR, RR) tyres.

---

## 3. Input Requirements

**`dfs`**: list of per-lap telemetry DataFrames. The position in the list must correspond to the row index of `df_laps` (the match is by index; a mismatch silently pairs the wrong telemetry with a lap). All channels are optional.

**`df_laps`**: lap summary.

| Column | Required | Description |
|---|---|---|
| `lap_time_s` | Yes | Lap duration in seconds |
| `lap_number` | Yes | Lap number (used by the shared helpers) |
| `is_pit_lap` | No | Marks in/out laps; used for exclusion |
| `fuel_burned`, `fuel_end`, `max_g_sum` | No | Used by `stint.py` for the fuel effect, fuel laps remaining and grip trend |

Channels used by the feature step: tyre core temperature per corner, tyre pressure per corner, lateral G, longitudinal G, speed. Wear detection additionally reads the wear-rate/state channels listed in 2.1.

There is no `scikit-learn` dependency in this module; it needs `numpy` and `pandas`, plus `scipy` through `stint.py`.

---

### 2.8 Wear measured by the simulator (`measure_rubber_grip`)

Independent of lap times: the mean rubber grip (% left) of each tyre per lap, the loss between the first and the last sample and its slope per lap. `level`: `none` (< 0.02 %/lap), `minimal` (< 0.15), `moderate` (< 0.5), `high`. It is returned as `grip_measured` (`start_pct`, `end_pct`, `loss_pct`, `loss_pct_per_lap`, `n_laps`, `level`, `per_tyre`, `laps`) with `wear_rate` (the `AID Tire Wear Rate` multiplier). When the pace trend finds nothing, the `reason` quotes this figure: minimal wear means "the simulator models wear but the loss is too small to move the lap time"; moderate or high means "the grip really fell, the lap times just do not show it" (`reason_code: wear_measured_not_in_times`).

Laps with a spin, a major incident or one that cost 1.5 s or more (see [18](./18_incidents.md)) are left out of the pace trend and listed in `incident_laps_excluded`; if fewer than 5 laps remain the answer is `insufficient_sample` with that explanation, instead of a trend drawn from distorted laps.

## 4. Output Schema

### 4.1 Early returns (`available: false`)

| `reason_code` | Meaning | Extra keys |
|---|---|---|
| `wear_inactive` | The simulator is not modelling tyre wear | `wear_tracking: false`, `wear_evidence` |
| `insufficient_sample` | Fewer than 5 valid laps | `wear_tracking`, `low_confidence: true`, `confidence: "low"`, `n_laps_used` |
| (none) | The stint helper could not fit (fewer than 3 laps) | `wear_tracking`, `reason` |

### 4.2 Full result (`available: true`)

| Key | Type | Unit | Description |
|---|---|---|---|
| `available` | bool | | `true` |
| `wear_tracking` | bool or null | | `true` / `false` / `null` (unknown) from `detect_wear_tracking` |
| `wear_evidence` | string | | Human-readable evidence for that decision |
| `wear_pct` | float or null | % | Wear state; `null` unless degradation is `reliable` |
| `remaining_laps` | int, `">40"` or null | laps | Laps until the 1.5 s cliff; `null` unless `reliable` |
| `current_delta_s` | float | s | Delta of the last valid lap versus the best |
| `cliff_threshold_s` | float | s | 1.5 |
| `degradation_rate_s_per_lap` | float | s/lap | `deg`, always >= 0 |
| `degradation_detected` | bool | | `reliable` (see 2.4) |
| `track_evolution_s_per_lap` | float | s/lap | Negative part of the slope (track evolution/noise), always <= 0 |
| `fuel_effect_s_per_lap` | float | s/lap | Fuel-mass effect (<= 0) |
| `raw_slope_s_per_lap` | float | s/lap | Unshrunk OLS slope |
| `slope_ci` | [float, float] or null | s/lap | 95 % CI of the raw slope |
| `confidence` | `"low"`, `"medium"` or `"high"` | | From `stint.py` (low if fewer than 8 laps or CI half-width > 0.2; high if >= 10 laps and half-width <= 0.05) |
| `low_confidence` | bool | | Mirrors `confidence == "low"` |
| `n_laps_used`, `n_laps_analyzed` | int | laps | Valid laps used (identical values, two names kept for compatibility) |
| `reason_code`, `reason` | string or null | | `no_detectable_degradation` plus a localized text when not `reliable`, otherwise `null` |
| `top_wear_factors` | list | | Up to 6 `{factor, correlation}` (absolute Pearson) |
| `wear_factors_reason` | string or null | | Why factors are empty (fewer than 6 laps) |
| `lap_data` | list | | Per lap `{lap, delta, trend}` |
| `projection` | list | | First 25 future laps `{lap, projected, p10, p90, cliff}` |
| `front_temp_trend_c_per_lap`, `rear_temp_trend_c_per_lap` | float or null | degC/lap | Axle temperature slopes |
| `temp_trend_reason` | string or null | | Same reason as `wear_factors_reason` |
| `left_mean_temp`, `right_mean_temp` | float or null | degC | Mean tyre temperature per side |
| `tyre_temps_available` | bool | | Any tyre temperature channel found |

Note: `reason`/`wear` texts are localized through `src/i18n.py` (keys `tyre_wear_inactive`, `tyre_insufficient_laps`, `tyre_no_degradation`, `tyre_factors_few_laps`); only `reason_code` is stable for programmatic use.

Nested examples:

```json
{ "lap": 12, "delta": 0.342, "trend": 0.318 }
{ "lap": 18, "projected": 1.124, "p10": 0.85, "p90": 1.40, "cliff": 1.5 }
{ "factor": "stress_fl", "correlation": 0.872 }
```

---

## 5. Interpretation Guide

- **`degradation_detected: false`** is a valid, common outcome: lap times show no reliable upward trend once fuel is accounted for. `wear_pct` and `remaining_laps` are intentionally `null` then. This is not a bug and not a claim that the tyres are perfect.
- **`degradation_rate_s_per_lap`**: the figure is the tyre part of the slope. Orders of magnitude commonly quoted for racing tyres are 0.05-0.15 s/lap (moderate) and above 0.20 s/lap (aggressive); these are rules of thumb and are **not** encoded or validated in the code (the code only clamps the total slope to +/-0.15 s/lap).
- **`track_evolution_s_per_lap`**: a clearly negative value means the lap times are improving beyond the fuel effect (rubbering-in, warm-up, driver learning).
- **`wear_pct`**: relative to the session's worst delta (or the cliff), not an absolute tyre life. Do not compare between compounds or circuits.
- **`remaining_laps`**: `">40"` means no crossing within the horizon. Keep a 2-3 lap buffer when planning stops (a rule of thumb, not computed by the module); use `p10`/`p90` for the uncertainty.
- **Top wear factors**: high correlation of `stress_{pos}` with delta suggests thermally driven loss (tyre outside 75-100 degC); high `mean_lat_g` correlation suggests load-driven wear. Correlation is not causation, and with 6-10 laps it is noisy.
- **Axle trends and left/right means**: a persistent difference between left and right mean temperature suggests load asymmetry (pressure/camber), and diverging front/rear trends suggest a balance shift. Interpretations, not outputs.

---

## 6. Limitations

- **Linear projection.** Real degradation is often non-linear (a slow phase then a cliff). The projection is a straight line from the recent pace and will miss a sudden cliff.
- **Fuel separation depends on the fuel channel.** Without a fuel channel (`fuel_burned` < 0.05 L/lap) the fuel effect is 0, so fuel burn is absorbed into the slope and degradation is underestimated (or reported as track evolution).
- **Small samples.** 5 laps is the technical minimum, 8 or more are needed for non-low confidence, and 6 for the factors. Short sessions produce `insufficient_sample`.
- **Reliability test uses the raw CI.** `degradation_detected` compares the lower bound of the unshrunk OLS CI (minus the fuel effect) with zero; the shrunk slope is what is reported as the rate.
- **Fixed constants.** Cliff 1.5 s and optimal window 75-100 degC are not compound-specific.
- **Positional telemetry alignment** between `dfs` and `df_laps` is assumed.
- **Wear detection is name-based.** An unrecognised wear channel gives `wear_tracking: null`, not `false`.
- **Pressure units** are not normalised in this module (only used as a correlation feature).
- **No cross-session calibration.**

---

## 7. Constants Reference

| Constant | Value | Where |
|---|---|---|
| `_OPT_MIN`, `_OPT_MAX` | 75 / 100 degC | `tyre_degradation.py` |
| `_CLIFF_S` | 1.5 s | `tyre_degradation.py` |
| `MIN_LAPS_FOR_FACTORS` | 6 | `tyre_degradation.py` |
| `_WEAR_CONST_RANGE` | 0.05 | `tyre_degradation.py` |
| Projection horizon / output | 40 / 25 laps | `tyre_degradation.py` |
| Band z / sigma floor | 1.28 / 0.25 s | `tyre_degradation.py` |
| Reliability: minimum rate | 0.01 s/lap | `tyre_degradation.py` |
| `MIN_LAPS_FOR_TREND` | 5 | `stint.py` |
| `MIN_LAPS_FOR_MEDIUM_CONF` | 8 | `stint.py` |
| `MAX_ABS_SLOPE_S_PER_LAP` | 0.15 | `stint.py` |
| `SLOPE_PRIOR_SD` | 0.05 | `stint.py` |
| `FUEL_S_PER_L` | 0.035 s/L | `stint.py` |
| `MIN_FUEL_BURN_L` | 0.05 L/lap | `stint.py` |

---

## 8. Verification Status

All formulas, thresholds and keys above were read directly from `tyre_degradation.py` and `stint.py` on 2026-10-03. Not verifiable from the code and therefore flagged: typical s/lap ranges and the 2-3 lap buffer (rules of thumb), and the physical meaning of the 1.5 s cliff (a convention).
