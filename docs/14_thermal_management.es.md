# Análisis de Gestión Térmica

## Descripción General

El módulo `thermal_management` realiza el análisis térmico integral de una sesión de
conducción. Procesa datos de temperatura de fluidos del motor, temperaturas de frenos,
presiones de neumáticos y balance de frenado, y devuelve diagnósticos con
recomendaciones de ajuste accionables.

### Por qué la gestión térmica es crítica en motorsport

En competición, los sistemas térmicos operan permanentemente cerca de sus límites de
diseño. Una temperatura de refrigerante fuera de rango puede provocar la detonación del
motor o la pérdida de potencia por sobreprotección electrónica. Los frenos que no
alcanzan su ventana de trabajo óptima exhiben fade progresivo o, en el extremo opuesto,
glazing del disco. Los neumáticos que construyen demasiada presión durante el rodaje
generan sobreviraje progresivo; los que construyen poca, subviraje con pérdida de
tracción en la zona de carga.

A diferencia de la telemetría de inputs (acelerador, freno, dirección), los canales
térmicos son indicadores diferidos: el piloto no percibe directamente la temperatura del
aceite ni la presión interna del neumático, pero ambas condicionan de forma determinante
el comportamiento dinámico del vehículo.

### Fuentes de datos y unidades nativas

El módulo es compatible con dos simuladores principales:

| Simulador | Presiones de neumático | Temperatura de fluidos |
|---|---|---|
| **iRacing** | kPa (≈ 170–250 kPa en condiciones normales) | °C |
| **Assetto Corsa (ACTI)** | PSI (≈ 20–40 PSI en condiciones normales) | °C |

La detección de unidades es automática: si el valor máximo del canal supera 100, se
interpreta como kPa y se convierte a bar (`÷ 100`); si supera 10 pero no 100, se
interpreta como PSI y se convierte a bar (`÷ 14.5038`). Todos los resultados de presión
se devuelven en **bar y PSI simultáneamente** para facilitar la comparación entre
plataformas.

---

## Algoritmo y Metodología

### Análisis de temperatura de fluidos del motor

Se evalúan dos canales independientes: temperatura del refrigerante del motor (agua) y
temperatura del aceite. Para cada canal se calcula la media por vuelta, el valor pico de
la sesión y la tendencia lineal (°C por vuelta) mediante regresión polinomial de primer
grado sobre el vector de medias por vuelta.

**Umbrales operativos:**

| Canal | Estado `warning` | Estado `critical` |
|---|---|---|
| Temperatura de agua | ≥ 105 °C | ≥ 115 °C |
| Temperatura de aceite | ≥ 130 °C | ≥ 140 °C |

- **`normal`**: temperatura dentro del rango de trabajo seguro; no se emite alerta.
- **`warning`**: temperatura elevada; se recomienda monitoreo estrecho y posible
  reducción de carga aerodinámica para aumentar flujo de refrigeración.
- **`critical`**: temperatura que compromete la integridad del motor; se emite una alerta
  explícita en la clave `alert` del resultado.

La tendencia (`trend_c_per_lap`) es especialmente relevante para sesiones de entrenamiento
largas: una tendencia positiva sostenida indica que el sistema de refrigeración no
disipa el calor generado a ritmo de carrera.

### Zonas de temperatura de frenos

Los frenos de carbono-carbono y los compuestos de competición tienen una ventana de
trabajo térmica estrecha. El módulo clasifica la temperatura media de cada esquina del
vehículo (FL, FR, RL, RR) en cinco estados:

| Estado | Rango de temperatura media | Interpretación |
|---|---|---|
| `too_cold` | < 200 °C | Freno frío; riesgo de glazing y mordida irregular |
| `suboptimal` | 200–300 °C | Por debajo de la ventana óptima; compuesto sin activar |
| `optimal` | 300–700 °C | Ventana de trabajo óptima |
| `hot` | 700–800 °C | Sobrecalentamiento incipiente; monitorear |
| `critical` | > 800 °C | Riesgo de ebullición de líquido de frenos y fallo de pastilla |

**Recomendaciones de conducto de freno** (`duct_recs`):

- Estado `too_cold` → acción `close`: cerrar el conducto para retener calor y alcanzar
  la ventana óptima.
- Estado `hot` o `critical` → acción `open`: abrir el conducto para incrementar el
  flujo de aire refrigerante; prioridad `alta` en caso `critical`.

Adicionalmente, el módulo calcula el **balance térmico freno-freno** como el cociente
entre la temperatura media del eje delantero y la del eje trasero
(`ratio_f_r = front_mean_c / rear_mean_c`). Este cociente alimenta directamente el
análisis de balance de frenado.

### Análisis de presión de neumáticos

Para cada esquina se registran dos presiones:

1. **Presión en caliente** (`hot`): media de la presión instantánea durante el rodaje.
   Si no existe un canal de presión en frío explícito, se estima como la media del
   primer 5 % del vector de muestras de la vuelta (neumático aún no termalizado).
2. **Presión en frío** (`cold`): presión de configuración, leída desde el canal de
   presión de puesta a punto cuando está disponible.

El **delta frío–caliente** (`delta_bar = hot_mean − cold_mean`) cuantifica la
construcción de presión durante la termalización. El objetivo de diseño del módulo es
un delta de **0.15 bar** (≈ 2.2 PSI), dentro de una ventana aceptable de 0.05–0.28 bar.

| Estado del delta | Interpretación | Acción recomendada |
|---|---|---|
| `low_delta` (< 0.05 bar) | Presión en frío demasiado alta | Reducir la presión de configuración |
| `ok` (0.05–0.28 bar) | Delta dentro de la ventana aceptable | Sin ajuste necesario |
| `high_delta` (> 0.28 bar) | Presión en frío demasiado baja | Aumentar la presión de configuración |

Cuando el ajuste recomendado supera **0.03 bar** de magnitud, el módulo emite una
recomendación explícita con la presión en frío objetivo calculada como:

```
target_cold = cold_mean − (delta_mean − 0.15)
target_cold = max(0.80 bar, target_cold)   # límite de seguridad inferior
```

### Normalización del balance de frenado

El canal de balance de frenado (`BrakeBias`, `dcBrakeBias`) puede entregarse como
fracción decimal (0.0–1.0, formato iRacing) o como porcentaje (0–100). La función
`_to_pct_bias` detecta automáticamente el formato: si el valor máximo es ≤ 1.05, se
multiplica por 100.

El módulo evalúa el balance en dos niveles:

1. **Análisis basado en temperatura** (preferente): si las temperaturas de freno están
   disponibles y ambos ejes superan los 50 °C (señal con significado físico), se
   compara el `ratio_f_r` con los umbrales 0.75 y 1.30.
   - Ratio > 1.30 (frenos delanteros mucho más calientes): reducir balance delantero
     en ≈ 2 pp, hasta el mínimo de 52 % delantero.
   - Ratio < 0.75 (frenos traseros mucho más calientes): aumentar balance delantero
     en ≈ 2 pp, hasta el máximo de 63 % delantero.

2. **Verificación de rango típico**: independientemente del análisis térmico, si el
   balance medio cae fuera del rango 52–63 % delantero, se emite una advertencia
   (`out_of_range`) que indica el riesgo asociado (bloqueo trasero por debajo de 52 %,
   o fade/bloqueo delantero por encima de 63 %).

---

## Canales de Telemetría Requeridos

Los canales marcados como opcionales activan sub-análisis adicionales cuando están
presentes, pero su ausencia no impide la ejecución del módulo.

| Canal | Nombres aceptados | Unidades nativas | Obligatorio |
|---|---|---|---|
| Temperatura de refrigerante | `WaterTemp`, `Water Temp`, `Engine Temp`, `CoolantTemp`, `Coolant Temp`, `Eng Coolant Temp` | °C | No |
| Temperatura de aceite | `OilTemp`, `Oil Temp`, `Eng Oil Temp`, `Engine Oil Temp`, `EngOilTemp` | °C | No |
| Temperatura de freno FL | `BrakeTempFL`, `Brake Temp FL`, `BrakeTempFrontLeft` | °C | No |
| Temperatura de freno FR | `BrakeTempFR`, `Brake Temp FR`, `BrakeTempFrontRight` | °C | No |
| Temperatura de freno RL | `BrakeTempRL`, `Brake Temp RL`, `BrakeTempRearLeft` | °C | No |
| Temperatura de freno RR | `BrakeTempRR`, `Brake Temp RR`, `BrakeTempRearRight` | °C | No |
| Presión en caliente FL | `TyrePressFL`, `Tire Pressure FL`, `Tyre Pres FL`, `LFpressure` | kPa / PSI / bar | No |
| Presión en caliente FR | `TyrePressFR`, `Tire Pressure FR`, `Tyre Pres FR`, `RFpressure` | kPa / PSI / bar | No |
| Presión en caliente RL | `TyrePressRL`, `Tire Pressure RL`, `Tyre Pres RL`, `LRpressure` | kPa / PSI / bar | No |
| Presión en caliente RR | `TyrePressRR`, `Tire Pressure RR`, `Tyre Pres RR`, `RRpressure` | kPa / PSI / bar | No |
| Presión en frío FL | `LFcoldPressure`, `TyrePressColdFL` | kPa / PSI / bar | No |
| Presión en frío FR | `RFcoldPressure`, `TyrePressColdFR` | kPa / PSI / bar | No |
| Presión en frío RL | `LRcoldPressure`, `TyrePressColdRL` | kPa / PSI / bar | No |
| Presión en frío RR | `RRcoldPressure`, `TyrePressColdRR` | kPa / PSI / bar | No |
| Balance de frenado | `BrakeBias`, `dcBrakeBias`, `Brake Bias`, `brake_bias` | % o fracción decimal | No |

El módulo acepta también variantes ortográficas menores. Si ningún nombre del grupo
coincide con las columnas del DataFrame, el sub-análisis correspondiente devuelve
`{"available": false}` y los demás continúan con normalidad.

---

## Esquema de Salida

La función principal `analizar_termica(dfs, df_laps)` devuelve un diccionario con la
siguiente estructura:

```json
{
  "available": true,
  "n_recommendations": 4,

  "water_temp": {
    "available": true,
    "channel": "Water",
    "mean_c": 98.4,
    "max_c": 107.2,
    "trend_c_per_lap": 0.31,
    "status": "warning",
    "warn_threshold_c": 105,
    "crit_threshold_c": 115,
    "per_lap": [{"lap": 1, "mean_c": 96.1}, ...],
    "alert": "Water temp elevada (107°C ≥ 105°C) — monitorear de cerca"
  },

  "oil_temp": { ... },

  "brake_temps": {
    "available": true,
    "optimal_range_c": [300, 700],
    "corners": {
      "FL": {"mean_c": 512.3, "max_c": 648.1, "status": "optimal", "per_lap": [...]},
      "FR": {"mean_c": 541.0, "max_c": 671.4, "status": "optimal", "per_lap": [...]},
      "RL": {"mean_c": 188.5, "max_c": 221.7, "status": "too_cold", "per_lap": [...]},
      "RR": {"mean_c": 193.2, "max_c": 229.0, "status": "too_cold", "per_lap": [...]}
    },
    "balance": {
      "front_mean_c": 526.7,
      "rear_mean_c": 190.9,
      "ratio_f_r": 2.76
    },
    "duct_recs": [
      {"corner": "RL", "action": "close", "reason": "...", "priority": "media"},
      {"corner": "RR", "action": "close", "reason": "...", "priority": "media"}
    ]
  },

  "tyre_pressure": {
    "available": true,
    "delta_target": {"bar": 0.15, "psi": 2.2},
    "delta_window": {
      "low":  {"bar": 0.05, "psi": 0.7},
      "high": {"bar": 0.28, "psi": 4.1}
    },
    "corners": {
      "FL": {
        "hot":   {"bar": 1.87, "psi": 27.1},
        "cold":  {"bar": 1.65, "psi": 23.9},
        "delta": {"bar": 0.22, "psi": 3.2},
        "status": "ok",
        "per_lap": [...]
      }
    },
    "recommendations": [
      {
        "corner": "RR",
        "direction": "raise",
        "delta_bar": 0.08,
        "delta_psi": 1.2,
        "current_cold": {"bar": 1.58, "psi": 22.9},
        "target_cold":  {"bar": 1.66, "psi": 24.1},
        "current_hot":  {"bar": 1.96, "psi": 28.4},
        "reason": "...",
        "priority": "baja"
      }
    ]
  },

  "brake_bias": {
    "available": true,
    "current_pct": 57.5,
    "typical_range": [52.0, 63.0],
    "out_of_range": null,
    "per_lap": [{"lap": 1, "bias_pct": 57.3}, ...],
    "recommendation": null
  }
}
```

Cuando `available` es `false` en la clave raíz, todos los sub-análisis carecen de datos
de telemetría y el resultado es `{"available": false}`.

---

## Guía de Interpretación

### Temperatura de fluidos

Un valor de `trend_c_per_lap` positivo y creciente a lo largo de una sesión extendida
es el indicador más relevante de un problema de refrigeración: significa que el
sistema no llega al equilibrio térmico. Un pico puntual (`max_c`) dentro de `warning`
en vuelta rápida, seguido de retorno a `normal`, es generalmente aceptable.

Ante estado `critical` en cualquier canal de fluido, la prioridad es abandonar la
puesta a punto de conducción y revisar el sistema de refrigeración antes de continuar.

### Temperaturas de freno

El estado `optimal` en los cuatro rincones simultáneamente es el objetivo de
configuración de conductos. Sin embargo, las condiciones de pista (temperatura ambiente,
tiempo en boxes, fases de safety car) pueden desplazar temporalmente las temperaturas.
Analizar la distribución `per_lap` permite distinguir un problema estructural de una
perturbación transitoria.

Un `ratio_f_r` muy superior a 1.0 en el campo `balance` indica un balance de frenado
excesivamente delantero desde el punto de vista térmico, independientemente de los
tiempos por vuelta. Esta señal es complementaria al comportamiento dinámico percibido
por el piloto.

### Presión de neumáticos

La presión en caliente de trabajo no es una constante: varía con la temperatura de
pista, la carga de combustible y el ritmo de conducción. La métrica relevante para la
configuración es el **delta frío–caliente**, no el valor absoluto de presión en
caliente. Trabajar con un delta consistente a lo largo de las vueltas indica que el
proceso de termalización del neumático es estable.

Si el canal de presión en frío no está disponible en la telemetría exportada, el módulo
estima la presión en frío a partir del primer 5 % de las muestras de la vuelta. Esta
estimación es menos precisa en vueltas de lanzamiento o salida de boxes, donde el
neumático aún no ha iniciado su ciclo de carga.

### Balance de frenado

Las recomendaciones de ajuste del balance de frenado son conservadoras por diseño:
el incremento o decremento sugerido es de ≈ 2 pp para evitar cambios abruptos en el
comportamiento de frenado. En ausencia de datos de temperatura de freno, el módulo no
emite recomendación de ajuste; solo verifica que el valor absoluto esté dentro del
rango típico de seguridad (52–63 % delantero).

---

## Limitaciones

1. **Dependencia de canales disponibles**: ningún canal de telemetría es obligatorio.
   Si el simulador o la configuración de exportación no incluye un canal específico
   (por ejemplo, temperatura de frenos en iRacing con exportación básica), el
   sub-análisis correspondiente devuelve `{"available": false}` sin interrumpir el
   resto del análisis.

2. **Estimación de presión en frío**: cuando el canal de presión en frío no está
   disponible, la estimación por el primer 5 % de muestras es una aproximación. En
   vueltas muy cortas (< 20 muestras) o con salidas de boxes al inicio, la estimación
   puede desviarse del valor real de configuración.

3. **Rango típico de balance de frenado**: los límites de 52–63 % delantero son valores
   genéricos de referencia aplicables a la mayoría de los vehículos GT y prototipos.
   Categorías con distribución de peso muy delantera o trasera (por ejemplo, monoplazas
   de Fórmula) pueden requerir rangos diferentes.

4. **Temperatura de frenos en iRacing**: la exportación estándar de iRacing no incluye
   canales de temperatura de freno en todas las configuraciones. En esos casos, el
   análisis de ductos y el balance térmico se omiten automáticamente.

5. **Sesión única**: `analizar_termica` opera sobre el conjunto de vueltas de una
   sesión. No está diseñado para comparaciones entre sesiones distintas; para eso se
   emplea `analizar_termica_comparativa`, que acepta dos DataFrames individuales de
   vuelta.

6. **Resolución temporal**: el módulo trabaja con medias por vuelta, no con series
   temporales de alta frecuencia. Los eventos térmicos de duración inferior a una vuelta
   (por ejemplo, sobretemperatura durante una frenada puntual) quedan capturados
   únicamente en el campo `max_c`, no en las tendencias ni en los estados por vuelta.
