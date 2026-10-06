# Quick Reference — Interpreting Results

[Ver en Español](./REFERENCIA_RAPIDA.es.md)

Cheat sheet for quick reference during or after a session. Full explanations: [User Guide](./USER_GUIDE.md).

---

## Tyres — Temperature States

| State | Range | Action |
|-------|-------|--------|
| Cold (blue) | < 65°C | Warm-up lap, do not push |
| Suboptimal | 65–80°C | Gentle, avoid heavily loaded corners |
| **Optimal** | **80–100°C** | **Ideal grip conditions** |
| Hot | 100–115°C | Reduce load or soften inputs |
| Overheated | > 115°C | Danger: grip severely reduced |

**Gradient ΔT > 20°C** → Internal stress. Possible pressure or compound issue.

### Diagnosis by temperature pattern

| Pattern | Most likely cause | Setup |
|---------|-------------------|-------|
| Inside >> Outside | High pressure | Reduce pressure |
| Outside >> Inside | Low pressure / too much camber | Increase pressure or reduce camber |
| Front tyres overheated | Understeer / hard braking | More front grip or brake balance adjustment |
| Rear tyres overheated | Oversteer / early power | Less throttle on exit or tighter diff |

---

## Brake Fade — Braking Efficiency

| Score | State | Action |
|-------|-------|--------|
| > 90 | Normal | No action required |
| 75–90 | Mild | Monitor over long stints |
| 60–75 | Moderate | Check air ducts or compound |
| < 60 | Severe | High risk. Pit stop or immediate adjustment |

**Fade always in a specific zone** → Localised problem (blocked duct, very long braking zone without cooling).  
**Progressive fade throughout the stint** → Normal in a long race with a soft compound.

---

## Driver Inputs — Nervousness

| NI (%) | Profile | Diagnosis |
|--------|---------|-----------|
| 0–20% | Smooth / clean | Ideal inputs, minimum wear |
| 20–40% | Normal | Natural activity in difficult corners |
| 40–60% | Reactive | Car may be unbalanced |
| 60–80% | Very nervous | Problematic setup or difficult track |
| 80–100% | Fighting | Uncontrollable car — review balance |

**FFT: high-band power (>2 Hz) elevated** → Driver is correcting errors instead of preventing them.  
**Brake-throttle overlap > 15%** → Pedal coordination to improve, or deliberate technique (trail braking).

---

## Suspension

### Bottoming

| Severity | Travel | Action |
|----------|--------|--------|
| Normal | < 90% of maximum | No changes |
| Alert | 90–95% | Check ride height |
| Critical | > 95% | Raise car or stiffen spring / compression |

**Excessive pitch under braking** → Soft front springs or insufficient compression damping.  
**Excessive roll in corners** → Soft anti-roll bars or soft springs.

### Roll/Pitch Signs

| Positive value | Negative value |
|----------------|----------------|
| Roll (+): load to the right | Roll (−): load to the left |
| Pitch (+): tail down (acceleration) | Pitch (−): nose down (braking) |

---

## Slip Angle — Car Balance

### Sideslip β

| β | Behaviour |
|---|-----------|
| 0–2° | Neutral, car follows steering direction |
| 2–5° | Controlled slip (normal at the limit) |
| 5–8° | Operating outside the optimal window |
| > 8° | Control limit — risk of spin-off |

### Balance αF − αR

| Value | Meaning | Setup to check |
|-------|---------|----------------|
| > +2° | Understeer (front tyres sliding) | Reduce front pressure, soften front bar, more camber |
| −2° to +2° | Neutral — ideal | Maintain setup |
| < −2° | Oversteer (rear stepping out) | Increase rear pressure, open diff, ease throttle on exit |

**% US / Neutral / OS during the lap:**
- Target: >60% of time neutral
- >30% understeer → very understeery setup, the car is losing lap time
- >20% oversteer → risk of excursions or track offs

---

## Time Delta — Where You Gain / Lose

| When the delta line... | It means... |
|------------------------|-------------|
| Goes up → | A is slower than B in that zone |
| Goes down → | A is faster than B in that zone |
| Flat | No difference |
| Spikes up sharply | Isolated problem point (braking, apex) |
| Rises gradually | Lower cornering speed throughout the corner |

---

## G-G Diagram — Grip Utilisation

| G-Efficiency | Interpretation |
|--------------|----------------|
| > 80% | Excellent use of available grip |
| 60–80% | Room for improvement, likely in braking or exits |
| < 60% | Driver is not taking the car to its limit |

**The 4 corners of the diagram:**
- Top-right: acceleration + right turn — are there points there? If not, throttle and cornering are not being combined
- Bottom-left: braking + left turn — trail braking

---

## Optimal Lap by Microsectors

| Figure | Meaning | Use it as |
|--------|---------|-----------|
| **Best lap** | Your fastest valid lap | Reference |
| **Realistic optimal** | Best microsectors stitched together only where speeds match (3 km/h) and with at least 75 m on the same lap | Target |
| **Theoretical optimal** | Sum of the best time of every microsector (ignores speed continuity) | Optimistic lower bound |

- Microsector 10 / 25 / 50 / 100 m: the theoretical figure gets faster as the microsector shrinks. Compare, do not chase.
- Needs 3 or more valid laps. With a synthesised `Distance` the result is indicative only (warning shown).
- Zones table: where the best lap loses most, which lap to take it from, what to look at.
- Imola example: best 1:57.605, realistic 1:54.107 (-3.498 s), theoretical 1:52.885 (-4.720 s).

---

## Data-Quality Score

| Score | Level | What to do |
|-------|-------|-----------|
| 75-100 | Good | Trust the results |
| 50-74 | Fair | Read "How to improve"; some panels are degraded |
| 0-49 | Poor | Fix the export first (missing or constant channels, too few laps) |

Weights: channels 40 %, laps 20 %, analysis modules 40 %. Channel states: OK, Missing, Constant, Synthesized, Partial, Gaps, Inactive. Module states: OK, Degraded, Unavailable.

---

## Setup Link (Assetto Corsa)

| Step | Where it looks |
|------|----------------|
| 1 | `<Documents>\Assetto Corsa\setups\<car>\<track>\*.ini` (or the folder in `AC_SETUPS_DIR`) |
| 2 | `<car>\generic\last.ini`, only after you confirm it was used |
| 3 | Manual upload of the `.ini` (always works; the only option in Docker unless the folder is mounted read-only) |

Recommendations then show **Current -> Suggested**. Units appear only where they are certain (psi, % brake bias and power, litres); otherwise raw game clicks. Conflicting suggestions: change one thing at a time.

---

## Formats, Limits and Status Codes

| Item | Value |
|------|-------|
| CSV (MoTeC / ACTI, iRacing) | Stable |
| `.ibt` iRacing, `.ld` MoTeC | **Experimental** (validated with 53 files of one author) |
| Minimum channels | Speed, Brake, Throttle |
| Upload limit | `MAX_UPLOAD_MB` per file (2048 by default), HTTP 413 above it |
| Saved library session | 5 MB maximum (HTTP 413) |
| Setup file | `.ini`/`.sp`, 256 KB maximum |
| HTTP 410 | The server lost the uploaded copy: the app uploads again and retries |
| Stint / optimal lap | 3 or more valid laps |
| Projection confidence | Always low below 8 valid laps; fallback to recent pace below 5 |
| Circuits | 19 recognised; 7 with corner names (Imola, Spa, Silverstone GP, Le Mans, Monaco = high confidence; Mugello, Brands Hatch GP = medium) |
| Two-file compare | 2 files with one lap each: first = reference, second = compared; warns if the cars differ |
| Tests | `python -m pytest tests -q`: 585 collected, 551 run, 34 e2e skipped without `E2E=1` |

---

## Two-File Compare Mode

Drop two files with one lap each (reference lap first). The app calls `/api/compare-laps` and `/api/telemetry/analyze` and merges both results and their metadata.

| Case (Red Bull Ring) | Result |
|----------------------|--------|
| Porsche Cayman GT4 fast lap vs slow lap (same car) | +3.25 s, no vehicle warning |
| Same fast lap vs Maserati GT MC GT4 lap | +1.44 s, **different-vehicles warning** (the gap includes the car difference) |

---

## Containers: Quick Fixes

| Symptom | Fix |
|---------|-----|
| `required variable POSTGRES_PASSWORD is missing a value` | `cp .env.example .env` and set the password |
| Docker Desktop: "Virtualization support not detected" | Enable VT-x/SVM in BIOS/UEFI, `wsl --install`, reboot |
| First backend build over 10 minutes / pip `read operation timed out` | Normal on the first build; run it again |
| kind: `migrate` fails 1-2 times (`failed to resolve host postgres`) | Normal; check `kubectl -n motorsport get pods` |
| PowerShell `curl` misbehaves | Use `curl.exe` |

Full list: [Deployment](./DEPLOYMENT.md#troubleshooting).

---

## Quick Diagnosis Guide

### "I am slow under braking"
1. Check the Time Delta: does the loss start before or after the braking point?
2. If before → you arrive quickly but the braking point is correct, the issue is the exit speed from the previous straight
3. If right at the brake point → try braking later
4. Check whether Brake Fade is active in those corners

### "The car won't turn in"
1. Check the balance (slip angle): is the % understeer high?
2. Look at the front tyres: are they overheated?
3. Check the G-G: are you combining braking and cornering (trail braking)?

### "The rear of the car moves around a lot"
1. Check sideslip β: are there peaks > 5° on exits?
2. Check the nervousness index: steering corrections on corner exit
3. Look at rear tyre temperatures: are they overheated?

### "The tyres are not coming up to temperature"
1. Confirm that the CSV has tyre temperature channels
2. Verify that you are not on an installation lap (outlap)
3. If still cold → check compound, pressure, or lack of aerodynamic downforce

### "The advanced results are not showing"
Some modules require specific channels:

| Module | Required channels |
|--------|------------------|
| Tyre temperature | TyreTempInner/Middle/Outer/CoreFL/FR/RL/RR |
| Brake Fade | LongitudinalG + Brake |
| Driver inputs | SteerAngle |
| Suspension | SuspTravelFL/FR/RL/RR |
| Slip angle | LateralG + YawRate + SteerAngle |

If any of these channels is not present in your MoTeC CSV, that module is reported as unavailable (see the health panel) instead of showing made-up results. A channel that never changes (for example brake temperatures fixed at one value) is also reported as unavailable. Bottoming is flagged at 90 % or more of the maximum travel observed. Minimum channels for any analysis: Speed, Brake, Throttle; a missing Distance is synthesised from speed (flagged `distance_synthetic`).

---

## Analysis Session Flow

```
Load the file(s): 1 file = session, 2 files = lap comparison (one lap each)
    ↓
Read the data-quality score first
    ↓
How much time am I losing and where? → Time Delta + Corners
    ↓
Why am I losing it? → G-G + Slip Angle (understeer/oversteer)
    ↓
Is the car up to temperature? → Tyres
    ↓
Are the brakes working correctly? → Brake Fade
    ↓
Is driving style the problem? → Driver Inputs
    ↓
Is the mechanical setup the problem? → Suspension + Slip Angle
    ↓
Optimal lap → which zones still cost time?
    ↓
Link the setup, save to the library, download the PDF report → share with the team
```

*Also available in [Español](./REFERENCIA_RAPIDA.es.md)*
