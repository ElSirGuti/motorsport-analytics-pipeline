# Setup Advisor

**Modulo:** `src/analytics/setup_advisor.py`
**Funciones principales:** `analizar_setup()`, `analizar_setup_sesion()`

---

## Descripcion General

El Setup Advisor es un motor basado en reglas que traduce metricas de telemetria en recomendaciones concretas de puesta a punto del vehiculo, acompanadas de estimaciones cuantitativas de ganancia de tiempo por vuelta. Su proposito es cerrar la brecha entre el dato bruto y la decision de ingenieria: en lugar de exponer numeros sin contexto, el modulo evalua multiples dominios de comportamiento dinamico, detecta patrones de problema, y produce salidas estructuradas que el ingeniero o el piloto pueden consumir directamente.

El modulo opera en dos modos complementarios:

- **Modo comparativo de vuelta (`analizar_setup`)**: analiza la comparacion entre dos vueltas especificas (vuelta A vs. vuelta B) con datos de angulo de deslizamiento, suspension, neumaticos, frenos e inputs del piloto.
- **Modo de sesion (`analizar_setup_sesion`)**: opera sobre agregados estadisticos de toda la sesion, combinando analisis de curvas, tendencia de degradacion y telemetria de sesion para producir recomendaciones representativas del comportamiento promedio.

Ambos modos generan una salida compatible, de modo que el componente de interfaz `SetupRecommendations` puede consumirlos de forma uniforme.

---

## Metodologia

### Arquitectura de reglas

El motor esta organizado en seis dominios de analisis independientes, cada uno implementado como una funcion privada de diagnostico:

| Dominio | Funcion privada (modo vuelta) | Funcion privada (modo sesion) |
|---|---|---|
| Neumaticos | `_analyse_tyres` | `_analyse_tyres_sesion` |
| Frenos | `_analyse_brakes` | `_analyse_frenos_sesion` |
| Suspension | `_analyse_suspension` | `_analyse_suspension_sesion` |
| Balance aerodinamico | `_analyse_slip` | `_analyse_balance_sesion` |
| Inputs del piloto | `_analyse_inputs` | `_analyse_inputs_sesion` |
| Analisis por curvas | `_analyse_corners` | `_analyse_corners` (compartida) |

Cada funcion recibe el dict de resultados del modulo correspondiente, verifica la disponibilidad de datos mediante la clave `available`, y retorna una lista de recomendaciones o una lista vacia si los datos no estan presentes.

### Diagnostico de neumaticos

El analisis de neumaticos opera en tres niveles:

1. **Gradiente de camber por posicion**: se calcula la diferencia entre la temperatura del borde interior y el borde exterior de cada neumatico. Un gradiente positivo mayor a 15 °C indica camber insuficiente (la banda interior trabaja en exceso); un gradiente negativo inferior a -12 °C indica camber excesivo. Los umbrales difieren porque la penalizacion asimetrica del camber es mas sensible al calentamiento interior.

2. **Estado de ventana de presion**: el estado `sobrecalentada` activa una recomendacion de aumento de presion de inflado; el estado `fria` activa una recomendacion de reduccion. La logica asume que presion y temperatura superficial estan correlacionadas en el regimen de operacion cubierto.

3. **Balance termico axial y lateral**: se calculan promedios de temperatura superficial por eje (delantero/trasero) y por lado (izquierdo/derecho). Un diferencial axial superior a 14 °C produce una recomendacion de balance termico; un diferencial lateral superior a 12 °C produce una recomendacion de asimetria. El umbral lateral es deliberadamente menor al axial porque la asimetria lateral tiene menor impacto en el tiempo de vuelta, y se clasifica con prioridad baja.

### Diagnostico de frenos

Se analiza la degradacion de eficiencia de frenada comparando la puntuacion de frenada observada contra una linea base de referencia. La formula de degradacion es:

```
degradacion_pct = (1 - score / baseline) * 100
```

Si la degradacion supera el 15 %, se emite una recomendacion de fade. Valores superiores al 30 % elevan la prioridad a `alta`. Adicionalmente, se identifican zonas de fade severo (severidad mayor al 30 % en zonas individuales) para permitir una intervencion puntual por curva o sector.

En el modo sesion, el diagnostico opera sobre la eficiencia media de frenada y la severidad media de fade. Una severidad media superior al 25 % o una eficiencia media inferior al 70 % activan una recomendacion de gestion termica de frenos.

### Diagnostico de suspension

La suspension se diagnostica en tres dimensiones:

- **Balance de barra estabilizadora (ARB)**: se calcula el cociente entre el roll maximo del eje delantero y el eje trasero. Un cociente mayor a 1.35 (delantero rola mas) indica subviraje estructural y sugiere endurecer el ARB trasero o ablandar el delantero. Un cociente menor a 0.75 indica sobreviraje estructural y sugiere la accion inversa.

- **Eventos de fondo de carrera (bottoming)**: se contabilizan los eventos en que el vehiculo toca el fondo durante la vuelta. La severidad maxima determina la prioridad: mayor al 95 % eleva la prioridad a `alta`. La recomendacion resultante apunta a un aumento de altura minima o rigidez de muelles.

- **Pitch longitudinal**: un angulo maximo de cabeceo superior a 15° bajo frenada indica transferencia de peso longitudinal excesiva. La recomendacion asociada apunta a ajuste de muelles delanteros o topes de compresion.

### Diagnostico de balance aerodinamico

El balance se extrae del modulo de angulo de deslizamiento (`slip_angle`). Los porcentajes de subviraje y sobreviraje se calculan sobre el tiempo total en cornering:

- Subviraje superior al 60 %: recomendacion de balance aerodinamico con prioridad `alta`, orientada a reducir downforce delantero o incrementar el trasero.
- Sobreviraje superior al 30 %: recomendacion opuesta con prioridad `alta`.
- Subviraje entre 45 % y 60 % con balance medio entre 2 y 4 grados: recomendacion de ajuste fino con prioridad `baja`.

En el modo sesion, los mismos umbrales se aplican sobre los promedios estadisticos de la sesion completa.

### Diagnostico de inputs del piloto / amortiguadores

La nerviosidad del volante se cuantifica mediante un score normalizado entre 0 y 1. Si el score supera 0.65, el modulo aplica un analisis espectral:

- **Alta frecuencia (banda `high` > 25 %)**: el origen probable es el rebote del amortiguador. La recomendacion apunta a reducir la rigidez de rebote.
- **Frecuencia media (banda `mid` > 35 %)**: el origen probable es la rigidez de muelles. La recomendacion apunta a ablandar los muelles.
- **Sin dominancia espectral clara**: recomendacion general de balance mecanico.

Adicionalmente, se evalua el porcentaje de solapamiento freno-acelerador como indicador de frenada de punta. Un solapamiento inferior al 5 % indica que el piloto no utiliza trail braking, lo que es una oportunidad tecnica, no un problema de setup.

### Analisis por curvas

El modulo identifica patrones repetidos entre curvas. Las detecciones activas son:

- **Frenada temprana sistematica**: tres o mas curvas con delta de punto de frenada mayor a 10 metros. La ganancia estimada escala linealmente con el numero de curvas afectadas (0.05–0.15 s por curva).
- **Velocidad de apex baja**: dos o mas curvas con delta de velocidad de apex inferior a -5 km/h. Ganancia estimada: 0.08–0.20 s por curva.
- **Aceleracion tardia**: tres o mas curvas con delta de punto de aceleracion mayor a 10 metros.

### Analisis de consistencia y degradacion (modo sesion)

Dos funciones adicionales operan exclusivamente en el modo sesion:

- `_analyse_consistency_sesion`: detecta curvas con desviacion estandar de perdida de tiempo superior a 0.12 s entre vueltas. Dos o mas curvas inconsistentes producen una recomendacion de tecnica, con ganancia proporcional al numero de curvas afectadas.

- `_analyse_degradacion_ritmo`: opera sobre la salida de `analizar_degradacion_stint()`. Una tasa de degradacion superior a 0.20 s/vuelta con R² mayor a 0.65 activa una recomendacion de alta prioridad. Tasas entre 0.08 y 0.20 s/vuelta con R² mayor a 0.45 producen una recomendacion de baja prioridad orientada a gestion de neumaticos.

### Deduplicacion y ordenamiento

Antes de retornar, el motor deduplica las recomendaciones por clave `(categoria, problema[:40])`, conservando la version de mayor prioridad cuando existe conflicto. El resultado se ordena por prioridad (`alta` > `media` > `baja`).

### Prioridad por curva

La funcion `_corner_priority` produce una lista independiente de las curvas con mayor perdida de tiempo (hasta 8 curvas), con un umbral minimo de 5 ms. Para cada curva, se identifica la fase dominante (frenada, apex, salida) aplicando factores de conversion aproximados:

- Frenada: 0.015 s por metro de delta de punto de frenada
- Apex: 0.012 s por km/h de delta de velocidad de apex
- Salida: 0.010 s por metro de delta de punto de aceleracion

---

## Canales Requeridos

### Modo comparativo de vuelta (`analizar_setup`)

| Canal / Seccion | Origen | Descripcion |
|---|---|---|
| `tyre_analysis.available` | Modulo de analisis de neumaticos | Habilita el diagnostico de presiones y camber |
| `tyre_analysis.lap_a / lap_b[].corners[]` | Modulo de analisis de neumaticos | Temperaturas interior, medio y exterior por posicion |
| `tyre_analysis.*.corners[].window_status` | Modulo de analisis de neumaticos | Estado de ventana de temperatura (`sobrecalentada`, `fria`, `optima`) |
| `tyre_analysis.*.corners[].surface_mean` | Modulo de analisis de neumaticos | Temperatura superficial media por neumatico |
| `brake_analysis.available` | Modulo de frenada | Habilita el diagnostico de fade |
| `brake_analysis.score_a / score_b` | Modulo de frenada | Puntuacion de eficiencia de frenada por vuelta |
| `brake_analysis.baseline_a / baseline_b` | Modulo de frenada | Linea base de referencia por vuelta |
| `brake_analysis.fade_zones_a / fade_zones_b` | Modulo de frenada | Zonas de fade con inicio, fin y severidad |
| `suspension.available` | Modulo de suspension | Habilita el diagnostico de ARB y bottoming |
| `suspension.summary_a / summary_b` | Modulo de suspension | Resumenes estadisticos de roll y pitch |
| `suspension.bottoming_a / bottoming_b` | Modulo de suspension | Lista de eventos de fondo con severidad y curva |
| `slip_angle.available` | Modulo de angulo de deslizamiento | Habilita el diagnostico de balance |
| `slip_angle.summary_a / summary_b` | Modulo de angulo de deslizamiento | Porcentajes de subviraje, sobreviraje y balance medio |
| `driver_inputs.available` | Modulo de inputs | Habilita el diagnostico de amortiguadores |
| `driver_inputs.nervousness_score_a / _b` | Modulo de inputs | Score de nerviosidad del volante |
| `driver_inputs.fft_bands_a / _b` | Modulo de inputs | Distribucion espectral de la senal de direccion |
| `driver_inputs.overlap_pct_a / _b` | Modulo de inputs | Porcentaje de solapamiento freno-acelerador |
| `corners[]` | Modulo de analisis por curvas | Lista de curvas con deltas de frenada, apex y aceleracion |

### Modo sesion (`analizar_setup_sesion`)

| Canal / Seccion | Origen | Descripcion |
|---|---|---|
| `curvas_sesion.available` | `session_corner_analysis` | Condicion de disponibilidad; aborta si es False |
| `curvas_sesion.corners[]` | `session_corner_analysis` | Curvas con perdida de tiempo media y desviacion estandar |
| `degradacion.tasa_s_per_lap` | `tyre_degradation` | Tasa de degradacion de ritmo en s/vuelta |
| `degradacion.r_squared` | `tyre_degradation` | R² del ajuste lineal de la tendencia de degradacion |
| `telemetria_sesion.tyre{}` | `session_telemetry_analysis` | Agregados de temperatura por posicion de neumatico |
| `telemetria_sesion.brake{}` | `session_telemetry_analysis` | Eficiencia media y severidad media de fade de frenos |
| `telemetria_sesion.suspension{}` | `session_telemetry_analysis` | Roll medio, ratio de roll, pitch medio, eventos de bottoming |
| `telemetria_sesion.inputs{}` | `session_telemetry_analysis` | Nerviosidad media, bandas FFT medias, solapamiento medio |
| `telemetria_sesion.balance{}` | `session_telemetry_analysis` | Porcentajes medios de subviraje y sobreviraje de sesion |

El parametro `telemetria_sesion` es opcional: si no se proporciona, el modulo opera unicamente con los datos de curvas y degradacion, produciendo un subconjunto reducido de recomendaciones.

---

## Esquema de Salida

### Salida de `analizar_setup` y `analizar_setup_sesion`

```python
{
    "available": bool,
    "recommendations": [
        {
            "category":        str,   # Categoria de setup (ej. "Camber")
            "problem":         str,   # Descripcion del problema detectado
            "root_cause":      str,   # Causa raiz tecnica
            "recommendation":  str,   # Accion concreta de ajuste
            "detail":          str,   # Explicacion tecnica extendida
            "solves":          str,   # Que mejora en el comportamiento del vehiculo
            "expected_gain":   str,   # Ganancia estimada en formato "X.XX–X.XXs/v"
            "gain_lo":         float, # Limite inferior de ganancia en segundos/vuelta
            "gain_hi":         float, # Limite superior de ganancia en segundos/vuelta
            "priority":        str,   # "alta" | "media" | "baja"
            "pilot_note":      str,   # Nota contextual para el piloto en ingles
        },
        ...
    ],
    "corner_priority": [
        {
            "corner_number":         int,
            "time_loss_seconds":     float,
            "braking_delta_meters":  float,
            "apex_speed_delta_kmh":  float,
            "throttle_delta_meters": float,
            "dominant_phase":        str,   # "frenada" | "apex" | "salida"
            "focus":                 str,   # Etiqueta localizada de la fase dominante
            "description":           str,
        },
        ...
    ],
    "total_gain_lo":    float, # Suma de gain_lo de todas las recomendaciones
    "total_gain_hi":    float, # Suma de gain_hi de todas las recomendaciones
    "total_gain_range": str,   # Formato "X.XX–X.XXs/v"
}
```

La salida de `analizar_setup` incluye adicionalmente la clave `areas_status`, ausente en `analizar_setup_sesion`:

```python
"areas_status": [
    {
        "domain":   str,   # Identificador del dominio
        "label":    str,   # Nombre legible (ej. "Neumaticos")
        "status":   str,   # "alta" | "media" | "baja" | "nominal"
        "n_issues": int,
    },
    ...
]
```

El campo `areas_status` solo incluye dominios para los que los datos estaban disponibles (`available == True`). Los dominios sin datos no aparecen en la lista.

### Rangos de ganancia estimada por dominio

| Dominio | Rango tipico (s/vuelta) | Base del calculo |
|---|---|---|
| Balance aerodinamico (subviraje/sobreviraje) | 0.10 – 0.40 | Porcentaje de tiempo en condicion critica |
| Temperatura de neumaticos (axial) | 0.10 – 0.30 | Diferencial termico vs. umbral |
| Fade de frenos (alta severidad) | 0.08 – 0.30 | Porcentaje de degradacion de eficiencia |
| Velocidad de apex | 0.08 – 0.20 × N curvas | N curvas con deficit > 5 km/h |
| Bottoming / altura minima | 0.05 – 0.25 | Frecuencia y severidad de eventos |
| Balance ARB | 0.06 – 0.20 | Ratio de roll fuera de ventana |
| Camber (gradiente termico) | 0.03 – 0.18 | Magnitud del gradiente interior-exterior |
| Amortiguadores (rebote) | 0.05 – 0.15 | Score de nerviosidad y energia en alta frecuencia |
| Consistencia de curvas | 0.05 – 0.15 × N curvas | Desviacion estandar de perdida de tiempo |

Estos rangos son estimaciones conservadoras basadas en correlaciones empiricas de ingenieria de competicion. No incorporan coeficientes de arrastre especificos del vehiculo ni modelos de neumaticos.

---

## Guia de Interpretacion

### Prioridad

La prioridad de cada recomendacion refleja la magnitud del problema y su impacto probable en el tiempo de vuelta:

- **`alta`**: problema significativo con impacto directo en rendimiento o seguridad. Debe atenderse antes del proximo stint o sesion de clasificacion.
- **`media`**: problema moderado que afecta el rendimiento de forma consistente. Puede abordarse entre sesiones o durante cambios de setup programados.
- **`baja`**: oportunidad de mejora menor o ajuste fino. Relevante en contextos de optimizacion cuando los problemas de mayor prioridad ya estan resueltos.

### Ganancia total estimada

El campo `total_gain_range` es la suma de los rangos de ganancia de todas las recomendaciones activas. Este numero NO debe interpretarse como la ganancia esperada si se aplican todos los ajustes simultaneamente: muchos problemas son interdependientes (resolver el balance reduce la degradacion, que a su vez afecta el camber efectivo en las ultimas vueltas del stint). La suma es un indicador del potencial teorico maximo no captado.

### `corner_priority`

La lista de prioridad por curvas permite focalizar el analisis de datos. Las curvas en las posiciones 1 a 3 son los candidatos principales para revision de video y datos sincronizados. La `dominant_phase` indica en que segmento de la curva se concentra la perdida de tiempo:

- **Frenada**: revisar punto de frenada, presion de freno y bloqueos.
- **Apex**: revisar velocidad de entrada, angulo de direccion y grip transversal.
- **Salida**: revisar punto de aplicacion de acelerador y traccion trasera.

### `pilot_note`

Este campo contiene una nota en ingles orientada al piloto, generada a partir de la clave del problema. Describe en terminos de sensacion de manejo que cambio puede esperar el piloto despues del ajuste, sin terminologia tecnica de ingenieria. Util para briefings cortos entre sesiones.

### Relacion entre dominios

Algunos problemas en dominios distintos pueden tener una causa raiz comun. Las combinaciones tipicas son:

- **Subviraje alto + frente mas caliente**: indica carga aerodinamica delantera excesiva o camber delantero insuficiente. Las dos recomendaciones son complementarias.
- **Nerviosidad alta en alta frecuencia + bottoming**: puede indicar un amortiguador trasero con rebote excesivo que provoca que el vehiculo bote sobre irregularidades. Resolver el bottoming puede reducir la nerviosidad derivada.
- **Fade de frenos + frente mas caliente**: un bias de frenos demasiado adelantado sobrecarga los discos delanteros termicamente. Ajustar el bias puede resolver ambos problemas de forma simultanea.

---

## Limitaciones

### Dependencia de datos disponibles

El modulo aplica las reglas de cada dominio unicamente si la clave `available` del modulo correspondiente es `True`. Si la sesion no incluye datos de angulo de deslizamiento (por ejemplo, por ausencia del canal de velocidad de rueda), el dominio de balance aerodinamico queda sin diagnostico, sin que esto genere un error. La clave `areas_status` refleja cuales dominios fueron evaluados.

### Umbrales fijos sin calibracion por vehiculo

Los umbrales numericos (gradientes de temperatura, ratios de roll, porcentajes de subviraje, etc.) son valores genericos derivados de experiencia empirica en vehiculos de competicion de categoria media-alta. No estan calibrados para vehiculos especificos. Un Formula 4 y un GT3 tienen ventanas de operacion de neumaticos, ratios de roll y tolerancias de camber fundamentalmente distintos. El uso del modulo en categorias con dinamica muy diferente (karting, vehiculos de arrastre) puede producir recomendaciones inadecuadas.

### Estimaciones de ganancia no validadas por modelo de vehiculo

Las ganancias estimadas en segundos por vuelta son rangos conservadores basados en correlaciones genericas. No incorporan el modelo de neumatico especifico, las caracteristicas aerodinamicas del circuito, ni el coeficiente de transferencia de calor del sistema de frenos. Deben tratarse como ordenes de magnitud, no como predicciones absolutas.

### Independencia entre recomendaciones

El motor trata cada dominio de forma independiente. No modela la interaccion entre ajustes: aplicar simultaneamente un aumento de camber negativo delantero y un endurecimiento del ARB delantero puede producir un balance diferente al predicho por las recomendaciones individuales. El ingeniero de pista debe evaluar las interacciones al implementar multiples cambios en paralelo.

### Ausencia de modelo de degradacion de neumatico por compuesto

El diagnostico de presiones y temperaturas asume una ventana de operacion fija (80–100 °C para la temperatura superficial). En la practica, la ventana varia segun el compuesto, el proveedor y las condiciones de pista. Los datos de temperatura superficial de neumnaticos pueden reflejar condiciones transitorias de calentamiento o enfriamiento que no representan el estado estacionario del compuesto.

### Modo sesion: sensibilidad a outliers en agregados

Los agregados estadisticos de sesion (medias de roll, temperatura, nerviosidad) son sensibles a vueltas atipicas: vueltas de entrada a boxes, vueltas bajo bandera amarilla o vueltas con incidentes pueden distorsionar las medias y producir recomendaciones incorrectas. Se recomienda filtrar vueltas atipicas antes de alimentar el modulo de telemetria de sesion.

### Falta de feedback de circuito

El modulo no recibe informacion sobre el trazado del circuito (numero de curvas lentas vs. rapidas, superficies abrasivas, perfil de altimetria). Una pista con predominio de curvas rapidas requiere configuraciones de camber y presion diferentes a una pista tecnica de curvas lentas. Esta dimension no esta contemplada en la logica de reglas actual.
