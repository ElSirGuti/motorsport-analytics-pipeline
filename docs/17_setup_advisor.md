# Vehicle Setup Advisor

## Overview

The Setup Advisor is a rule-based telemetry translation engine that converts raw sensor measurements and derived analytics into concrete, prioritised vehicle setup recommendations with estimated lap-time gains. Rather than requiring engineers to correlate dozens of raw channels manually, the module aggregates six independent analytical domains — tyres, brakes, suspension, aerodynamic balance, driver inputs, and corner-level performance — and emits a ranked, deduplicated list of actionable changes.

The module exposes two entry points:

- **`analizar_setup(result, lang)`** — lap-comparison mode. Operates on the structured output of a two-lap telemetry comparison (laps A and B) and is best suited for qualifying and back-to-back setup runs.
- **`analizar_setup_sesion(curvas_sesion, degradacion, telemetria_sesion, lang)`** — session aggregate mode. Combines corner-pattern consistency analysis, tyre degradation trends, and session-averaged telemetry signals. Intended for race stints and multi-lap practice sessions.

Both entry points return the same output schema and are fully compatible with the `SetupRecommendations` UI component.

---

## Methodology

### Aerodynamic and Mechanical Balance: Lateral G vs Steering Angle Correlation

Balance diagnosis is performed in `_analyse_slip()` and `_analyse_balance_sesion()` using slip-angle summary data derived from the lateral-G and yaw-rate channels.

The core metric is the **balance mean** (`balance_mean`), a signed scalar representing the average yaw demand relative to the available lateral grip. Positive values indicate the front axle is working harder than the rear (understeer tendency); negative values indicate the opposite (oversteer). The companion percentage metrics `understeer_pct` and `oversteer_pct` quantify what fraction of cornering time the vehicle spent in each regime.

Decision thresholds:

| Condition | Threshold | Priority | Recommended action |
|---|---|---|---|
| Understeer dominant | `understeer_pct > 60 %` | alta | Reduce front wing / stiffen front ARB |
| Oversteer dominant | `oversteer_pct > 30 %` | alta | Reduce rear wing / stiffen rear ARB |
| Mild understeer | `balance_mean` in (2, 4] and `understeer_pct > 45 %` | baja | Fine-tune front aero or tyre pressure |

These thresholds are deliberately conservative: sporadic excursions during track-limit events do not trigger high-priority recommendations. The module requires the imbalance to be structurally persistent across the lap sample before escalating.

### Brake Temperature Differential: Bias and Thermal Fade

Brake analysis operates in two paths.

**Fade path** (`_analyse_brakes()`, lap-level): A degradation percentage is computed as `(1 − score / baseline) × 100`, where `score` is the integrated brake-pressure efficiency over the lap and `baseline` is the expected value from the first braking event. Fade exceeding 15 % triggers a recommendation; above 30 % the priority escalates to `alta`. Spatially resolved fade zones (brake events where severity > 30 %) are listed with track-distance coordinates so the engineer can correlate them with specific corner entries.

**Thermal path** (`_analyse_tyres()`, per-corner tyre section; `_analyse_frenos_sesion()` and `_analyse_tyres_sesion()`, session level): The front-to-rear axle temperature differential (`front_rear_delta`) is compared against a ±14 °C threshold. A front-heavy differential indicates insufficient rear brake contribution and flags a bias adjustment toward the rear. A rear-heavy differential flags the opposite. Per-corner brake temperature (`brake_temp_mean`) is also evaluated: sustained readings above 750 °C indicate the brake compound is operating outside its optimal window; above 900 °C the priority is `alta` and duct sizing becomes the primary recommendation vector.

### Camber Analysis: Inner/Middle/Outer Gradient

Camber diagnosis uses the temperature gradient across the tyre cross-section. For each wheel position, the signed difference `inner − outer` is computed.

- `gradient > 15 °C`: insufficient camber — the inner shoulder is carrying disproportionate load. Recommendation: add camber.
- `gradient < −12 °C`: excessive camber — the outer shoulder is overworked. Recommendation: reduce camber.

In session mode (`_analyse_tyres_sesion()`), the same gradient logic applies to session-averaged inner/outer mean temperatures, and the trigger threshold is raised slightly to 18 °C to filter out transient laps (out laps, safety car periods) that would otherwise inflate the average.

### Suspension: Anti-Roll Bar Balance, Bottoming, and Pitch

Anti-roll bar diagnosis derives from the **roll ratio** `max_roll_f / max_roll_r` (lap mode) or `mean_roll_f / mean_roll_r` (session mode).

- `ratio > 1.35` (lap) or `> 1.40` (session): front roll angle dominates → stiffen front ARB or soften rear ARB.
- `ratio < 0.75` (lap) or `< 0.70` (session): rear roll angle dominates → stiffen rear ARB or soften front ARB.

Bottoming events from the plank/skid-block sensors are evaluated both by count and severity. Session averages above 0.5 events per lap, or any corner where bottoming occurs in more than 3 % of laps, trigger a ride-height recommendation. Severity above 95 % escalates priority to `alta`.

Pitch under braking is flagged when `max_pitch > 15°`, indicating excessive longitudinal weight transfer that typically points to spring rate or damper compression settings.

### Driver Inputs and Damper Frequency Analysis

The steering-input nervousness score (0–1) is the normalised RMS of high-frequency steering corrections. When it exceeds 0.65, the FFT band decomposition determines the dominant frequency:

- **High-frequency band > 25 %** of total input energy → damper rebound issue. High-speed rebound that is too soft allows the tyre to lose contact briefly on kerbs and bumps, which the driver compensates for with micro-corrections.
- **Mid-frequency band > 35 %** → spring rate issue. The chassis resonant frequency is close to a track forcing frequency.
- **Neither band dominant** → general mechanical balance problem requiring broader investigation.

A secondary diagnostic checks the brake-throttle overlap percentage. A value below 5 % (lap) or 4 % (session) indicates the driver is not trail-braking — a technique deficit that may itself be a consequence of an unstable setup, and is surfaced as a low-priority coaching note.

### Pilot Note Generation

Every recommendation carries a `pilot_note` — a brief, jargon-free sentence the pilot can understand without an engineering intermediary. Notes are resolved by `_pilot_note_for(problem_key)` from a static lookup table (`_PILOT_NOTE_MAP`). The table maps internal problem keys to plain-language descriptions of the **felt symptom** rather than the engineering root cause. When no specific mapping exists, the default note `"Setup adjustment noted — check feel in next sector"` is used.

---

## Input Requirements

### Lap-comparison mode — `analizar_setup(result, lang)`

`result` is a dictionary aggregating the outputs of the pipeline's upstream analytics modules. The advisor reads the following keys; any absent key causes the corresponding domain to be silently skipped.

| Key | Source module | Required fields |
|---|---|---|
| `tyre_analysis` | Tyre temperature analysis | `available`, `lap_a`, `lap_b` (each with `corners` list; per-corner `inner`, `middle`, `outer`, `surface_mean`, `window_status`) |
| `brake_analysis` | Brake fade module | `available`, `score_a/b`, `baseline_a/b`, `fade_zones_a/b` |
| `suspension` | Suspension module | `available`, `summary_a/b` (`max_roll_f/r`, `max_pitch`, `mean_pitch`), `bottoming_a/b` |
| `slip_angle` | Slip angle module | `available`, `summary_a/b` (`understeer_pct`, `oversteer_pct`, `balance_mean`) |
| `driver_inputs` | Driver inputs module | `available`, `nervousness_score_a/b`, `fft_bands_a/b` (`high`, `mid`), `overlap_pct_a/b` |
| `corners` | Corner analysis | List of corner dicts with `corner_number`, `time_loss_seconds`, `braking_delta_meters`, `apex_speed_delta_kmh`, `throttle_delta_meters` |

### Session mode — `analizar_setup_sesion(curvas_sesion, degradacion, telemetria_sesion, lang)`

| Parameter | Source | Required fields |
|---|---|---|
| `curvas_sesion` | `analizar_curvas_sesion()` | `available`, `corners` (same schema as above, with `std_loss_seconds` for consistency analysis) |
| `degradacion` | `analizar_degradacion_stint()` | `tasa_s_per_lap`, `r_squared` |
| `telemetria_sesion` | `analizar_telemetria_sesion()` | Nested dict with keys `tyre`, `brake`, `suspension`, `inputs`, `balance`; all optional |

The `lang` parameter accepts `"es"` (Spanish, default) or `"en"` (English). All human-readable strings in the output are translated accordingly via the `i18n` module.

---

## Output Schema

Both entry points return a dictionary with the following structure.

```python
{
    "available": bool,                  # False if no input data could be processed
    "recommendations": [                # Priority-sorted, deduplicated list
        {
            "category":        str,     # Domain label (e.g. "Aerodinámica / Balance")
            "problem":         str,     # Human-readable problem statement
            "root_cause":      str,     # Engineering root cause
            "recommendation":  str,     # Specific setup change to make
            "detail":          str,     # Extended explanation (may be empty)
            "solves":          str,     # What the change resolves
            "expected_gain":   str,     # Formatted range e.g. "0.12–0.40s/v"
            "gain_lo":         float,   # Lower bound of gain estimate (seconds/lap)
            "gain_hi":         float,   # Upper bound of gain estimate (seconds/lap)
            "priority":        str,     # "alta" | "media" | "baja"
            "pilot_note":      str,     # Plain-language note for the driver
        },
        ...
    ],
    "areas_status": [                   # Per-domain health summary (lap mode only)
        {
            "domain":   str,            # Internal key: "tyres" | "brakes" | etc.
            "label":    str,            # Display label
            "status":   str,            # Worst priority in domain, or "nominal"
            "n_issues": int,
        },
        ...
    ],
    "corner_priority": [                # Top 8 corners ranked by time loss
        {
            "corner_number":         int,
            "time_loss_seconds":     float,
            "braking_delta_meters":  float,
            "apex_speed_delta_kmh":  float,
            "throttle_delta_meters": float,
            "dominant_phase":        str,   # "frenada" | "apex" | "salida"
            "focus":                 str,   # Translated phase label
            "description":           str,
        },
        ...
    ],
    "total_gain_lo":    float,          # Sum of gain_lo across all recommendations
    "total_gain_hi":    float,          # Sum of gain_hi across all recommendations
    "total_gain_range": str,            # Formatted "lo–hi"
}
```

**Deduplication**: when the same `(category, problem[:40])` key appears from multiple laps or domains, only the highest-priority instance is retained. Ties are broken by first occurrence.

**Priority ordering**: the final list is sorted `alta → media → baja` using `_PRIORITY_RANK = {"alta": 0, "media": 1, "baja": 2}`.

---

## Interpretation Guide

### How the Race Engineer reads this output

The engineer's primary entry points are `recommendations` and `areas_status`.

Start with `areas_status` for a domain-level triage: any domain showing `"alta"` needs to be addressed before the next session. Cross-reference with `corner_priority` to understand whether the balance or tyre issues are localised to specific track sectors or are global.

For each `"alta"` recommendation, read `root_cause` and `detail` together. The `root_cause` names the physical phenomenon; `detail` typically includes the raw sensor values that triggered the rule, which can be verified directly against the telemetry overlay. The `expected_gain` range is additive across independent domains but should be treated as a theoretical upper bound — real-world gains depend on the completeness of the setup change and the driver's ability to exploit it.

When multiple recommendations exist in the same domain (e.g., both camber and pressure flags on the same tyre position), investigate whether they are causally linked. Excess camber generates excessive inner-shoulder heat, which can independently trigger an overheating pressure flag — treating both as independent adjustments will over-correct.

The `solves` field is useful for briefing meetings: it describes the downstream effect the change addresses, in terms the whole team can align on (e.g., "reduces understeer at apex" rather than "decreases front roll stiffness ratio").

### How the Driver reads this output

The driver should focus exclusively on `pilot_note` within each recommendation and on `corner_priority`.

`pilot_note` is deliberately free of engineering jargon. It describes the **felt** symptom and, where applicable, the short-term driving adjustment that can compensate until the setup change is applied. Examples:

- "Car is pushing wide — try a later apex and smoother steering inputs" (understeer pending ARB adjustment)
- "Rear locking under braking — bias adjustment coming" (rear brake overheating pending bias change)
- "Setup change incoming — expect different kerb response next lap" (ride height adjustment pending)

`corner_priority` tells the driver which corners to prioritise focus on. The `dominant_phase` field (`braking`, `apex`, `exit`) directs attention: a braking-phase deficit calls for a later, harder brake point experiment; an apex-phase deficit suggests the current line geometry is suboptimal; an exit-phase deficit typically points to throttle application timing.

The driver should not attempt to adjust technique to compensate for `alta`-priority mechanical issues — the setup must be changed. `pilot_note` for `alta` items is intended as a lap-survival cue, not a long-term driving strategy.

---

## Limitations

**Rule-based, not model-based.** All thresholds in the advisor are fixed scalar values derived from domain expertise. They are not learned from data and do not adapt to circuit layout, ambient conditions, or tyre compound characteristics. A 14 °C front/rear temperature differential that indicates a brake bias problem on a high-downforce circuit may be entirely acceptable on a low-speed circuit with balanced corner distribution. Engineers operating on atypical circuits should treat `media` and `baja` recommendations with additional skepticism.

**Additive gain estimates are not independent.** `total_gain_lo` and `total_gain_hi` are arithmetic sums of individual recommendation gain ranges. In practice, setup changes interact: correcting camber may partially resolve a temperature imbalance, rendering the pressure recommendation unnecessary. The total gain figure is an upper bound under the assumption that all changes are applied and are fully independent, which is rarely true.

**Lap-mode requires two comparable laps.** `analizar_setup()` is designed for back-to-back lap comparisons (e.g., the fastest lap vs. the previous lap, or a setup-change lap vs. a baseline). Comparing laps from different conditions (wet vs. dry, different fuel loads, different tyre states) will produce misleading recommendations.

**Session-mode consistency analysis requires a minimum lap count.** The standard deviation of time loss per corner (`std_loss_seconds`) is only meaningful when computed over several laps. Sessions with fewer than four or five valid laps may produce false consistency alerts driven by a single outlier lap.

**Brake fade zone analysis requires spatially aligned data.** The `fade_zones` detection assumes the telemetry is spatially synchronised to a reference lap. If the data exporter does not normalise to distance-based coordinates, zone boundary values in meters will not correspond to identifiable track positions.

**No ground-truth validation.** The `expected_gain` ranges are heuristic estimates. There is currently no feedback loop between applied recommendations and subsequent lap-time data, so the accuracy of the gain estimates cannot be empirically validated from within the pipeline.

**Language support.** All recommendation text fields are resolved at call time via the `i18n` module. If a translation key is missing for a given language, the system falls back to the raw key string rather than raising an exception. Engineers using `lang="en"` should verify that their installation includes a complete English translation bundle.
