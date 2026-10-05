# Corner detection: the unified corner map

Module: `src/analytics/corner_map.py` (`build_corner_map`). Measurement: `scripts/benchmark_corners.py` and `scripts/crossval_corner_map.py`. Reports: `docs/benchmarks/corners_baseline_legacy.*` (before), `corners_baseline.*`, `corners_after_core.*` (after, with before/after comparison and cross-validation) and `corners_crossval.json`.

Stage 1 is the core and its measurement (sections 1 to 8). Stage 2a migrated the backend consumers (stint, per-session corner analysis, insights, comparison, optimal lap, racing line, setup advisor, PDF, `main.py`) to the map: see section 9. The UI (stage 2b) still has to use the new fields.

## 1. The problem

The project had two families of corner detectors that disagree, plus a segmenter on top of one of them:

- speed minima (`metrics.detect_apex_points`): needs the car to slow down;
- curvature of the telemetry coordinates (`geometry.detectar_apexes_perfectos`): sees bends but also noise;
- the segmenter (`metrics.segment_corners`: braking + apex + full throttle), used by stint and per-session analysis: needs all three events.

On one Imola lap they gave 5 vs 11 apexes (session mode 7 corners, comparison mode 11). A corner a car takes flat out has no speed minimum: Variante Bassa at Imola (minimum geometric radius 478 m, speed always rising with a GT4), and with high-downforce cars also Eau Rouge/Raidillon (164 m) and Blanchimont (203 m) at Spa, fast corners at Silverstone. Measured baseline on 81 real laps (recall of named corners, `docs/benchmarks/corners_baseline_legacy.md`): speed 0.73, geometry 0.90, segmenter 0.78, union 0.95 (Silverstone 0.73, the weakest), with 1.1 to 4.5 extra detections per lap.

## 2. The algorithm

`build_corner_map(laps, venue=None, lap_length_m=None, options=None)` returns `{"corners": [...], "discarded": [...], "summary": {...}}`. `laps` is one DataFrame or a list of clean laps (raw or aligned) with `Distance` and `Speed` and, when present, `Brake`, `Throttle`, `CarCoordX/Y` (or the yaw/GPS channels `geometry.py` can use). It only reads the versioned JSON files (never the installed game) and is deterministic.

1. **Candidates per lap.** Speed minima, curvature peaks and braking zones, computed on a 1 m grid so the result does not depend on the sampling rate. Detections of different detectors closer than `merge_detectors_m` are one event. A braking zone with no event after it becomes a candidate itself (at its release point).
2. **Consensus across laps.** Events are clustered by lap fraction (half-width `max(cluster_tol_min_m, cluster_tol_frac * length)`), each lap counting once per cluster. A cluster is kept when it appears in at least `min_share` of the laps. With fewer than 3 laps the consensus is relaxed (`relaxed_share`; with 1 or 2 laps any lap is enough), `confidence` is scaled down and a warning is added. The position is the median over laps.
3. **Track template** (only if the circuit is recognised by `circuits.recognize`, i.e. venue known and measured length within 4 %). Candidates: the sub-apexes of `src/data/track_geometry/<id>.json` with radius below `template_max_radius_m` and all tabulated corners of `circuits.json` (even above that radius). Each atom close to a tabulated corner is owned by it (one to one). A telemetry cluster within `match_pad_m` of a template corner supports it and refines its position, shrunk towards the template: `pos = template + n/(n + prior_laps) * (telemetry - template)`, where `n` is the number of laps with evidence. A template corner with **no** telemetry evidence is kept, with kind `flat_out` (or `kink` if it is unnamed and nearly straight), at its geometric (or tabulated) position, instead of being dropped.
4. **Unbacked telemetry.** On a known circuit, a telemetry-only cluster needs `unbacked_min_support` or it goes to `discarded` (reason `no track/table backing`). Without a template (unknown circuit) the telemetry consensus is trusted as is.
5. **Compound corners.** Atoms or clusters closer than `group_gap_m` (and spanning at most `group_max_span_m`, so a whole sector is never chained) become ONE corner with `sub_apexes`, `is_complex: true`. Two separately tabulated corners are never merged (Rivazza 1 and 2).
6. **Names.** `circuits.assign_names` (one to one, in lap order, no duplicates). A tabulated corner nobody found is a virtual `flat_out` corner already created in step 3. Unnamed unbacked bends sharper than `kink_max_radius_m` are kept as `kink`; flatter ones are listed in `discarded`.
7. **Evidence and kind** (independent of which detector fired): for every corner and every lap the module measures a speed minimum (recovery of at least `speed_drop_min_kmh` on both sides), the brake peak (`brake_present_pct`), the throttle minimum (`throttle_lift_pct`) and the curvature. `kind` is `braking` if braked in at least `braking_share` of the laps, else `lift` (speed minimum or throttle lift in at least half), else `flat_out` / `kink`. `flat_out_share` is the share of laps with neither a minimum, nor braking, nor a lift.

### Output per corner

`number` (1..N in lap order), `name`, `table_order`, `fraction`, `apex_distance_m`, `start_m`, `end_m` (approximate window: brake lead or 30 m before the first sub-apex to 40 m after the last, cut at the midpoint to the neighbours), `kind`, `direction` (`left`/`right`, from the geometry or the telemetry coordinates), `min_radius_m` (track geometry if available, else a coarse telemetry estimate smoothed over 75 m), `sources` (`speed`, `geometry`, `brake`, `track_geometry`, `table`), `confidence` (0..1, noisy-or of the telemetry support, 0.6 for geometry backing and 0.5 for table backing), `evidence` (`laps_found`, `laps_total`, `detection_share`, `speed_min_kmh`, `speed_min_share`, `speed_drop_kmh`, `brake_peak_pct`, `brake_share`, `throttle_min_pct`), `is_complex`, `sub_apexes` (`fraction`, `distance_m`, `radius_m`, `direction`) and `flat_out_share`. The `summary` has `n_corners`, `n_named`, `n_discarded`, `n_laps`, `lap_length_m`, `circuit`, `method`, `params`, `warnings`.

### Additions to `circuits.json`

Imola now has corner 9, Variante Bassa (`apex_fraction` 0.94, `"kind": "flat_out"`). The telemetry curvature peak of the Imola laps (several cars) is at about 0.94 to 0.95 and the AC racing line puts the minimum radius (478 m) at 0.923; 0.94 is within 85 m of both. The optional per-corner `"kind"` (`braking`, `lift`, `flat_out`, `kink`) is validated by `validate_database` and ignored by `assign_names`; a flat-out corner needs no detectable apex, so the "far from every geometric corner" warning skips it and `ac_track_geometry.compare_with_table` does not report it as a table corner without a peak.

## 3. Parameters

| Parameter | Default | Meaning and why |
|---|---|---|
| `merge_detectors_m` | 60 | Same value as the benchmark union and `circuit_apexes.py` deduplication. |
| `brake_zone_search_m` | 150 | A braking zone is its own candidate only if nothing is found within this after it. |
| `cluster_tol_frac`, `cluster_tol_min_m` | 0.012, 60 | Cluster half-width: 1.2 % of the lap, at least 60 m. The grid prefers 90 m, but that changes only Monaco (objective 0.842 against 0.831) and 90 m merges two apexes 80 m apart, so the chicane resolution was kept. |
| `min_share` | 0.6 | Share of laps a candidate must appear in (as in `circuit_apexes.py --min-share`). |
| `relaxed_share`, `relaxed_below_laps` | 0.5, 3 | Consensus with fewer than 3 laps. |
| `template_max_radius_m` | 400 | Same cut as the geometry export. |
| `table_atom_tol_m` | 150 | An atom this close (and within the circuit tolerance) to a tabulated corner belongs to it. |
| `match_pad_m` | 90 | Telemetry within this of a template corner supports it. |
| `unbacked_min_support` | 0.4 | Telemetry-only corner on a known circuit needs this support (`share * reliability * detectors`). |
| `prior_laps` | 4 | The template counts as 4 laps of evidence (shrinkage); 0 = pure telemetry position. |
| `kink_max_radius_m`, `kink_radius_m` | 200, 200 | Boundary between a corner and a kink (the "fast" class starts around 150 m). |
| `group_gap_m`, `group_max_span_m` | 120, 200 | Compound corners: the chicane rule, with a span cap (without it Monaco chained 5 atoms over 290 m and merged Grand Hotel and Portier). |
| `speed_drop_min_kmh` | 3 | Smallest recovery that counts as a speed minimum. |
| `brake_present_pct` | 8 | Brake pressure that counts as braking (above the 3 % of `detect_braking_points`, which catches touches). |
| `throttle_lift_pct` | 85 | Throttle below this near the apex is a lift. |
| `braking_share` | 0.5 | Share of laps braked for `kind: braking`. |
| `min_confidence` | 0.3 | Corners below this go to `discarded`. |

Only `min_share`, `cluster_tol_min_m`, `match_pad_m`, `unbacked_min_support` and `group_gap_m` were searched (243 configurations); the rest are reasoned values.

## 4. Validation

`scripts/crossval_corner_map.py` runs leave-one-circuit-out over Imola, Spa, Silverstone, Le Mans and Monaco (81 real laps, 15 files, 4 cars plus the project fixtures): for each circuit the five parameters above are chosen looking only at the other four, and evaluated on the left-out one. To avoid circularity the tuned variants do NOT inject the table (`use_table=False`): `map_no_table` (consensus), `single_lap_no_table` and `map_telemetry` (telemetry only, no template). Objective: `recall - 0.10 * noise - 0.02 * extras` (noise = detections that are neither a tabulated corner nor within 80 m of a geometric corner).

Result: 4 of the 5 folds choose the configuration that is best with all circuits (`min_share` 0.6, `cluster_tol_min_m` 90, `match_pad_m` 90, `unbacked_min_support` 0.4, `group_gap_m` 120); the Monaco fold chooses `cluster_tol_min_m` 60. The defaults of `corner_map` are that configuration except `cluster_tol_min_m` 60 (see the table), so the cross-validated and the in-sample numbers coincide (recall 0.92 without the table, noise 0.02 per lap). The objective over the grid ranges from 0.760 to 0.842 (median 0.783); the defaults score 0.831. The optimum is stable, but five circuits of one simulator is a small sample, and the template dominates the result (the parameters matter little once the geometry is there; they matter for `map_telemetry`).

Extra out-of-sample check: an Imola file with a car not used for the design (`f1_2020_mercedes`, 9 laps, added after the baseline and therefore not in the tables) gives `map_no_table` recall 1.00 on the detectable corners (0.89 with Bassa), 0 noise, 1.0 extra per lap; the union detector gives 1.00 with 3.0 extras and 0.89 noise per lap.

## 5. Results, before and after

81 real laps, recall of named corners without Variante Bassa (so it is comparable with the baseline, which had 8 Imola corners), extras per lap = detections without a tabulated corner:

| | Recall | Extras/lap | Noise/lap | Position std (m) |
|---|---|---|---|---|
| speed (before) | 0.73 | 1.86 | 0.43 | 33.3 |
| geometry (before) | 0.90 | 3.57 | 0.41 | 29.5 |
| segmenter (before) | 0.78 | 1.14 | 0.26 | 32.7 |
| union (before) | 0.95 | 4.43 | 0.80 | 28.0 |
| `corner_map` (with table, circular) | 1.00 | 2.96 | 0.00 | - |
| `map_no_table` (not circular) | 1.00 (0.92 with Bassa) | 2.85 | 0.00 | - |
| `single_lap_no_table` | 1.00 (0.92 with Bassa) | 2.52 | 0.00 | 23.9 |
| `map_telemetry` (no template) | 0.91 (0.84) | 1.64 | 0.06 | - |

By circuit, `map_no_table` (detectable recall / extras): Imola 1.00 (0.89 with Bassa) / 1.0, Le Mans 1.00 / 16.6, Monaco 1.00 / 4.0, Silverstone 1.00 / 5.0 (before 0.73), Spa 1.00 / 2.0. Without any template (`map_telemetry`) Silverstone is 0.68 (Monaco 0.83, Spa 0.93, Imola 0.92, Le Mans 1.00): the improvement there comes from the track geometry, not from the consensus.

Consensus alone (`map_telemetry`) gives 0.91 recall with 1.6 extras and 0.06 noise; the template adds the corners the car does not slow down for. The std of the position between laps is not defined for the consensus maps (one map for all laps); the lap-by-lap map has 24 to 25 m (25.0 with the table, 23.9 without) against 28 to 33 m for the old detectors (the shrinkage towards the template is part of that, see limits).

Objectives and honest reading:

- Recall of named corners >= 0.95 overall and >= 0.90 per circuit: met without the table (1.00 on every circuit; Imola 0.89 only because Variante Bassa cannot be found without the table, see below), and 1.00 with it.
- Extras per lap <= 2: NOT met (2.5 to 3.0 overall). Most "extras" are real corners that the tables do not list (Le Mans has 4 tabulated corners and about 21 corners; Silverstone 10 of 15). The measure that separates noise from real corners is noise per lap, which fell from 0.8 (union) to 0.0.
- Variante Bassa is produced as a named `flat_out` corner even with a GT4 (flat-out share 95 % in the 21-lap Imola file), but only through the table: its radius (478 m) is above the 400 m cut of the geometry export, so `use_table=False` cannot name it.
- Position std lower than the best old detector: met for the lap-by-lap map (23.9 to 25.0 against 28.0), at the price of shrinking positions towards the template.

## 6. Limits

- The template exists for the 16 Assetto Corsa circuits only, and was derived from the AI racing line; the validation data are all Assetto Corsa. For other simulators the positions are fractions of the lap and should carry over, but this has not been measured. A circuit without geometry or table uses the telemetry consensus (recall 0.91 on the known circuits with the template switched off, noticeably worse on Silverstone and Monaco).
- Extras are still counted against partial tables; cars that never brake at a corner give `flat_out_share` close to 1 and kind `lift` or `flat_out` per car, not per circuit.
- `min_radius_m` of a corner with no geometric atom (Bassa, unknown circuits) is a coarse telemetry estimate, and `direction` there comes from the telemetry coordinates.
- `start_m` / `end_m` are approximate windows, not curvature extents.
- Position shrinkage trades fidelity to the actual apex of one lap for stability across laps: if you need the lap's own apex, use `options={"prior_laps": 0}` or the evidence windows.
- With 1 or 2 laps there is no real consensus (relaxed mode, lower confidence); a spurious apex of a single lap is kept if the circuit has no template.
- Several corners that are separated in the table and close together (Rivazza 1 and 2, 128 m) rely on the table to stay separate; without it a chain of atoms is split only by `group_gap_m` and `group_max_span_m`.

## 7. How to add a circuit

1. Recognition entry in `src/data/circuits.json` (id, aliases, length, `corners: []`).
2. Geometry (car-independent): `python scripts/ac_track_reference.py <track> --compare` then `--export-all` writes `src/data/track_geometry/<id>.json` from the game's AI line (read-only on the game folder). With it the map already finds every bend sharper than 400 m, named or not.
3. Names: find where the corners are on real laps with `python scripts/circuit_apexes.py LOG.csv --json`, name them with the official layout in front of you, and add them (strictly increasing `apex_fraction`, `order`). A bend the car takes flat out will not appear in that list: take its position from the geometry (`scripts/ac_track_reference.py`) and add it with `"kind": "flat_out"`.
4. Check with `python scripts/benchmark_corners.py FOLDER --circuit <id>` and `python -m pytest tests/test_circuits.py tests/test_corner_map.py -q`.

## 8. Reproduce

```bash
python scripts/benchmark_corners.py FOLDERS... --md out.md --out out.json \
    --compare docs/benchmarks/corners_baseline_legacy.json --crossval docs/benchmarks/corners_crossval.json
python scripts/crossval_corner_map.py FOLDERS... --out docs/benchmarks/corners_crossval.json   # about 90 s
```

The reports in `docs/benchmarks/` were produced with the author's telemetry folders plus `tests/fixtures`; the `f1_2020_mercedes` file was excluded (`--exclude f1_2020`) to keep the 81 laps of the baseline.

## 9. Integration: the map is the only source of corners (stage 2a)

Since stage 2a every analysis takes its corners from the map (switch `CORNER_DETECTION=map`, the default; `legacy` keeps the previous per-module detectors untouched, for comparison or rollback; see `docs/DEPLOYMENT.md`). The map is built **once per session** and shared between endpoints: `src/analytics/corner_service.py` builds it and `session_cache.corner_map_cache` (small LRU, `CORNER_MAP_CACHE_MAX` entries, same TTL as the frame cache) stores it under the key `(purpose, file SHA-256 / file_id, venue, lap length, options)`. A second endpoint, or a second upload of the same bytes, reuses the first build (about 0.25 to 0.4 s for a 21-lap Imola file). A map that cannot be built or has no corners never breaks an analysis: that request falls back to the legacy path.

| Consumer | What changed |
|---|---|
| `analyze-session`, `stint/analyze`, `optimal-lap`, `compare-session-laps`, `/api/report/pdf` | Session map from the clean flying laps of the file (`select_map_laps`: no pit/outlier laps, the usual lap length +-4 %, the 30 fastest). Same corners, numbers and names in all of them. |
| `compare-laps`, `telemetry/analyze`, `telemetry/compare` | Map of the two compared laps (relaxed consensus, template if the circuit is recognised). `compare-laps` and `telemetry/analyze` share one build. |
| `session_corner_analysis` (`curvas_sesion`) | Per lap, the metrics are measured inside the map windows `start_m`..`end_m` against the reference (fastest) lap (`src/analytics/corner_metrics.py`) instead of detecting corners and `pair_corners`. |
| `racing_line_rl`, `setup_sesion` | Same observations. `flat_out` / `kink` corners are not trained and not coached; a delta not measurable in a lap counts as "similar" for the Q table. |
| `insights.analizar_errores_por_curva`, `lap_comparator.compare_laps` | Take `corner_map=`; corners, `apexes` and `sectores` (numbers and names) come from the map. |
| `optimal_lap` | Corner breakdown and top zones use the map numbers and names; the microsector zones are the Voronoi cells of the map apexes as before. |
| `circuits.enrich_*` | With a map in the result they copy number and name from it; `annotate_corners_from_map` is the new public helper. Without a map nothing changed. |
| PDF | Corner tables from the map; `flat_out` / `kink` corners get a mark ("flat out" / "a fondo", locale `corner_map.*.json`), a hatched bar and no brake/apex/throttle values. |

**Measured in the windows.** The window of a corner is the one the map gives (`start_m`..`end_m`, cut at the midpoint to the neighbours, so windows never overlap and the corner losses never add up to more than the lap delta). Time loss = time spent in the window against the reference lap (positive = slower). Braking point = start of the main braking zone up to 300 m before the apex (and after the previous corner's apex); apex speed = minimum speed in the window; throttle application = first full throttle after the apex (up to 300 m, before the next apex). Positions are lap fractions, so laps of slightly different length compare cleanly; laps whose length is more than 4 % off (out laps, partial laps) are not compared in session mode.

**`flat_out` / `kink` corners** keep the time lost in their window but report braking, apex and throttle as not available: the existing fields are `0.0` with `braking_available` / `apex_available` / `throttle_available` `false` (comparison mode: `braking_delta_available`, `throttle_delta_available`, `apex_delta_available`).

### New fields

* Additive object `corner_map` in the responses of `analyze-session`, `stint/analyze`, `optimal-lap`, `compare-session-laps`, `compare-laps`, `telemetry/analyze`, `telemetry/compare` (absent with `CORNER_DETECTION=legacy`): `mode`, `circuit` (the `circuit` summary or null), `method` (`consensus+template` / `consensus`), `params` (the five tuned parameters and the consensus thresholds), `n_laps`, `lap_length_m`, `n_corners`, `n_named`, `n_discarded`, `warnings` (for example "only 2 lap(s): relaxed consensus", "unknown circuit"), `corners` (the corner fields of section 2, with `sub_apexes`, without series). Positions are in the metres of `lap_length_m`; `apexes` and the comparison corners are scaled to lap A.
* Every corner of `curvas_sesion.corners`, of `corners` in comparisons and of `optimal-lap.corners` gets `number`, `name` (== `corner_name`), `kind`, `direction`, `min_radius_m`, `flat_out_share`, `confidence`, `is_complex` (session and comparison also `start_m`/`end_m` or `start_distance`/`end_distance`). `optimal-lap.top_zones` get `corner_kind`. Comparison corners get `apex_delta_available`. `apexes` rows get `corner_number`, `corner_name`, `kind`, `direction`, `min_radius_m`, `start_m`, `end_m`, `confidence`, `flat_out_share`, `is_complex` next to `Distance`, `Curvature`, `Speed`, `Throttle`, `Brake`, `Elevation`.
* Nothing was renamed or removed: the current UI keeps working, but it will list more corners than before (Imola: 7 to 10 in session mode).

### What changes, legacy against map

Same files, in-process, `scripts/compare_corner_modes.py`:

| File | Endpoint | Corners legacy | Corners map | Names legacy / map |
|---|---|---|---|---|
| Imola, 21 laps (`cayman_gt4_imola_assetto_corsa.csv`) | stint | 7 | 10 | 7 / 9 (+ Rivazza 2, Variante Bassa flat out; corner 7 is an unnamed `lift` bend) |
| Imola | compare-session-laps, optimal-lap | 11 | 10 | 8 / 9 |
| Spa (`porsche_gt4_spa.csv`) | stint | 5 | 13 | 4 / 10 (Eau Rouge/Raidillon, Malmedy, Rivage, Pouhon, Fagnes, Blanchimont flat out added) |
| Spa | compare-session-laps, optimal-lap | 14 | 13 | 9 / 10 |
| Red Bull Ring (`vuelta_rapida.csv` vs `vuelta_lenta.csv`) | compare-laps, telemetry/analyze | 7 | 8 | no table: none / none (corner 6 is `flat_out`) |

Everything that is not a corner (laps, times, degradation, fuel, Monte Carlo, optimal lap times, chart series, data quality) is identical between the modes to 1e-6 on every file tried (fixtures, the Downloads CSV, `.ld` of ACTI and iRacing `.ibt`/`.ld`), with one exception that is a corner effect: in a short stint with only two laps of the usual length (Oran Park South `.ibt`, 4 laps, 2 of them partial) the racing-line module has fewer than 2 observations per corner and reports "unavailable", which also moves the data-quality score. Speed of the Imola analysis: the corner stage costs 0.30 s with the map (0.25 s build + 0.05 s measurements) against 0.28 s legacy, and the flow upload + session + stint + optimal lap takes 2.84 s with the map against 2.96 to 2.99 s legacy (`scripts/profile_pipeline.py`, first calls; the difference is within run-to-run noise, the map is built once and then served from the cache).

**The map as it reaches the API.** `scripts/benchmark_corners.py` has a variant `api_map` (the flying laps of the raw segmented session, as `select_map_laps` picks them, default options, same venue); `docs/benchmarks/corners_api.md` (13 files, 57 laps: the folders available in this run, fewer than the 81 laps of the baseline) gives recall 1.00, 0.0 noise and 3.68 extras per lap, equal to `corner_map` (the table is in the template, so this is the circular figure: the non-circular ones are in section 5). Writing it exposed a real bug in the first lap selection (a 235 m trailing segment of a one-lap file was chosen as the "fastest lap" and the map came out empty), now fixed and covered by a test.

### Limits specific to the integration

* The map of a session needs at least one flying lap; with 1 or 2 laps the consensus is relaxed (warning in `corner_map.warnings`). Two single-lap files give a map from those two laps only.
* In comparisons the map positions are scaled to the length of lap A; a lap of a very different length (a different layout) is a different map.
* The measurement windows are approximate (`start_m`/`end_m`); a braking point further than 300 m before the apex is censored ("not available"), as it was.
* `lap_history` (SQLite, `guardar_en_historial`) is keyed by venue and corner number: rows saved with the old numbering do not match the new numbers.
* Corners listed in `corner_map` but with no window of at least 10 samples in the aligned frame (very short laps) are left out of `corners` in comparison mode.
* The `ml_*` modules (clusters, potential) take the corners as given: `flat_out` corners enter them with zero braking/apex/throttle deltas.
