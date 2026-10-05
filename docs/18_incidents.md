# 18 - Incidents: spins, saves and off-track excursions

Module `src/analytics/incidents.py`, text in `src/locales/extra/incidents.{en,es}.json`, UI `frontend/src/components/IncidentsPanel.jsx`. The result is the `incidents` object of `POST /api/analyze-session` and `POST /api/stint/analyze`; the panel sits in the stint section.

[Ver en Español](./18_incidents.es.md)

## What it detects

| `kind` | Meaning |
|---|---|
| `spin` | The car turned sideways far enough to point backwards (peak slip angle >= 100 deg) or rotated >= 150 deg. |
| `slide` | A big slide that was saved (peak slip angle between 45 and 100 deg, less than 150 deg of rotation). |
| `off_track` | Wheels left the track (two or more wheels, or one wheel with a high dirt level). |

A spin and an off-track within 3 s of each other are one event (`went_off: true`). An excursion that crosses the start/finish line is merged across the two laps. Events with a speed below 30 km/h at the onset, in the pit lane, or one wheel brushing a kerb are ignored.

## Signals (it uses the best the log has)

| Need | 1st choice | 2nd | 3rd |
|---|---|---|---|
| Slip angle | body velocity `BodyVelX/Y` (ACTI: `Chassis Velocity X/Y`), `atan2(vy, vx)` | position + yaw rate: yaw the path does not explain over 2 s (self-calibrated: units and sign differ between loggers; discarded if position and yaw disagree) | yaw rate only (>= 120 deg in 2.5 s with a speed collapse or a very high yaw rate) |
| Off-track | tyre dirt `Dirt*` (ACTI `Tire Dirt Level`): it only rises while a wheel is on the grass | `TrackSurface` (iRacing `PlayerTrackSurface`, 0 = off track) | distance to the median line of the other laps (needs 3 laps and position) |

`summary.slip_source` and `summary.off_track_source` (also `sources`) tell which was used; the UI shows it. If the log has no signal for a detector, that detector is simply silent.

## Cause diagnosis

For each event it reads the 3 s before the onset and compares with what the **other laps** did at the same place (median over +-25 m). Each cause is the sum of evidence (0..1) with the numbers that support it; the top ones with a score >= 0.25 are returned with `confidence` (`high` >= 0.7 and a margin, `medium` >= 0.45, `low`).

| Code | Evidence used |
|---|---|
| `too_much_throttle` | throttle >= 35 % at the onset (and rising / above the other laps), rear wheelspin (`SlipRatio`), rear slip angle larger than front |
| `lift_off` | throttle dropped >= 35 points in 0.6 s with lateral load >= 0.6 g and no braking |
| `braking_instability` | brake >= 20 % with steering, rear wheels slower than front (lock), more brake than other laps |
| `too_much_steering` | steering above the other laps at this corner, or a very fast steering input (>= 250 deg/s) |
| `late_correction` | no counter-steer within 0.45 s of the slide, or a very small one (needs body velocity) |
| `overcorrection` | the slip angle swung > 30 deg to both sides within 3 s |
| `entry_too_fast` | entry speed above the other laps (>= 4 km/h or >= 3 %) |
| `low_grip` | tyres colder than the session median, dirty tyres, surface grip < 95 %, lower lateral g than usual, early or slow lap |
| `kerb_or_bump` | vertical acceleration spike (or suspension travel speed spike) |
| `downshift` | gear dropped in the last 0.8 s without brake or throttle |
| `wind` | only when wind >= 15 km/h at >= 150 km/h with low lateral g; low confidence by design |
| `understeer_off` | off-track with front tyres sliding more than the rear, or already at the usual lateral g |

## Limits (said in the UI too)

- Causes are **inferences** from inputs and car state, not a certainty.
- Contact with other cars, damp patches and bumps outside the logged channels are not visible.
- Wind: only the strength is known; its direction is expressed in a frame that differs between sims, so it never counts as a main cause. It is not assessed at all when the log has no wind channel.
- With few laps there is no reference: the comparisons with "your other laps" are skipped (needs at least 2 other laps at that place).
- `lap_delta_s` (time the lap lost) is only given when the clean laps give a usable reference.

## Output

`incidents = { available, events[], summary, sources }`. Each event: `id`, `lap`, `kind`, `went_off`, `severity` (`minor|moderate|major`), `t_s`, `distance_m`, `fraction`, `duration_s`, `peak_slip_deg`, `rotation_deg`, `min_speed_kmh`, `off_track {peak_dirt, wheels, duration_s}`, `lap_time_s`, `lap_delta_s`, `lap_invalidated`, `corner {corner_number, corner_name, corner_kind}` (from the unified corner map), `context`, `primary_cause`, `causes[] {code, score, confidence, label, advice, evidence[]}` and a `trace` (+-4 s around the onset: speed, throttle, brake, steer, slip, lateral g). `summary` has counts by kind, the most frequent causes and `hot_spots` (corners with 2 or more incidents).

## Extra channels this needed

`src/io/loaders.py` (`COLUMN_ALIASES`) now maps, for CSV, `.ld` and `.ibt`: `BodyVelX/Y`, `Dirt{FL,FR,RL,RR}`, `SlipAngle*`, `SlipRatio*`, `WheelSpeed*`, `TyreLoad*`, `TyreGrip*`, `WindSpeed`, `WindDir`, `SurfaceGrip`, `VerticalG`, `TCActive`, `ABSActive`, `LapInvalid` and `TrackSurface`. Missing ones are simply absent. iRacing `OnPitRoad` now feeds `InPit`.

## Tests

`tests/test_incidents.py` (synthetic sessions with a power-on spin, a saved slide, off-track from dirt, kerbs, the yaw-only fallback, hot spots, corner naming, EN/ES key parity, both endpoints, and real fixtures: clean Imola gives no event and the Spa session gives its one real spin) and `tests/e2e/test_e2e_flows.py::test_incidents_panel_shows_spin_and_cause`.
