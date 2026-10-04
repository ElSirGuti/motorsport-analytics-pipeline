# Banco de pruebas de curvas: linea base

Fecha: 2026-10-04. Generado con `python scripts/benchmark_corners.py` (no modifica ningun detector; solo los ejecuta y compara con la tabla de `circuits.json`).

Detectores: `speed` (metrics.detect_apex_points), `geometry` (geometry.detectar_apexes_perfectos), `segmenter` (metrics.segment_corners, el que usan stint/sesion/comparacion) y `union` (los tres, deduplicados a 60 m).

Metricas: **recall** = curvas tabuladas con una deteccion emparejada dentro de tolerancia / curvas tabuladas (media por vuelta); **extras** = detecciones por vuelta sin curva tabulada; **std m** = desviacion tipica de la posicion de cada curva entre vueltas (media de curvas con >= 2 apariciones); **aparece %** = porcentaje medio de vueltas en que cada curva tabulada es detectada.

## Total

15 archivos utilizados, 81 vueltas completas.

| Detector | Recall | Detecciones/vuelta | Extras/vuelta | Std (m) | Aparece % |
|---|---|---|---|---|---|
| speed | 0.73 | 7.67 | 1.89 | 35.94 | 73.28 |
| geometry | 0.9 | 10.74 | 3.59 | 31.74 | 90.0 |
| segmenter | 0.78 | 7.33 | 1.15 | 32.7 | 78.44 |
| union | 0.95 | 11.96 | 4.46 | 30.05 | 94.71 |

## Por circuito y coche

Cada fila: recall / extras por vuelta / std en m. Std '-' = menos de 2 apariciones de cualquier curva.

| Circuito | Coche | Vueltas | Tab. | Tol. (m) | speed | geometry | segmenter | union |
|---|---|---|---|---|---|---|---|---|
| **Autodromo Enzo e Dino Ferrari (Imola)** (total) | todos | 56 | 8 | 122 | 0.76 / 0.6 / 37.2 | 0.93 / 2.2 / 30.7 | 0.86 / 0.3 / 33.8 | 0.98 / 2.8 / 28.8 |
| Autodromo Enzo e Dino Ferrari (Imola) | ferrari_458 | 4 | 8 | 122 | 1.00 / 0.5 / 17.1 | 0.81 / 1.8 / 17.2 | 0.91 / 0.2 / 12.8 | 1.00 / 2.2 / 18.7 |
| Autodromo Enzo e Dino Ferrari (Imola) | ks_porsche_919_hybrid_2016 | 5 | 8 | 122 | 0.78 / 1.2 / 76.6 | 0.78 / 2.0 / 72.6 | 0.75 / 1.4 / 79.1 | 0.78 / 3.0 / 59.5 |
| Autodromo Enzo e Dino Ferrari (Imola) | ks_porsche_cayman_gt4_clubsport | 47 | 8 | 122 | 0.74 / 0.5 / 26.9 | 0.95 / 2.3 / 19.5 | 0.86 / 0.2 / 22.8 | 1.00 / 2.9 / 20.8 |
| **Circuit de la Sarthe (Le Mans)** (total) | todos | 7 | 4 | 90 | 0.68 / 10.3 / 58.7 | 0.82 / 15.0 / 65.8 | 0.64 / 7.3 / 59.2 | 0.89 / 17.4 / 68.7 |
| Circuit de la Sarthe (Le Mans) | ks_porsche_919_hybrid_2016 | 7 | 4 | 90 | 0.68 / 10.3 / 58.7 | 0.82 / 15.0 / 65.8 | 0.64 / 7.3 / 59.2 | 0.89 / 17.4 / 68.7 |
| **Circuit de Monaco** (total) | todos | 3 | 6 | 120 | 1.00 / 6.7 / 7.7 | 1.00 / 4.7 / 7.0 | 0.94 / 4.7 / 5.6 | 1.00 / 6.7 / 6.0 |
| Circuit de Monaco | cky_porschecarrera_gt_04 (pocas vueltas) | 2 | 6 | 120 | 1.00 / 6.5 / 7.5 | 1.00 / 5.0 / 6.3 | 0.92 / 4.0 / 6.1 | 1.00 / 6.0 / 5.6 |
| Circuit de Monaco | f_porsche_gt2rs_mr (pocas vueltas) | 1 | 6 | 120 | 1.00 / 7.0 / - | 1.00 / 4.0 / - | 1.00 / 6.0 / - | 1.00 / 8.0 / - |
| **Silverstone Circuit** (total) | todos | 6 | 10 | 145 | 0.62 / 1.2 / 29.1 | 0.67 / 2.5 / 32.8 | 0.52 / 1.3 / 28.5 | 0.73 / 3.7 / 30.3 |
| Silverstone Circuit | ks_porsche_919_hybrid_2016 | 6 | 10 | 145 | 0.62 / 1.2 / 29.1 | 0.67 / 2.5 / 32.8 | 0.52 / 1.3 / 28.5 | 0.73 / 3.7 / 30.3 |
| **Circuit de Spa-Francorchamps** (total) | todos | 9 | 10 | 174 | 0.59 / 2.3 / 24.4 | 0.92 / 3.7 / 19.3 | 0.57 / 0.3 / 17.1 | 0.92 / 4.3 / 15.6 |
| Circuit de Spa-Francorchamps | ks_porsche_cayman_gt4_clubsport | 9 | 10 | 174 | 0.59 / 2.3 / 24.4 | 0.92 / 3.7 / 19.3 | 0.57 / 0.3 / 17.1 | 0.92 / 4.3 / 15.6 |

## Consistencia entre detectores

Detecciones medias por vuelta (cuantas curvas ve cada detector en la misma vuelta) frente a las curvas tabuladas.

| Circuito | Tabuladas | speed | geometry | segmenter | union |
|---|---|---|---|---|---|
| Autodromo Enzo e Dino Ferrari (Imola) | 8 | 6.68 | 9.62 | 7.16 | 10.64 |
| Circuit de la Sarthe (Le Mans) | 4 | 13.0 | 18.29 | 9.86 | 21.0 |
| Circuit de Monaco | 6 | 12.67 | 10.67 | 10.33 | 12.67 |
| Silverstone Circuit | 10 | 7.33 | 9.17 | 6.5 | 11.0 |
| Circuit de Spa-Francorchamps | 10 | 8.22 | 12.89 | 6.0 | 13.56 |

## Curvas nunca detectadas

Curvas tabuladas sin ninguna deteccion emparejada (en ningun detector, ninguna vuelta, ningun archivo del circuito): candidatas a 'curva a fondo' o a posicion mal tabulada.

- Ninguna.

Nunca detectadas por cada detector (aunque otro si las vea):

- Autodromo Enzo e Dino Ferrari (Imola): speed: ninguna; geometry: ninguna; segmenter: ninguna
- Circuit de la Sarthe (Le Mans): speed: ninguna; geometry: ninguna; segmenter: ninguna
- Circuit de Monaco: speed: ninguna; geometry: ninguna; segmenter: ninguna
- Silverstone Circuit: speed: Abbey, Aintree; geometry: ninguna; segmenter: Aintree
- Circuit de Spa-Francorchamps: speed: Eau Rouge / Raidillon, Blanchimont; geometry: ninguna; segmenter: Eau Rouge / Raidillon, Malmedy, Blanchimont

## Archivos utilizados

- cayman_gt4_imola_assetto_corsa.csv (imola, ks_porsche_cayman_gt4_clubsport, 21 vueltas)
- porsche_gt4_spa.csv (spa_francorchamps, ks_porsche_cayman_gt4_clubsport, 3 vueltas)
- fn_imola_&_ks_porsche_cayman_gt4_clubsport_&_piloto_&_stint_1.ld (imola, ks_porsche_cayman_gt4_clubsport, 21 vueltas)
- imola_&_ferrari_458_&_piloto_&_stint_1.ld (imola, ferrari_458, 4 vueltas)
- imola_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_1.ld (imola, ks_porsche_919_hybrid_2016, 4 vueltas)
- imola_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld (imola, ks_porsche_919_hybrid_2016, 1 vueltas)
- ks_silverstone_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld (silverstone, ks_porsche_919_hybrid_2016, 5 vueltas)
- ks_silverstone_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_3.ld (silverstone, ks_porsche_919_hybrid_2016, 1 vueltas)
- monaco_2020_&_cky_porschecarrera_gt_04_&_piloto_&_stint_1.ld (monaco, cky_porschecarrera_gt_04, 2 vueltas)
- monaco_2020_&_f_porsche_gt2rs_mr_&_piloto_&_stint_1.ld (monaco, f_porsche_gt2rs_mr, 1 vueltas)
- spa_&_ks_porsche_cayman_gt4_clubsport_&_piloto_&_stint_1.ld (spa_francorchamps, ks_porsche_cayman_gt4_clubsport, 3 vueltas)
- sx_lemans_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_2.ld (le_mans, ks_porsche_919_hybrid_2016, 4 vueltas)
- sx_lemans_&_ks_porsche_919_hybrid_2016_&_piloto_&_stint_3.ld (le_mans, ks_porsche_919_hybrid_2016, 3 vueltas)
- imola_5laps.csv.gz (imola, ks_porsche_cayman_gt4_clubsport, 5 vueltas)
- spa_3laps.csv.gz (spa_francorchamps, ks_porsche_cayman_gt4_clubsport, 3 vueltas)

## Archivos omitidos

- vuelta_lenta.csv: circuito reconocido pero sin curvas tabuladas
- vuelta_rapida.csv: circuito reconocido pero sin curvas tabuladas
- vuelta_rapida_mc.csv: circuito reconocido pero sin curvas tabuladas
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
- bmwm2g87_oran gp 2026-06-09 21-10-09.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran gp 2026-06-09 21-10-09_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-15-58.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-15-58_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-23-44.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-23-44_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-27-03.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-27-03_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-28-12.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-28-12_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-31-36.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-31-36_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-36-08.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-36-08_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-42-39.ibt: circuito reconocido pero sin curvas tabuladas
- bmwm2g87_oran south 2026-06-14 20-42-39_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- fordmustanggt4_limerock 2019 gp 2026-06-08 17-57-09.ibt: circuito reconocido pero sin curvas tabuladas
- fordmustanggt4_limerock 2019 gp 2026-06-08 17-57-09_Stint_1.ld: circuito reconocido pero sin curvas tabuladas
- rbr_fast.csv.gz: circuito reconocido pero sin curvas tabuladas
- rbr_other_car.csv.gz: circuito reconocido pero sin curvas tabuladas
- rbr_slow.csv.gz: circuito reconocido pero sin curvas tabuladas

## Limitaciones

- La verdad de referencia son SOLO las curvas tabuladas en `circuits.json`; las curvas reales no tabuladas cuentan como 'extras', que por tanto mezclan ruido y curvas reales.
- Un acierto exige una deteccion a menos de la tolerancia del circuito; no valida el nombre mas alla de la posicion y el orden (emparejamiento uno a uno de `circuits.assign_names`).
- Los fixtures del repo son recortes de archivos que tambien pueden estar en la carpeta de descargas, asi que algunas vueltas pueden contarse dos veces.
- Circuitos y coches con pocas vueltas dan metricas de estabilidad poco fiables (marcados en la tabla).
- El detector `segmenter` se ejecuta sobre la vuelta remuestreada a 1 m; los demas sobre la vuelta cruda.
