# 14 - Análisis de Gestión Térmica

[See in English](./14_thermal_management.md)

**Módulo:** `src/analytics/thermal_management.py`
**Funciones principales:** `analizar_termica(dfs, df_laps)`, `analizar_termica_comparativa(df_a, df_b, label_a, label_b)`
**Reconciliado con el código:** 2026-10-03 (las versiones EN y ES comparten la misma estructura)

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Algoritmo](#2-algoritmo)
3. [Canales de Entrada](#3-canales-de-entrada)
4. [Esquema de Salida](#4-esquema-de-salida)
5. [Guía de Interpretación](#5-guía-de-interpretación)
6. [Limitaciones](#6-limitaciones)
7. [Referencia de Constantes](#7-referencia-de-constantes)
8. [Estado de Verificación](#8-estado-de-verificación)

---

## 1. Descripción General

El módulo ofrece un análisis independiente del simulador de cinco señales térmicas relevantes para el tiempo por vuelta y la fiabilidad: temperatura del refrigerante (agua), temperatura del aceite, temperatura de frenos por esquina, presión de neumáticos (en caliente y delta caliente-frío) y reparto de frenada. `analizar_termica` recibe un DataFrame de telemetría por vuelta (`dfs`), calcula cada sub-análisis de forma independiente y devuelve un único diccionario con los resultados por sub-análisis, recomendaciones y alertas. `df_laps` se acepta por simetría de la API pero no se usa.

Cada sub-análisis es opcional: cuando faltan sus canales devuelve `{"available": false, "reason": ...}` y los demás continúan. Si ninguno está disponible, el resultado global es `{"available": false}`.

Todos los umbrales del módulo son heurísticas fijas (ver sección 7). No se derivan de la telemetría ni se ajustan por coche, compuesto o temperatura ambiente, y no provienen de una norma publicada; trátalos como reglas empíricas de ingeniería.

`main.py` llama al módulo para la sesión completa (`analizar_termica(dfs, df_laps)`), para la vista de una vuelta (`analizar_termica(laps, pd.DataFrame())`) y, mediante `analizar_termica_comparativa`, para la comparación de vueltas.

La numeración de vueltas en las salidas (`"lap": 1, 2, ...`) es la **posición** del DataFrame en `dfs` más uno, no el número de vuelta del simulador.

---

## 2. Algoritmo

### 2.1 Temperaturas de fluidos (`_analyse_fluid`)

Una rutina genérica sirve para agua (`"Water"`) y aceite (`"Oil"`). Para cada vuelta resuelve el primer nombre de canal coincidente de la lista de candidatos y toma la media de la vuelta; las vueltas sin el canal se omiten.

- `mean_c`: media de las medias por vuelta; `max_c`: **máximo de las medias por vuelta** (no el pico instantáneo).
- `trend_c_per_lap`: pendiente de un ajuste de primer grado de las medias por vuelta frente a la posición de vuelta, solo con al menos 3 vueltas (si no, `null`).
- Estado según `max_c`: `critical` si `>= crit`, `warning` si `>= warn`, si no `normal`.

| Fluido | `warning` desde | `critical` desde |
|---|---|---|
| Agua | 105 degC | 115 degC |
| Aceite | 130 degC | 140 degC |

`warning` y `critical` añaden además una cadena `alert` localizada. El estado usa medias por vuelta, por lo que un pico instantáneo breve dentro de una vuelta no lo dispara.

### 2.2 Temperaturas de frenos (`_analyse_brake_temps`)

Para cada esquina (FL, FR, RL, RR) y vuelta se guardan la media, el máximo y el mínimo del canal. Dos protecciones preceden a la clasificación:

- Ningún canal de temperatura de frenos: `available: false` (`thermal_brake_no_channel`).
- **Protección de canal constante:** si la dispersión de todas las esquinas y vueltas (mayor máximo menos menor mínimo) es inferior a 1 degC, el canal se trata como un valor de relleno que el simulador no completó (por ejemplo fijo en la temperatura ambiente) y el sub-análisis devuelve `available: false` (`thermal_brake_constant`). En caso contrario todos los frenos se marcarían como demasiado fríos.

Se clasifica la media sobre las vueltas de cada esquina:

| Media de la esquina | Estado |
|---|---|
| < 200 degC | `too_cold` |
| 200 a < 300 degC | `suboptimal` |
| 300 a 700 degC (inclusive) | `optimal` |
| > 700 a 800 degC (inclusive) | `hot` |
| > 800 degC | `critical` |

**Balance térmico:** media de las esquinas delanteras y media de las traseras (las que existan) y `ratio_f_r = delantero / trasero` (`null` si la media trasera no es positiva). El balance se calcula solo si ambos ejes tienen datos.

**Recomendaciones de ductos** (las prioridades son las cadenas en español `media` / `alta`, no localizadas):

- `too_cold` da `close` (prioridad `media`).
- `hot` da `open` (`media`); `critical` da `open` (`alta`).
- `suboptimal` y `optimal` no producen recomendación.

La salida incluye también `optimal_range_c: [300, 700]`.

### 2.3 Presiones de neumáticos (`_analyse_tyre_pressure`)

**Detección de unidades (`_to_bar`)**, por canal, a partir del valor máximo observado:

```
max > 100  -> kPa, multiplicar por 0.01
max > 10   -> PSI, multiplicar por 1/14.5038
si no      -> ya está en bar
```

Todos los valores internos y de salida están en bar, y cada salida incluye también `psi` (objetos `{bar, psi}`, bar redondeado a 2 decimales, PSI a 1). La heurística clasifica mal una serie de presión con valores por debajo de 10 PSI o una serie en bar por encima de 10.

**Presión en caliente** por vuelta: media del canal de presión en vivo (y su máximo, `hot_max_bar`).

**La presión en frío** proviene solo de un canal dedicado de presión en frío (`LFcoldPressure`, etc.). No se estima a partir del inicio de la vuelta: en un stint continuo el inicio de la vuelta ya está caliente, y usarlo daba un delta cercano a 0 y consejos falsos de "subir presión" (ese proxy se eliminó). Sin canal en frío, `cold` y `delta` no aparecen, el `status` de la esquina es `ok`, una `note` explica el motivo y no se hace recomendación de presión para esa esquina.

**Delta** = media en caliente menos media en frío por vuelta; el delta de la esquina es la media sobre las vueltas.

| Delta medio | `status` |
|---|---|
| < 0,05 bar | `low_delta` (poco aumento: la presión en frío puede ser demasiado alta) |
| 0,05 a 0,28 bar | `ok` |
| > 0,28 bar | `high_delta` (mucho aumento: la presión en frío puede ser demasiado baja) |

**Recomendación** (solo con frío y delta disponibles):

```
target_cold  = max(0.8, cold - (delta - 0.15))
delta_adjust = target_cold - cold
se emite si |delta_adjust| >= 0.03 bar
direction    = "lower" si delta_adjust < 0, si no "raise"
priority     = "media" si |delta_adjust| > 0.1, si no "baja"
```

La recomendación se emite siempre que el ajuste alcance 0,03 bar, incluso si `status` es `ok` (el objetivo es el punto medio de 0,15 bar, no la ventana).

### 2.4 Reparto de frenada (`_analyse_brake_bias`)

`_to_pct_bias` convierte una fracción a porcentaje cuando el máximo es <= 1,05 (`dcBrakeBias` de iRacing); en otro caso la deja igual. Se informan las medias por vuelta y su promedio (`current_pct`).

1. **Evidencia térmica** (requiere temperaturas de frenos disponibles con balance, ratio no nulo y ambas medias de eje por encima de 50 degC): ratio **> 1,30** da `reduce` con `suggested = max(52, current - 2)`; ratio **< 0,75** da `increase` con `suggested = min(63, current + 2)`. Prioridad `media`.
2. **Comprobación de rango:** texto `out_of_range` si `current_pct < 52` o `> 63` (orientativo).

---

## 3. Canales de Entrada

Cada búsqueda resuelve el primer nombre coincidente que exista en el DataFrame.

| Señal | Nombres de canal aceptados | Unidad esperada |
|---|---|---|
| Agua | `WaterTemp`, `Water Temp`, `Engine Temp`, `CoolantTemp`, `Coolant Temp`, `Eng Coolant Temp` | degC |
| Aceite | `OilTemp`, `Oil Temp`, `Eng Oil Temp`, `Engine Oil Temp`, `EngOilTemp` | degC |
| Temp. de frenos | `BrakeTemp{FL,FR,RL,RR}`, `Brake Temp {FL..}`, `BrakeTemp{FrontLeft,...}` | degC |
| Presión en caliente | `TyrePress{FL..}`, `Tire Pressure {FL..}`, `Tyre Pres {FL..}`, iRacing `LFpressure`, `RFpressure`, `LRpressure`, `RRpressure` | kPa / PSI / bar (auto) |
| Presión en frío | `LFcoldPressure`, `RFcoldPressure`, `LRcoldPressure`, `RRcoldPressure`, `TyrePressCold{FL..}` | kPa / PSI / bar (auto) |
| Reparto de frenada | `BrakeBias`, `dcBrakeBias`, `Brake Bias`, `brake_bias` | fracción (0-1) o % |

Notas por simulador (comportamiento típico, no impuesto por el código): iRacing expone temperatura de agua/aceite, presiones en kPa y `dcBrakeBias` como fracción; Assetto Corsa expone temperaturas de frenos y presiones en PSI. Que cada simulador o herramienta de exportación proporcione un canal concreto depende del coche y del exportador; el módulo solo informa de lo que hay.

---

## 4. Esquema de Salida

```json
{
  "available": true,
  "n_recommendations": 3,
  "water_temp": {
    "available": true, "channel": "Water",
    "per_lap": [{"lap": 1, "mean_c": 92.4}],
    "mean_c": 93.2, "max_c": 94.1, "trend_c_per_lap": 0.85, "status": "normal",
    "warn_threshold_c": 105, "crit_threshold_c": 115
  },
  "oil_temp": {"...": "misma estructura que water_temp"},
  "brake_temps": {
    "available": true, "optimal_range_c": [300, 700],
    "corners": {"FL": {"mean_c": 312.5, "max_c": 489.0, "status": "optimal",
                        "per_lap": [{"lap": 1, "mean_c": 305.2, "max_c": 471.0, "min_c": 120.0}]}},
    "balance": {"front_mean_c": 315.0, "rear_mean_c": 280.0, "ratio_f_r": 1.13},
    "duct_recs": [{"corner": "RL", "action": "close", "reason": "...", "priority": "media"}]
  },
  "tyre_pressure": {
    "available": true,
    "delta_target": {"bar": 0.15, "psi": 2.2},
    "delta_window": {"low": {"bar": 0.05, "psi": 0.7}, "high": {"bar": 0.28, "psi": 4.1}},
    "corners": {"FL": {"hot": {"bar": 1.87, "psi": 27.1}, "cold": {"bar": 1.65, "psi": 23.9},
                        "delta": {"bar": 0.22, "psi": 3.2}, "status": "ok",
                        "per_lap": [{"lap": 1, "hot_bar": 1.871, "hot_max_bar": 1.903,
                                     "cold_bar": 1.65, "delta_bar": 0.221}]}},
    "recommendations": [{"corner": "RR", "direction": "raise", "delta_bar": 0.09, "delta_psi": 1.3,
                         "current_cold": {"bar": 1.60, "psi": 23.2},
                         "target_cold": {"bar": 1.69, "psi": 24.5},
                         "current_hot": {"bar": 1.94, "psi": 28.1},
                         "reason": "...", "priority": "baja"}]
  },
  "brake_bias": {
    "available": true, "current_pct": 57.3,
    "per_lap": [{"lap": 1, "bias_pct": 57.1}],
    "typical_range": [52.0, 63.0], "out_of_range": null, "recommendation": null
  }
}
```

Notas:

- Sin canal en frío, la entrada de una esquina tiene `hot`, `per_lap` (con `cold_bar`/`delta_bar` nulos), `status: "ok"` y `note`; no tiene las claves `cold` ni `delta`.
- `n_recommendations` = recomendaciones de ductos + recomendaciones de presión + (1 si hay recomendación de reparto) + (1 si hay alerta de agua) + (1 si hay alerta de aceite). El texto `out_of_range` del reparto no cuenta.
- El `alert` de fluidos solo existe para `warning`/`critical`. Los textos (`reason`, `alert`, `out_of_range`) se localizan (ES/EN) mediante `src/i18n.py` (claves `thermal_*`); los valores de `priority` son cadenas fijas en español.
- `analizar_termica_comparativa` ejecuta el mismo análisis sobre dos vueltas y añade `label_a` y `label_b`; no calcula ningún diferencial entre las vueltas.

---

## 5. Guía de Interpretación

- **Fluidos:** `normal` con una tendencia pequeña es el objetivo. `warning` con una tendencia claramente positiva en un stint largo es el patrón a vigilar, ya que el pico puede derivar a `critical`. La tendencia es una pendiente de medias por vuelta, por lo que es ruidosa con pocas vueltas; 3 vueltas es solo el mínimo para que exista. Afirmaciones como "0,5 degC/vuelta es preocupante" son reglas empíricas, no umbrales codificados.
- **Frenos:** revisa las cuatro esquinas y compara delantero y trasero con `ratio_f_r`. El código solo actúa con ratios por encima de 1,30 o por debajo de 0,75; un ratio equilibrado cercano a 1 es el ideal intuitivo (una interpretación, no un umbral codificado). Usa `per_lap` para distinguir una vuelta transitoria de frenada fuerte de un patrón consistente.
- **Presiones de neumáticos:** el `delta` es la cifra a leer, y solo existe con canal en frío. El objetivo de 0,15 bar y la ventana de 0,05-0,28 bar son aproximaciones genéricas; los objetivos varían según compuesto y fabricante, así que usa la recomendación como estimación de dirección y magnitud a contrastar con la guía del proveedor de neumáticos.
- **Reparto de frenada:** la `recommendation` aparece solo con evidencia térmica fuerte; `out_of_range` es un aviso suave frente a una ventana de 52-63 % que supone coches tipo GT.
- **Patrones comunes (basados en experiencia, no verificados por el código):** frenos traseros fríos en coches sin ductos traseros, un `warning` transitorio de aceite en la vuelta 2 de una tanda corta, y `high_delta` en todas las esquinas tras un cambio de neumáticos sin mantas térmicas.

---

## 6. Limitaciones

- **Análisis por lotes posterior a la sesión.** Sin streaming ni alertas en vivo.
- **La presión en frío necesita un canal dedicado.** Sin él se omite el consejo basado en el delta (por diseño, tras eliminar el poco fiable proxy del inicio de vuelta).
- **El pico de fluidos es una media por vuelta.** Un pico breve dentro de una vuelta se promedia.
- **Sin conocimiento de compuesto, ambiente ni circuito.** Todos los umbrales son fijos y no provienen de una norma.
- **La autodetección de unidades por el máximo** puede fallar en los límites (ver 2.3).
- **Promedios de vuelta completa.** Sin sectorización: una zona de frenada fuerte puede ocultar el resto de la vuelta.
- **La disponibilidad del canal de frenos depende del simulador/exportación.** Si un simulador no exporta temperaturas de frenos, o exporta un valor constante de relleno, `brake_temps` no está disponible y la recomendación de reparto se reduce a la comprobación de rango.
- **Los índices de vuelta son posicionales**, no números de vuelta del simulador.
- **Las prioridades son cadenas fijas en español**, no localizadas.

---

## 7. Referencia de Constantes

| Constante | Valor |
|---|---|
| Frenos: frío / óptimo bajo / óptimo alto / límite caliente | 200 / 300 / 700 / 800 degC |
| Dispersión de canal de frenos constante | < 1 degC |
| Agua warn / crit | 105 / 115 degC |
| Aceite warn / crit | 130 / 140 degC |
| Vueltas mínimas para la tendencia de fluidos | 3 |
| Delta de presión bajo / alto / objetivo | 0,05 / 0,28 / 0,15 bar |
| Umbral de recomendación de presión / suelo | 0,03 bar / 0,8 bar |
| Corte de prioridad de presión | 0,1 bar |
| Umbrales del ratio de reparto | > 1,30 reducir, < 0,75 aumentar |
| Paso / límites del reparto | 2,0 puntos / 52-63 % |
| Temperatura mínima de eje para evidencia de reparto | 50 degC |
| Conversión de unidades | 1 bar = 14,5038 PSI = 100 kPa |

---

## 8. Estado de Verificación

Algoritmos, umbrales y claves se leyeron de `thermal_management.py` el 2026-10-03; la eliminación del proxy de presión en frío por inicio de vuelta y la protección de canal de frenos constante están en el código actual y faltaban en versiones anteriores de este documento. No verificable desde el código: la justificación de ingeniería de los umbrales (200/300/700/800 degC, 0,05-0,28 bar, 52-63 %), qué canales exporta cada simulador, y los "patrones comunes" de la sección 5.
