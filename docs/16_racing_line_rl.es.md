# Optimización de Trazada mediante Q-Learning Tabular

**Módulo:** `src/analytics/racing_line_rl.py`  
**Función principal:** `optimizar_trazada_rl(dfs, df_laps, precomputed_obs=None)`  
**Dependencias:** NumPy (sin frameworks externos de RL)

---

## Descripción General

Este módulo implementa un sistema de aprendizaje por refuerzo offline para identificar el patrón de ejecución óptimo en cada curva de una sesión. A partir del historial de vueltas del piloto, un agente tabular aprende qué combinación de punto de frenada, velocidad en el vértice y punto de aplicación del acelerador produjo la menor pérdida de tiempo en comparación con la vuelta de referencia.

El diseño deliberadamente evita frameworks externos (Stable-Baselines, RLlib, Gymnasium) para mantener la portabilidad y la transparencia algorítmica. Todo el aprendizaje se realiza con matrices NumPy, lo que permite auditar directamente cada entrada de la tabla Q.

El resultado no es una trayectoria geométrica en el mapa, sino una **prescripción de ejecución por fases**: dónde frenar, qué velocidad sostener en el ápice y cuándo retomar el acelerador, expresada como desviación relativa al comportamiento medio del piloto en las últimas vueltas disponibles.

---

## Marco de Aprendizaje por Refuerzo

### Espacio de estados

Cada curva se representa mediante tres dimensiones, cada una discretizada en tres intervalos:

| Dimensión | Variable continua | Bordes de discretización | Etiquetas |
|---|---|---|---|
| Frenada | `brake_delta` (m) | −10, +10 | `early`, `similar`, `late` |
| Velocidad en ápice | `apex_delta` (km/h) | −3, +3 | `slow`, `similar`, `fast` |
| Aceleración de salida | `thtl_delta` (m) | −8, +8 | `late`, `similar`, `early` |

Las variables continuas expresan diferencias respecto a la vuelta de referencia (la más rápida de la sesión). Un valor positivo en `brake_delta` indica que el piloto frenó más tarde que la referencia; un valor negativo en `apex_delta` indica que pasó el vértice más lento.

La combinación de tres dimensiones con tres intervalos cada una genera un espacio de estados de **27 celdas** (3³), gestionado como un arreglo NumPy de forma `(3, 3, 3)`.

### Acción implícita y recompensa

El modelo no distingue estados de acciones de forma separada: cada observación de vuelta es simultáneamente un estado y su resultado. La función de recompensa es:

```
R = −time_loss_s
```

donde `time_loss_s` es la pérdida de tiempo acumulada en la curva respecto a la referencia, calculada por `_estimate_corner_time_loss`. Al negar la pérdida, valores de recompensa más altos corresponden a ejecuciones más eficientes.

### Hiperparámetros

| Parámetro | Valor | Justificación |
|---|---|---|
| Tasa de aprendizaje (`α`) | 0.4 | Convergencia moderadamente rápida con pocos datos |
| Factor de descuento (`γ`) | 0.0 | Cada curva es independiente; no existe horizonte temporal entre curvas |
| Épocas de entrenamiento | 30 | Suficiente para estabilizar una tabla de 27 celdas con 3–15 observaciones típicas |

La elección de `γ = 0` es arquitectónicamente significativa: el problema se trata como una serie de bandidos estocásticos independientes (one-step MDP), uno por curva. No se modela transición entre estados dentro de una curva ni dependencia entre curvas consecutivas.

### Regla de actualización

La actualización de cada celda sigue la forma incremental de la ecuación de Bellman simplificada (sin término de valor futuro):

```
Q(s) ← Q(s) + α · (R − Q(s))
```

Cuando una celda se visita por primera vez, se inicializa directamente con el valor de recompensa observado. Las visitas posteriores promedian exponencialmente hacia el valor esperado. Las celdas no visitadas permanecen como `NaN` y quedan excluidas de la selección del óptimo.

---

## Procedimiento de Entrenamiento

### Extracción de observaciones

Si no se proporcionan observaciones precalculadas, el módulo las genera mediante `_get_per_lap_observations`:

1. Se filtra el conjunto de vueltas para conservar únicamente las **vueltas volantes** (sin entrada a pits y con tiempo de vuelta registrado).
2. Se designa como referencia la vuelta con menor `lap_time_s`.
3. Para cada vuelta restante se ejecuta `align_pair` (alineación temporal/espacial) y `segment_corners` (segmentación de curvas).
4. Por cada curva emparejada se calcula `time_loss_s`, `brake_delta`, `apex_delta` y `thtl_delta`.

El resultado es un diccionario indexado por número de curva, donde cada entrada contiene la lista de observaciones de todas las vueltas válidas.

### Ciclo de entrenamiento por curva

Para cada curva con al menos dos observaciones disponibles:

1. Se instancia un `_CornerAgent` con tabla Q inicializada a `NaN`.
2. Se itera el conjunto completo de observaciones durante 30 épocas, actualizando la tabla Q en cada paso.
3. Al término del entrenamiento se identifica la **celda óptima** como aquella con el valor Q máximo entre las visitadas.
4. El **perfil actual del piloto** se determina como el bin promedio de las últimas tres vueltas (o todas si hay menos de tres), redondeado al entero más próximo y limitado al rango [0, 2].

### Cálculo del potencial de mejora

La ganancia potencial por curva se estima como:

```
potential_gain_s = max(0, Q_optimo − Q_actual)
```

Si la celda correspondiente al perfil actual no ha sido visitada (valor `NaN`), se sustituye `Q_actual` por la media de todas las recompensas observadas en esa curva. La ganancia total de la sesión es la suma de las ganancias individuales por curva.

---

## Esquema de Salida

La función `optimizar_trazada_rl` retorna un diccionario con la siguiente estructura:

```json
{
  "available": true,
  "n_corners": 12,
  "total_potential_gain_s": 0.847,
  "corners": [
    {
      "corner_number": 7,
      "n_laps": 14,
      "mean_time_loss_s": 0.142,
      "potential_gain_s": 0.098,
      "current_execution": {
        "brake": "late",
        "apex": "slow",
        "exit": "late"
      },
      "optimal_execution": {
        "brake": "similar",
        "apex": "similar",
        "exit": "early"
      },
      "already_optimal": false,
      "recommendations": [
        "Brake earlier",
        "Carry more apex speed",
        "Apply throttle earlier"
      ],
      "q_heatmap": [ ... ]
    }
  ]
}
```

El array `corners` se ordena de mayor a menor `potential_gain_s`, de modo que las curvas con mayor margen de mejora aparecen primero.

### Campo `q_heatmap`

Contiene 9 entradas (3 niveles de frenada × 3 niveles de velocidad en ápice), con la dimensión de aceleración colapsada mediante el máximo. Cada entrada expone:

- `brake`: etiqueta del bin de frenada
- `apex`: etiqueta del bin de velocidad en ápice
- `q`: valor Q máximo observado en esa celda (o `null` si no fue visitada)
- `count`: número total de observaciones que cayeron en esa celda

Este heatmap permite al frontend representar visualmente la densidad de exploración del espacio de estados y la calidad relativa de cada combinación.

Cuando no es posible producir resultados (menos de dos vueltas comparables o todas las curvas con observaciones insuficientes), el campo `available` vale `false` y se incluye un campo `reason` con la causa.

---

## Guía de Interpretación

### Lectura del perfil de ejecución

Cada dimensión del estado representa una desviación relativa a la vuelta de referencia, no una medida absoluta:

- **`brake: "late"`** — el piloto frenó en promedio más de 10 m después que en la referencia. No implica que la referencia sea óptima; implica que el piloto es inconsistente con ella.
- **`apex: "slow"`** — la velocidad en el vértice fue más de 3 km/h inferior a la referencia. Puede indicar una trazada más conservadora o una frenada excesiva.
- **`exit: "similar"`** — el punto de aceleración completa difiere menos de 8 m respecto a la referencia. La ejecución de salida es consistente.

### Interpretación del `potential_gain_s`

Este valor **no es una garantía de mejora**; es el diferencial entre la media Q del perfil actual y el máximo Q observado en el historial de la sesión. Si el historial contiene pocas vueltas (< 5), la estimación tiene alta varianza y debe interpretarse como una indicación cualitativa, no cuantitativa.

Un valor de `0.000` con `already_optimal: true` significa que el perfil promedio del piloto ya coincide con la celda de mayor valor Q en la tabla, no necesariamente que no exista margen absoluto de mejora.

### Priorización de curvas

El orden descendente por `potential_gain_s` sugiere dónde concentrar el trabajo de análisis. Sin embargo, curvas con bajo potencial calculado pero alto `mean_time_loss_s` merecen atención: indican que el piloto pierde tiempo consistentemente pero la diferenciación entre bins es pequeña, lo que puede reflejar limitaciones del vehículo más que de la técnica.

---

## Limitaciones

**Granularidad del espacio de estados.** La discretización en tres bins por dimensión implica que diferencias de ejecución inferiores a los umbrales definidos (10 m en frenada, 3 km/h en ápice, 8 m en aceleración) no se distinguen. Dos vueltas muy diferentes dentro de un mismo bin reciben el mismo tratamiento.

**Dependencia de la vuelta de referencia.** Todas las variables continuas son deltas respecto a la vuelta más rápida de la sesión. Si esa vuelta es atípica (tráfico favorable, condiciones de pista inusuales), los deltas quedan sesgados y el estado aprendido puede no generalizarse.

**Ausencia de transiciones entre curvas.** El factor de descuento `γ = 0` modela cada curva como un problema independiente. En la realidad, la ejecución de una curva afecta la velocidad de entrada a la siguiente, especialmente en chicanas y sectores de alta velocidad encadenados. Este efecto queda fuera del modelo.

**Volumen de datos.** Con menos de cinco vueltas por curva, la tabla Q queda mayoritariamente sin visitar y los valores estimados tienen alta varianza. El módulo requiere un mínimo de dos observaciones para procesar una curva, pero la fiabilidad estadística se alcanza aproximadamente a partir de cinco.

**Estacionariedad del comportamiento.** El modelo promedia el perfil del piloto sobre las últimas tres vueltas y el óptimo sobre toda la sesión. Si las condiciones de pista evolucionaron durante la sesión (goma en pista, cambio de temperatura, lluvia), las observaciones tempranas y tardías no son comparables y la tabla Q mezcla condiciones heterogéneas.

**Ausencia de exploración activa.** Al tratarse de aprendizaje offline, el agente no puede explorar estados no visitados. Si el piloto nunca ejecutó una combinación determinada (por ejemplo, frenar tarde con velocidad alta en ápice), esa celda permanece `NaN` aunque pudiera ser superior a las observadas.
