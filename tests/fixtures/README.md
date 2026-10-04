# Real telemetry fixtures

Small cut-outs of **real** Assetto Corsa / MoTeC CSV exports, used by
`tests/test_regression_real.py` (and the e2e tests) to catch bugs that synthetic data never
shows: Distance synthesized from an invalid clock, partial segments, overlapping corner
windows, 3-point extrapolation, LateralG sign conventions...

| File | Origin | Content | Size |
|---|---|---|---|
| `imola_5laps.csv.gz` | `cayman_gt4_imola_assetto_corsa.csv` (Porsche Cayman GT4, Imola, 21 laps) | session laps 1-5 (the first one is slow: out lap), ~6000 samples, tyre wear active | ~340 KB |
| `spa_3laps.csv.gz` | `porsche_gt4_spa.csv` (Porsche Cayman GT4, Spa) | 3 full laps + a trailing half lap, tyre wear **disabled** in the simulator | ~325 KB |
| `rbr_fast.csv.gz` | `vuelta_rapida.csv` (Porsche Cayman GT4, Red Bull Ring) | ONE fast lap, all rows | ~60 KB |
| `rbr_slow.csv.gz` | `vuelta_lenta.csv` (same car and track) | ONE slow lap (~3.2 s slower), all rows | ~60 KB |
| `rbr_other_car.csv.gz` | `vuelta_rapida_mc.csv` (Maserati GT MC GT4, same track) | ONE fast lap with a **different car** | ~70 KB |

The three `rbr_*` files cover the **two-file compare mode** (`/api/compare-laps` + `/api/telemetry/analyze`) used by `tests/test_compare_two_laps.py` and the e2e tests. Regenerate with `--lap-fast`, `--lap-slow` and `--lap-other-car` (see `scripts/make_fixtures.py`).

## What is kept

* The MoTeC header (venue, vehicle, units row, comma-decimal number format) unchanged.
* The original channel names. Roughly 56 of 169 channels remain: everything the pipeline reads
  (speed, pedals, G, steering, yaw rate, coordinates, tyre/brake temperatures, pressures, fuel,
  suspension travel, lap/pit/clock channels, tyre rubber grip and wear-rate for
  `detect_wear_tracking`). Damage, torques, radii, wind, ERS/KERS, camber, etc. were dropped.
* Samples decimated from 20 Hz to **10 Hz** and trimmed to whole laps (via `Session Lap Count`).
* The `Distance` channel does not exist in these files, so the loader synthesizes it from
  `Session Time Left` (as with the real files): that is part of what is being tested.

## Personal data

The originals belong to the repository owner and contain his **driver name** in the header.
The generator **anonymizes the `Driver` field by default** (it becomes `Test Driver`); use
`--no-anonymize` only for private, local use and never commit the result.

## Regenerate

The source CSVs are not in the repository:

```bash
python scripts/make_fixtures.py \
    --imola path/to/cayman_gt4_imola_assetto_corsa.csv \
    --spa   path/to/porsche_gt4_spa.csv
# options: --out DIR  --step N (decimation, default 2)  --no-anonymize
```

The output is deterministic (gzip with `mtime=0`). Files use the `.csv.gz` extension on
purpose: `*.csv` is tracked with Git LFS (`.gitattributes`) and these small fixtures must be
plain blobs. Tests decompress them to a temporary `.csv` before uploading.
