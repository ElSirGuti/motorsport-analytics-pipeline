# 17 - Setup Advisor

[Ver en Español](./17_setup_advisor.es.md)

**Module:** `src/analytics/setup_advisor.py`
**Entry points:** `analizar_setup(result, lang)` (two-lap comparison) and `analizar_setup_sesion(curvas_sesion, degradacion, telemetria_sesion, lang)` (whole session)
**Related module (Assetto Corsa linkage):** `src/analytics/ac_setups.py` and the router `src/api/setups.py`
**Reconciled with the code:** 2026-10-03 (EN and ES versions share the same structure)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Rule Engine](#2-rule-engine)
3. [Rules and Thresholds](#3-rules-and-thresholds)
4. [Assetto Corsa Setup Linkage](#4-assetto-corsa-setup-linkage)
5. [Input Requirements](#5-input-requirements)
6. [Output Schema](#6-output-schema)
7. [Interpretation Guide](#7-interpretation-guide)
8. [Limitations and Known Inconsistencies](#8-limitations-and-known-inconsistencies)
9. [Verification Status](#9-verification-status)

---

## 1. Overview

The Setup Advisor is a purely rule-based engine: fixed thresholds on metrics produced by other modules are turned into setup recommendations, each with a priority, a pilot-friendly note and an estimated lap-time gain range. It learns nothing from data.

- **`analizar_setup`** reads the dictionary of a two-lap comparison (tyres, brakes, suspension, slip angle, driver inputs, corners) and also returns a per-domain `areas_status`.
- **`analizar_setup_sesion`** reads session aggregates: corner patterns, the stint trend and the aggregated telemetry from `analizar_telemetria_sesion`. It returns `{"available": false}` when `curvas_sesion["available"]` is false.

Both return the same recommendation structure. Every recommendation carries stable, language-independent keys (`problem_key`, `category_key`, `rec_key`, and `pos` when the rule is about one tyre) so that other modules, notably the Assetto Corsa setup linker (section 4), can map a recommendation to concrete setup parameters without parsing translated text.

---

## 2. Rule Engine

- Each rule builds a recommendation through `_rec_t(...)`: translation keys for category, problem, root cause, recommendation, detail and "solves", a gain range `(gain_lo, gain_hi)` in seconds per lap, and a priority (`alta`, `media`, `baja`; fixed Spanish literals).
- Texts come from the locale files via `src/i18n.py` (`src/locales/*.json` and `src/locales/extra/`). An explicit `lang` argument is now honoured (the public functions run inside that language's i18n context); `lang=None` (default) keeps using the active context language set per request by `main.py`.
- `pilot_note` is looked up from `_PILOT_NOTE_MAP` (problem key to a plain-language note; default `pilot_note_default`).
- **De-duplication:** key `(category, first 40 characters of the problem text)`; the highest-priority instance is kept (earlier instance on ties). The result is sorted `alta`, `media`, `baja`.
- **Totals:** `total_gain_lo` / `total_gain_hi` are the plain sums of `gain_lo` / `gain_hi` over the kept recommendations (2 decimals); `total_gain_range` is `"lo-hi"` formatted.
- **`areas_status`** (lap mode only): for each domain with available data, the worst priority present or `nominal`, plus `n_issues`.
- **`corner_priority`**: corners with `|time_loss_seconds| >= 0.005`, top 8 by absolute loss. The dominant phase is the largest of `|brake_delta| x 0.015`, `|apex_delta| x 0.012`, `|throttle_delta| x 0.010` (assumed sensitivities in s per m or km/h, not measured), labelled `frenada` / `apex` / `salida`.

---

## 3. Rules and Thresholds

Gains are the hard-coded heuristic ranges in seconds per lap and have no empirical validation. "Lap mode" rules run once for lap A and once for lap B.

### 3.1 Tyres

| Mode | Rule | Condition | Priority | Gain (s/lap) |
|---|---|---|---|---|
| Lap | Camber, inner hot | `inner - outer > 15` degC | alta | 0.04-0.18 |
| Lap | Camber, outer hot | `inner - outer < -12` degC | media | 0.03-0.15 |
| Lap | Pressure, overheated | `window_status == "sobrecalentada"` | alta | 0.05-0.15 |
| Lap | Pressure, cold | `window_status == "fria"` | media | 0.03-0.12 |
| Lap | Front vs rear surface temperature | front mean - rear mean `> 14` or `< -14` | alta | 0.10-0.30 |
| Lap | Left vs right asymmetry | `|left - right| > 12` | baja | 0.02-0.08 |
| Session | Overheating | mean temperature `> 120` (window 80-100 + 20) | alta | 0.05-0.18 |
| Session | Too cold | mean temperature `< 65` (80 - 15) | media | 0.04-0.12 |
| Session | Camber | `|camber_gradient| > 18` where `camber_gradient = inner_mean - outer_mean` | media | 0.03-0.10 |
| Session | Brake temperature per corner | `brake_temp_mean > 750` (alta if `> 900`) | media/alta | 0.05-0.20 |
| Session | Front/rear delta | `|front_rear_delta| > 14` (front hotter / rear hotter) | media | 0.08-0.25 / 0.06-0.20 |
| Session | Left/right delta | `|left_right_delta| > 12` | baja | 0.02-0.08 |

### 3.2 Brakes

| Mode | Condition | Priority | Gain |
|---|---|---|---|
| Lap | Fade `(1 - score/baseline) x 100 > 15` % (alta if `> 30`) | media/alta | 0.08-0.25 |
| Lap | Fade zones with `severity > 0.30` | alta | 0.05-0.20 |
| Session | `mean_fade_severity > 0.25` or `0 < mean_efficiency < 0.70` (alta if severity `> 0.35`) | media/alta | 0.08-0.30 |
| Session | `mean_fade_severity > 0.10` (light) | baja | 0.03-0.10 |

### 3.3 Suspension

| Mode | Condition | Priority | Gain |
|---|---|---|---|
| Lap | Roll ratio front/rear `> 1.35` (needs both roll maxima `> 3`) | media | 0.06-0.20 |
| Lap | Roll ratio `< 0.75` | media | 0.06-0.20 |
| Lap | Any bottoming event (alta if max severity `> 0.95`) | media/alta | 0.05-0.20 |
| Lap | `max_pitch > 15` | baja | 0.03-0.12 |
| Session | Any corner with bottoming `> 3` % or mean events/lap `> 0.5` (alta if events `> 1.5` or a corner `> 8` %) | media/alta | 0.05-0.25 |
| Session | `roll_ratio > 1.40` / `< 0.70` | media | 0.05-0.18 |
| Session | `mean_pitch > 15` | baja | 0.03-0.12 |

### 3.4 Balance (from slip-angle / yaw summaries)

| Mode | Condition (first matching) | Priority | Gain |
|---|---|---|---|
| Lap | `understeer_pct > 60` | alta | 0.12-0.40 |
| Lap | `oversteer_pct > 30` | alta | 0.10-0.35 |
| Lap | `2 < balance_mean <= 4` and `understeer_pct > 45` | baja | 0.04-0.12 |
| Session | `mean_understeer_pct > 60` | alta | 0.12-0.40 |
| Session | `mean_oversteer_pct > 30` | alta | 0.10-0.35 |
| Session | `mean_understeer_pct > 40` | baja | 0.05-0.15 |

### 3.5 Driver inputs

| Mode | Condition | Priority | Gain |
|---|---|---|---|
| Lap | nervousness `> 0.65` and high-frequency band `> 0.25` | media | 0.05-0.15 |
| Lap | nervousness `> 0.65` and mid band `> 0.35` (if not high) | baja | 0.04-0.12 |
| Lap | nervousness `> 0.65`, neither band | media | 0.05-0.20 |
| Lap | brake/throttle overlap `< 5` % | baja | 0.03-0.10 |
| Session | nervousness `> 0.65` and `fft_high > 0.28` | media | 0.04-0.15 |
| Session | nervousness `> 0.65` and `fft_mid > 0.38` (independent of the previous rule) | baja | 0.03-0.10 |
| Session | `0.40 < nervousness <= 0.65` | baja | 0.02-0.08 |
| Session | mean overlap `< 4` % | baja | 0.04-0.12 |

### 3.6 Corners and consistency

| Condition | Priority | Gain |
|---|---|---|
| At least 3 corners with `braking_delta_meters > 10` | media | 0.05 x n to 0.15 x n |
| At least 2 corners with `apex_speed_delta_kmh < -5` | alta | 0.08 x n to 0.20 x n |
| At least 3 corners with `throttle_delta_meters > 10` | media | 0.04 x n to 0.12 x n |
| Session: at least 2 corners with `std_loss_seconds > 0.12` | media | 0.05 x n to 0.15 x n |

### 3.7 Degradation (session mode only)

`_analyse_degradacion_ritmo` uses `tasa_s_per_lap` and `r_squared` from `analizar_degradacion_stint`:

| Condition | Priority | Gain |
|---|---|---|
| net rate `> 0.12` and `r2 > 0.65` (alta if `>= 0.15`) | media/alta | `0.25 x rate` to `0.55 x rate` |
| `0.08 < net rate <= 0.12` and `r2 > 0.45` | baja | `0.15 x rate` to `0.35 x rate` |

See 8 on the first row: it cannot fire with the current stint module.

---

## 4. Assetto Corsa Setup Linkage

`src/analytics/ac_setups.py` links the advisor's recommendations to the real parameters of the user's Assetto Corsa setup (`.ini` / `.sp`) and produces a "current -> suggested" view. It is exposed by `src/api/setups.py` under `/api/setups`:

| Endpoint | Purpose |
|---|---|
| `POST /api/setups/detect` | Vehicle / venue / driver (and date, session type, format) from the first bytes of a CSV, `.ibt` or `.ld`, or from a stored `file_id` |
| `GET /api/setups/candidates` | Finds setups for a car and track: states `track_setups`, `generic_only`, `none`, `no_access` |
| `GET /api/setups/file` | Reads one setup by id |
| `POST /api/setups/parse` | Parses an uploaded `.ini` / `.sp` (max 256 KiB) |
| `POST /api/setups/annotate` | Body `{setup, recommendations}`; returns the recommendations decorated with `setup_link`, plus `n_linked`, `conflicts` and `summary` |

How the link works:

1. **Locating setups.** The folder is the one set in the Settings view (`/api/settings/paths`) if any, then `AC_SETUPS_DIR` if set, otherwise the first existing `<Documents>/Assetto Corsa/setups` (Windows known-folder API, `USERPROFILE`, home). Layout `<car>/<track>/*.ini` plus `<car>/generic/last.ini`. When the server cannot see the folder (Docker, Linux, macOS) the state is `no_access` and the user can upload the file instead. In Docker, mount the folder read-only and set `AC_SETUPS_DIR` (see `docker-compose.override.example.yml`).
2. **Safety.** Car and track names are validated against a strict character set and matched against the real directory listing; the resolved path must stay inside the setups folder; only `.ini`/`.sp` regular files up to 256 KiB and 2000 sections are read.
3. **Parsing.** Sections such as `PRESSURE_LF`, `CAMBER_RR`, `ARB_FRONT`, `FRONT_BIAS` are classified into groups (aero, tyres, suspension, brakes, diff, electronics, other); wheel suffixes `LF/RF/LR/RR` map to FL/FR/RL/RR. The game stores "clicks": real units are claimed only where certain (tyre pressure in psi, front brake bias and brake power in %, fuel in litres); everything else is shown raw.
4. **Ranges.** Minimum/maximum/step are attached only if the car's unpacked `content/cars/<car>/data/setup.ini` is readable (`AC_ROOT` / `AC_INSTALL_DIR`, Steam libraries). Encrypted `data.acd` archives are deliberately not opened; the source is reported as `car_data`, `encrypted` or `not_found`.
5. **Mapping.** `_MAP` is keyed by the advisor's `rec_key` and lists `(parameter base, target, direction, multiplier, alternative)`; `target` is `pos` (the tyre of the rule), `front`, `rear`, `all`, `bias_pos` or none. Examples: `setup_rec_camber_add` -> `CAMBER` at that wheel, -1; `setup_rec_pressure_raise` -> `PRESSURE`, +1; `setup_rec_arb_front` -> `ARB_FRONT`, +1; `setup_rec_understeer` -> `ARB_FRONT`, -1 flagged as an *alternative* to the aero change. `_RELATED` lists parameters to merely display when no safe change can be derived (for example ride height and springs for bottoming).
6. **Safe actions.** Each action has `current`, `suggested`, `delta`, `direction`, `status` (`ok`, `direction_only`, `at_limit`), `alternative` and a `note`. The suggested value is `current + direction x step x multiplier`, clamped to the car's limits and to hard bounds (ARB and pressure >= 0, front bias 0-100). A step of 1 click is assumed (with a note) only for pressure, ARBs and front bias; otherwise only the direction is given. If the value is already at the limit in the wanted direction the status is `at_limit` instead of incoherent advice.
7. **Conflicts.** If two non-alternative actions push the same parameter in opposite directions, it is listed in `conflicts`.

Recommendations without a mapping are returned unchanged (without `setup_link`).

---

## 5. Input Requirements

### Lap mode: `analizar_setup(result)`

Absent keys silently skip the domain.

| Key | Fields read |
|---|---|
| `tyre_analysis` | `available`; `lap_a` / `lap_b` with `corners` (`corner`, `inner`, `middle`, `outer`, `surface_mean`, `window_status` in {`optima`, `sobrecalentada`, `fria`}) |
| `brake_analysis` | `available`, `score_a/b`, `baseline_a/b`, `fade_zones_a/b` (`start`, `end`, `severity`) |
| `suspension` | `available`, `summary_a/b` (`max_roll_f`, `max_roll_r`, `max_pitch`, `mean_pitch`), `bottoming_a/b` (`severity`, `corner`) |
| `slip_angle` | `available`, `summary_a/b` (`understeer_pct`, `oversteer_pct`, `balance_mean`) |
| `driver_inputs` | `available`, `nervousness_score_a/b`, `fft_bands_a/b` (`high`, `mid`), `overlap_pct_a/b` |
| `corners` | list with `corner_number`, `time_loss_seconds`, `braking_delta_meters`, `apex_speed_delta_kmh`, `throttle_delta_meters`, `description` |

### Session mode: `analizar_setup_sesion(...)`

| Parameter | Source | Fields read |
|---|---|---|
| `curvas_sesion` | `analizar_curvas_sesion()` | `available`, `corners` (also `std_loss_seconds`) |
| `degradacion` | `analizar_degradacion_stint()` | `tasa_s_per_lap`, `r_squared` |
| `telemetria_sesion` | `analizar_telemetria_sesion()` | optional `tyre` (per-corner `mean_temp`, `max_temp`, `camber_gradient`, `inner_mean`, `outer_mean`, `brake_temp_mean`, `brake_temp_max`; plus `front_rear_delta`, `left_right_delta`), `brake` (`mean_efficiency`, `min_efficiency`, `mean_fade_severity`, `mean_fade_pct`), `suspension` (`mean_roll_f/r`, `roll_ratio`, `mean_pitch`, `mean/max_bottoming_events`, `corner_bottoming_pct`), `inputs` (`mean_nervousness`, `mean_fft_high/mid`, `mean_overlap_pct`), `balance` (`mean_understeer_pct`, `mean_oversteer_pct`, `balance_mean`) |

---

## 6. Output Schema

```python
{
    "available": bool,              # lap mode: recommendations or areas_status exist; session mode: recommendations exist
    "recommendations": [{
        "category": str, "problem": str, "root_cause": str, "recommendation": str,
        "detail": str, "solves": str,
        "expected_gain": str,       # localized "lo-hi s/lap"
        "gain_lo": float, "gain_hi": float,
        "priority": "alta" | "media" | "baja",
        "pilot_note": str,
        "problem_key": str, "category_key": str, "rec_key": str,   # stable identifiers
        "pos": "FL" | "FR" | "RL" | "RR",                          # only for per-tyre rules
        # added by /api/setups/annotate:
        "setup_link": {"actions": [...], "related": [...]},
    }],
    "areas_status": [{"domain": str, "label": str, "status": str, "n_issues": int}],   # lap mode only
    "corner_priority": [{"corner_number": int, "time_loss_seconds": float, "braking_delta_meters": float,
                         "apex_speed_delta_kmh": float, "throttle_delta_meters": float,
                         "dominant_phase": "frenada" | "apex" | "salida", "focus": str, "description": str}],
    "total_gain_lo": float, "total_gain_hi": float, "total_gain_range": str
}
```

`areas_status` domains: `tyres`, `brakes`, `suspension`, `aero`, `inputs`, `corners`. Session mode does not return `areas_status`.

---

## 7. Interpretation Guide

- Start with `areas_status` (lap mode) to triage, then read `alta` recommendations: `root_cause` names the phenomenon and `detail` normally embeds the numbers that triggered the rule, which can be checked against the telemetry.
- `expected_gain` is a heuristic range; the total is a naive sum. Treat it as an optimistic upper bound, because setup changes interact.
- When several rules fire for the same tyre (camber and pressure), they may share a cause; do not apply all as independent corrections.
- `pilot_note` describes the felt symptom without engineering jargon; for `alta` items it is a short-term cue, not a substitute for the change.
- `corner_priority` shows where to look first; `dominant_phase` is a heuristic based on assumed sensitivities.
- With a linked AC setup, read `setup_link.actions`: `status: ok` gives a concrete value, `direction_only` only the direction, `at_limit` means the parameter cannot move that way. Check `conflicts` before applying several changes. Alternative actions (`alternative: true`) are not additions: choose one route.

---

## 8. Limitations and Known Inconsistencies

- **Rule-based with fixed thresholds.** Not adapted to circuit, compound, ambient conditions or car. The gain ranges are not validated against real lap times.
- **Gains are not independent.** Totals are plain sums.
- **Two comparable laps** are needed in lap mode; mixed conditions give misleading output.
- **Session consistency** (`std_loss_seconds`) is unreliable with fewer than about 5 laps.
- **`lang`** is now honoured when passed (fixed 2026-10-03); the priorities and `window_status` values below remain Spanish literals.
- **Priorities are fixed Spanish strings** (`alta`/`media`/`baja`) and `window_status` values (`optima`, `sobrecalentada`, `fria`) are Spanish literals used as data contracts.
- **Degradation rule (fixed 2026-10-03):** the "high" rule required `tasa_s_per_lap > 0.20` although the stint slope is clamped to +/-0.15, so it never fired, and `tasa_s_per_lap` includes the fuel effect. The rule now uses the net `degradation_s_per_lap` (fallback to `tasa_s_per_lap` if absent) with high `> 0.12` (80 % of the clamp; alta from 0.15, reachable because net = slope - fuel effect can exceed the clamp) and moderate `0.08-0.12`. It is skipped with `low_confidence`, fewer than `MIN_LAPS_FOR_TREND` laps, or `wear_active=False` (sim with tyre wear off; `main.py` passes `detect_wear_tracking`).
- **Lap/session coherence (fixed 2026-10-03):** the two modes gave opposite advice. Both now share `_camber_diagnosis` and `_pressure_direction`. Camber: negative camber loads the inner shoulder, so inner hotter than outer = too much negative camber = REDUCE it (the session rule was right; lap mode said "add"); outer hotter = ADD. Pressure (temperature-only, no pressure channel, so this is the less certain call): an overheated tyre is assumed to be flexing too much (docs 09/14: higher pressure reduces deformation heat), so RAISE pressure, unless the tread centre is more than 5 degC hotter than the shoulder mean (over-inflated), then LOWER; a cold tyre gets LOWER. Session mode has no tread-zone split, so it follows the default. Pinned by `tests/test_advisor_rl_fixes.py`.
- **Dependence on upstream modules:** the quality of every rule is that of the metric that feeds it (for example the slip-angle balance summary).

---

## 9. Verification Status

Thresholds, gain ranges, keys and the AC mapping were read from `setup_advisor.py`, `ac_setups.py` and `src/api/setups.py` on 2026-10-03; the degradation rule, camber/pressure coherence and `lang` fixes above were reproduced with failing synthetic tests first. The recommendation texts (e.g. wing/ARB advice) live in the locale files and were not audited for engineering correctness. Not verifiable from the code: the physical meaning of the sign of `balance_mean`, why each threshold value was chosen, and the pressure direction (no pressure data enters these rules). Earlier versions of this document described a "balance mean = lateral-G versus steering-angle correlation" and several threshold values that are not what the code does; those statements were removed.
