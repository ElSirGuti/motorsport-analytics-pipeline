# Degradación de Neumáticos — Predicción por Regresión Polinomial Ridge

**Módulo:** `src/analytics/tyre_degradation.py`  
**Fecha de revisión:** 2026-06-17

---

## Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Algoritmo y Metodología](#algoritmo-y-metodología)
   - 2.1 [Extracción de Características por Vuelta](#21-extracción-de-características-por-vuelta)
   - 2.2 [Modelo de Regresión Ridge Polinomial](#22-modelo-de-regresión-ridge-polinomial)
   - 2.3 [Proyección Lineal y Umbral de Cliff](#23-proyección-lineal-y-umbral-de-cliff)
   - 2.4 [Estado de Desgaste (wear_pct)](#24-estado-de-desgaste-wear_pct)
   - 2.5 [Importancia de Factores por Correlación](#25-importancia-de-factores-por-correlación)
   - 2.6 [Tendencias de Temperatura por Eje y Lado](#26-tendencias-de-temperatura-por-eje-y-lado)
3. [Canales Requeridos](#canales-requeridos)
4. [Esquema de Salida](#esquema-de-salida)
5. [Guía de Interpretación](#guía-de-interpretación)
6. [Limitaciones](#limitaciones)
7. [Referencias](#referencias)

---

## Descripción General

El desgaste del neumático es uno de los factores más determinantes en la estrategia de carrera y en la velocidad de vuelta sostenida. A medida que el compuesto se degrada, la capa de caucho en la zona de contacto pierde elasticidad y capacidad de generar fuerzas de adherencia, lo que produce un aumento progresivo del tiempo de vuelta. Este aumento no es lineal: existe un punto de inflexión conocido como *performance cliff* a partir del cual la degradación se acelera de forma brusca y la penalización en tiempo de vuelta se vuelve significativa.

El módulo `tyre_degradation.py` implementa una cadena de análisis que:

1. Extrae, para cada vuelta válida de la sesión, un vector de características físicas que sirven como *proxies* del desgaste: temperatura del núcleo del neumático, porcentaje de tiempo fuera de la ventana térmica óptima, presión, fuerzas G laterales y longitudinales, y velocidad media.
2. Entrena un modelo de regresión polinomial con regularización Ridge sobre esas características para predecir la diferencia de tiempo de vuelta respecto a la mejor vuelta de la sesión (*delta vs best*), que actúa como variable objetivo representativa del estado de degradación.
3. Calcula una tendencia lineal sobre el delta por número de vuelta, proyecta el comportamiento futuro y estima cuántas vueltas restan antes de alcanzar el umbral de *cliff* (1,5 segundos de penalización acumulada).
4. Reporta métricas secundarias de temperatura por eje (delantero/trasero) y por lado (izquierdo/derecho) para facilitar el diagnóstico de asimetría de desgaste.

La función principal del módulo es `predecir_degradacion_neumatico(dfs, df_laps)`, que recibe la lista de DataFrames por vuelta y el resumen de vueltas de la sesión, y devuelve un diccionario estructurado con todos los indicadores de desgaste.

---

## Algoritmo y Metodología

### 2.1 Extracción de Características por Vuelta

La función interna `_lap_features(df)` procesa el DataFrame de telemetría de una vuelta individual y devuelve un diccionario con las siguientes características:

**Temperatura del núcleo del neumático** — Para cada posición (FL, FR, RL, RR), el módulo resuelve el nombre de canal correcto mediante una tabla de sinónimos que cubre los formatos nativos de iRacing (`LFtempCM`, `LFtempM`) y las exportaciones de MoTeC (`Tyre Temp FL Centre`, `TyreTempCore_FL`). Una vez resuelto el canal:

- `temp_{pos}`: Temperatura media de la vuelta (°C), calculada como la media aritmética de todas las muestras válidas.
- `stress_{pos}`: Fracción de muestras en la vuelta en que la temperatura cae fuera de la ventana óptima [75 °C, 100 °C], expresada en el intervalo [0, 1]. Un valor de `stress = 0.3` indica que el 30 % de la vuelta el neumático trabajó fuera de su rango de operación ideal.

La ventana óptima de 75–100 °C es un valor de referencia para compuestos de circuito de uso general. Compuestos de lluvia o de alta energía pueden tener ventanas distintas; los umbrales `_OPT_MIN` y `_OPT_MAX` son constantes editables en el módulo.

**Presión de neumático** — `pres_{pos}`: Presión media de la vuelta (bar o kPa según el simulador/datalogger). No se realiza conversión de unidades; la escala relativa es suficiente para el modelo de regresión.

**Fuerzas G laterales** — `mean_lat_g`: Media del valor absoluto de la aceleración lateral durante la vuelta (G). Es la métrica más directa del trabajo transversal del neumático, vinculado al desgaste por cizalladura del compuesto.

**Fuerza de frenada** — `mean_brake_g`: Media del valor absoluto de la deceleración longitudinal durante los eventos de frenada (muestras con G longitudinal < −0,1 G). Captura el estrés térmico y el desgaste por abrasión en la entrada a curvas.

**Velocidad media** — `mean_speed`: Velocidad media de la vuelta, útil como covariable para normalizar el nivel de energía del stint.

Si un canal no está disponible en el DataFrame, la característica correspondiente se asigna a `NaN`. El pipeline de modelado gestiona los valores faltantes mediante imputación por la mediana.

---

### 2.2 Modelo de Regresión Ridge Polinomial

El modelo se construye como una cadena (`sklearn.pipeline.Pipeline`) con cuatro etapas:

```
Imputer (median) → StandardScaler → PolynomialFeatures (grado 1 o 2) → Ridge (α = 1.0)
```

**Variable objetivo:** `delta_vs_best` — diferencia en segundos entre el tiempo de vuelta observado y el mejor tiempo de la sesión. Un valor de 0,0 indica que la vuelta es la más rápida registrada; un valor de 2,5 indica que esa vuelta fue 2,5 segundos más lenta que el mejor registro.

**Selección del grado polinomial:** Si el número de vueltas volantes disponibles es mayor o igual a 6, se usa grado 2 (captura curvatura en la progresión de degradación). Con menos de 6 vueltas se usa grado 1 para evitar el sobreajuste en muestras escasas.

**Regularización Ridge:** El parámetro `alpha = 1.0` penaliza los coeficientes de gran magnitud, lo que estabiliza el modelo cuando algunas características están correlacionadas entre sí (por ejemplo, temperatura del eje delantero y temperatura del eje trasero suelen moverse conjuntamente). La regularización es especialmente importante en el espacio polinomial expandido, donde el número de variables puede superar al número de observaciones.

**Imputación por mediana:** Los valores `NaN` introducidos por canales no disponibles se sustituyen por la mediana de la columna correspondiente antes de escalar. Esto permite que el modelo opere con conjuntos de datos parciales, aunque la precisión se reduce cuando faltan características clave como la temperatura del neumático.

---

### 2.3 Proyección Lineal y Umbral de Cliff

Paralelamente al modelo Ridge, se ajusta una regresión lineal simple (`numpy.polyfit`, grado 1) sobre la serie temporal de `delta_vs_best` en función del número de vuelta. Esta regresión lineal directa sobre la señal observada es la que se utiliza para la proyección futura, ya que es más interpretable y robusta para la extrapolación que el modelo polinomial multivariante.

Sea $n$ el número de vuelta y $\delta(n)$ el delta observado, el ajuste lineal produce:

$$
\hat{\delta}(n) = m \cdot n + b
$$

donde $m$ (`degradation_rate_s_per_lap`) es la tasa de degradación en segundos por vuelta y $b$ es el intercepto. La proyección se evalúa para las 40 vueltas futuras siguientes a la vuelta actual:

$$
n_{\text{cliff}} = \min \left\{ n_f \in \mathbb{N} : \hat{\delta}(n_f) \geq 1.5 \right\}
$$

El umbral de *cliff* está fijado en $\Delta_{\text{cliff}} = 1{,}5$ s (`_CLIFF_S`). Si ninguna de las 40 vueltas proyectadas supera este umbral, el módulo reporta `remaining_laps = ">40"`, indicando que el neumático tiene vida útil suficiente para ese horizonte de análisis.

---

### 2.4 Estado de Desgaste (wear_pct)

El porcentaje de desgaste es una normalización del delta de la última vuelta respecto a la escala máxima del stint:

$$
\text{wear\_pct} = \min\!\left(100,\ \max\!\left(0,\ \frac{\delta_{\text{actual}}}{\delta_{\text{max\_scale}}} \times 100 \right)\right)
$$

donde:

$$
\delta_{\text{max\_scale}} = \max\!\left(\Delta_{\text{cliff}},\ \max(\delta_{\text{arr}}) \times 1.2,\ 0.3 \right)
$$

El factor 1,2 sobre el delta máximo observado añade un margen de escala para evitar que vueltas ruidosas saturen el indicador en el 100 %. El mínimo de 0,3 s garantiza que la escala sea siempre positiva incluso cuando todos los deltas son prácticamente cero.

---

### 2.5 Importancia de Factores por Correlación

Para identificar qué variables físicas contribuyen más al incremento del tiempo de vuelta, el módulo calcula el coeficiente de correlación de Pearson entre cada característica y el vector `delta_vs_best`:

$$
\rho_{X_j, \delta} = \frac{\text{Cov}(X_j, \delta)}{\sigma_{X_j} \cdot \sigma_\delta}
$$

Se reportan los seis factores con mayor $|\rho|$. Esta lista (`top_wear_factors`) orienta al ingeniero hacia los canales de mayor poder predictivo en esa sesión específica: si `stress_rr` encabeza la lista, el eje trasero derecho está operando fuera de ventana térmica de forma sistemática y correlacionada con la pérdida de rendimiento.

---

### 2.6 Tendencias de Temperatura por Eje y Lado

Se calculan cuatro métricas adicionales mediante regresiones lineales independientes sobre las temperaturas medias por vuelta:

- `front_temp_trend_c_per_lap`: Pendiente de la temperatura media del eje delantero (FL + FR) en función del número de vuelta (°C/vuelta).
- `rear_temp_trend_c_per_lap`: Ídem para el eje trasero (RL + RR).
- `left_mean_temp`: Temperatura media de sesión del lado izquierdo (FL + RL), en °C.
- `right_mean_temp`: Temperatura media de sesión del lado derecho (FR + RR), en °C.

La diferencia `left_mean_temp − right_mean_temp` es un indicador de asimetría de carga: en circuitos con predominio de curvas a derechas, el lado izquierdo suele mostrar temperaturas más altas por la mayor transferencia de carga lateral.

---

## Canales Requeridos

El módulo opera con detección de sinónimos: para cada canal, busca en orden de preferencia los nombres de la tabla interna y usa el primero que encuentre en el DataFrame.

| Canal | Sinónimos principales (iRacing / MoTeC) | Obligatorio |
|---|---|---|
| Temperatura neumático FL | `Tyre Temp FL Centre`, `LFtempCM`, `LFtempM`, `TyreTempFL` | No* |
| Temperatura neumático FR | `Tyre Temp FR Centre`, `RFtempCM`, `RFtempM`, `TyreTempFR` | No* |
| Temperatura neumático RL | `Tyre Temp RL Centre`, `LRtempCM`, `LRtempM`, `TyreTempRL` | No* |
| Temperatura neumático RR | `Tyre Temp RR Centre`, `RRtempCM`, `RRtempM`, `TyreTempRR` | No* |
| Presión neumático FL | `Tyre Pres FL`, `LFpressure`, `LFcoldPressure` | No |
| Presión neumático FR | `Tyre Pres FR`, `RFpressure`, `RFcoldPressure` | No |
| Presión neumático RL | `Tyre Pres RL`, `LRpressure`, `LRcoldPressure` | No |
| Presión neumático RR | `Tyre Pres RR`, `RRpressure`, `RRcoldPressure` | No |
| Aceleración lateral | `LateralG`, `Lateral G`, `LatAccel`, `Lateral Acc` | No |
| Aceleración longitudinal | `LongitudinalG`, `Longitudinal G`, `LongAccel` | No |
| Velocidad | `Speed`, `Ground Speed`, `GPS Speed`, `VehicleSpeed` | No |
| Tiempo de vuelta | `lap_time_s` en `df_laps` | **Sí** |
| Número de vuelta | `lap_number` en `df_laps` | No** |

\* La temperatura del neumático no es estrictamente obligatoria; si ninguna posición tiene canal disponible, el modelo opera solo con las G-loads y la velocidad. La calidad predictiva se reduce significativamente.

\*\* Si `lap_number` no está presente, se asigna un índice secuencial 1, 2, 3… que equivale a asumir que las vueltas son consecutivas sin pit stops intermedios.

**Requisito de datos mínimo:** Al menos 3 vueltas volantes válidas (excluyendo vueltas de pit) con tiempo de vuelta registrado. Con menos de 3 vueltas el módulo devuelve `{available: False}`.

---

## Esquema de Salida

La función `predecir_degradacion_neumatico` devuelve un diccionario con la siguiente estructura:

```json
{
  "available": true,
  "wear_pct": 38.5,
  "remaining_laps": 14,
  "current_delta_s": 0.578,
  "cliff_threshold_s": 1.5,
  "degradation_rate_s_per_lap": 0.0412,
  "n_laps_analyzed": 18,
  "top_wear_factors": [
    {"factor": "stress_rr", "correlation": 0.874},
    {"factor": "mean_lat_g", "correlation": 0.791},
    {"factor": "temp_rr", "correlation": 0.763},
    {"factor": "stress_rl", "correlation": 0.709},
    {"factor": "mean_brake_g", "correlation": 0.648},
    {"factor": "lap_number", "correlation": 0.591}
  ],
  "lap_data": [
    {"lap": 3, "delta": 0.041, "trend": 0.035},
    {"lap": 4, "delta": 0.098, "trend": 0.076}
  ],
  "projection": [
    {"lap": 19, "projected": 0.619, "cliff": 1.5},
    {"lap": 20, "projected": 0.660, "cliff": 1.5}
  ],
  "front_temp_trend_c_per_lap": 0.312,
  "rear_temp_trend_c_per_lap": 0.481,
  "left_mean_temp": 87.4,
  "right_mean_temp": 91.2,
  "tyre_temps_available": true
}
```

| Campo | Tipo | Descripción |
|---|---|---|
| `available` | bool | `true` si el análisis completó correctamente |
| `wear_pct` | float [0–100] | Estado de desgaste estimado en porcentaje |
| `remaining_laps` | int o `">40"` | Vueltas restantes antes del umbral de cliff |
| `current_delta_s` | float | Delta de la última vuelta vs. mejor vuelta (s) |
| `cliff_threshold_s` | float | Umbral de cliff usado en el análisis (s) |
| `degradation_rate_s_per_lap` | float | Tasa de degradación lineal (s/vuelta) |
| `n_laps_analyzed` | int | Número de vueltas usadas en el modelo |
| `top_wear_factors` | lista | Factores con mayor correlación con el delta, ordenados de mayor a menor |
| `lap_data` | lista | Delta observado y tendencia lineal para cada vuelta analizada |
| `projection` | lista | Delta proyectado para las 25 vueltas siguientes |
| `front_temp_trend_c_per_lap` | float o null | Pendiente de temperatura del eje delantero (°C/vuelta) |
| `rear_temp_trend_c_per_lap` | float o null | Pendiente de temperatura del eje trasero (°C/vuelta) |
| `left_mean_temp` | float o null | Temperatura media de sesión del lado izquierdo (°C) |
| `right_mean_temp` | float o null | Temperatura media de sesión del lado derecho (°C) |
| `tyre_temps_available` | bool | Indica si al menos un canal de temperatura fue resuelto |

En caso de error, el diccionario devuelve `{"available": false, "reason": "<descripción>"}` con las siguientes razones posibles: `"scikit-learn not installed"`, `"fewer than 3 flying laps"`, `"invalid lap times"`, `"insufficient data after extraction"`.

---

## Guía de Interpretación

### Estado de Desgaste (`wear_pct`)

| Rango | Estado | Acción recomendada |
|---|---|---|
| 0–25 % | Neumático fresco | Sin acción; establecer referencia de delta |
| 25–50 % | Desgaste moderado | Monitorear tendencia; válido para stints largos |
| 50–75 % | Desgaste avanzado | Considerar ventana de pit en las próximas vueltas |
| 75–90 % | Desgaste crítico | Planificar pit en la vuelta siguiente si las condiciones lo permiten |
| > 90 % | Cliff inminente | Pit inmediato o asumir penalización significativa en ritmo |

### Vueltas Restantes (`remaining_laps`)

El valor `remaining_laps` es una proyección lineal y debe interpretarse como una estimación de orden de magnitud, no como un conteo exacto. Los factores que aumentan la incertidumbre incluyen: tráfico, safety car, cambios de condiciones de pista, y conducción defensiva que altera el patrón de carga sobre el neumático.

Un valor `">40"` indica que la degradación observada es tan lenta que el modelo no detecta una amenaza de cliff en el horizonte de 40 vueltas. Esto puede ocurrir en circuitos de baja energía, con compuestos duros, o en stints cortos donde la muestra aún no refleja la tendencia real de degradación.

### Tasa de Degradación (`degradation_rate_s_per_lap`)

| Tasa (s/vuelta) | Interpretación |
|---|---|
| < 0.02 | Degradación casi nula; compuesto muy duro o circuito de baja energía |
| 0.02–0.06 | Degradación normal; estrategia de un stop factible |
| 0.06–0.12 | Degradación alta; estrategia de dos stops probable |
| > 0.12 | Degradación severa; neumático fuera de ventana o conducción agresiva |

Una tasa negativa (posible en las primeras vueltas de un stint mientras el neumático se calienta) es físicamente coherente y no indica un error del modelo. A medida que el stint avanza, la tasa converge a valores positivos crecientes.

### Factores de Desgaste Dominantes

La lista `top_wear_factors` permite identificar la causa raíz de la degradación:

- **`stress_{pos}` lidera la lista:** El neumático en esa posición opera frecuentemente fuera de su ventana térmica. Si `stress_rr` es dominante en un circuito con muchas curvas a derechas, la presión trasera derecha puede estar demasiado baja o el *camber* trasero derecho genera sobretemperatura en el interior.
- **`mean_lat_g` lidera la lista:** Las fuerzas laterales son el driver principal del desgaste. El compuesto puede estar al límite de su capacidad para el nivel de carga aerodinámica / mecánica del vehículo.
- **`lap_number` lidera la lista:** La degradación está correlacionada principalmente con el tiempo transcurrido. Sugiere un proceso de desgaste progresivo sin un mecanismo térmico o mecánico dominante; posiblemente abrasión acumulada.
- **`mean_brake_g` lidera la lista:** Los frenos o la gestión de entrada en curva son la fuente principal del desgaste. En neumáticos traseros, puede indicar sobreestimulación del eje trasero en frenada (diferencial o balance de frenado trasero).

### Asimetría de Temperatura

La diferencia `right_mean_temp − left_mean_temp` es una señal de desequilibrio de carga lateral:

- **Diferencia > 5 °C persistente:** Desequilibrio de setup. Revisar camber, presiones y reparto de rigidez antibalanceo entre lados.
- **Diferencia coherente con el perfil del circuito:** Normal. Circuitos con más curvas a derechas cargarán más el lado izquierdo.

Las tendencias `front_temp_trend_c_per_lap` y `rear_temp_trend_c_per_lap` muestran si alguno de los ejes acumula temperatura de forma creciente a lo largo del stint. Una pendiente trasera superior a 0,5 °C/vuelta con el eje delantero estable suele indicar que el diferencial o la salida de curva están transfiriendo más energía al eje trasero de lo esperado.

---

## Limitaciones

**1. Dependencia de la calidad de los datos de temperatura**

El modelo Ridge polinomial obtiene su mayor poder predictivo cuando dispone de los cuatro canales de temperatura del neumático. Si el sistema de adquisición de datos no registra temperatura de neumáticos (frecuente en telemetría de bajo coste o en algunos modos de exportación de iRacing), el modelo cae back al uso de fuerzas G y número de vuelta. En ese caso, `tyre_temps_available` será `false` y la calidad de la predicción disminuye considerablemente.

**2. Sesgo por fuera de sesión (out-of-distribution)**

El modelo se entrena y evalúa sobre la misma sesión. No generaliza a otras sesiones, otros compuestos, ni otras condiciones de pista. La proyección de las 40 vueltas asume que el comportamiento futuro seguirá la misma tendencia lineal que el stint actual; cualquier evento externo (safety car, lluvia, cambio de temperatura ambiental) invalida esa extrapolación.

**3. Mínimo de tres vueltas volantes**

El análisis requiere al menos tres vueltas válidas. En sesiones de clasificación cortas o tras penalizaciones que reducen las vueltas volantes por debajo de ese umbral, el módulo devuelve `available: False`. Esto es una limitación intencional: con dos o menos puntos, el ajuste lineal y el modelo de regresión no son estadísticamente significativos.

**4. Proyección lineal vs. degradación real no lineal**

La degradación real del neumático sigue una curva con tres fases bien diferenciadas: calentamiento inicial (pendiente negativa), zona de operación estable (pendiente suave) y cliff (pendiente brusca). El modelo lineal de proyección captura adecuadamente la fase de operación estable pero subestima la aceleración del cliff. Por este motivo, `remaining_laps` debe interpretarse como una estimación conservadora: el neumático puede alcanzar el cliff antes de lo proyectado si la degradación entra en la fase no lineal.

**5. Umbral de cliff fijo**

El umbral de 1,5 segundos (`_CLIFF_S`) es un valor heurístico adecuado para categorías de turismo o GT. Para monoplazas con tiempos de vuelta de 60–80 segundos y degradación más pronunciada, este umbral puede resultar permisivo. Para carreras de resistencia de largo stint, puede ser excesivamente conservador. El parámetro es editable directamente en el módulo.

**6. Ausencia de modelado de temperatura de pista**

El módulo no incorpora la temperatura ambiental ni la temperatura de pista como covariables. Estos factores afectan directamente la ventana óptima del neumático y la tasa de degradación. En circuitos donde la temperatura de pista varía más de 10 °C entre sesiones, el modelo entrenado en una sesión no es directamente comparable al de otra.

**7. Resolución de nombres de canal sensible al orden**

La resolución de sinónimos de canales itera la lista en orden de prioridad y selecciona el primer nombre coincidente. En el caso de formatos de exportación no convencionales o nombres personalizados por el datalogger, puede suceder que el canal resuelto no sea el más representativo (por ejemplo, temperatura interior vs. temperatura del núcleo). Verificar qué canal fue seleccionado mediante los logs del módulo (`tyre_degradation: wear=...`) cuando se sospeche de resultados anómalos.

---

## Referencias

1. Milliken, W. F., & Milliken, D. L. (1995). *Race Car Vehicle Dynamics*. SAE International. — Capítulos 17–18: Degradación del neumático; relación entre temperatura de núcleo y coeficiente de fricción; ventana óptima de temperatura.

2. Pacejka, H. B. (2012). *Tire and Vehicle Dynamics* (3rd ed.). Butterworth-Heinemann. — Modelo de Magic Formula; dependencia del coeficiente de deslizamiento con la temperatura y el desgaste acumulado.

3. Hoerl, A. E., & Kennard, R. W. (1970). Ridge Regression: Biased Estimation for Nonorthogonal Problems. *Technometrics*, 12(1), 55–67. — Formulación matemática de la regresión Ridge; control del sesgo-varianza en presencia de multicolinealidad.

4. Biscani, F., & Izzo, D. (2020). A parallel global multiobjective framework for optimization: pagmo. *Journal of Open Source Software*, 5(53), 2338. — Contexto de optimización de estrategia de neumáticos; uso de modelos de degradación como función de coste en problemas de optimización de parada en boxes.

5. Ferreira da Silva, A., & Velenis, E. (2016). Analysis and identification of tyre thermal behaviour for motorsport applications. *Vehicle System Dynamics*, 54(11), 1561–1578. — Modelado térmico de neumático de competición; definición formal de ventana óptima y cliff térmico; validación con datos de telemetría de GP2.
