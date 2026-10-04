# Detección de curvas: el mapa de curvas unificado

Módulo: `src/analytics/corner_map.py` (`build_corner_map`). Medición: `scripts/benchmark_corners.py` y `scripts/crossval_corner_map.py`. Informes: `docs/benchmarks/corners_baseline_legacy.*` (antes), `corners_baseline.*`, `corners_after_core.*` (después, con la comparación antes/después y la validación cruzada) y `corners_crossval.json`.

Esta es la etapa 1 (el núcleo y su medición). Los consumidores del análisis (stint, análisis de curvas por sesión, insights, vuelta óptima, línea de carrera, PDF, `main.py`) siguen usando los detectores antiguos; se migran en la etapa 2.

## 1. El problema

El proyecto tenía dos familias de detectores de curvas que no coinciden, más un segmentador construido sobre una de ellas:

- mínimos de velocidad (`metrics.detect_apex_points`): exige que el coche frene o levante;
- curvatura de las coordenadas de la telemetría (`geometry.detectar_apexes_perfectos`): ve curvas pero también ruido;
- el segmentador (`metrics.segment_corners`: frenada + ápice + gas a fondo), que usan stint y el análisis por sesión: necesita los tres eventos.

En una vuelta de Imola daban 5 contra 11 ápices (modo sesión 7 curvas, modo comparación 11). Una curva que un coche toma a fondo no tiene mínimo de velocidad: Variante Bassa en Imola (radio mínimo geométrico 478 m, velocidad siempre creciente con un GT4) y, con coches de mucho apoyo, también Eau Rouge/Raidillon (164 m) y Blanchimont (203 m) en Spa y las curvas rápidas de Silverstone. Línea base medida sobre 81 vueltas reales (recall de curvas con nombre, `docs/benchmarks/corners_baseline_legacy.md`): velocidad 0,73, geometría 0,90, segmentador 0,78, unión 0,95 (Silverstone 0,73, el más flojo), con entre 1,1 y 4,5 detecciones extra por vuelta.

## 2. El algoritmo

`build_corner_map(laps, venue=None, lap_length_m=None, options=None)` devuelve `{"corners": [...], "discarded": [...], "summary": {...}}`. `laps` es un DataFrame o una lista de vueltas limpias (crudas o alineadas) con `Distance` y `Speed` y, si existen, `Brake`, `Throttle`, `CarCoordX/Y` (o los canales de guiñada/GPS que sabe usar `geometry.py`). Solo lee los JSON versionados (nunca el juego instalado) y es determinista.

1. **Candidatos por vuelta.** Mínimos de velocidad, picos de curvatura y zonas de frenada, calculados sobre una rejilla de 1 m para que el resultado no dependa de la frecuencia de muestreo. Las detecciones de distintos detectores a menos de `merge_detectors_m` forman un solo evento. Una zona de frenada sin ningún evento detrás se convierte en candidato (en el punto donde se suelta el freno).
2. **Consenso entre vueltas.** Los eventos se agrupan por fracción de vuelta (semianchura `max(cluster_tol_min_m, cluster_tol_frac * longitud)`), y cada vuelta cuenta una vez por grupo. Un grupo se conserva si aparece en al menos `min_share` de las vueltas. Con menos de 3 vueltas el consenso se relaja (`relaxed_share`; con 1 o 2 vueltas basta una), la `confidence` baja y se añade un aviso. La posición es la mediana entre vueltas.
3. **Plantilla de pista** (solo si `circuits.recognize` reconoce el circuito: venue conocido y longitud medida dentro del 4 %). Candidatos: los sub-ápices de `src/data/track_geometry/<id>.json` con radio menor que `template_max_radius_m` y todas las curvas tabuladas de `circuits.json` (aunque superen ese radio). Cada átomo cercano a una curva tabulada pertenece a ella (uno a uno). Un grupo de telemetría a menos de `match_pad_m` de una curva de la plantilla la respalda y refina su posición, encogida hacia la plantilla: `pos = plantilla + n/(n + prior_laps) * (telemetría - plantilla)`, con `n` el número de vueltas con evidencia. Una curva de la plantilla **sin** evidencia de telemetría se conserva, con tipo `flat_out` (o `kink` si no tiene nombre y es casi recta), en su posición geométrica (o tabulada), en lugar de descartarse.
4. **Telemetría sin respaldo.** En un circuito conocido, un grupo solo de telemetría necesita `unbacked_min_support` o pasa a `discarded` (motivo `no track/table backing`). Sin plantilla (circuito desconocido) se confía en el consenso de telemetría tal cual.
5. **Curvas compuestas.** Los átomos o grupos a menos de `group_gap_m` (y con una extensión máxima de `group_max_span_m`, para no encadenar todo un sector) forman UNA curva con `sub_apexes` e `is_complex: true`. Dos curvas tabuladas por separado nunca se funden (Rivazza 1 y 2).
6. **Nombres.** `circuits.assign_names` (uno a uno, en orden de vuelta, sin duplicar). Una curva tabulada que nadie encontró es una curva virtual `flat_out` ya creada en el paso 3. Las curvas sin nombre y sin respaldo más cerradas que `kink_max_radius_m` se conservan como `kink`; las más abiertas van a `discarded`.
7. **Evidencia y tipo** (independiente del detector que disparó): para cada curva y cada vuelta se mide el mínimo de velocidad (recuperación de al menos `speed_drop_min_kmh` a ambos lados), el pico de freno (`brake_present_pct`), el mínimo de gas (`throttle_lift_pct`) y la curvatura. `kind` es `braking` si se frenó en al menos `braking_share` de las vueltas; si no, `lift` (mínimo de velocidad o levantar gas en al menos la mitad); si no, `flat_out` / `kink`. `flat_out_share` es la fracción de vueltas sin mínimo, sin frenada y sin levantar.

### Salida por curva

`number` (1..N en orden de vuelta), `name`, `table_order`, `fraction`, `apex_distance_m`, `start_m`, `end_m` (ventana aproximada: la distancia de frenada o 30 m antes del primer sub-ápice hasta 40 m después del último, cortada en el punto medio con las vecinas), `kind`, `direction` (`left`/`right`, de la geometría o de las coordenadas de la telemetría), `min_radius_m` (geometría de pista si existe; si no, una estimación gruesa de la telemetría suavizada a 75 m), `sources` (`speed`, `geometry`, `brake`, `track_geometry`, `table`), `confidence` (0..1, "o ruidosa" del apoyo de telemetría, 0,6 por geometría y 0,5 por tabla), `evidence` (`laps_found`, `laps_total`, `detection_share`, `speed_min_kmh`, `speed_min_share`, `speed_drop_kmh`, `brake_peak_pct`, `brake_share`, `throttle_min_pct`), `is_complex`, `sub_apexes` (`fraction`, `distance_m`, `radius_m`, `direction`) y `flat_out_share`. El `summary` tiene `n_corners`, `n_named`, `n_discarded`, `n_laps`, `lap_length_m`, `circuit`, `method`, `params`, `warnings`.

### Cambios en `circuits.json`

Imola tiene ahora la curva 9, Variante Bassa (`apex_fraction` 0,94, `"kind": "flat_out"`). El pico de curvatura de la telemetría en las vueltas de Imola (varios coches) está en torno a 0,94 a 0,95 y la línea de IA de AC pone el radio mínimo (478 m) en 0,923; 0,94 queda a menos de 85 m de ambos. El campo opcional `"kind"` por curva (`braking`, `lift`, `flat_out`, `kink`) lo valida `validate_database` y lo ignora `assign_names`; una curva a fondo no exige ápice detectable, así que el aviso de "lejos de toda curva geométrica" la omite y `ac_track_geometry.compare_with_table` no la cuenta como curva de la tabla sin pico.

## 3. Parámetros

| Parámetro | Valor | Significado y motivo |
|---|---|---|
| `merge_detectors_m` | 60 | Mismo valor que la unión del banco y que la deduplicación de `circuit_apexes.py`. |
| `brake_zone_search_m` | 150 | Una zona de frenada es candidato propio solo si no hay nada a menos de esta distancia después. |
| `cluster_tol_frac`, `cluster_tol_min_m` | 0,012, 60 | Semianchura del grupo: 1,2 % de la vuelta, mínimo 60 m. La rejilla prefiere 90 m, pero eso solo cambia Monaco (objetivo 0,842 frente a 0,831) y 90 m funde dos ápices a 80 m, así que se mantuvo la resolución de chicanes. |
| `min_share` | 0,6 | Fracción de vueltas en que debe aparecer (como `circuit_apexes.py --min-share`). |
| `relaxed_share`, `relaxed_below_laps` | 0,5, 3 | Consenso con menos de 3 vueltas. |
| `template_max_radius_m` | 400 | El mismo corte que la exportación de geometría. |
| `table_atom_tol_m` | 150 | Un átomo a esta distancia (y dentro de la tolerancia del circuito) de una curva tabulada pertenece a ella. |
| `match_pad_m` | 90 | La telemetría a esta distancia de una curva de la plantilla la respalda. |
| `unbacked_min_support` | 0,4 | Una curva solo de telemetría en un circuito conocido necesita este apoyo (`fracción * fiabilidad * detectores`). |
| `prior_laps` | 4 | La plantilla cuenta como 4 vueltas de evidencia (encogimiento); 0 = posición de telemetría pura. |
| `kink_max_radius_m`, `kink_radius_m` | 200, 200 | Frontera entre curva y kink (la clase "rápida" empieza hacia 150 m). |
| `group_gap_m`, `group_max_span_m` | 120, 200 | Curvas compuestas: la regla de la chicane, con tope de extensión (sin él, en Monaco se encadenaban 5 átomos a lo largo de 290 m y se fundían Grand Hotel y Portier). |
| `speed_drop_min_kmh` | 3 | Menor recuperación que cuenta como mínimo de velocidad. |
| `brake_present_pct` | 8 | Presión de freno que cuenta como frenada (por encima del 3 % de `detect_braking_points`, que recoge toques). |
| `throttle_lift_pct` | 85 | Gas por debajo de esto cerca del ápice = levantar. |
| `braking_share` | 0,5 | Fracción de vueltas con freno para `kind: braking`. |
| `min_confidence` | 0,3 | Las curvas por debajo van a `discarded`. |

Solo se buscaron `min_share`, `cluster_tol_min_m`, `match_pad_m`, `unbacked_min_support` y `group_gap_m` (243 configuraciones); el resto son valores razonados.

## 4. Validación

`scripts/crossval_corner_map.py` hace leave-one-circuit-out sobre Imola, Spa, Silverstone, Le Mans y Monaco (81 vueltas reales, 15 archivos, 4 coches más los fixtures del proyecto): para cada circuito se eligen los cinco parámetros anteriores mirando solo los otros cuatro, y se evalúa en el excluido. Para evitar circularidad las variantes ajustadas NO inyectan la tabla (`use_table=False`): `map_no_table` (consenso), `single_lap_no_table` y `map_telemetry` (solo telemetría, sin plantilla). Objetivo: `recall - 0,10 * ruido - 0,02 * extras` (ruido = detecciones que no son curva tabulada ni están a menos de 80 m de una curva geométrica).

Resultado: 4 de los 5 pliegues eligen la configuración que es mejor con todos los circuitos (`min_share` 0,6, `cluster_tol_min_m` 90, `match_pad_m` 90, `unbacked_min_support` 0,4, `group_gap_m` 120); el pliegue de Monaco elige `cluster_tol_min_m` 60. Los valores por defecto de `corner_map` son esa configuración salvo `cluster_tol_min_m` 60 (véase la tabla), así que las cifras de validación cruzada y en muestra coinciden (recall 0,92 sin la tabla, ruido 0,02 por vuelta). El objetivo en la rejilla va de 0,760 a 0,842 (mediana 0,783); los valores por defecto dan 0,831. El óptimo es estable, pero cinco circuitos de un solo simulador son una muestra pequeña, y la plantilla domina el resultado (los parámetros importan poco una vez hay geometría; importan para `map_telemetry`).

Comprobación extra fuera de muestra: un archivo de Imola con un coche no usado en el diseño (`f1_2020_mercedes`, 9 vueltas, añadido después de la línea base y por tanto fuera de las tablas) da con `map_no_table` recall 1,00 en las curvas detectables (0,89 con Bassa), 0 ruido y 1,0 extra por vuelta; el detector unión da 1,00 con 3,0 extras y 0,89 de ruido por vuelta.

## 5. Resultados, antes y después

81 vueltas reales, recall de curvas con nombre sin Variante Bassa (para que sea comparable con la línea base, que tenía 8 curvas en Imola), extras por vuelta = detecciones sin curva tabulada:

| | Recall | Extras/vuelta | Ruido/vuelta | Std de posición (m) |
|---|---|---|---|---|
| speed (antes) | 0,73 | 1,86 | 0,43 | 33,3 |
| geometry (antes) | 0,90 | 3,57 | 0,41 | 29,5 |
| segmenter (antes) | 0,78 | 1,14 | 0,26 | 32,7 |
| union (antes) | 0,95 | 4,43 | 0,80 | 28,0 |
| `corner_map` (con tabla, circular) | 1,00 | 2,96 | 0,00 | - |
| `map_no_table` (no circular) | 1,00 (0,92 con Bassa) | 2,85 | 0,00 | - |
| `single_lap_no_table` | 1,00 (0,92 con Bassa) | 2,52 | 0,00 | 23,9 |
| `map_telemetry` (sin plantilla) | 0,91 (0,84) | 1,64 | 0,06 | - |

Por circuito, `map_no_table` (recall detectable / extras): Imola 1,00 (0,89 con Bassa) / 1,0, Le Mans 1,00 / 16,6, Monaco 1,00 / 4,0, Silverstone 1,00 / 5,0 (antes 0,73), Spa 1,00 / 2,0. Sin ninguna plantilla (`map_telemetry`) Silverstone queda en 0,68 (Monaco 0,83, Spa 0,93, Imola 0,92, Le Mans 1,00): la mejora ahí viene de la geometría de pista, no del consenso.

El consenso solo (`map_telemetry`) da 0,91 de recall con 1,6 extras y 0,06 de ruido; la plantilla añade las curvas en las que el coche no frena ni levanta. La desviación de la posición entre vueltas no está definida para los mapas por consenso (un solo mapa para todas las vueltas); el mapa vuelta a vuelta tiene entre 24 y 25 m (25,0 con la tabla, 23,9 sin ella) frente a 28 a 33 m de los detectores antiguos (parte de eso es el encogimiento hacia la plantilla, véanse los límites).

Objetivos y lectura honesta:

- Recall con nombre >= 0,95 en total y >= 0,90 por circuito: cumplido sin la tabla (1,00 en todos los circuitos; Imola 0,89 solo porque Variante Bassa no se puede encontrar sin la tabla, véase abajo) y 1,00 con ella.
- Extras por vuelta <= 2: NO se cumple (entre 2,5 y 3,0 en total). La mayoría de los "extras" son curvas reales que las tablas no listan (Le Mans tiene 4 curvas tabuladas y unas 21 curvas; Silverstone 10 de 15). La medida que separa ruido de curvas reales es el ruido por vuelta, que bajó de 0,8 (unión) a 0,0.
- Variante Bassa sale como curva `flat_out` con nombre incluso con un GT4 (en el archivo de Imola de 21 vueltas, el 95 % de las vueltas no tiene frenada ni mínimo de velocidad ahí), pero solo a través de la tabla: su radio (478 m) supera el corte de 400 m de la exportación de geometría, así que con `use_table=False` no se puede nombrar.
- Desviación de posición menor que la del mejor detector antiguo: cumplido en el mapa vuelta a vuelta (23,9 a 25,0 frente a 28,0), a costa de encoger las posiciones hacia la plantilla.

## 6. Límites

- La plantilla existe solo para los 16 circuitos de Assetto Corsa y se derivó de la línea de IA; los datos de validación son todos de Assetto Corsa. Para otros simuladores las posiciones son fracciones de vuelta y deberían servir, pero no se ha medido. Un circuito sin geometría ni tabla usa el consenso de telemetría (recall 0,91 en los circuitos conocidos con la plantilla apagada, claramente peor en Silverstone y Monaco).
- Los extras se siguen contando contra tablas parciales; un coche que nunca frena en una curva da un `flat_out_share` cercano a 1 y un tipo `lift` o `flat_out` por coche, no por circuito.
- `min_radius_m` de una curva sin átomo geométrico (Bassa, circuitos desconocidos) es una estimación gruesa de la telemetría, y la `direction` sale de las coordenadas de la telemetría.
- `start_m` / `end_m` son ventanas aproximadas, no extensiones de curvatura.
- El encogimiento de la posición cambia fidelidad al ápice real de una vuelta por estabilidad entre vueltas: si necesitas el ápice propio de la vuelta, usa `options={"prior_laps": 0}` o las ventanas de evidencia.
- Con 1 o 2 vueltas no hay consenso real (modo relajado, menor confianza); un ápice espurio de una sola vuelta se conserva si el circuito no tiene plantilla.
- Curvas separadas en la tabla y muy próximas (Rivazza 1 y 2, 128 m) dependen de la tabla para seguir separadas; sin ella, una cadena de átomos solo se parte con `group_gap_m` y `group_max_span_m`.

## 7. Cómo añadir un circuito

1. Entrada de reconocimiento en `src/data/circuits.json` (id, alias, longitud, `corners: []`).
2. Geometría (independiente del coche): `python scripts/ac_track_reference.py <pista> --compare` y luego `--export-all` escribe `src/data/track_geometry/<id>.json` a partir de la línea de IA del juego (solo lectura sobre la carpeta del juego). Con eso el mapa ya encuentra toda curva más cerrada que 400 m, con nombre o sin él.
3. Nombres: localiza dónde están las curvas en vueltas reales con `python scripts/circuit_apexes.py LOG.csv --json`, ponles nombre con el trazado oficial delante y añádelas (`apex_fraction` estrictamente creciente, `order`). Una curva que el coche toma a fondo no saldrá en esa lista: toma su posición de la geometría (`scripts/ac_track_reference.py`) y añádela con `"kind": "flat_out"`.
4. Comprueba con `python scripts/benchmark_corners.py CARPETA --circuit <id>` y `python -m pytest tests/test_circuits.py tests/test_corner_map.py -q`.

## 8. Reproducir

```bash
python scripts/benchmark_corners.py CARPETAS... --md out.md --out out.json \
    --compare docs/benchmarks/corners_baseline_legacy.json --crossval docs/benchmarks/corners_crossval.json
python scripts/crossval_corner_map.py CARPETAS... --out docs/benchmarks/corners_crossval.json   # unos 90 s
```

Los informes de `docs/benchmarks/` se generaron con las carpetas de telemetría del autor más `tests/fixtures`; el archivo `f1_2020_mercedes` se excluyó (`--exclude f1_2020`) para conservar las 81 vueltas de la línea base.
