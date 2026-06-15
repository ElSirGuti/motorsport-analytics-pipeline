# Quick Reference — Interpreting Results

🌐 [Ver en Español](./REFERENCIA_RAPIDA.es.md)

Cheat sheet for quick reference during or after a session.

---

## Tyres — Temperature States

| State | Range | Action |
|-------|-------|--------|
| Cold (blue) | < 65°C | Warm-up lap, do not push |
| Suboptimal | 65–80°C | Gentle, avoid heavily loaded corners |
| **Optimal** ✓ | **80–100°C** | **Ideal grip conditions** |
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

If any of these channels is not present in your MoTeC CSV, that module is automatically disabled and will not appear in the view.

---

## Analysis Session Flow

```
Load the CSVs
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
Copy the report → share with the team
```

*Also available in [Español 🇪🇸](./REFERENCIA_RAPIDA.es.md)*
