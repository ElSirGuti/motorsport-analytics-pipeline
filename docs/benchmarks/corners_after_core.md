# Banco de pruebas de curvas: despues del nucleo (mapa unificado)

Fecha: 2026-10-04. Generado con `python scripts/benchmark_corners.py` (no modifica ningun detector; solo los ejecuta y compara con la tabla de `circuits.json`).

Detectores existentes: `speed` (metrics.detect_apex_points), `geometry` (geometry.detectar_apexes_perfectos), `segmenter` (metrics.segment_corners, el que usan stint/sesion/comparacion) y `union` (los tres, deduplicados a 60 m).

Mapa de curvas unificado (`src/analytics/corner_map.py`): `corner_map` (consenso sobre todas las vueltas limpias del archivo + plantilla de pista + tabla), `map_no_table` (igual pero sin inyectar la tabla: su recall NO es circular), `map_telemetry` (solo consenso de telemetria, sin plantilla) y `single_lap` (el mapa completo construido vuelta a vuelta).

Metricas: **recall** = curvas tabuladas con una deteccion emparejada dentro de tolerancia / curvas tabuladas (media por vuelta); **recall det.** = lo mismo sin las curvas tabuladas con `kind: flat_out` (comparable con la linea base antigua, que no tenia Variante Bassa); **extras** = detecciones por vuelta sin curva tabulada (mezcla ruido y curvas reales no tabuladas); **ruido** = extras que ademas no estan a menos de 80 m de ninguna curva geometrica de la pista (ruido casi seguro); **std m** = desviacion tipica de la posicion de cada curva entre vueltas (media de curvas con >= 2 apariciones; no definida para los mapas por consenso, que dan el mismo mapa a todas las vueltas); **aparece %** = porcentaje medio de vueltas en que cada curva tabulada es detectada.

Atencion: `corner_map` inyecta las curvas de la tabla (curvas virtuales), asi que su recall con nombre contra esa misma tabla es alto por construccion. La medida no circular es `map_no_table` (y la validacion cruzada por circuito, que ajusta los umbrales sin mirar el circuito evaluado).

## Total

15 archivos utilizados, 81 vueltas completas.

| Detector | Recall | Recall det. | Detecciones/vuelta | Extras/vuelta | Ruido/vuelta | Std (m) | Aparece % |
|---|---|---|---|---|---|---|---|
| speed | 0.68 | 0.73 | 7.67 | 1.86 | 0.43 | 33.25 | 67.75 |
| geometry | 0.83 | 0.9 | 10.74 | 3.57 | 0.41 | 29.46 | 83.16 |
| segmenter | 0.72 | 0.78 | 7.33 | 1.14 | 0.26 | 32.7 | 72.01 |
| union | 0.88 | 0.95 | 11.96 | 4.43 | 0.8 | 28.04 | 87.45 |
| corner_map | 1.0 | 1.0 | 11.6 | 2.96 | 0.0 | - | 100.0 |
| map_no_table | 0.92 | 1.0 | 10.8 | 2.85 | 0.0 | - | 92.33 |
| map_telemetry | 0.84 | 0.91 | 8.83 | 1.64 | 0.06 | - | 83.91 |
| single_lap | 1.0 | 1.0 | 11.27 | 2.63 | 0.0 | 24.99 | 100.0 |
| single_lap_no_table | 0.92 | 1.0 | 10.47 | 2.52 | 0.0 | 23.88 | 92.33 |

## Por circuito

Cada celda: recall / recall det. / extras por vuelta / ruido por vuelta.

| Circuito | Vueltas | Tab. | Tol. (m) | speed | geometry | segmenter | union | corner_map | map_no_table | map_telemetry | single_lap | single_lap_no_table |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Autodromo Enzo e Dino Ferrari (Imola) | 56 | 9 | 122 | 0.68 / 0.76 / 0.6 / 0.3 | 0.83 / 0.93 / 2.2 / 0.2 | 0.76 / 0.86 / 0.3 / 0.1 | 0.87 / 0.98 / 2.8 / 0.6 | 1.00 / 1.00 / 1.0 / 0.0 | 0.89 / 1.00 / 1.0 / 0.0 | 0.82 / 0.92 / 0.0 / 0.0 | 1.00 / 1.00 / 0.7 / 0.0 | 0.89 / 1.00 / 0.7 / 0.0 |
| Circuit de la Sarthe (Le Mans) | 7 | 4 | 90 | 0.68 / 0.68 / 10.3 / 2.6 | 0.82 / 0.82 / 15.0 / 2.7 | 0.64 / 0.64 / 7.3 / 1.9 | 0.89 / 0.89 / 17.4 / 3.9 | 1.00 / 1.00 / 16.6 / 0.0 | 1.00 / 1.00 / 16.6 / 0.0 | 1.00 / 1.00 / 10.7 / 0.4 | 1.00 / 1.00 / 15.3 / 0.0 | 1.00 / 1.00 / 15.3 / 0.0 |
| Circuit de Monaco | 3 | 6 | 120 | 1.00 / 1.00 / 6.7 / 0.0 | 1.00 / 1.00 / 4.7 / 0.0 | 0.94 / 0.94 / 4.7 / 0.0 | 1.00 / 1.00 / 6.7 / 0.0 | 1.00 / 1.00 / 4.0 / 0.0 | 1.00 / 1.00 / 4.0 / 0.0 | 0.83 / 0.83 / 4.3 / 0.0 | 1.00 / 1.00 / 4.0 / 0.0 | 1.00 / 1.00 / 4.0 / 0.0 |
| Silverstone Circuit | 6 | 10 | 145 | 0.62 / 0.62 / 1.2 / 0.2 | 0.67 / 0.67 / 2.5 / 0.2 | 0.52 / 0.52 / 1.3 / 0.2 | 0.73 / 0.73 / 3.7 / 0.3 | 1.00 / 1.00 / 5.0 / 0.0 | 1.00 / 1.00 / 5.0 / 0.0 | 0.68 / 0.68 / 2.8 / 0.2 | 1.00 / 1.00 / 4.5 / 0.0 | 1.00 / 1.00 / 4.5 / 0.0 |
| Circuit de Spa-Francorchamps | 9 | 10 | 174 | 0.59 / 0.59 / 2.3 / 0.0 | 0.92 / 0.92 / 3.7 / 0.2 | 0.57 / 0.57 / 0.3 / 0.0 | 0.92 / 0.92 / 4.3 / 0.4 | 1.00 / 1.00 / 3.0 / 0.0 | 1.00 / 1.00 / 2.0 / 0.0 | 0.93 / 0.93 / 3.0 / 0.0 | 1.00 / 1.00 / 3.0 / 0.0 | 1.00 / 1.00 / 2.0 / 0.0 |

## Por circuito y coche

Cada fila: recall / extras por vuelta / std en m. Std '-' = menos de 2 apariciones de cualquier curva.

| Circuito | Coche | Vueltas | segmenter | union | corner_map | map_no_table | single_lap | single_lap_no_table |
|---|---|---|---|---|---|---|---|---|
| Autodromo Enzo e Dino Ferrari (Imola) | ferrari_458 | 4 | 0.81 / 0.2 / 12.8 | 0.89 / 2.2 / 18.7 | 1.00 / 1.0 / - | 0.89 / 1.0 / - | 1.00 / 1.0 / 8.2 | 0.89 / 1.0 / 7.7 |
| Autodromo Enzo e Dino Ferrari (Imola) | ks_porsche_919_hybrid_2016 | 5 | 0.67 / 1.4 / 79.1 | 0.69 / 3.0 / 59.5 | 1.00 / 0.8 / - | 0.89 / 0.8 / - | 1.00 / 0.6 / 63.4 | 0.89 / 0.6 / 58.5 |
| Autodromo Enzo e Dino Ferrari (Imola) | ks_porsche_cayman_gt4_clubsport | 47 | 0.77 / 0.2 / 22.8 | 0.89 / 2.8 / 18.8 | 1.00 / 1.0 / - | 0.89 / 1.0 / - | 1.00 / 0.7 / 10.1 | 0.89 / 0.7 / 9.7 |
| Circuit de la Sarthe (Le Mans) | ks_porsche_919_hybrid_2016 | 7 | 0.64 / 7.3 / 59.2 | 0.89 / 17.4 / 68.7 | 1.00 / 16.6 / - | 1.00 / 16.6 / - | 1.00 / 15.3 / 72.0 | 1.00 / 15.3 / 72.0 |
| Circuit de Monaco | cky_porschecarrera_gt_04 (pocas vueltas) | 2 | 0.92 / 4.0 / 6.1 | 1.00 / 6.0 / 5.6 | 1.00 / 4.0 / - | 1.00 / 4.0 / - | 1.00 / 4.0 / 3.8 | 1.00 / 4.0 / 3.8 |
| Circuit de Monaco | f_porsche_gt2rs_mr (pocas vueltas) | 1 | 1.00 / 6.0 / - | 1.00 / 8.0 / - | 1.00 / 4.0 / - | 1.00 / 4.0 / - | 1.00 / 4.0 / - | 1.00 / 4.0 / - |
| Silverstone Circuit | ks_porsche_919_hybrid_2016 | 6 | 0.52 / 1.3 / 28.5 | 0.73 / 3.7 / 30.3 | 1.00 / 5.0 / - | 1.00 / 5.0 / - | 1.00 / 4.5 / 40.6 | 1.00 / 4.5 / 40.6 |
| Circuit de Spa-Francorchamps | ks_porsche_cayman_gt4_clubsport | 9 | 0.57 / 0.3 / 17.1 | 0.92 / 4.3 / 15.6 | 1.00 / 3.0 / - | 1.00 / 2.0 / - | 1.00 / 3.0 / 5.0 | 1.00 / 2.0 / 5.0 |

## Consistencia entre detectores

Detecciones medias por vuelta (cuantas curvas ve cada detector en la misma vuelta) frente a las curvas tabuladas.

| Circuito | Tabuladas | speed | geometry | segmenter | union | corner_map | map_no_table | map_telemetry | single_lap | single_lap_no_table |
|---|---|---|---|---|---|---|---|---|---|---|
| Autodromo Enzo e Dino Ferrari (Imola) | 9 | 6.68 | 9.62 | 7.16 | 10.64 | 9.98 | 8.98 | 7.41 | 9.71 | 8.71 |
| Circuit de la Sarthe (Le Mans) | 4 | 13.0 | 18.29 | 9.86 | 21.0 | 20.57 | 20.57 | 14.71 | 19.29 | 19.29 |
| Circuit de Monaco | 6 | 12.67 | 10.67 | 10.33 | 12.67 | 10.0 | 10.0 | 9.33 | 10.0 | 10.0 |
| Silverstone Circuit | 10 | 7.33 | 9.17 | 6.5 | 11.0 | 15.0 | 15.0 | 9.67 | 14.5 | 14.5 |
| Circuit de Spa-Francorchamps | 10 | 8.22 | 12.89 | 6.0 | 13.56 | 13.0 | 12.0 | 12.33 | 13.0 | 12.0 |

## Antes / despues

'Antes' = `docs/benchmarks/corners_baseline_legacy.json` (tabla de Imola con 8 curvas, sin Variante Bassa). 'Despues' usa el recall det. (mismas 8 curvas) para ser comparable; entre parentesis el recall con las 9 curvas. Cada celda: recall / extras por vuelta.

| Circuito | segmenter antes | union antes | corner_map | map_no_table | single_lap | single_lap_no_table | map_telemetry |
|---|---|---|---|---|---|---|---|
| Autodromo Enzo e Dino Ferrari (Imola) | 0.86 / 0.3 | 0.98 / 2.8 | 1.00 / 1.0 | 1.00 (0.89) / 1.0 | 1.00 / 0.7 | 1.00 (0.89) / 0.7 | 0.92 (0.82) / 0.0 |
| Circuit de la Sarthe (Le Mans) | 0.64 / 7.3 | 0.89 / 17.4 | 1.00 / 16.6 | 1.00 / 16.6 | 1.00 / 15.3 | 1.00 / 15.3 | 1.00 / 10.7 |
| Circuit de Monaco | 0.94 / 4.7 | 1.00 / 6.7 | 1.00 / 4.0 | 1.00 / 4.0 | 1.00 / 4.0 | 1.00 / 4.0 | 0.83 / 4.3 |
| Silverstone Circuit | 0.52 / 1.3 | 0.73 / 3.7 | 1.00 / 5.0 | 1.00 / 5.0 | 1.00 / 4.5 | 1.00 / 4.5 | 0.68 / 2.8 |
| Circuit de Spa-Francorchamps | 0.57 / 0.3 | 0.92 / 4.3 | 1.00 / 3.0 | 1.00 / 2.0 | 1.00 / 3.0 | 1.00 / 2.0 | 0.93 / 3.0 |
| **Total** | 0.78 / 1.15 | 0.95 / 4.46 | 1.00 / 2.96 | 1.00 / 2.85 | 1.00 / 2.63 | 1.00 / 2.52 | 0.91 / 1.64 |

Estabilidad (std de la posicion entre vueltas, m): antes segmenter 32.7, union 30.05; despues single_lap 24.99, single_lap_no_table 23.88.

## Validacion cruzada por circuito

Leave-one-circuit-out: los parametros de cada fila se eligieron mirando solo los otros 4 circuitos (rejilla de 243 configuraciones: min_share en [0.5, 0.6, 0.75], cluster_tol_min_m en [40.0, 60.0, 90.0], match_pad_m en [40.0, 60.0, 90.0], unbacked_min_support en [0.4, 0.6, 0.8], group_gap_m en [80.0, 120.0, 160.0]). 'En muestra' = los parametros por defecto de corner_map (el optimo con todos los circuitos) evaluados en ese circuito.

Cada celda: validacion cruzada (en muestra entre parentesis). Recall con nombre contra la tabla, sin inyectarla; ruido = detecciones sin curva tabulada ni geometrica.

| Circuito | Vueltas | Recall consenso (telemetria + geometria) | Recall vuelta a vuelta | Recall solo telemetria | Extras/vuelta | Ruido/vuelta | Parametros elegidos sin mirar el circuito |
|---|---|---|---|---|---|---|---|
| imola | 56 | 0.89 (0.89) | 0.89 (0.89) | 0.82 (0.82) | 0.6 (0.6) | 0.01 (0.01) | min_share=0.6, cluster_tol_min_m=90.0, match_pad_m=90.0, unbacked_min_support=0.4, group_gap_m=120.0 |
| le_mans | 7 | 1.00 (1.00) | 1.00 (1.00) | 1.00 (1.00) | 14.2 (14.2) | 0.14 (0.14) | min_share=0.6, cluster_tol_min_m=90.0, match_pad_m=90.0, unbacked_min_support=0.4, group_gap_m=120.0 |
| monaco | 3 | 1.00 (1.00) | 1.00 (1.00) | 0.83 (0.83) | 4.1 (4.1) | 0.00 (0.00) | min_share=0.6, cluster_tol_min_m=60.0, match_pad_m=90.0, unbacked_min_support=0.4, group_gap_m=120.0 |
| silverstone | 6 | 1.00 (1.00) | 1.00 (1.00) | 0.68 (0.68) | 4.1 (4.1) | 0.06 (0.06) | min_share=0.6, cluster_tol_min_m=90.0, match_pad_m=90.0, unbacked_min_support=0.4, group_gap_m=120.0 |
| spa_francorchamps | 9 | 1.00 (1.00) | 1.00 (1.00) | 0.93 (0.93) | 2.3 (2.3) | 0.00 (0.00) | min_share=0.6, cluster_tol_min_m=90.0, match_pad_m=90.0, unbacked_min_support=0.4, group_gap_m=120.0 |
| **Total** | 81 | 0.92 (0.92) | 0.92 (0.92) | 0.84 (0.84) | 2.3 (2.3) | 0.02 (0.02) | |

Objetivo medio en la rejilla: minimo 0.7596, mediana 0.7832, maximo 0.8418; por defecto 0.8311. 4 de 5 pliegues eligen la misma configuracion que el optimo con todos los circuitos. Los valores por defecto de `corner_map` coinciden con ese optimo salvo cluster_tol_min_m 60 (optimo de la rejilla: 90) (se mantiene el valor razonado: la diferencia de objetivo es pequena). El optimo es estable, pero la muestra son 5 circuitos de un solo simulador.

Variante evaluada: `map_no_table, single_lap_no_table y map_telemetry (media)`. Objetivo: recall - 0.1 * ruido - 0.02 * extras, media de las tres variantes.

## Mapas de curvas

Mapa `corner_map` del archivo con mas vueltas de cada circuito. `kind`: braking / lift / flat_out / kink; `a fondo %` = porcentaje de vueltas sin minimo de velocidad ni frenada.

### Autodromo Enzo e Dino Ferrari (Imola) (fn_imola_&_ks_porsche_cayman_gt4_clubsport_&_piloto_&_stint_1.ld)

| # | Nombre | Fraccion | Tipo | Dir. | Radio min (m) | Conf. | A fondo % | Compleja |
|---|---|---|---|---|---|---|---|---|
| 1 | Tamburello | 0.147 | braking | left | 69.3 | 0.96 | 0 | si |
| 2 | Villeneuve | 0.293 | braking | right | 74.9 | 0.96 | 0 | si |
| 3 | Tosa | 0.352 | braking | left | 40.5 | 0.97 | 0 | no |
| 4 | Piratella | 0.480 | braking | left | 85.7 | 0.96 | 0 | no |
| 5 | Acque Minerali | 0.584 | braking | right | 50.5 | 0.97 | 0 | si |
| 6 | Variante Alta | 0.694 | braking | left | 49.1 | 0.95 | 0 | si |
| 7 | - | 0.809 | lift | right | 354.2 | 0.60 | 33 | no |
| 8 | Rivazza 1 | 0.847 | braking | left | 50.5 | 0.97 | 0 | no |
| 9 | Rivazza 2 | 0.871 | braking | left | 64.9 | 0.96 | 0 | no |
| 10 | Variante Bassa | 0.940 | flat_out | right | 354.2 | 0.50 | 95 | no |

### Circuit de la Sarthe (Le Mans) (sx_lemans_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld)

| # | Nombre | Fraccion | Tipo | Dir. | Radio min (m) | Conf. | A fondo % | Compleja |
|---|---|---|---|---|---|---|---|---|
| 1 | - | 0.049 | lift | right | 202.2 | 0.85 | 0 | no |
| 2 | Dunlop Chicane | 0.064 | braking | left | 55.7 | 0.97 | 0 | si |
| 3 | - | 0.081 | lift | left | 214.9 | 0.60 | 50 | no |
| 4 | - | 0.096 | lift | right | 176.1 | 0.85 | 25 | no |
| 5 | - | 0.107 | braking | left | 79.1 | 0.85 | 0 | no |
| 6 | - | 0.117 | lift | right | 122.8 | 0.60 | 25 | no |
| 7 | - | 0.141 | braking | right | 133.5 | 0.85 | 25 | no |
| 8 | - | 0.303 | braking | left | 64.4 | 0.85 | 0 | si |
| 9 | - | 0.447 | braking | right | 52.4 | 0.94 | 0 | si |
| 10 | Mulsanne | 0.569 | braking | right | 45.2 | 0.97 | 0 | no |
| 11 | - | 0.710 | braking | right | 193.2 | 0.88 | 0 | no |
| 12 | - | 0.724 | braking | left | 47.4 | 0.85 | 0 | no |
| 13 | Arnage | 0.747 | braking | right | 36.8 | 0.97 | 0 | no |
| 14 | - | 0.848 | braking | right | 144.1 | 0.94 | 0 | no |
| 15 | - | 0.865 | lift | left | 197.0 | 0.94 | 0 | no |
| 16 | - | 0.881 | lift | left | 160.9 | 0.94 | 0 | no |
| 17 | - | 0.895 | lift | right | 136.3 | 0.60 | 0 | no |
| 18 | - | 0.912 | braking | left | 146.9 | 0.94 | 0 | no |
| 19 | - | 0.931 | lift | right | 388.6 | 0.60 | 50 | no |
| 20 | - | 0.942 | lift | left | 338.8 | 0.60 | 50 | no |
| 21 | Ford Chicanes | 0.981 | braking | left | 56.9 | 0.97 | 0 | si |

### Circuit de Monaco (monaco_2020_&_cky_porschecarrera_gt_04_&_piloto_&_stint_1.ld)

| # | Nombre | Fraccion | Tipo | Dir. | Radio min (m) | Conf. | A fondo % | Compleja |
|---|---|---|---|---|---|---|---|---|
| 1 | Sainte Devote | 0.066 | braking | right | 42.2 | 0.94 | 0 | si |
| 2 | - | 0.182 | braking | right | 275.2 | 0.60 | 0 | no |
| 3 | - | 0.271 | braking | right | 47.2 | 0.87 | 0 | si |
| 4 | Grand Hotel Hairpin | 0.382 | braking | left | 14.2 | 0.94 | 0 | si |
| 5 | Portier | 0.431 | braking | right | 29.0 | 0.94 | 0 | no |
| 6 | - | 0.518 | braking | right | 176.7 | 0.82 | 0 | no |
| 7 | Nouvelle Chicane | 0.641 | braking | right | 30.5 | 0.94 | 0 | si |
| 8 | Tabac | 0.717 | braking | left | 61.6 | 0.94 | 0 | si |
| 9 | - | 0.824 | braking | left | 42.6 | 0.87 | 0 | si |
| 10 | La Rascasse | 0.881 | braking | right | 19.9 | 0.94 | 0 | si |

### Silverstone Circuit (ks_silverstone_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld)

| # | Nombre | Fraccion | Tipo | Dir. | Radio min (m) | Conf. | A fondo % | Compleja |
|---|---|---|---|---|---|---|---|---|
| 1 | Abbey | 0.053 | braking | right | 135.0 | 0.98 | 0 | no |
| 2 | - | 0.080 | lift | left | 187.8 | 0.84 | 40 | no |
| 3 | Village | 0.134 | braking | right | 39.7 | 0.97 | 0 | no |
| 4 | The Loop | 0.159 | braking | left | 35.3 | 0.97 | 0 | si |
| 5 | Aintree | 0.194 | flat_out | left | 105.7 | 0.80 | 80 | no |
| 6 | Brooklands | 0.317 | braking | left | 57.8 | 0.97 | 0 | no |
| 7 | Luffield | 0.351 | braking | right | 50.5 | 0.97 | 0 | no |
| 8 | - | 0.414 | kink | right | 257.8 | 0.60 | 60 | no |
| 9 | Copse | 0.507 | braking | right | 125.4 | 0.97 | 0 | no |
| 10 | - | 0.616 | braking | right | 164.0 | 0.96 | 0 | no |
| 11 | - | 0.650 | braking | right | 92.2 | 0.94 | 0 | si |
| 12 | Stowe | 0.838 | braking | right | 103.9 | 0.97 | 0 | no |
| 13 | - | 0.891 | lift | left | 373.7 | 0.60 | 0 | no |
| 14 | Vale | 0.919 | braking | left | 39.7 | 0.97 | 0 | si |
| 15 | Club | 0.962 | flat_out | right | 118.4 | 0.80 | 60 | no |

### Circuit de Spa-Francorchamps (spa_&_ks_porsche_cayman_gt4_clubsport_&_piloto_&_stint_1.ld)

| # | Nombre | Fraccion | Tipo | Dir. | Radio min (m) | Conf. | A fondo % | Compleja |
|---|---|---|---|---|---|---|---|---|
| 1 | La Source | 0.056 | braking | right | 26.7 | 0.97 | 0 | no |
| 2 | Eau Rouge / Raidillon | 0.163 | lift | right | 163.9 | 0.94 | 0 | si |
| 3 | Les Combes | 0.352 | braking | right | 63.3 | 0.97 | 0 | si |
| 4 | Malmedy | 0.376 | lift | right | 78.4 | 0.91 | 0 | no |
| 5 | Rivage | 0.440 | braking | right | 50.2 | 0.97 | 0 | no |
| 6 | - | 0.470 | braking | left | 70.5 | 0.94 | 0 | no |
| 7 | Pouhon | 0.549 | braking | left | 122.4 | 0.97 | 0 | no |
| 8 | Fagnes | 0.647 | braking | right | 83.6 | 0.97 | 0 | si |
| 9 | Stavelot | 0.708 | braking | right | 61.8 | 0.97 | 0 | no |
| 10 | - | 0.745 | lift | right | 133.3 | 0.94 | 0 | no |
| 11 | - | 0.884 | lift | left | 203.1 | 0.79 | 0 | no |
| 12 | Blanchimont | 0.906 | flat_out | left | 266.0 | 0.50 | 100 | no |
| 13 | Bus Stop | 0.973 | braking | left | 25.5 | 0.97 | 0 | si |

## Curvas nunca detectadas

Curvas tabuladas sin ninguna deteccion emparejada (en ningun detector, ninguna vuelta, ningun archivo del circuito): candidatas a 'curva a fondo' o a posicion mal tabulada.

- Ninguna.

Nunca detectadas por cada detector (aunque otro si las vea):

- Autodromo Enzo e Dino Ferrari (Imola): speed: ninguna; geometry: ninguna; segmenter: ninguna; map_no_table: Variante Bassa; single_lap_no_table: Variante Bassa
- Circuit de la Sarthe (Le Mans): speed: ninguna; geometry: ninguna; segmenter: ninguna; map_no_table: ninguna; single_lap_no_table: ninguna
- Circuit de Monaco: speed: ninguna; geometry: ninguna; segmenter: ninguna; map_no_table: ninguna; single_lap_no_table: ninguna
- Silverstone Circuit: speed: Abbey, Aintree; geometry: ninguna; segmenter: Aintree; map_no_table: ninguna; single_lap_no_table: ninguna
- Circuit de Spa-Francorchamps: speed: Eau Rouge / Raidillon, Blanchimont; geometry: ninguna; segmenter: Eau Rouge / Raidillon, Malmedy, Blanchimont; map_no_table: ninguna; single_lap_no_table: ninguna

## Archivos utilizados

- fn_imola_&_ks_porsche_cayman_gt4_clubsport_&_piloto_&_stint_1.ld (imola, ks_porsche_cayman_gt4_clubsport, 21 vueltas, mapa en 2.3 s incluidas las 4 variantes y el modo vuelta a vuelta)
- imola_&_ferrari_458_&_piloto_&_stint_1.ld (imola, ferrari_458, 4 vueltas, mapa en 0.54 s incluidas las 4 variantes y el modo vuelta a vuelta)
- imola_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_1.ld (imola, ks_porsche_919_hybrid_2016, 4 vueltas, mapa en 0.54 s incluidas las 4 variantes y el modo vuelta a vuelta)
- imola_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld (imola, ks_porsche_919_hybrid_2016, 1 vueltas, mapa en 0.12 s incluidas las 4 variantes y el modo vuelta a vuelta)
- ks_silverstone_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld (silverstone, ks_porsche_919_hybrid_2016, 5 vueltas, mapa en 0.74 s incluidas las 4 variantes y el modo vuelta a vuelta)
- ks_silverstone_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_3.ld (silverstone, ks_porsche_919_hybrid_2016, 1 vueltas, mapa en 0.15 s incluidas las 4 variantes y el modo vuelta a vuelta)
- monaco_2020_&_cky_porschecarrera_gt_04_&_piloto_&_stint_1.ld (monaco, cky_porschecarrera_gt_04, 2 vueltas, mapa en 0.26 s incluidas las 4 variantes y el modo vuelta a vuelta)
- monaco_2020_&_f_porsche_gt2rs_mr_&_piloto_&_stint_1.ld (monaco, f_porsche_gt2rs_mr, 1 vueltas, mapa en 0.13 s incluidas las 4 variantes y el modo vuelta a vuelta)
- spa_&_ks_porsche_cayman_gt4_clubsport_&_piloto_&_stint_1.ld (spa_francorchamps, ks_porsche_cayman_gt4_clubsport, 3 vueltas, mapa en 0.47 s incluidas las 4 variantes y el modo vuelta a vuelta)
- sx_lemans_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld (le_mans, ks_porsche_919_hybrid_2016, 4 vueltas, mapa en 0.61 s incluidas las 4 variantes y el modo vuelta a vuelta)
- sx_lemans_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_3.ld (le_mans, ks_porsche_919_hybrid_2016, 3 vueltas, mapa en 0.44 s incluidas las 4 variantes y el modo vuelta a vuelta)
- cayman_gt4_imola_assetto_corsa.csv (imola, ks_porsche_cayman_gt4_clubsport, 21 vueltas, mapa en 2.09 s incluidas las 4 variantes y el modo vuelta a vuelta)
- porsche_gt4_spa.csv (spa_francorchamps, ks_porsche_cayman_gt4_clubsport, 3 vueltas, mapa en 0.31 s incluidas las 4 variantes y el modo vuelta a vuelta)
- imola_5laps.csv.gz (imola, ks_porsche_cayman_gt4_clubsport, 5 vueltas, mapa en 0.4 s incluidas las 4 variantes y el modo vuelta a vuelta)
- spa_3laps.csv.gz (spa_francorchamps, ks_porsche_cayman_gt4_clubsport, 3 vueltas, mapa en 0.29 s incluidas las 4 variantes y el modo vuelta a vuelta)

## Archivos omitidos

- acu_sepang_&_honda_nsx_gt500_2023_&_piloto_&_stint_1.ld: circuito reconocido pero sin curvas tabuladas
- acu_sepang_&_rss_formula_hybrid_2017_&_piloto_&_stint_1.ld: circuito reconocido pero sin curvas tabuladas
- el capitan_&_ddm_honda_s2000_ap1_&_piloto_&_stint_1.ld: circuito no esta en la tabla
- imola_&_ks_porsche_991_carrera_s_&_piloto_&_stint_1.ld: sin vueltas completas
- ks_brands_hatch_&_ks_ferrari_330_p4_&_piloto_&_stint_1.ld: sin vueltas completas
- ks_nordschleife_&_ks_mclaren_p1_&_piloto_&_stint_1.ld: circuito reconocido pero sin curvas tabuladas
- ks_nordschleife_&_ks_mclaren_p1_&_piloto_&_stint_2.ld: circuito reconocido pero sin curvas tabuladas
- ks_nordschleife_&_ks_mclaren_p1_&_piloto_&_stint_3.ld: circuito reconocido pero sin curvas tabuladas
- ks_nordschleife_&_ks_mclaren_p1_&_piloto_&_stint_4.ld: circuito reconocido pero sin curvas tabuladas
- ks_nordschleife_&_ks_mclaren_p1_&_piloto_&_stint_5.ld: circuito reconocido pero sin curvas tabuladas
- ks_red_bull_ring_&_ks_maserati_gt_mc_gt4_&_piloto_&_stint_1.ld: circuito reconocido pero sin curvas tabuladas
- ks_red_bull_ring_&_ks_porsche_cayman_gt4_clubsport_&_piloto_&_stint_1.ld: circuito reconocido pero sin curvas tabuladas
- ks_silverstone_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_1.ld: longitud medida 5641 m no encaja con la tabla (5891 m): otro trazado
- ks_silverstone_&_ks_porsche_cayman_gt4_std_&_piloto_&_stint_1.ld: longitud medida 2956 m no encaja con la tabla (5891 m): otro trazado
- ks_silverstone_&_ks_porsche_cayman_gt4_std_&_piloto_&_stint_2.ld: longitud medida 2957 m no encaja con la tabla (5891 m): otro trazado
- mugello_&_lotus_exos_125_&_piloto_&_stint_1.ld: sin vueltas completas
- onin_&_ks_mazda_rx7_spirit_r_&_piloto_&_stint_1.ld: circuito no esta en la tabla
- onin_&_ks_mazda_rx7_spirit_r_&_piloto_&_stint_2.ld: circuito no esta en la tabla
- rt_california_highway_&_s2000_2003_time_attack_&_piloto_&_stint_1.ld: circuito no esta en la tabla
- rt_california_highway_&_s2000_2003_time_attack_&_piloto_&_stint_2.ld: circuito no esta en la tabla
- spa_&_ks_mercedes_c9_&_piloto_&_stint_1.ld: sin vueltas completas
- sx_lemans_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_1.ld: sin vueltas completas
- zw_croft_&_ferrari_458_&_piloto_&_stint_1.ld: circuito no esta en la tabla
- zw_croft_&_ferrari_458_&_piloto_&_stint_2.ld: circuito no esta en la tabla
- vuelta_lenta.csv: circuito reconocido pero sin curvas tabuladas
- vuelta_rapida.csv: circuito reconocido pero sin curvas tabuladas
- vuelta_rapida_mc.csv: circuito reconocido pero sin curvas tabuladas
- rbr_fast.csv.gz: circuito reconocido pero sin curvas tabuladas
- rbr_other_car.csv.gz: circuito reconocido pero sin curvas tabuladas
- rbr_slow.csv.gz: circuito reconocido pero sin curvas tabuladas

## Limitaciones

- La verdad de referencia son SOLO las curvas tabuladas en `circuits.json`; las curvas reales no tabuladas cuentan como 'extras', que por tanto mezclan ruido y curvas reales (de ahi la columna ruido).
- Un acierto exige una deteccion a menos de la tolerancia del circuito; no valida el nombre mas alla de la posicion y el orden (emparejamiento uno a uno de `circuits.assign_names`).
- Los fixtures del repo son recortes de archivos que tambien pueden estar en la carpeta de descargas, asi que algunas vueltas pueden contarse dos veces.
- Circuitos y coches con pocas vueltas dan metricas de estabilidad poco fiables (marcados en la tabla).
- El detector `segmenter` se ejecuta sobre la vuelta remuestreada a 1 m; los demas sobre la vuelta cruda.
- La tabla y la geometria de pista no son independientes de la telemetria: la tabla se ajusto con minimos de velocidad de estas mismas vueltas. Por eso el numero honesto es `map_no_table` y la validacion cruzada.
