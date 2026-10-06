# 17 - Asesor de Setup

[See in English](./17_setup_advisor.md)

**Módulo:** `src/analytics/setup_advisor.py`
**Puntos de entrada:** `analizar_setup(result, lang)` (comparación de dos vueltas) y `analizar_setup_sesion(curvas_sesion, degradacion, telemetria_sesion, lang)` (sesión completa)
**Módulo relacionado (vinculación con Assetto Corsa):** `src/analytics/ac_setups.py` y el router `src/api/setups.py`
**Reconciliado con el código:** 2026-10-03 (las versiones EN y ES comparten la misma estructura)

---

## Tabla de Contenidos

1. [Descripción General](#1-descripción-general)
2. [Motor de Reglas](#2-motor-de-reglas)
3. [Reglas y Umbrales](#3-reglas-y-umbrales)
4. [Vinculación con el Setup de Assetto Corsa](#4-vinculación-con-el-setup-de-assetto-corsa)
5. [Requisitos de Entrada](#5-requisitos-de-entrada)
6. [Esquema de Salida](#6-esquema-de-salida)
7. [Guía de Interpretación](#7-guía-de-interpretación)
8. [Limitaciones e Inconsistencias Conocidas](#8-limitaciones-e-inconsistencias-conocidas)
9. [Estado de Verificación](#9-estado-de-verificación)

---

## 1. Descripción General

El Asesor de Setup es un motor puramente basado en reglas: umbrales fijos sobre métricas producidas por otros módulos se convierten en recomendaciones de setup, cada una con prioridad, una nota apta para el piloto y un rango estimado de ganancia de tiempo por vuelta. No aprende nada de los datos.

- **`analizar_setup`** lee el diccionario de una comparación de dos vueltas (neumáticos, frenos, suspensión, ángulo de deriva, inputs del piloto, curvas) y devuelve además un `areas_status` por dominio.
- **`analizar_setup_sesion`** lee agregados de sesión: patrones de curva, la tendencia del stint y la telemetría agregada de `analizar_telemetria_sesion`. Devuelve `{"available": false}` cuando `curvas_sesion["available"]` es falso.

Ambos devuelven la misma estructura de recomendación. Cada recomendación lleva claves estables e independientes del idioma (`problem_key`, `category_key`, `rec_key` y `pos` cuando la regla trata de un neumático concreto) para que otros módulos, en particular el vinculador de setups de Assetto Corsa (sección 4), puedan asociar una recomendación a parámetros concretos del setup sin interpretar texto traducido.

---

## 2. Motor de Reglas

- Cada regla construye una recomendación mediante `_rec_t(...)`: claves de traducción para categoría, problema, causa raíz, recomendación, detalle y "soluciona", un rango de ganancia `(gain_lo, gain_hi)` en segundos por vuelta y una prioridad (`alta`, `media`, `baja`; literales fijos en español).
- Los textos provienen de los archivos de idioma mediante `src/i18n.py` (`src/locales/*.json` y `src/locales/extra/`). Un argumento `lang` explícito se respeta ahora (las funciones públicas se ejecutan dentro del contexto de i18n de ese idioma); con `lang=None` (por defecto) se sigue usando el idioma del contexto activo fijado por petición en `main.py`.
- `pilot_note` se obtiene de `_PILOT_NOTE_MAP` (clave de problema a nota en lenguaje llano; por defecto `pilot_note_default`).
- **Deduplicación:** clave `(categoría, primeros 40 caracteres del texto del problema)`; se conserva la instancia de mayor prioridad (la anterior en caso de empate). El resultado se ordena `alta`, `media`, `baja`.
- **Totales:** `total_gain_lo` / `total_gain_hi` son las sumas simples de `gain_lo` / `gain_hi` de las recomendaciones conservadas (2 decimales); `total_gain_range` es el formato `"lo-hi"`.
- **`areas_status`** (solo modo vuelta): para cada dominio con datos disponibles, la peor prioridad presente o `nominal`, más `n_issues`.
- **`corner_priority`**: curvas con `|time_loss_seconds| >= 0.005`, las 8 primeras por pérdida absoluta. La fase dominante es la mayor entre `|brake_delta| x 0,015`, `|apex_delta| x 0,012` y `|throttle_delta| x 0,010` (sensibilidades supuestas en s por m o km/h, no medidas), con etiquetas `frenada` / `apex` / `salida`.

---

## 3. Reglas y Umbrales

Las ganancias son los rangos heurísticos fijos en segundos por vuelta y no tienen validación empírica. Las reglas del "modo vuelta" se ejecutan una vez para la vuelta A y otra para la B.

### 3.1 Neumáticos

| Modo | Regla | Condición | Prioridad | Ganancia (s/vuelta) |
|---|---|---|---|---|
| Vuelta | Caída, interior caliente | `inner - outer > 15` degC | alta | 0,04-0,18 |
| Vuelta | Caída, exterior caliente | `inner - outer < -12` degC | media | 0,03-0,15 |
| Vuelta | Presión, sobrecalentado | `window_status == "sobrecalentada"` | alta | 0,05-0,15 |
| Vuelta | Presión, frío | `window_status == "fria"` | media | 0,03-0,12 |
| Vuelta | Temperatura superficial delantero vs trasero | media delantera - media trasera `> 14` o `< -14` | alta | 0,10-0,30 |
| Vuelta | Asimetría izquierda vs derecha | `|izq - der| > 12` | baja | 0,02-0,08 |
| Sesión | Sobrecalentamiento | temperatura media `> 120` (ventana 80-100 + 20) | alta | 0,05-0,18 |
| Sesión | Demasiado frío | temperatura media `< 65` (80 - 15) | media | 0,04-0,12 |
| Sesión | Caída | `|camber_gradient| > 18` con `camber_gradient = inner_mean - outer_mean` | media | 0,03-0,10 |
| Sesión | Temperatura de freno por esquina | `brake_temp_mean > 750` (alta si `> 900`) | media/alta | 0,05-0,20 |
| Sesión | Delta delantero/trasero | `|front_rear_delta| > 14` (delantero más caliente / trasero más caliente) | media | 0,08-0,25 / 0,06-0,20 |
| Sesión | Delta izquierda/derecha | `|left_right_delta| > 12` | baja | 0,02-0,08 |

### 3.2 Frenos

| Modo | Condición | Prioridad | Ganancia |
|---|---|---|---|
| Vuelta | Fade `(1 - score/baseline) x 100 > 15` % (alta si `> 30`) | media/alta | 0,08-0,25 |
| Vuelta | Zonas de fade con `severity > 0.30` | alta | 0,05-0,20 |
| Sesión | `mean_fade_severity > 0.25` o `0 < mean_efficiency < 0.70` (alta si la severidad `> 0.35`) | media/alta | 0,08-0,30 |
| Sesión | `mean_fade_severity > 0.10` (leve) | baja | 0,03-0,10 |

### 3.3 Suspensión

| Modo | Condición | Prioridad | Ganancia |
|---|---|---|---|
| Vuelta | Ratio de balanceo delantero/trasero `> 1.35` (requiere ambos máximos de balanceo `> 3`) | media | 0,06-0,20 |
| Vuelta | Ratio de balanceo `< 0.75` | media | 0,06-0,20 |
| Vuelta | Cualquier evento de tope (alta si la severidad máxima `> 0.95`) | media/alta | 0,05-0,20 |
| Vuelta | `max_pitch > 15` | baja | 0,03-0,12 |
| Sesión | Alguna esquina con topes `> 3` % o media de eventos/vuelta `> 0.5` (alta si eventos `> 1.5` o una esquina `> 8` %) | media/alta | 0,05-0,25 |
| Sesión | `roll_ratio > 1.40` / `< 0.70` | media | 0,05-0,18 |
| Sesión | `mean_pitch > 15` | baja | 0,03-0,12 |

### 3.4 Balance (a partir de resúmenes de ángulo de deriva / guiñada)

| Modo | Condición (la primera que coincida) | Prioridad | Ganancia |
|---|---|---|---|
| Vuelta | `understeer_pct > 60` | alta | 0,12-0,40 |
| Vuelta | `oversteer_pct > 30` | alta | 0,10-0,35 |
| Vuelta | `2 < balance_mean <= 4` y `understeer_pct > 45` | baja | 0,04-0,12 |
| Sesión | `mean_understeer_pct > 60` | alta | 0,12-0,40 |
| Sesión | `mean_oversteer_pct > 30` | alta | 0,10-0,35 |
| Sesión | `mean_understeer_pct > 40` | baja | 0,05-0,15 |

### 3.5 Inputs del piloto

| Modo | Condición | Prioridad | Ganancia |
|---|---|---|---|
| Vuelta | nerviosismo `> 0.65` y banda de alta frecuencia `> 0.25` | media | 0,05-0,15 |
| Vuelta | nerviosismo `> 0.65` y banda media `> 0.35` (si no es alta) | baja | 0,04-0,12 |
| Vuelta | nerviosismo `> 0.65`, ninguna banda | media | 0,05-0,20 |
| Vuelta | solapamiento freno/acelerador `< 5` % | baja | 0,03-0,10 |
| Sesión | nerviosismo `> 0.65` y `fft_high > 0.28` | media | 0,04-0,15 |
| Sesión | nerviosismo `> 0.65` y `fft_mid > 0.38` (independiente de la regla anterior) | baja | 0,03-0,10 |
| Sesión | `0.40 < nerviosismo <= 0.65` | baja | 0,02-0,08 |
| Sesión | solapamiento medio `< 4` % | baja | 0,04-0,12 |

### 3.6 Curvas y consistencia

| Condición | Prioridad | Ganancia |
|---|---|---|
| Al menos 3 curvas con `braking_delta_meters > 10` | media | 0,05 x n a 0,15 x n |
| Al menos 2 curvas con `apex_speed_delta_kmh < -5` | alta | 0,08 x n a 0,20 x n |
| Al menos 3 curvas con `throttle_delta_meters > 10` | media | 0,04 x n a 0,12 x n |
| Sesión: al menos 2 curvas con `std_loss_seconds > 0.12` | media | 0,05 x n a 0,15 x n |

### 3.7 Degradación (solo modo sesión)

`_analyse_degradacion_ritmo` usa `tasa_s_per_lap` y `r_squared` de `analizar_degradacion_stint`:

| Condición | Prioridad | Ganancia |
|---|---|---|
| tasa neta `> 0,12` y `r2 > 0.65` (alta si `>= 0,15`) | media/alta | `0,25 x tasa` a `0,55 x tasa` |
| `0,08 < tasa neta <= 0,12` y `r2 > 0.45` | baja | `0,15 x tasa` a `0,35 x tasa` |

Ver el apartado 8 sobre la primera fila: no puede dispararse con el módulo de stint actual.

---

## 4. Vinculación con el Setup de Assetto Corsa

`src/analytics/ac_setups.py` vincula las recomendaciones del asesor con los parámetros reales del setup de Assetto Corsa del usuario (`.ini` / `.sp`) y produce una vista "actual -> sugerido". Se expone en `src/api/setups.py` bajo `/api/setups`:

| Endpoint | Propósito |
|---|---|
| `POST /api/setups/detect` | Vehículo / circuito / piloto (y fecha, tipo de sesión, formato) a partir de los primeros bytes de un CSV, `.ibt` o `.ld`, o de un `file_id` almacenado |
| `GET /api/setups/candidates` | Busca setups para un coche y circuito: estados `track_setups`, `generic_only`, `none`, `no_access` |
| `GET /api/setups/file` | Lee un setup por id |
| `POST /api/setups/parse` | Analiza un `.ini` / `.sp` subido (máx. 256 KiB) |
| `POST /api/setups/annotate` | Cuerpo `{setup, recommendations}`; devuelve las recomendaciones decoradas con `setup_link`, más `n_linked`, `conflicts` y `summary` |

Cómo funciona el vínculo:

0. **Cambios de setup a mitad de sesión.** `src/analytics/setup_segments.py` corta la sesión en las vueltas en que el usuario indica que empieza un setup nuevo y ejecuta este asesor en cada tramo por separado (`POST /api/stint/segments`); cada tramo necesita al menos 3 vueltas válidas.
1. **Localización de setups.** La carpeta es la definida en la vista Ajustes (`/api/settings/paths`) si existe, luego `AC_SETUPS_DIR` si está definida; si no, la primera `<Documents>/Assetto Corsa/setups` existente (API de carpetas conocidas de Windows, `USERPROFILE`, home). Estructura `<coche>/<circuito>/*.ini` más `<coche>/generic/last.ini`. Cuando el servidor no puede ver la carpeta (Docker, Linux, macOS) el estado es `no_access` y el usuario puede subir el archivo. En Docker, monta la carpeta en solo lectura y define `AC_SETUPS_DIR` (ver `docker-compose.override.example.yml`).
2. **Seguridad.** Los nombres de coche y circuito se validan con un conjunto estricto de caracteres y se comparan con el listado real del directorio; la ruta resuelta debe quedar dentro de la carpeta de setups; solo se leen archivos regulares `.ini`/`.sp` de hasta 256 KiB y 2000 secciones.
3. **Análisis.** Secciones como `PRESSURE_LF`, `CAMBER_RR`, `ARB_FRONT`, `FRONT_BIAS` se clasifican en grupos (aero, tyres, suspension, brakes, diff, electronics, other); los sufijos `LF/RF/LR/RR` se asignan a FL/FR/RL/RR. El juego guarda "clics": las unidades reales solo se afirman donde son seguras (presión en psi, reparto de frenada y potencia de freno en %, combustible en litros); lo demás se muestra en bruto.
4. **Rangos.** Mínimo/máximo/paso solo se adjuntan si es legible el `content/cars/<coche>/data/setup.ini` desempaquetado del coche (`AC_ROOT` / `AC_INSTALL_DIR`, bibliotecas de Steam). Los archivos cifrados `data.acd` deliberadamente no se abren; la fuente se informa como `car_data`, `encrypted` o `not_found`.
5. **Mapeo.** `_MAP` se indexa por el `rec_key` del asesor y lista `(base del parámetro, destino, dirección, multiplicador, alternativa)`; `target` es `pos` (el neumático de la regla), `front`, `rear`, `all`, `bias_pos` o ninguno. Ejemplos: `setup_rec_camber_add` -> `CAMBER` en esa rueda, -1; `setup_rec_pressure_raise` -> `PRESSURE`, +1; `setup_rec_arb_front` -> `ARB_FRONT`, +1; `setup_rec_understeer` -> `ARB_FRONT`, -1 marcado como *alternativa* al cambio aerodinámico. `_RELATED` lista parámetros que solo se muestran cuando no se puede derivar un cambio seguro (por ejemplo altura y muelles para los topes).
6. **Acciones seguras.** Cada acción tiene `current`, `suggested`, `delta`, `direction`, `status` (`ok`, `direction_only`, `at_limit`), `alternative` y una `note`. El valor sugerido es `current + dirección x paso x multiplicador`, limitado a los límites del coche y a cotas duras (ARB y presión >= 0, reparto delantero 0-100). Solo se supone un paso de 1 clic (con nota) para presión, ARB y reparto delantero; en otro caso solo se da la dirección. Si el valor ya está en el límite en la dirección deseada, el estado es `at_limit` en lugar de un consejo incoherente.
7. **Conflictos.** Si dos acciones no alternativas empujan el mismo parámetro en direcciones opuestas, se lista en `conflicts`.

Las recomendaciones sin mapeo se devuelven sin cambios (sin `setup_link`).

---

## 5. Requisitos de Entrada

### Modo vuelta: `analizar_setup(result)`

Las claves ausentes omiten el dominio en silencio.

| Clave | Campos leídos |
|---|---|
| `tyre_analysis` | `available`; `lap_a` / `lap_b` con `corners` (`corner`, `inner`, `middle`, `outer`, `surface_mean`, `window_status` en {`optima`, `sobrecalentada`, `fria`}) |
| `brake_analysis` | `available`, `score_a/b`, `baseline_a/b`, `fade_zones_a/b` (`start`, `end`, `severity`) |
| `suspension` | `available`, `summary_a/b` (`max_roll_f`, `max_roll_r`, `max_pitch`, `mean_pitch`), `bottoming_a/b` (`severity`, `corner`) |
| `slip_angle` | `available`, `summary_a/b` (`understeer_pct`, `oversteer_pct`, `balance_mean`) |
| `driver_inputs` | `available`, `nervousness_score_a/b`, `fft_bands_a/b` (`high`, `mid`), `overlap_pct_a/b` |
| `corners` | lista con `corner_number`, `time_loss_seconds`, `braking_delta_meters`, `apex_speed_delta_kmh`, `throttle_delta_meters`, `description` |

### Modo sesión: `analizar_setup_sesion(...)`

| Parámetro | Origen | Campos leídos |
|---|---|---|
| `curvas_sesion` | `analizar_curvas_sesion()` | `available`, `corners` (también `std_loss_seconds`) |
| `degradacion` | `analizar_degradacion_stint()` | `tasa_s_per_lap`, `r_squared` |
| `telemetria_sesion` | `analizar_telemetria_sesion()` | opcionales `tyre` (por esquina `mean_temp`, `max_temp`, `camber_gradient`, `inner_mean`, `outer_mean`, `brake_temp_mean`, `brake_temp_max`; más `front_rear_delta`, `left_right_delta`), `brake` (`mean_efficiency`, `min_efficiency`, `mean_fade_severity`, `mean_fade_pct`), `suspension` (`mean_roll_f/r`, `roll_ratio`, `mean_pitch`, `mean/max_bottoming_events`, `corner_bottoming_pct`), `inputs` (`mean_nervousness`, `mean_fft_high/mid`, `mean_overlap_pct`), `balance` (`mean_understeer_pct`, `mean_oversteer_pct`, `balance_mean`) |

---

## 6. Esquema de Salida

```python
{
    "available": bool,              # modo vuelta: existen recomendaciones o areas_status; modo sesión: existen recomendaciones
    "recommendations": [{
        "category": str, "problem": str, "root_cause": str, "recommendation": str,
        "detail": str, "solves": str,
        "expected_gain": str,       # "lo-hi s/vuelta" localizado
        "gain_lo": float, "gain_hi": float,
        "priority": "alta" | "media" | "baja",
        "pilot_note": str,
        "problem_key": str, "category_key": str, "rec_key": str,   # identificadores estables
        "pos": "FL" | "FR" | "RL" | "RR",                          # solo en reglas por neumático
        # añadido por /api/setups/annotate:
        "setup_link": {"actions": [...], "related": [...]},
    }],
    "areas_status": [{"domain": str, "label": str, "status": str, "n_issues": int}],   # solo modo vuelta
    "corner_priority": [{"corner_number": int, "time_loss_seconds": float, "braking_delta_meters": float,
                         "apex_speed_delta_kmh": float, "throttle_delta_meters": float,
                         "dominant_phase": "frenada" | "apex" | "salida", "focus": str, "description": str}],
    "total_gain_lo": float, "total_gain_hi": float, "total_gain_range": str
}
```

Dominios de `areas_status`: `tyres`, `brakes`, `suspension`, `aero`, `inputs`, `corners`. El modo sesión no devuelve `areas_status`.

---

## 7. Guía de Interpretación

- Empieza por `areas_status` (modo vuelta) para el triaje y luego lee las recomendaciones `alta`: `root_cause` nombra el fenómeno y `detail` suele incluir los números que dispararon la regla, que se pueden contrastar con la telemetría.
- `expected_gain` es un rango heurístico; el total es una suma ingenua. Trátalo como una cota superior optimista, porque los cambios de setup interactúan.
- Cuando varias reglas se disparan para el mismo neumático (caída y presión), pueden compartir causa; no las apliques todas como correcciones independientes.
- `pilot_note` describe el síntoma percibido sin jerga de ingeniería; para elementos `alta` es una indicación a corto plazo, no sustituye al cambio.
- `corner_priority` muestra dónde mirar primero; `dominant_phase` es una heurística basada en sensibilidades supuestas.
- Con un setup de AC vinculado, lee `setup_link.actions`: `status: ok` da un valor concreto, `direction_only` solo la dirección, `at_limit` significa que el parámetro no puede moverse en ese sentido. Revisa `conflicts` antes de aplicar varios cambios. Las acciones alternativas (`alternative: true`) no se suman: elige una vía.

---

## 8. Limitaciones e Inconsistencias Conocidas

- **Basado en reglas con umbrales fijos.** No se adapta a circuito, compuesto, condiciones ambientales ni coche. Los rangos de ganancia no están validados con tiempos reales.
- **Las ganancias no son independientes.** Los totales son sumas simples.
- **Se necesitan dos vueltas comparables** en modo vuelta; condiciones mezcladas dan resultados engañosos.
- **La consistencia de sesión** (`std_loss_seconds`) no es fiable con menos de unas 5 vueltas.
- **`lang`** se respeta ahora cuando se pasa (corregido el 2026-10-03); las prioridades y los valores de `window_status` siguen siendo literales en español.
- **Las prioridades son cadenas fijas en español** (`alta`/`media`/`baja`) y los valores de `window_status` (`optima`, `sobrecalentada`, `fria`) son literales en español usados como contrato de datos.
- **Regla de degradación (corregida el 2026-10-03):** la regla "alta" exigía `tasa_s_per_lap > 0.20` aunque la pendiente del stint está limitada a +/-0,15, por lo que nunca se disparaba, y `tasa_s_per_lap` incluye el efecto del combustible. Ahora usa la degradación neta `degradation_s_per_lap` (con respaldo a `tasa_s_per_lap` si falta): alta `> 0,12` (80 % del límite; prioridad alta desde 0,15, alcanzable porque neta = pendiente - efecto combustible puede superar el límite) y moderada `0,08-0,12`. Se omite con `low_confidence`, menos de `MIN_LAPS_FOR_TREND` vueltas o `wear_active=False` (simulador con desgaste apagado; `main.py` pasa `detect_wear_tracking`).
- **Coherencia vuelta/sesión (corregida el 2026-10-03):** los dos modos daban consejos opuestos. Ahora comparten `_camber_diagnosis` y `_pressure_direction`. Caída: la caída negativa carga el hombro interior, así que interior más caliente que exterior = demasiada caída negativa = REDUCIRLA (la regla de sesión era correcta; el modo vuelta decía "añadir"); exterior más caliente = AÑADIR. Presión (solo con temperatura, sin canal de presión, por lo que es la decisión menos segura): se asume que un neumático sobrecalentado flexiona demasiado (docs 09/14: más presión reduce el calor de deformación), así que SUBIR presión, salvo que el centro de la banda esté más de 5 degC por encima de la media de los hombros (sobreinflado), entonces BAJAR; un neumático frío recibe BAJAR. El modo sesión no tiene desglose por zonas, así que sigue el valor por defecto. Fijado por `tests/test_advisor_rl_fixes.py`.
- **Dependencia de módulos previos:** la calidad de cada regla es la de la métrica que la alimenta (por ejemplo el resumen de balance del ángulo de deriva).

---

## 9. Estado de Verificación

Umbrales, rangos de ganancia, claves y el mapeo de AC se leyeron de `setup_advisor.py`, `ac_setups.py` y `src/api/setups.py` el 2026-10-03; las correcciones anteriores (regla de degradación, coherencia caída/presión y `lang`) se reprodujeron antes con pruebas sintéticas que fallaban. Los textos de recomendación (p. ej. consejos de alerón/ARB) viven en los archivos de idioma y no se auditaron en cuanto a corrección de ingeniería. No verificable desde el código: el significado físico del signo de `balance_mean`, por qué se eligió cada valor umbral y el sentido del consejo de presión (ninguna presión entra en estas reglas). Versiones anteriores de este documento describían un "balance mean = correlación entre G lateral y ángulo de volante" y varios valores de umbral que no son lo que hace el código; esas afirmaciones se eliminaron.
