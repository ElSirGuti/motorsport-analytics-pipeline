# User Guide — Motorsport Analytics Pipeline

[Leer en Español](./GUIA_USUARIO.es.md)

This guide explains, in plain language, how to use the application and what the results of each analysis mean. You do not need any math or engineering background to interpret them.

---

## Getting Started

### What does this tool do?

It analyses telemetry and tells you **where you are gaining time, where you are losing it, and why**. It works in two ways:

- **Full session (1 CSV):** the session is split into laps automatically and you get a lap table, stint analysis (pace, fuel, tyres, pit window) and setup recommendations.
- **Lap comparison (2 CSVs, or 2 laps picked from a session):** a side-by-side comparison with corner-by-corner diagnosis and the advanced analyses (tyres, brakes, suspension, driving style, balance).

### Files you need

CSV files exported from **MoTeC i2** (Assetto Corsa via ACTI, iRacing). See [Exporting telemetry](#exporting-telemetry) for the steps and the channels the app understands.

### How to start

1. Install and start the backend and the frontend (see the [README](../README.md#quick-start)) and open `http://localhost:5173`.
2. In the top bar choose the language (ES/EN) and the mode: **Engineer** (everything) or **Pilot** (technical panels hidden).
3. Drop your CSV file(s) in the upload area. One file is treated as a full session; two files are treated as two single laps to compare.
4. Press analyze. A progress bar shows the steps. Large files can take a few minutes (a ~57 MB session took about 25 s); keep the tab open.
5. When it finishes, the upload area collapses into a file bar. Press **New analysis** to start over.

---

## The Interface at a Glance

The top bar holds the brand, the language switch and the Pilot/Engineer toggle. A **side rail** lets you jump between sections. The page is otherwise a single long view: **moving the mouse over any chart synchronises the cursor position across all the others**.

### Full session (1 CSV)

| Section | What it shows |
|---------|---------------|
| **Session overview** | Lap table, best lap, health panel, track map |
| **Stint analysis** | Lap-time evolution, degradation, fuel strategy, pit window, Monte Carlo projection, track evolution |
| **Setup & strategy** | Corner analysis across the session, tyre degradation, thermal management, racing line and setup recommendations |

**Lap table:** tick **two laps (A/B)** and press **Compare** to open a full comparison of those laps, or press **Best vs Worst** to compare the fastest and the slowest flying lap automatically. Laps marked **PIT** (in/out laps) and **outlier** (time far from the median) are excluded from the degradation and projection statistics.

**Health panel:** lists the analysis modules (thermal, setup, tyre degradation, racing line, slip, corners) as available or unavailable. Unavailable usually means the CSV does not contain the channels that module needs.

### Lap comparison (2 CSVs, or 2 laps of a session)

| Section | What it shows |
|---------|---------------|
| **Core lap** | Summary, speed trace + cumulative time delta, brake & throttle overlay, track map, corner analysis and sectors |
| **Vehicle dynamics** | G-G diagram, tyres, brakes, suspension, slip angle (hidden in Pilot mode) |
| **Driver & inputs** | Steering and pedal style (hidden in Pilot mode) |
| **Strategy & setup** | Lap-time potential, anomalies, setup recommendations and the engineer report (copy as text or download as PDF) |

Click a corner in the corner analysis and all charts zoom into that zone.

---

## How to Read Each Analysis

---

### Speed & Time Delta

**What you see:**
- Speed trace for both laps overlaid
- A "delta" line that rises and falls

**How to interpret it:**
- The delta line **rises** → Lap A is **losing time** relative to B in that zone
- The delta line **falls** → Lap A is **gaining time**
- If the delta ends positive (e.g. `+0.8s`), Lap A is slower by that amount

**Practical example:**
> The delta rises sharply at the braking point of corner 3 → you are braking late or too hard.  
> The delta falls at the exit of corner 5 → your corner exit is better than the other lap.

**Zoom by corner:** Click on any corner in the analysis table and all charts automatically zoom into that zone.

---

### Brake & Throttle

**What you see:**
- Two brake pressure traces (0–100%) overlaid
- Two throttle position traces (0–100%) overlaid

**How to interpret it:**
- If one brake trace starts **earlier** than the other → that driver brakes sooner (more conservative, or needs more distance)
- If the throttle curves have different shapes at the corner exit → difference in turn-in point or throttle progression

**What to look for:**
- Brake release and throttle application with no significant overlap
- A smooth, progressive throttle application through slow corners

---

### Track Map

Shows the circuit drawn from the GPS/game coordinates. The marker moves in sync with the cursor on the other charts, so you can locate yourself on track while analysing data.

---

### G-G Diagram (Friction Circle)

**What you see:**
- A scatter cloud showing all combinations of lateral and longitudinal force during the lap
- A circle representing the estimated grip limit

**How to interpret it:**
- **Points near the edge of the circle** → the driver is making good use of the available grip
- **Points in the centre** → grip is being left unused (conservative braking or cornering)
- **Empty corners** (no points at diagonal combinations) → the driver is not combining braking + steering or acceleration + steering efficiently

**The G-Sum efficiency** shown in the summary (0–100%) indicates how well total grip is being exploited on average.

---

### Corner Analysis

**What you see:**
- One card per detected corner showing: time gained/lost, braking diagnosis, exit diagnosis

**The status for each zone:**

| Colour | Meaning |
|---------------|---------|
| Green | No issue detected |
| Yellow | Minor difference (0.05–0.15 s) |
| Red | Significant difference (>0.15 s) |

**Common diagnoses you will see:**
- *"Late braking / hot entry"* → the braking point is compressed, time is lost through overheating of the manoeuvre
- *"Understeer at apex"* → the car runs wide at the vertex, speed is lost
- *"Slow throttle progression"* → the throttle opens too slowly on the exit

---

### Tyre Temperatures

**What you see:**
- Temperature of each tyre (FL, FR, RL, RR) across its 4 zones: Inner, Middle, Outer, and Core
- A colour-coded status per tyre
- The percentage of time spent in the optimal window

**The statuses:**

| Colour | Status | Temperature | What to do |
|--------|--------|-------------|------------|
| Light blue | Cold | < 65 °C | The tyre has poor grip. Normal for the first couple of laps. |
| Blue | Sub-optimal | 65–80 °C | Almost ready. Do not push hard on direction changes yet. |
| Green | Optimal | 80–100 °C | The tyre is in its working range. You can push. |
| Orange | Hot | 100–115 °C | Grip starts to drop. Be careful with overloading in long corners. |
| Red | Overheated | > 115 °C | The tyre is degraded. Grip drops quickly. |

**The ΔT gradient (Surface − Core):**
- If ΔT > 20 °C → the core has not reached working temperature, or there is internal mechanical stress
- A low and uniform ΔT → the tyre is working well across its full thickness

**Common patterns:**

| Pattern | Likely cause |
|---------|--------------|
| Inner much hotter than outer | Tyre pressure too high |
| Outer much hotter than inner | Pressure too low, or too much negative camber |
| All tyres cold for the entire lap | Cold track or installation lap |
| Only rear tyres overheated | Oversteer / excessive power-on throttle |
| Only front tyres overheated | Understeer / very aggressive braking |

---

### Brake Fade — Braking Efficiency

**What you see:**
- A braking efficiency score per lap (0–100)
- Fade zones marked on the track map
- Comparison against the baseline (reference from the first braking events)

**How to interpret it:**

Efficiency measures **how much deceleration you produce per 1% of pedal pressure**. If you press hard and the car does not brake the same as at the start of the stint → there is fade.

| Score | Meaning |
|-------|---------|
| > 90 | Brakes in perfect condition |
| 75–90 | Mild degradation, normal on long stints |
| 60–75 | Moderate fade. Possible overheating. |
| < 60 | Severe fade. The car is not braking as it should. Accident risk. |

**Fade zones:**
- The red bars on the distance chart mark where an efficiency drop >15% relative to the baseline was detected
- If fade always appears at the same corner → there is a specific cooling problem at that braking zone

**Practical tip:**
> If fade only appears in the final laps of a stint, that is normal (accumulated thermal degradation). If it appears from lap 2–3, the brake system may be undersized, or the air ducts are blocked.

---

### Driver Inputs — Driving Style

**What you see:**
- A **nervousness** index (0–100%) per lap
- The frequency distribution of steering corrections (FFT)
- The percentage of brake-throttle overlap

**The nervousness index:**

| Range | Interpretation |
|-------|---------------|
| 0–20% | Very smooth driver. Clean and stable inputs. |
| 20–40% | Normal. Some activity through difficult corners. |
| 40–60% | Reactive driver. Many micro-corrections. Possible chronic understeer being fought with the wheel. |
| 60–80% | Very nervous. The car is probably not balanced. |
| 80–100% | Extreme. The driver is fighting the car. |

**The frequency bands (FFT):**

| Band | Frequency | What it represents |
|------|-----------|-------------------|
| Low | < 0.5 Hz | Tracing inputs: long corners, slow direction changes |
| Mid | 0.5–2 Hz | Car balance: response to normal disturbances |
| High | > 2 Hz | Micro-corrections: the driver is "saving" situations |

A faster driver typically has **more power in the low band** (doing things earlier) and **less in the high band** (needing fewer corrections).

**Brake-throttle overlap:**
- A high % (>15%) is not always bad: in some cars it is a balance technique
- In most cases, high overlap = poorly coordinated pedal work = lost time

---

### Suspension — Pitch, Roll, and Bottoming

**What you see:**
- Roll (lateral lean) and pitch (longitudinal lean) traces throughout the lap
- Detected bottoming events (when the damper reaches its travel limit)

**Roll (lateral lean):**
- **Positive roll** → the car leans to the right (right-hand corner)
- **Negative roll** → it leans to the left (left-hand corner)
- If roll is very high → the car has low anti-roll bar stiffness, or the springs are too soft

**Pitch (longitudinal lean):**
- **Negative pitch** (nose down) → braking zone
- **Positive pitch** (tail down) → acceleration zone
- Exaggerated nose-dive under braking → soft front springs or insufficient damping

**Bottoming — Bottom-out events:**

A bottoming event is flagged when suspension travel reaches 90 % or more of the maximum travel observed in the file (a heuristic, not a measured limit). It is problematic because:
- The car suddenly goes rigid (grip loss)
- Aerodynamics become destabilised
- It can damage the bodywork

| Severity | Description |
|----------|-------------|
| 90-95% | Close to the limit but controlled (90% is the detection threshold) |
| 95–98% | Frequent bottoming. Recommended to adjust ride height or springs |
| > 98% | Severe bottoming. The car is making mechanical contact |

> If bottoming always occurs at the same corner → check the ride height in that section of the track (bump) or reduce the damper compression speed.

---

### Slip Angle — Car Balance

**What you see:**
- The β (beta) angle of the chassis: how much the car's centre of gravity slides laterally
- The balance αF − αR: whether the car tends to understeer or oversteer

**The β (sideslip) angle:**

| β | Meaning |
|---|---------|
| 0–2° | Neutral. The car follows the direction of the wheels. |
| 2–5° | Some slip. Normal in fast laps with a balanced car. |
| > 5° | Significant slip. The car is working outside its optimal point. |
| > 8° | The car is at the limit of control. Possible oversteer on corner exit. |

**The balance αF − αR:**

| Value | Interpretation |
|-------|---------------|
| > +2° | **Understeer**: the front wheels slide more than the rears. The car runs straight. |
| −2° to +2° | **Neutral**: the car responds as expected. |
| < −2° | **Oversteer**: the rear wheels slide more. The tail tends to step out. |

**How to use this data?**

If you see consistent understeer in medium/high-speed corners → the front setup needs more grip (higher pressure, more camber, less front anti-roll bar stiffness).

If you see oversteer at the exit of slow corners → the throttle is being opened too early, or the differential is too open.

**The US/Neutral/OS percentage:**
- A well-balanced car should be >60% neutral throughout the lap
- If you have >30% of time in understeer → the front setup is dominant

---

### Engineer Report

The **"Copy Report"** button generates text ready to paste into a WhatsApp group, Notion, or an email. It contains:
- Session metadata
- Summary of differences by corner
- The most important points from the advanced analysis

---

## Quick Glossary

| Term | Plain definition |
|------|-----------------|
| **Delta** | Cumulative time difference between two laps |
| **Apex** | The point closest to the inside of a corner |
| **Pitch** | The car tilts forward or backward (like braking hard on a bicycle) |
| **Roll** | The car leans to the sides through corners |
| **Bottoming** | The damper reaches its travel limit and bottoms out |
| **Understeer** | The car "goes straight" instead of turning. The front wheels lose grip. |
| **Oversteer** | The rear of the car tends to step out. The rear wheels lose grip. |
| **Fade** | The brakes lose efficiency due to overheating |
| **β (beta)** | Lateral slip angle of the whole chassis |
| **FFT / PSD** | Frequency analysis of steering corrections |
| **Nervousness** | Index measuring how many steering micro-corrections the driver makes |
| **ΔT** | Temperature difference between the tyre surface and core |
| **Stint** | Race period between two pit stops |
| **Lateral / longitudinal G** | Force felt through corners (lateral) or under braking/acceleration (longitudinal) |

---

## Exporting telemetry

The app reads **CSV files only**. Export them from the program you use:

**Assetto Corsa (ACTI + MoTeC i2)**
1. Record the session with the ACTI telemetry app (see the ACTI documentation for installation).
2. Open the log in **MoTeC i2** and use **File -> Export -> Export to Spreadsheet (CSV)**.
3. For a **single lap**, select that lap's time range; for a **full session**, select the whole range (lap 1 to the last lap). Export all channels, ideally at 60 Hz or more.
4. The header block of the MoTeC CSV (Driver, Vehicle, Venue) is read automatically and used for labels.

**iRacing**
1. iRacing records `.ibt` files; the app does not read `.ibt` directly. Convert them to CSV with MoTeC i2 or a third-party tool.
2. The loader detects iRacing exports by the `SessionTime`, `Session Time` or `SessionLapCount` columns and normalises units (speed m/s to km/h, pedals 0-1 to 0-100, suspension m to mm, tyre pressure kPa/PSI to bar).

**Required channels:** `Speed`, `Brake`, `Throttle`. If one is missing, the API returns a `400` error listing the columns it found.

**Recognised channels and aliases** (the loader renames them automatically; the full table is `COLUMN_ALIASES` in `src/io/loaders.py`):

| Category | Canonical name | Examples of accepted names |
|----------|----------------|----------------------------|
| Speed | `Speed` | `Speed`, `Ground Speed`, `Chassis Velocity X` |
| Distance | `Distance` | `Distance`, `Lap Distance`, `LapDistance` |
| Brake / Throttle | `Brake`, `Throttle` | `Brake Pos`, `Throttle Pos`, `Gas` |
| Steering | `SteerAngle` | `Steering Angle`, `Steering Wheel Angle` |
| Lateral / longitudinal G | `LateralG`, `LongitudinalG` | `Lateral Acc`, `CG Accel Lateral`, `Longitudinal Acc`, `CG Accel Longitudinal` |
| Yaw rate | `YawRate` | `Chassis Yaw Rate`, `Yaw Rate` |
| Lap counter | `SessionLapCount` | `Session Lap Count`, `Lap` |
| Position | `CarCoordX/Y/Z` | `Car Coord X/Y/Z` |
| Tyre temperature | `TyreTemp{Core,Inner,Middle,Outer}{FL,FR,RL,RR}` | `Tire Temp Core FL`, `Tyre Temp (I) FL`, `LFtempCL` |
| Tyre pressure | `TyrePress{FL,FR,RL,RR}` | `Tire Pressure FL`, `LFpressure` |
| Suspension travel | `SuspTravel{FL,FR,RL,RR}` | `Suspension Travel FL`, `LFshockDefl` |
| Brake temperature / bias | `BrakeTemp{FL,FR,RL,RR}`, `BrakeBias` | `Brake Temp FL`, `dcBrakeBias` |
| Water / oil temperature | `WaterTemp`, `OilTemp` | `Coolant Temp`, `Eng Oil Temp` |

Missing optional channels do not stop the analysis: the affected panel is shown as unavailable.

**What if there is no `Distance` channel?** The app synthesises it by integrating speed over a valid time clock (`LR/HR/MR Sample Clock`, `SessionTime`, `Time`, `Lap Time`...). Clocks that only toggle 0/1 are not used. The response flags this with `distance_synthetic`. It is accurate enough for session and stint analysis; for lap-to-lap comparison a real distance channel is more reliable.

---

## Data Quality Notes

- **Lap detection:** laps are found from the lap-counter channel or, if absent, from distance resets. Segments shorter than 30 s (partial laps, pit stubs) are discarded.
- **Pit and outlier laps:** laps with the `In Pit` channel active, or with a time outside 70-115 % of the median, are marked and left out of regressions and projections.
- **Corner windows** never overlap: each is trimmed halfway between neighbouring apexes. The summary reports the time delta inside corners (`corners_time_delta_s`) and outside them (`outside_corners_delta_s`). Corners of two laps are matched by apex distance.
- **"Not measurable" is not "zero":** if a braking or throttle delta shows `0.0` but is flagged as not available (`braking_delta_available` / `throttle_delta_available` = false), it could not be measured.
- **Constant channels:** a channel that never changes (for example brake temperatures stuck at one value) is reported as unavailable with a reason instead of producing made-up advice.
- **Slip angle:** the sign convention of lateral G is detected from its correlation with the yaw rate and flipped when needed (Assetto Corsa logs it inverted).
- **Invalid files:** an empty CSV, or one without `Speed`, `Brake` and `Throttle`, is rejected with a clear message.

## Example Result

Validated with a Porsche Cayman GT4 Clubsport at Imola (Assetto Corsa, MoTeC CSV of about 57 MB without a `Distance` channel):

- 21 laps detected (laps 1 and 21 are pit laps); best lap is lap 11 with 1:57.605; race laps between 117.6 and 122.4 s.
- Track length about 4862 m, top speed 243.9 km/h, 11 corners found by geometry.
- Fuel consumption 1.758 L/lap; pace trend -0.077 s/lap (the car gets faster as the fuel burns off, so this is an improvement, not tyre wear).
- The full analysis finished in about 25 s.

## Known Limitations

- Corner detection from speed alone finds 7 corners at Imola against 11 from geometry (chicanes merge into one).
- Bottoming detection is a heuristic: suspension travel at or above 90 % of the maximum travel observed in the file.
- Depending on the simulator and the export, some channels may be missing; the panels tell you when that is the case.

---

## Common Issues

**No corners detected:**
- The CSV has no usable distance data, or the data is very noisy
- Try with a complete lap (no cut laps)

**A panel says "unavailable" (check the health panel):**
- The CSV lacks the channels that module needs (tyre temperatures, brake temperatures, suspension travel, `YawRate` and `LateralG` for slip angle...)
- Channels with a constant value are also reported as unavailable

**The app says it could not find several laps:**
- A session file needs a lap-counter channel (`Session Lap Count`) or a distance that resets every lap
- Stint analysis needs at least 3 laps

**Error 400 when uploading:**
- The CSV is empty or does not contain `Speed`, `Brake` and `Throttle` (the message lists the columns that were found)

**Error 422 when comparing:**
- The selected lap is out of range, both laps are the same, or there are not enough valid flying laps for automatic selection

**Charts do not synchronise:**
- Move the cursor slowly; if the browser has high CPU usage there may be lag

**Analysis takes too long:**
- Session files of tens of MB can take tens of seconds or more in the backend; keep the tab open

---

## Recommended Workflow

```
1. Load the file(s) and wait for the analysis (for a session, pick two laps or use Best vs Worst)
2. Look at the TIME DELTA: where do the lines diverge?
3. Click on the corners where you lose the most time
4. Check the G-G: are you using all the available grip?
5. Review the tyres: are they at optimal temperature?
6. Check the balance (slip angle): is the setup balanced?
7. Look at the driving style: is the car forcing a lot of corrections?
8. Copy the engineer report to share with the team
```

*Also available in [Español](./GUIA_USUARIO.es.md)*
