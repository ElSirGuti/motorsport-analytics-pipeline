# 16 - Optimización de Trazada (Q-Learning Tabular)

[See in English](./16_racing_line_rl.md)

**Módulo:** `src/analytics/racing_line_rl.py`
**Función principal:** `optimizar_trazada_rl(dfs, df_laps, precomputed_obs=None)`
**Fuente de observaciones:** `get_corner_observations` en `src/analytics/session_corner_analysis.py`
**Dependencias:** solo NumPy (sin framework de RL)
**Reconciliado con el código:** 2026-10-03 (las versiones EN y ES comparten la misma estructura)

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Método](#2-método)
3. [Procedimiento de Entrenamiento](#3-procedimiento-de-entrenamiento)
4. [Esquema de Salida](#4-esquema-de-salida)
5. [Guía de Interpretación](#5-guía-de-interpretación)
6. [Limitaciones](#6-limitaciones)
7. [Referencia de Constantes](#7-referencia-de-constantes)
8. [Estado de Verificación](#8-estado-de-verificación)

---

## 1. Descripción General

Para cada curva detectada en una sesión, el módulo observa cómo ejecutó cada vuelta tres fases de la curva (punto de frenada, velocidad en el vértice, aplicación del acelerador) respecto a la vuelta más rápida de la sesión, y busca qué combinación discretizada de esas tres fases se asoció con la menor pérdida de tiempo. Después compara esa combinación con la ejecución reciente del piloto e informa la ganancia de tiempo estimada y una recomendación en lenguaje llano.

Caracterización honesta: el "agente" es una tabla de 27 celdas por curva que guarda una media móvil exponencial de las recompensas observadas. Como el factor de descuento es 0 y la "acción" es la propia ejecución observada, no hay un problema de decisión secuencial: es una media corrida empírica por estado, dependiente del orden, seguida de un argmax (un resumen al estilo bandido contextual). Llamarlo "aprendizaje por refuerzo" es una convención de modelado, no evidencia de que se descubra una política óptima. La salida debe leerse como "en qué patrón de ejecución fue más rápido este piloto en esta curva, en esta sesión", no como un óptimo físico.

---

## 2. Método

### 2.1 Espacio de estados

Tres deltas respecto a la vuelta de referencia se discretizan con `numpy.digitize` en tres intervalos cada uno (3 x 3 x 3 = 27 celdas por curva):

| Dimensión | Señal | Bordes | Etiquetas de los intervalos 0 / 1 / 2 |
|---|---|---|---|
| Punto de frenada | `brake_delta` (m) | -10, +10 | `early`, `similar`, `late` |
| Velocidad en vértice | `apex_delta` (km/h) | -3, +3 | `slow`, `similar`, `fast` |
| Aplicación del acelerador | `thtl_delta` (m) | -8, +8 | `late`, `similar`, `early` |

Semántica de `digitize`: valor < borde inferior da el intervalo 0; inferior <= valor < superior da el 1; valor >= superior da el 2.

Definición de los deltas (de `get_corner_observations`, vuelta menos referencia):

- `brake_delta` = distancia del punto de frenada de la vuelta menos la de la referencia (positivo = frenó más tarde en la vuelta).
- `apex_delta` = velocidad en el vértice de la vuelta menos la de la referencia (positivo = más rápido).
- `thtl_delta` = distancia de full throttle de la vuelta menos la de la referencia (positivo = alcanzó el full throttle más tarde).

Eje del acelerador (corregido el 2026-10-03): `detect_full_throttle_points` devuelve la distancia a la que se alcanza por primera vez el full throttle tras una curva, así que `thtl_delta` es (distancia de la vuelta) menos (distancia de la referencia) y un valor positivo significa que se alcanzó el full throttle MÁS TARDE. El intervalo 2 (delta positivo) se etiqueta ahora `late` y el 0 `early`; si el intervalo óptimo es mayor que el actual se emite `rl_throttle_later`, si es menor `rl_throttle_earlier`. Antes las etiquetas y ambas recomendaciones estaban invertidas.

### 2.2 Recompensa y regla de actualización

```
reward = -time_loss_s          (time_loss_s > 0: vuelta más lenta que la referencia en esta curva)
Q[s] <- reward                         en la primera visita de la celda s
Q[s] <- Q[s] + 0.4 * (reward - Q[s])   en visitas posteriores
```

Con `gamma = 0` el objetivo es solo la recompensa inmediata; no existe estado sucesor. Las celdas no visitadas quedan en `NaN` y nunca se eligen como óptimas.

`time_loss_s` proviene de `_estimate_corner_time_loss` (en `src/telemetry/lap_comparator.py`): entre el más temprano de los dos puntos de frenada y el más tardío de los dos puntos de full throttle, integra `ds * (1/v_vuelta - 1/v_ref)` sobre las velocidades alineadas por distancia (velocidad mínima 1 m/s). Puede ser negativo si la vuelta fue más rápida que la referencia en esa curva.

### 2.3 Extracción de la política

```
opt = argmax sobre las celdas visitadas de Q[brake_bin, apex_bin, thtl_bin]
```

No hay un número mínimo de visitas: una celda visitada por una sola vuelta puede ganar.

---

## 3. Procedimiento de Entrenamiento

1. **Vuelta de referencia.** Entre las vueltas válidas (no `is_pit_lap`, con `lap_time_s`), la de menor tiempo. Se requieren al menos 2 vueltas válidas; si no, no hay observaciones.
2. **Extracción de observaciones** (se omite si se pasa `precomputed_obs`, lo que hace `main.py` reutilizando las observaciones ya calculadas para el análisis de curvas). Para cada otra vuelta válida: solo se conservan los canales `Distance`, `Speed`, `Brake`, `Throttle`; la vuelta y la referencia se alinean por distancia (`align_pair`); se detectan las curvas de cada una (`segment_corners`); las curvas de la vuelta se emparejan con las de la referencia **por proximidad del vértice** (`pair_corners`, separación máxima 150 m), no por índice. El número de curva es el índice (base 1) de la curva en la vuelta de referencia. Las vueltas que lanzan una excepción se omiten.
3. **Entrenamiento por curva.** Se omiten las curvas con menos de 2 observaciones. Un agente nuevo ejecuta 30 épocas sobre las observaciones de la curva en orden de vuelta, aplicando la regla de 2.2. Como el orden de reproducción es fijo, el valor de cada celda es un promedio ponderado por recencia de sus observaciones (la más reciente de la celda pesa más).
4. **Perfil de ejecución actual.** Últimas 3 observaciones (o todas si hay menos): se promedia el índice de intervalo de cada eje, se redondea con `round` de Python y se limita a [0, 2]. Es una media redondeada de índices de intervalo, no una moda, y puede caer en una celda que ninguna vuelta visitó realmente.
5. **Ganancia potencial.**

```
current_q      = Q[celda actual]; si esa celda es NaN: media de (-time_loss) sobre todas las observaciones de la curva
potential_gain = max(0, Q[opt] - current_q)
total          = suma de potential_gain sobre las curvas
```

6. **Recomendaciones**: por cada eje donde el intervalo óptimo difiere del actual, un mensaje localizado (`rl_brake_later/earlier`, `rl_apex_faster/slower`, `rl_throttle_earlier/later`); si ninguno difiere, `rl_already_optimal`.

---

## 4. Esquema de Salida

Cuando los datos son insuficientes la respuesta es `{"available": false, "reason": "..."}` con una de dos cadenas en inglés, no localizadas: `no corner observations extracted` (menos de 2 vueltas válidas o ninguna curva emparejada) o `all corners had <2 observations`. Una curva con menos de 2 observaciones se omite en silencio; `available` es falso solo cuando se omiten todas.

```json
{
  "available": true,
  "n_corners": 8,
  "total_potential_gain_s": 0.412,
  "corners": [
    {
      "corner_number": 5,
      "n_laps": 18,
      "mean_time_loss_s": 0.087,
      "potential_gain_s": 0.063,
      "current_execution": {"brake": "late", "apex": "slow", "exit": "late"},
      "optimal_execution": {"brake": "similar", "apex": "similar", "exit": "early"},
      "already_optimal": false,
      "recommendations": ["Frena antes", "Lleva más velocidad en el ápice", "Aplica el acelerador antes"],
      "q_heatmap": [{"brake": "early", "apex": "slow", "q": -0.041, "count": 90}]
    }
  ]
}
```

Nivel superior: `available`, `n_corners` (curvas con al menos 2 observaciones), `total_potential_gain_s` (suma de ganancias por curva, redondeada a 3 decimales), `corners` (ordenadas por `potential_gain_s` descendente).

Por curva: `corner_number`, `n_laps` (observaciones; como máximo el número de vueltas válidas menos 1, porque la referencia no se compara consigo misma), `mean_time_loss_s`, `potential_gain_s`, `current_execution`, `optimal_execution` (etiquetas por `brake` / `apex` / `exit`), `already_optimal`, `recommendations`, `q_heatmap`.

`q_heatmap` tiene 9 celdas (frenada x vértice); `q` es la mejor Q entre los tres intervalos de acelerador (o `null` si no se visitó) y `count` es el número de observaciones reales (vueltas) de esas celdas. Corregido el 2026-10-03: antes el contador se incrementaba también en cada una de las 30 épocas de entrenamiento, por lo que `count` era 30 x el número de observaciones.

---

## 5. Guía de Interpretación

- **`potential_gain_s`** es la cifra accionable: el tiempo estimado recuperable en esa curva al pasar al mejor patrón aprendido. Las curvas se ordenan por él.
- **`current_execution` frente a `optimal_execution`** muestra la dirección del cambio. Recuerda que el perfil actual es una media redondeada de intervalos.
- **`mean_time_loss_s`** da contexto: una ganancia grande con una pérdida media pequeña suele indicar pocas vueltas atípicas; una pérdida media grande con ganancia grande es una debilidad consistente.
- **`q_heatmap`**: los valores son pérdida de tiempo negativa en segundos; más cerca de cero es mejor; `null` significa sin evidencia.
- **`total_potential_gain_s`** es una cota superior optimista: suma curvas independientes (sin interacción), y el argmax sobre 27 celdas ruidosas está sesgado al alza (gana una celda que tuvo suerte una vez).

---

## 6. Limitaciones

- **Datos escasos.** 27 celdas por curva frente a típicamente 5-30 vueltas: la mayoría de celdas están vacías y los ganadores pueden apoyarse en una sola vuelta. El `count` del heatmap es el número real de observaciones, así que un `count` de 1 significa exactamente una vuelta.
- **El emparejamiento de curvas por proximidad del vértice** (150 m) aún puede fallar si una curva no se detecta en algunas vueltas; no hay compensación por cambios de límites de pista, clima o pianos durante la sesión.
- **Independencia entre curvas** (`gamma = 0`): ignora el acoplamiento salida-entrada de chicanes y secciones en S.
- **Dependencia de la referencia.** Todos los deltas son relativos a la única vuelta más rápida de la sesión; las anomalías de esa vuelta sesgan todo. No hay normalización entre sesiones.
- **Intervalos gruesos** (3 por eje), elegidos para que la tabla se pueda llenar con una sola sesión.
- **Sin inferencia causal.** No se controlan la carga de combustible, el estado de los neumáticos ni la temperatura.
- **Offline.** Nada se actualiza dentro de un stint salvo que se vuelva a llamar a la función con datos nuevos.
- **Eje del acelerador:** `early`/`late` siguen ahora el signo de `thtl_delta` (negativo = antes, positivo = después), ver 2.1.

---

## 7. Referencia de Constantes

| Constante | Valor |
|---|---|
| `_BRAKE_BINS` | [-10, 10] m |
| `_APEX_BINS` | [-3, 3] km/h |
| `_THTL_BINS` | [-8, 8] m |
| `_LR` (alfa) | 0,4 |
| `_GAMMA` | 0,0 (declarado; no se usa en la actualización) |
| `_EPOCHS` | 30 |
| Observaciones mínimas por curva | 2 |
| Vueltas recientes para el perfil actual | 3 |
| `PAIR_MAX_APEX_GAP_M` (en `src/telemetry/metrics.py`) | 150 m |

---

## 8. Estado de Verificación

Fórmulas, constantes, claves y el comportamiento de `count` se comprobaron contra el código el 2026-10-03. La inflación de `count` (30 por observación) y las etiquetas/recomendaciones invertidas del eje del acelerador se reprodujeron con pruebas sintéticas y se corrigieron ese mismo día (`tests/test_advisor_rl_fixes.py`); con los registros reales de Imola/Spa el consejo de acelerador cambió de sentido. No verificable desde el código: la utilidad de las recomendaciones como consejo de pilotaje (no existe en el repositorio validación contra mejoras reales de tiempo por vuelta).
