# User Guide — Motorsport Analytics Pipeline

🌐 [Leer en Español](./GUIA_USUARIO.es.md)

This guide explains, in plain language, how to use the application and what the results of each analysis mean. You do not need any math or engineering background to interpret them.

---

## Getting Started

### What does this tool do?

It compares two telemetry laps side by side and tells you **where you are gaining time, where you are losing it, and why**. It also analyses tyre condition, brakes, suspension, and driving style — all automatically.

### Files you need

CSV files exported from **MoTeC i2** or any compatible simulator (Assetto Corsa, etc.). Each file represents a lap or a session.

### How to start

1. Open the app in your browser (`http://localhost:5173`)
2. Drag or select **two CSV files** in the upload panel
3. Click **"Compare Laps"**
4. Wait a few seconds — the full analysis loads automatically

> If the file contains multiple laps, the system picks the two fastest valid ones.

---

## The Interface at a Glance

The page is a single long view with sections. You can scroll through it or use the interactive crosshair cursor: **moving the mouse over any chart synchronises the position across all the others**.

| Section | What it shows |
|---------|---------------|
| **Header** | Driver name, vehicle, circuit, lap time for each lap |
| **Speed & Delta** | Speed trace + cumulative time difference |
| **Brake & Throttle** | Overlay of both laps for braking and throttle |
| **Track Map** | Circuit layout with the current position |
| **G-G Diagram** | Total grip used per lap |
| **Corner Analysis** | Table with times, braking, and acceleration per corner |
| **Tyres** | Temperature and interpretation for all 4 tyres |
| **Brakes** | Efficiency and thermal fade detection |
| **Driver Inputs** | Driving style at the wheel (smooth vs. nervous) |
| **Suspension** | Roll, pitch, and bottoming events |
| **Slip Angle** | Car balance (understeer vs. oversteer) |
| **Engineer Report** | Exportable text with the full summary |

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

| Icon / Colour | Meaning |
|---------------|---------|
| Green ✓ | No issue detected |
| Yellow ⚠ | Minor difference (0.05–0.15 s) |
| Red ✗ | Significant difference (>0.15 s) |

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

A bottoming event occurs when the damper reaches its travel limit. This is problematic because:
- The car suddenly goes rigid (grip loss)
- Aerodynamics become destabilised
- It can damage the bodywork

| Severity | Description |
|----------|-------------|
| < 95% | Close to the limit but controlled |
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

## Common Issues

**No corners detected:**
- The CSV has no distance data, or the data is noisy
- Try with a complete lap (no cut laps)

**Tyres always shown as "cold":**
- The CSV does not include tyre temperature channels (TyreTempInner, TyreTempMiddle, etc.)
- Verify that the MoTeC channel set includes wheel temperatures

**Slip angle analysis does not appear:**
- The CSV needs `YawRate` and `LateralG` channels
- If the simulator does not export YawRate, this module is disabled automatically

**Charts do not synchronise:**
- Move the cursor slowly — synchronisation happens every frame at 60 fps
- If the browser has high CPU usage, there may be lag

**Analysis takes too long:**
- CSVs with more than 50,000 rows can take 10–20 seconds in the backend
- Normal for long laps (>5 minutes) with a high sampling rate

---

## Recommended Workflow

```
1. Load the two laps → wait for the analysis
2. Look at the TIME DELTA: where do the lines diverge?
3. Click on the corners where you lose the most time
4. Check the G-G: are you using all the available grip?
5. Review the tyres: are they at optimal temperature?
6. Check the balance (slip angle): is the setup balanced?
7. Look at the driving style: is the car forcing a lot of corrections?
8. Copy the engineer report to share with the team
```

*Also available in [Español 🇪🇸](./GUIA_USUARIO.es.md)*
