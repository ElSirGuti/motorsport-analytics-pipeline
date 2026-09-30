# Tyre Degradation Model

## Overview

The tyre degradation module (`src/analytics/tyre_degradation.py`) quantifies how much performance a tyre set has surrendered across a stint and projects how many laps remain before the compound reaches a performance cliff.

In motorsport, tyre wear is one of the most consequential variables in race strategy. A set that has dropped even 1.5 seconds from its reference pace creates compounding disadvantages: gap erosion to competitors on fresher rubber, loss of ability to defend or attack under braking, and increased risk of thermal runaway at high-stress circuits. Having a numerical model that converts raw telemetry into a scalar wear state allows engineers and drivers to make data-backed decisions on pit-stop windows, stint length targets, and driving style adjustments.

The module trains a **polynomial Ridge regression** on all flying laps of a session, using per-lap features derived from tyre temperature, tyre pressure, lateral G-load, braking G-load, and lap number. The target variable is lap-time delta relative to the personal best, not the raw lap time itself, which makes the model robust to differences in circuit length and traffic.

---

## Algorithm / Methodology

### 1. Lap Filtering

Pit laps are excluded using the `is_pit_lap` flag when available. Any lap with a null `lap_time_s` is also dropped. A minimum of three flying laps is required to proceed.

### 2. Per-Lap Feature Extraction

For each flying lap, a feature vector is assembled from the raw high-frequency telemetry slice:

| Feature | Description |
|---|---|
| `temp_{pos}` | Mean tyre core temperature per corner (FL, FR, RL, RR) in °C |
| `stress_{pos}` | Fraction of samples outside the optimal thermal window [75 °C, 100 °C] |
| `pres_{pos}` | Mean tyre pressure per corner |
| `mean_lat_g` | Mean absolute lateral acceleration (cornering load proxy) |
| `mean_brake_g` | Mean absolute longitudinal deceleration (braking load proxy, negative values only) |
| `mean_speed` | Mean vehicle speed |
| `lap_number` | Sequential lap number within the stint |

Channel names are resolved via a priority-ordered lookup table that covers both iRacing native channel names and MoTeC export conventions (e.g., `LFtempCM`, `Tyre Temp FL Centre`). If a channel is absent, the corresponding feature is set to `NaN` and imputed at model-fit time.

### 3. Target Variable

For each lap *i* with measured time *t_i* and session best time *t_best*:

```
δ_i = t_i − t_best
```

This delta, expressed in seconds, is the regression target. A fresh tyre at its best will produce δ ≈ 0; a worn tyre on a degrading compound will produce increasing δ over successive laps.

### 4. Ridge Polynomial Regression

The pipeline consists of four sequential stages:

```
X_raw → Imputer (median) → StandardScaler → PolynomialFeatures (degree d) → Ridge (α = 1.0)
```

The polynomial degree *d* is chosen adaptively: d = 2 when six or more laps are available, d = 1 otherwise. The Ridge regularisation term (α = 1.0) prevents overfitting on short stints where the feature matrix may be poorly conditioned after polynomial expansion.

Formally, the model minimises:

```
min_w  ||y − Xw||² + α||w||²
```

where X is the imputed, scaled, polynomial-expanded feature matrix and y is the vector of lap-time deltas.

### 5. Linear Trend and Cliff Projection

In parallel to the full multivariate model, a **simple linear regression** is fit directly on lap number versus delta to extract a clean monotonic trend:

```
δ̂(n) = β₁ · n + β₀
```

where *n* is the lap number. The slope β₁ (seconds per lap) is the primary **degradation rate** reported to the consumer. This univariate fit is deliberately kept separate from the Ridge model: it sacrifices explanatory power for interpretability and stable forward projection.

Remaining useful laps are estimated by projecting δ̂(n) up to 40 laps ahead and finding the first lap *n* at which the projected delta crosses the cliff threshold:

```
remaining_laps = argmin_k { δ̂(n_last + k) ≥ 1.5 s }
```

If no crossing occurs within the 40-lap horizon, the function reports `">40"`.

### 6. Wear State (0–100 %)

A scalar wear percentage is derived from the most recent lap's delta:

```
wear_pct = clamp(δ_last / max_scale × 100,  0, 100)
```

where `max_scale = max(1.5, max(δ) × 1.2, 0.3)`. This rescaling anchors 100 % to the observed worst-case degradation of the session (or to the cliff threshold, whichever is larger), preventing the metric from saturating prematurely on circuits with naturally small lap-time spread.

### 7. Axle Temperature Trends

Front and rear axle temperature trends are computed independently by fitting a first-degree polynomial on mean front-axle temperature and mean rear-axle temperature across laps. The resulting slopes (°C per lap) provide a secondary indicator of thermal evolution and axle-level load imbalance.

---

## Input Requirements

### `dfs` (list of DataFrames)

A list where each element is a pandas DataFrame containing the high-frequency telemetry samples for one lap. The order must correspond to the row order of `df_laps`. At minimum, the lap number column must be resolvable; all other channels are optional and degrade gracefully to `NaN` when absent.

### `df_laps` (DataFrame)

A lap-summary DataFrame with at least the following columns:

| Column | Type | Required | Description |
|---|---|---|---|
| `lap_time_s` | float | Yes | Lap duration in seconds |
| `lap_number` | int/float | No* | Sequential lap number; inferred from row position if absent |
| `is_pit_lap` | bool | No | Marks in/out laps; used to exclude non-representative laps |

\* Strongly recommended. Without `lap_number`, the stint position axis is inferred from index order.

### scikit-learn

The module requires `scikit-learn` at runtime (`Ridge`, `PolynomialFeatures`, `StandardScaler`, `SimpleImputer`). If the package is not installed, the function returns immediately with `{"available": False, "reason": "scikit-learn not installed"}`.

---

## Output Schema

The function `predecir_degradacion_neumatico(dfs, df_laps)` returns a dictionary. All keys are present when `available` is `True`.

| Key | Type | Unit | Description |
|---|---|---|---|
| `available` | bool | — | `True` if the model ran successfully |
| `wear_pct` | float | % | Wear state of the current tyre set (0 = fresh, 100 = at/beyond cliff) |
| `remaining_laps` | int or `">40"` | laps | Projected laps before the 1.5 s performance cliff |
| `current_delta_s` | float | s | Lap-time penalty on the most recent lap vs session best |
| `cliff_threshold_s` | float | s | The delta threshold used to define the performance cliff (1.5 s) |
| `degradation_rate_s_per_lap` | float | s/lap | Linear slope β₁ from univariate trend fit |
| `n_laps_analyzed` | int | laps | Number of flying laps used in the fit |
| `top_wear_factors` | list of objects | — | Up to six features ranked by absolute Pearson correlation with delta |
| `lap_data` | list of objects | — | Per-lap observed delta and linear trend value |
| `projection` | list of objects | — | Up to 25 future laps with projected delta and cliff threshold |
| `front_temp_trend_c_per_lap` | float or null | °C/lap | Rate of mean front axle temperature change per lap |
| `rear_temp_trend_c_per_lap` | float or null | °C/lap | Rate of mean rear axle temperature change per lap |
| `left_mean_temp` | float or null | °C | Session mean temperature of left-side tyres |
| `right_mean_temp` | float or null | °C | Session mean temperature of right-side tyres |
| `tyre_temps_available` | bool | — | Whether any tyre temperature channel was found in the data |

### Nested Object Schemas

**`lap_data` element**

```json
{ "lap": 12, "delta": 0.342, "trend": 0.318 }
```

**`projection` element**

```json
{ "lap": 18, "projected": 1.124, "cliff": 1.5 }
```

**`top_wear_factors` element**

```json
{ "factor": "stress_fl", "correlation": 0.872 }
```

---

## Interpretation Guide

### Degradation Rate (`degradation_rate_s_per_lap`)

A value near **0.00 s/lap** means the compound is stable and lap time is not eroding. Values in the **0.05–0.15 s/lap** range are typical of moderate-wear compounds on abrasive surfaces. Values above **0.20 s/lap** indicate aggressive degradation that will likely force an early pit stop or a significant driving-style adaptation.

Negative values are physically possible early in a stint (tyres cycling into the operating window) and should not be interpreted as wear.

### Wear Percentage

This is a relative metric anchored to the current session's worst-case delta, not to an absolute tyre life calendar. Use it as a directional gauge: a car with 80 % wear is significantly closer to the cliff than one at 40 %, but the absolute number should not be compared between sessions on different compounds or circuits without recalibration.

### Remaining Laps

When the model returns `">40"`, degradation is so mild that the cliff does not appear within the 40-lap projection window. This is common on durable compounds (hard tyres, cool conditions) or short stints. When a specific number is returned, plan pit-stop windows with at least 2–3 laps of buffer to account for model uncertainty.

### Top Wear Factors

High correlation between `stress_{pos}` (the fraction of time outside the 75–100 °C thermal window) and delta indicates thermally-driven degradation: the tyre is either running too cold (poor grip, not reaching operating temperature) or overheating (rubber graining or blistering). High correlation with `mean_lat_g` points to mechanical wear from sustained cornering loads — common on high-downforce circuits with slow, high-load corners.

### Axle Temperature Trends

A positive `front_temp_trend_c_per_lap` combined with a flat `rear_temp_trend_c_per_lap` suggests progressive front-end loading, which may indicate increasing understeer as rear grip recovers relative to the front. A large difference between `left_mean_temp` and `right_mean_temp` signals an asymmetric load balance and may warrant a tyre pressure or camber adjustment.

---

## Limitations

**Minimum data requirement.** The model requires at least three flying laps. Sessions with very short stints (qualifying single-lap runs, formation laps only) will return `available: False`.

**Linear extrapolation of a nonlinear phenomenon.** The univariate linear trend used for projection is a deliberate simplification. Real tyre degradation often follows a quadratic or piecewise profile: slow early wear, followed by a more rapid cliff. The linear model underestimates remaining life when the compound is still building temperature and overestimates it when degradation accelerates sharply.

**No compound or track surface knowledge.** The module is agnostic to compound hardness, rubber age, or track abrasiveness. The cliff threshold of 1.5 s and the optimal temperature window of 75–100 °C are fixed constants that may not be appropriate for all compound types (e.g., super-soft qualifiers operate at higher temperatures; wet-weather tyres have a narrower window).

**Channel availability.** The model is most accurate when all four tyre temperature channels, both G-load channels, and tyre pressure channels are present. When channels are missing, median imputation fills the gap, which can flatten the feature space and reduce the model's ability to identify the physical cause of degradation.

**Telemetry alignment.** The mapping between `dfs` list elements and `df_laps` rows is positional. Any mismatch between the lap-summary table and the telemetry slice list will silently associate the wrong high-frequency data with a lap.

**No inter-session calibration.** Wear percentage and remaining laps are calibrated on the current session only. Comparing raw output values between sessions, compounds, or conditions requires normalisation that the module does not perform.
