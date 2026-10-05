# 15 - Modelo de Degradación de Neumáticos

[See in English](./15_tyre_degradation.md)

**Módulo:** `src/analytics/tyre_degradation.py`
**Funciones principales:** `predecir_degradacion_neumatico(dfs, df_laps)`, `detect_wear_tracking(dfs)`
**Helpers compartidos (de `src/analytics/stint.py`):** `analizar_degradacion_stint`, `_projection_laps`, `MIN_LAPS_FOR_TREND`
**Reconciliado con el código:** 2026-10-03 (las versiones EN y ES comparten la misma estructura)

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Algoritmo](#2-algoritmo)
3. [Requisitos de Entrada](#3-requisitos-de-entrada)
4. [Esquema de Salida](#4-esquema-de-salida)
5. [Guía de Interpretación](#5-guía-de-interpretación)
6. [Limitaciones](#6-limitaciones)
7. [Referencia de Constantes](#7-referencia-de-constantes)
8. [Estado de Verificación](#8-estado-de-verificación)

---

## 1. Descripción General

El módulo cuantifica cuánto rendimiento (tiempo por vuelta) ha perdido un juego de neumáticos a lo largo de un stint y proyecta cuántas vueltas quedan antes de un "cliff" de rendimiento (una pérdida de 1,5 s respecto a la mejor vuelta).

**No** ajusta un modelo de aprendizaje automático. Versiones anteriores de este documento describían una regresión polinomial Ridge; ese modelo ya no existe en el código y aquí no se usa `scikit-learn`. El diseño actual reutiliza deliberadamente el motor de tendencia de `stint.py`, de modo que la página de neumáticos y la de stint nunca discrepen en la pendiente, y sigue tres principios:

1. **No inventar desgaste.** Si el simulador no modelaba el desgaste de neumáticos, no se calcula degradación.
2. **No reportar degradación negativa.** Un tiempo por vuelta que baja es consumo de combustible, evolución de pista o ruido, no "neumáticos que mejoran". Se informa por separado.
3. **No proyectar con pocos datos.** Por debajo de un mínimo de vueltas válidas no se proyecta nada, y la estimación del cliff solo se produce cuando la degradación es estadísticamente distinguible de cero.

---

## 2. Algoritmo

### 2.1 Detección de seguimiento de desgaste (`detect_wear_tracking`)

Antes de cualquier cálculo, el módulo comprueba si el simulador modelaba realmente el desgaste. Recorre todas las columnas de todos los DataFrames de vuelta:

- **Canales de tasa de desgaste** (nombres exactos): `AID Tire Wear Rate`, `AID Tyre Wear Rate`, `Tire Wear Rate`, `Tyre Wear Rate`, `TyreWearRate`, `TireWearRate`. Se registra el máximo del valor absoluto.
- **Canales de estado de desgaste/agarre** (prefijo, sin distinguir mayúsculas): `tire/tyre rubber grip`, `tire/tyre wear`, `tirewear`, `tyrewear`, `tire/tyre life`, `tirelife`, `tyrelife`, `tyregrip` (el nombre en el loader de `Tire Rubber Grip FL..RR`). Se registran el mínimo y el máximo de toda la sesión por canal.

Decisión, en este orden:

| Condición | Resultado |
|---|---|
| Existe un canal de tasa y su máximo absoluto es <= 1e-9 | `active = False` ("... == 0 durante toda la sesión") |
| Existen canales de estado y **todos** tienen un rango de sesión < 0,05 | `active = False` ("... constante en la sesión") |
| Existen canales de estado y al menos uno varía | `active = True` |
| Solo hay canales de tasa, con valores > 0 | `active = True` |
| Ningún canal de desgaste | `active = None` (desconocido: el análisis continúa, marcado como tal) |

Cuando `active` es `False` la función retorna de inmediato con `available: False`, `wear_tracking: False`, `reason_code: "wear_inactive"`, el `reason` localizado y `wear_evidence`. No se calcula nada más.

### 2.2 Selección de vueltas

Las vueltas válidas salen de `_projection_laps(df_laps)` (compartido con el módulo de stint):

1. Solo vueltas de carrera: se eliminan las vueltas de boxes (`is_pit_lap`), los valores atípicos de tiempo (< 70 % o > 115 % de la mediana, aplicado cuando existen al menos 3 vueltas) y las vueltas sin tiempo.
2. Se eliminan las vueltas de salida de boxes (la vuelta posterior a una de boxes) si quedan suficientes (al menos `MIN_LAPS_FOR_TREND`).
3. Se elimina la primera vuelta de la sesión (salida parada/lanzada con neumáticos fríos) cuando hay más de `MIN_LAPS_FOR_TREND` vueltas.

Si quedan menos de `MIN_LAPS_FOR_TREND` (= 5) vueltas válidas, la función retorna `available: False`, `low_confidence: true`, `confidence: "low"`, `reason_code: "insufficient_sample"` y el número de vueltas encontradas (`n_laps_used`).

### 2.3 Variable objetivo

Para cada vuelta válida con tiempo `t_i` y el mejor tiempo válido `t_best`:

```
delta_i = t_i - t_best
```

### 2.4 Tendencia y pendiente de degradación

La pendiente no se calcula aquí. `analizar_degradacion_stint(df_laps)` (en `stint.py`) produce:

- `tasa_s_per_lap`: la **pendiente total robusta** del tiempo por vuelta frente al número de vuelta: pendiente OLS contraída (Bayes empírico, desviación previa 0,05 s/vuelta) hacia el efecto explícito del combustible y limitada a +/-0,15 s/vuelta.
- `fuel_effect_s_per_lap`: el efecto de la masa de combustible, `-0,035 s/L x consumo medio por vuelta` (negativo = el coche es más rápido a medida que se vacía el depósito), aplicado solo si el consumo medio es al menos 0,05 L/vuelta (si no, 0).
- `slope_se_s_per_lap` y `slope_ci`: error estándar e intervalo de confianza del 95 % de la pendiente **OLS cruda** (el IC no es el contraído).
- `anchor_lap`, `anchor_time_s`: mediana de las últimas tres vueltas válidas y su número de vuelta medio.

El módulo de neumáticos separa entonces la componente de neumático:

```
total       = tasa_s_per_lap
deg         = max(0, total - fuel_effect)        # degradation_rate_s_per_lap, siempre >= 0
track_evo   = min(0, total - fuel_effect)        # track_evolution_s_per_lap, siempre <= 0
ci_lo_deg   = slope_ci[0] - fuel_effect
reliable    = (deg >= 0.01) and (ci_lo_deg > 0)  # degradation_detected
```

Como `fuel_effect` es <= 0, restarlo devuelve la ganancia por combustible, así que un coche con tiempo plano mientras quema combustible muestra degradación positiva. Un resto negativo nunca se reporta como degradación; va a `track_evolution_s_per_lap`.

### 2.5 Proyección del cliff

La proyección avanza 40 vueltas desde la última vuelta válida, anclada al ritmo reciente (no a la ordenada en el origen de la regresión):

```
proj(l)  = anchor_delta + deg * (l - anchor_lap)
sigma    = max( std(residuos de un ajuste lineal de delta, ddof=2), 0.25 )
band(l)  = 1.28 * sqrt( (slope_se * (l - anchor_lap))^2 + sigma^2 )
p10(l)   = max(0, proj(l) - band(l))
p90(l)   = proj(l) + band(l)
```

con `anchor_delta = anchor_time_s - t_best`. El factor 1,28 da una banda del 80 % (p10-p90). La lista `projection` contiene solo las primeras 25 vueltas futuras, cada una con `projected`, `p10`, `p90` y `cliff`.

`remaining_laps` se produce **solo cuando `reliable` es verdadero**: es el primer número de vueltas `k` posteriores a la última para el que `proj >= 1,5 s`, o la cadena `">40"` si no hay cruce en 40 vueltas. Si no es fiable vale `null`.

### 2.6 Estado de desgaste (0-100 %)

Solo cuando `reliable` es verdadero:

```
max_scale = max(1.5, 1.2 * max(delta), 0.3)
wear_pct  = clamp( delta_last / max_scale * 100, 0, 100 ), redondeado a 0,1
```

En caso contrario `wear_pct` es `null`. La escala se ancla al umbral del cliff o al peor delta de la sesión (x1,2), el que sea mayor.

### 2.7 Características por vuelta y factores de desgaste

Para cada vuelta válida cuyo fragmento de telemetría exista en `dfs` (emparejado por el índice de fila de `df_laps`), se construye un vector de características con el primer canal encontrado en una lista de prioridad (nombres nativos de iRacing como `LFtempCM` y nombres tipo MoTeC como `Tyre Temp FL Centre`):

| Característica | Descripción |
|---|---|
| `temp_{fl,fr,rl,rr}` | Temperatura media del núcleo del neumático (requiere más de 5 muestras no nulas) |
| `stress_{pos}` | Fracción de muestras fuera de la ventana de 75-100 degC |
| `pres_{pos}` | Presión media del neumático (requiere más de 5 muestras; aquí no se convierten unidades) |
| `mean_lat_g` | Aceleración lateral absoluta media |
| `mean_brake_g` | Deceleración longitudinal absoluta media, contando solo muestras por debajo de -0,1 g (0 si no hay) |
| `mean_speed` | Velocidad media (se calcula pero se excluye del ranking de correlaciones) |

Cuando al menos `MIN_LAPS_FOR_FACTORS` (= 6) vueltas tienen características:

- **Factores de desgaste**: correlación de Pearson absoluta de cada característica (NaN imputado con la mediana; las constantes se omiten; se excluyen `lap_number` y `mean_speed`) con `delta_vs_best`. Las seis mayores se devuelven en `top_wear_factors`. La `correlation` reportada es el valor absoluto, por lo que el signo no está disponible.
- **Tendencias de temperatura por eje**: pendiente (degC por vuelta) de un ajuste de primer grado de la temperatura media delantera (`temp_fl`, `temp_fr`) y trasera (`temp_rl`, `temp_rr`) frente al número de vuelta; los huecos se rellenan hacia atrás y luego hacia delante.

Con menos de 6 vueltas ambos se omiten y `wear_factors_reason` / `temp_trend_reason` explican el motivo. `left_mean_temp` y `right_mean_temp` son la media de todas las temperaturas por vuelta de los neumáticos izquierdos (FL, RL) y derechos (FR, RR).

---

## 3. Requisitos de Entrada

**`dfs`**: lista de DataFrames de telemetría por vuelta. La posición en la lista debe corresponder al índice de fila de `df_laps` (el emparejamiento es por índice; un desajuste asocia en silencio telemetría equivocada a una vuelta). Todos los canales son opcionales.

**`df_laps`**: resumen de vueltas.

| Columna | Obligatoria | Descripción |
|---|---|---|
| `lap_time_s` | Sí | Duración de la vuelta en segundos |
| `lap_number` | Sí | Número de vuelta (usado por los helpers compartidos) |
| `is_pit_lap` | No | Marca vueltas de entrada/salida; se usa para excluir |
| `fuel_burned`, `fuel_end`, `max_g_sum` | No | Usadas por `stint.py` para el efecto del combustible, vueltas de combustible restantes y tendencia de agarre |

Canales usados en el paso de características: temperatura del núcleo del neumático por esquina, presión por esquina, G lateral, G longitudinal y velocidad. La detección de desgaste lee además los canales de tasa/estado de desgaste de la sección 2.1.

Este módulo no depende de `scikit-learn`; necesita `numpy` y `pandas`, más `scipy` a través de `stint.py`.

---

### 2.8 Desgaste medido por el simulador (`measure_rubber_grip`)

Independiente de los tiempos por vuelta: el agarre medio de la goma (% restante) de cada neumático por vuelta, la pérdida entre la primera y la última muestra y su pendiente por vuelta. `level`: `none` (< 0,02 %/vuelta), `minimal` (< 0,15), `moderate` (< 0,5), `high`. Se devuelve como `grip_measured` (`start_pct`, `end_pct`, `loss_pct`, `loss_pct_per_lap`, `n_laps`, `level`, `per_tyre`, `laps`) junto con `wear_rate` (el multiplicador `AID Tire Wear Rate`). Cuando la tendencia de ritmo no encuentra nada, la `reason` cita esta cifra: desgaste mínimo significa "el simulador modela el desgaste pero la pérdida es demasiado pequeña para mover el tiempo"; moderado o alto significa "el agarre sí cayó, los tiempos simplemente no lo muestran" (`reason_code: wear_measured_not_in_times`).

Las vueltas con un trompo, un incidente grave o que costaron 1,5 s o más (ver [18](./18_incidents.es.md)) se dejan fuera de la tendencia de ritmo y se listan en `incident_laps_excluded`; si quedan menos de 5 vueltas la respuesta es `insufficient_sample` con esa explicación, en lugar de una tendencia dibujada con vueltas distorsionadas.

## 4. Esquema de Salida

### 4.1 Retornos tempranos (`available: false`)

| `reason_code` | Significado | Claves extra |
|---|---|---|
| `wear_inactive` | El simulador no modela el desgaste de neumáticos | `wear_tracking: false`, `wear_evidence` |
| `insufficient_sample` | Menos de 5 vueltas válidas | `wear_tracking`, `low_confidence: true`, `confidence: "low"`, `n_laps_used` |
| (ninguno) | El helper de stint no pudo ajustar (menos de 3 vueltas) | `wear_tracking`, `reason` |

### 4.2 Resultado completo (`available: true`)

| Clave | Tipo | Unidad | Descripción |
|---|---|---|---|
| `available` | bool | | `true` |
| `wear_tracking` | bool o null | | `true` / `false` / `null` (desconocido) según `detect_wear_tracking` |
| `wear_evidence` | string | | Evidencia legible de esa decisión |
| `wear_pct` | float o null | % | Estado de desgaste; `null` salvo que la degradación sea `reliable` |
| `remaining_laps` | int, `">40"` o null | vueltas | Vueltas hasta el cliff de 1,5 s; `null` salvo que sea `reliable` |
| `current_delta_s` | float | s | Delta de la última vuelta válida respecto a la mejor |
| `cliff_threshold_s` | float | s | 1,5 |
| `degradation_rate_s_per_lap` | float | s/vuelta | `deg`, siempre >= 0 |
| `degradation_detected` | bool | | `reliable` (ver 2.4) |
| `track_evolution_s_per_lap` | float | s/vuelta | Parte negativa de la pendiente (evolución de pista/ruido), siempre <= 0 |
| `fuel_effect_s_per_lap` | float | s/vuelta | Efecto de la masa de combustible (<= 0) |
| `raw_slope_s_per_lap` | float | s/vuelta | Pendiente OLS sin contraer |
| `slope_ci` | [float, float] o null | s/vuelta | IC 95 % de la pendiente cruda |
| `confidence` | `"low"`, `"medium"` o `"high"` | | Proviene de `stint.py` (low si hay menos de 8 vueltas o la semiamplitud del IC > 0,2; high si >= 10 vueltas y semiamplitud <= 0,05) |
| `low_confidence` | bool | | Refleja `confidence == "low"` |
| `n_laps_used`, `n_laps_analyzed` | int | vueltas | Vueltas válidas usadas (valores idénticos, dos nombres por compatibilidad) |
| `reason_code`, `reason` | string o null | | `no_detectable_degradation` más un texto localizado cuando no es `reliable`; si no, `null` |
| `top_wear_factors` | lista | | Hasta 6 `{factor, correlation}` (Pearson absoluta) |
| `wear_factors_reason` | string o null | | Por qué no hay factores (menos de 6 vueltas) |
| `lap_data` | lista | | Por vuelta `{lap, delta, trend}` |
| `projection` | lista | | Primeras 25 vueltas futuras `{lap, projected, p10, p90, cliff}` |
| `front_temp_trend_c_per_lap`, `rear_temp_trend_c_per_lap` | float o null | degC/vuelta | Pendientes de temperatura por eje |
| `temp_trend_reason` | string o null | | Mismo motivo que `wear_factors_reason` |
| `left_mean_temp`, `right_mean_temp` | float o null | degC | Temperatura media de neumáticos por lado |
| `tyre_temps_available` | bool | | Se encontró algún canal de temperatura de neumático |

Nota: los textos `reason` se localizan mediante `src/i18n.py` (claves `tyre_wear_inactive`, `tyre_insufficient_laps`, `tyre_no_degradation`, `tyre_factors_few_laps`); solo `reason_code` es estable para uso programático.

Ejemplos de objetos anidados:

```json
{ "lap": 12, "delta": 0.342, "trend": 0.318 }
{ "lap": 18, "projected": 1.124, "p10": 0.85, "p90": 1.40, "cliff": 1.5 }
{ "factor": "stress_fl", "correlation": 0.872 }
```

---

## 5. Guía de Interpretación

- **`degradation_detected: false`** es un resultado válido y frecuente: los tiempos no muestran una tendencia al alza fiable una vez descontado el combustible. `wear_pct` y `remaining_laps` son entonces `null` a propósito. No es un fallo ni afirma que los neumáticos sean perfectos.
- **`degradation_rate_s_per_lap`**: la cifra es la parte de neumático de la pendiente. Órdenes de magnitud habituales en neumáticos de competición son 0,05-0,15 s/vuelta (moderado) y más de 0,20 s/vuelta (agresivo); son reglas empíricas y **no** están codificadas ni validadas en el código (el código solo limita la pendiente total a +/-0,15 s/vuelta).
- **`track_evolution_s_per_lap`**: un valor claramente negativo indica que los tiempos mejoran más allá del efecto del combustible (engomado de pista, calentamiento, aprendizaje del piloto).
- **`wear_pct`**: relativo al peor delta de la sesión (o al cliff), no una vida útil absoluta. No comparar entre compuestos ni circuitos.
- **`remaining_laps`**: `">40"` significa que no hay cruce en el horizonte. Mantén un margen de 2-3 vueltas al planear paradas (regla empírica, no calculada por el módulo); usa `p10`/`p90` para la incertidumbre.
- **Factores de desgaste**: una correlación alta de `stress_{pos}` con el delta sugiere pérdida de origen térmico (neumático fuera de 75-100 degC); una correlación alta con `mean_lat_g` sugiere desgaste por carga. Correlación no es causalidad, y con 6-10 vueltas es ruidosa.
- **Tendencias por eje y medias izquierda/derecha**: una diferencia persistente entre la temperatura media izquierda y derecha sugiere asimetría de carga (presión/caída), y tendencias delantera/trasera divergentes sugieren un cambio de balance. Son interpretaciones, no salidas.

---

## 6. Limitaciones

- **Proyección lineal.** La degradación real suele ser no lineal (fase lenta y luego cliff). La proyección es una recta desde el ritmo reciente y no anticipa un cliff repentino.
- **La separación del combustible depende del canal de combustible.** Sin canal de combustible (`fuel_burned` < 0,05 L/vuelta) el efecto del combustible es 0, por lo que el consumo se absorbe en la pendiente y la degradación se subestima (o se reporta como evolución de pista).
- **Muestras pequeñas.** 5 vueltas es el mínimo técnico, se necesitan 8 o más para confianza no baja y 6 para los factores. Sesiones cortas producen `insufficient_sample`.
- **El test de fiabilidad usa el IC crudo.** `degradation_detected` compara con cero el límite inferior del IC OLS sin contraer (menos el efecto del combustible); lo que se reporta como tasa es la pendiente contraída.
- **Constantes fijas.** Cliff de 1,5 s y ventana óptima de 75-100 degC no son específicos del compuesto.
- **Se asume alineación posicional** de la telemetría entre `dfs` y `df_laps`.
- **La detección de desgaste se basa en nombres.** Un canal de desgaste no reconocido da `wear_tracking: null`, no `false`.
- **Unidades de presión** no normalizadas en este módulo (solo se usa como característica de correlación).
- **Sin calibración entre sesiones.**

---

## 7. Referencia de Constantes

| Constante | Valor | Dónde |
|---|---|---|
| `_OPT_MIN`, `_OPT_MAX` | 75 / 100 degC | `tyre_degradation.py` |
| `_CLIFF_S` | 1,5 s | `tyre_degradation.py` |
| `MIN_LAPS_FOR_FACTORS` | 6 | `tyre_degradation.py` |
| `_WEAR_CONST_RANGE` | 0,05 | `tyre_degradation.py` |
| Horizonte de proyección / salida | 40 / 25 vueltas | `tyre_degradation.py` |
| z de la banda / suelo de sigma | 1,28 / 0,25 s | `tyre_degradation.py` |
| Fiabilidad: tasa mínima | 0,01 s/vuelta | `tyre_degradation.py` |
| `MIN_LAPS_FOR_TREND` | 5 | `stint.py` |
| `MIN_LAPS_FOR_MEDIUM_CONF` | 8 | `stint.py` |
| `MAX_ABS_SLOPE_S_PER_LAP` | 0,15 | `stint.py` |
| `SLOPE_PRIOR_SD` | 0,05 | `stint.py` |
| `FUEL_S_PER_L` | 0,035 s/L | `stint.py` |
| `MIN_FUEL_BURN_L` | 0,05 L/vuelta | `stint.py` |

---

## 8. Estado de Verificación

Todas las fórmulas, umbrales y claves anteriores se leyeron directamente de `tyre_degradation.py` y `stint.py` el 2026-10-03. No verificable desde el código y por tanto señalado: los rangos típicos de s/vuelta y el margen de 2-3 vueltas (reglas empíricas), y el significado físico del cliff de 1,5 s (una convención).
