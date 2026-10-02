# Motorsport Analytics Pipeline

> Análisis de telemetría de vueltas y sesiones de Assetto Corsa e iRacing a partir de exportaciones CSV tipo MoTeC: comparación de vueltas, diagnóstico curva a curva, análisis de stint y neumáticos, y recomendaciones de setup.

[Read in English](README.md)

## Inicio rápido

```bash
# 1. Backend (desde la raíz del proyecto)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# 2. Frontend (segunda terminal)
cd frontend && npm install && npm run dev

# 3. Abre http://localhost:5173 y suelta un CSV (ver "Uso de la aplicación")
```

## Tabla de contenidos

- [Qué es](#qué-es)
- [Instalación](#instalación)
- [Uso de la aplicación](#uso-de-la-aplicación)
- [Formatos de telemetría](#formatos-de-telemetría)
- [Notas de calidad de datos y comportamiento](#notas-de-calidad-de-datos-y-comportamiento)
- [Ejemplo de resultado](#ejemplo-de-resultado)
- [Arquitectura](#arquitectura)
- [API](#api)
- [Configuración](#configuración)
- [Desarrollo y tests](#desarrollo-y-tests)
- [Documentación](#documentación)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

## Qué es

Un backend FastAPI y un frontend React. Subes archivos CSV de telemetría y obtienes:

- **Modo sesión (1 CSV):** la sesión completa se segmenta automáticamente en vueltas. Obtienes una tabla de vueltas (con las vueltas de pit y atípicas marcadas), análisis de stint (degradación de ritmo, estrategia de combustible, proyección Monte Carlo, ventana de pit, evolución de pista), análisis de curvas de la sesión, degradación de neumáticos, gestión térmica, optimización de trazada y recomendaciones de setup.
- **Modo comparación (2 CSV de una vuelta cada uno, o 2 vueltas elegidas de una sesión):** time delta alineado por distancia, superposición de velocidad/freno/acelerador, diagnóstico curva a curva, diagrama G-G, eventos de subviraje/sobreviraje, análisis de neumáticos/frenos/suspensión/inputs/slip angle, módulos de ML (detección de anomalías, clustering de estilo, potencial de vuelta) e informe PDF.

La interfaz tiene dos vistas: **Ingeniero** (todo) y **Piloto** (paneles técnicos ocultos). Idiomas: español e inglés (los mensajes y reportes de la API siguen el parámetro `lang` o `Accept-Language`).

## Instalación

### Requisitos

| Herramienta | Versión |
|---|---|
| Python | 3.10+ (la imagen Docker usa 3.11) |
| Node.js | 18+ (la imagen Docker usa 20) |
| Git | cualquiera |

### Local

```bash
git clone https://github.com/ElSirGuti/motorsport-analytics-pipeline.git
cd motorsport-analytics-pipeline

python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt    # añade -r requirements-dev.txt para los tests

cd frontend && npm install && cd ..
```

Ejecuta los dos procesos en terminales separadas:

```bash
uvicorn main:app --reload --port 8000     # API en http://localhost:8000 (docs en /docs)
cd frontend && npm run dev                # UI en http://localhost:5173
```

También puedes ejecutar `python main.py`, que lee `API_HOST`, `API_PORT` y `API_RELOAD` del entorno.

### Docker

```bash
docker compose up --build
```

`docker-compose.yml` levanta el `backend` (puerto 8000, health check en `/api/health`) y el `frontend` (nginx sirviendo el build de producción en el puerto 5173). La imagen del frontend incorpora la URL de la API en tiempo de build (`VITE_API_URL`, por defecto `http://localhost:8000/api`), por lo que el navegador debe poder alcanzar la API en esa dirección.

## Uso de la aplicación

1. Abre `http://localhost:5173` y elige el idioma (ES/EN) y el modo (Piloto/Ingeniero) en la barra superior.
2. Suelta archivos CSV en el área de carga. El modo se detecta por la cantidad de archivos:
   - **1 CSV = sesión completa**, segmentada automáticamente en vueltas.
   - **2 CSV = dos vueltas sueltas** para comparar.
3. Pulsa analizar. Una barra de progreso por pasos muestra las etapas (los archivos grandes pueden tardar varios minutos; una sesión de ~57 MB tardó unos 25 s). Al terminar, el área de carga se compacta en una barra de archivo con el botón **Nuevo análisis**.
4. Navega con el riel lateral:
   - Sesión: *Resumen de sesión*, *Análisis de stint*, *Setup y estrategia*.
   - Comparación: *Vuelta base*, *Dinámica del vehículo*, *Piloto y entradas*, *Estrategia y setup*.
   - El modo Piloto oculta los paneles técnicos (dinámica del vehículo y piloto y entradas).
5. En la tabla de vueltas de la sesión, marca **dos vueltas (A/B)** y pulsa **Comparar**, o usa **Mejor vs Peor**. Las vueltas de pit y atípicas aparecen marcadas.
6. Un panel de salud indica qué módulos de análisis produjeron datos y cuáles no están disponibles para ese archivo.
7. El resultado de una comparación se puede copiar como reporte de texto o descargar como PDF.

Guía completa: [Guía de Usuario](docs/GUIA_USUARIO.es.md).

## Formatos de telemetría

El cargador (`src/io/loaders.py`) lee únicamente **CSV**. Fuentes soportadas:

| Fuente | Notas |
|---|---|
| Assetto Corsa vía ACTI, exportado como CSV de MoTeC | El separador (coma o punto y coma) se detecta automáticamente; el bloque de cabecera de MoTeC (Driver, Vehicle, Venue) se lee como metadatos y la fila de unidades se omite. |
| iRacing exportado a CSV (`.ibt` convertido con MoTeC i2 o una herramienta de terceros) | Se detecta por `SessionTime`, `Session Time` o `SessionLapCount`. La velocidad en m/s se convierte a km/h, los pedales de 0-1 se escalan a 0-100, la suspensión de metros a mm, la presión de neumáticos de kPa/PSI a bar y el brake bias de fracción a porcentaje. |

Los pasos de exportación de cada programa (ACTI, MoTeC i2, iRacing) están en la [Guía de Usuario](docs/GUIA_USUARIO.es.md#exportar-la-telemetría).

**Canales obligatorios:** `Speed`, `Brake`, `Throttle`. Si falta alguno o no tiene valores numéricos, la API responde `400` con un mensaje que lista las columnas encontradas.

**Distancia:** si el canal `Distance` no existe (o nunca supera los 10 m), se sintetiza integrando `Speed` sobre un reloj válido (`LR/HR/MR Sample Clock`, `SessionTime`, `Time`, `Lap Time`; un reloj que sea una onda cuadrada 0/1 se descarta; si no hay ninguno se usa `Session Time Left`, luego el cronómetro de vuelta y, en último caso, 100 Hz fijos). Las respuestas con metadatos (`/api/compare-session-laps`, `/api/report/pdf`) marcan `metadata.distance_synthetic = true`. La distancia sintética es adecuada para el análisis de stint y de sesión; la comparación vuelta contra vuelta es más fiable con un canal de distancia real.

**Canales reconocidos (nombre canónico: ejemplos de alias aceptados):**

| Grupo | Nombres canónicos | Ejemplos de alias |
|---|---|---|
| Base | `Speed`, `Brake`, `Throttle`, `Distance`, `Gear`, `RPM` | `Ground Speed`, `Brake Pos`, `Throttle Pos`, `Lap Distance` |
| Dinámica | `SteerAngle`, `LateralG`, `LongitudinalG`, `YawRate` | `Steering Angle`, `CG Accel Lateral`, `CG Accel Longitudinal`, `Chassis Yaw Rate` |
| Vueltas y tiempo | `LapTime`, `SessionLapCount` | `Lap Time`, `Session Lap Count`, `Lap` |
| Posición | `CarCoordX/Y/Z` | `Car Coord X` |
| Clima | `AirTemp`, `RoadTemp` | `Air Temp`, `Road Temp` |
| Temperatura de neumáticos (4 zonas x 4 esquinas) | `TyreTemp{Core,Inner,Middle,Outer}{FL,FR,RL,RR}` | `Tire Temp Core FL`, `LFtempCL` |
| Presión de neumáticos | `TyrePress{FL..RR}`, `TyrePressCold{FL..RR}` | `Tire Pressure FL`, `LFpressure`, `LFcoldPressure` |
| Recorrido de suspensión | `SuspTravel{FL..RR}` | `Suspension Travel FL`, `LFshockDefl` |
| Frenos | `BrakeTemp{FL..RR}`, `BrakeBias` | `Brake Temp FL`, `dcBrakeBias` |
| Fluidos | `WaterTemp`, `OilTemp` | `Coolant Temp`, `Eng Oil Temp` |

La tabla completa de alias es `COLUMN_ALIASES` en `src/io/loaders.py`. La ausencia de canales opcionales no aborta el análisis: el panel afectado se declara no disponible.

## Notas de calidad de datos y comportamiento

- **La segmentación de vueltas** es única para todos los endpoints: por canal contador de vueltas (`Session Lap Count`, `Lap`, ...) o, si no existe, por reinicios de distancia. Los segmentos parciales de menos de 30 s se descartan. Si se encuentran menos de 2 vueltas, la API responde con un mensaje de error.
- **Vueltas de pit y atípicas:** una vuelta se marca como pit si el canal `In Pit` lo indica; las vueltas fuera del 70-115 % de la mediana también se marcan como atípicas y se excluyen de regresiones y proyecciones.
- **Las ventanas de curva no se solapan:** cada ventana se recorta en el punto medio entre ápices vecinos. El `summary` de la comparación incluye `corners_time_delta_s` (tiempo ganado/perdido dentro de curvas) y `outside_corners_delta_s` (el resto).
- **El emparejado de curvas** entre dos vueltas usa la distancia del ápice, no el índice de curva.
- **Valores no medibles:** `braking_delta_available` y `throttle_delta_available` indican si los deltas de frenada/acelerador pudieron medirse. Un `0.0` con `available = false` significa "no medible", no "sin diferencia".
- **Canales constantes** (por ejemplo, temperaturas de freno fijas en un solo valor) devuelven `available: false` con un `reason` en lugar de generar recomendaciones falsas.
- **Convención de signo del slip angle:** la convención de signo de `LateralG` se detecta por su correlación con la velocidad de guiñada y se invierte si hace falta (Assetto Corsa la registra invertida) antes de calcular el ángulo de deslizamiento.
- **Validación de entrada:** un CSV vacío o sin los canales mínimos devuelve `400` con un mensaje claro. Las selecciones de vuelta inválidas devuelven `422`.
- **La evolución de pista** (`track_evolution`) y el **`health_summary`** forman parte de las respuestas de stint y de compare-session.

## Ejemplo de resultado

Validado con un Porsche Cayman GT4 Clubsport en Imola (Assetto Corsa, CSV MoTeC de ~57 MB sin canal `Distance`):

| Dato | Valor |
|---|---|
| Vueltas detectadas | 21 (las vueltas 1 y 21 son de pit) |
| Mejor vuelta | Vuelta 11, 1:57.605 |
| Rango de vueltas de carrera | 117.6 - 122.4 s |
| Longitud de pista | ~4862 m |
| Velocidad máxima | 243.9 km/h |
| Curvas por geometría | 11 |
| Consumo de combustible | 1.758 L/vuelta |
| Tendencia de degradación | -0.077 s/vuelta (el coche mejora al consumir combustible) |
| Tiempo de análisis completo | ~25 s |

El CSV no forma parte del repositorio.

## Arquitectura

```
main.py                  App FastAPI: endpoints, CORS, logging, mapeo de errores
src/
  io/                    loaders.py (ingesta CSV, alias, normalización de unidades, síntesis de distancia)
                         exporters.py (reporte de texto), pdf_exporter.py (reporte PDF)
  processing/            alignment.py (alineación por distancia), filters.py (filtros de señal)
  telemetry/             lap_comparator.py, metrics.py, session_analyzer.py
  analytics/             Módulos avanzados (ver tabla)
  i18n.py, locales/      Traducciones del backend (en.json, es.json)
  visualization/         (paquete vacío)
frontend/                React 19 + Vite + Recharts (ver frontend/README.md)
tests/                   suite pytest (48 tests)
scripts/                 Generador de datos de ejemplo y de imágenes de la documentación
data/                    laptime_history.db (historial usado por el módulo ML de tiempo de vuelta)
docs/                    Guías de usuario y documentación científica (ES/EN)
```

Módulos de `src/analytics/`:

| Módulo | Propósito | Doc |
|---|---|---|
| `geometry.py` | Curvatura y detección de ápices | [01](docs/01_geometry.es.md) |
| `alignment.py` | Alineación por distancia y time delta | [02](docs/02_time_delta.es.md) |
| `dynamics.py` | Diagrama G-G, eventos de subviraje/sobreviraje | [03](docs/03_gg_diagram.es.md), [04](docs/04_dynamics.es.md) |
| `compression.py` | Compresión RDP del payload | [02](docs/02_time_delta.es.md) |
| `insights.py` | Diagnóstico curva a curva | [01](docs/01_geometry.es.md) |
| `ml_anomaly.py` | Zonas anómalas con Isolation Forest | [05](docs/05_anomaly_detection.es.md) |
| `ml_clustering.py` | Perfiles de estilo por curva con K-Means | [06](docs/06_clustering.es.md) |
| `ml_laptime.py` | Vuelta alcanzable (P10), consistencia, XGBoost, historial en SQLite | [07](docs/07_lap_time_potential.es.md) |
| `stint.py` | Segmentación de vueltas, métricas por vuelta, degradación, combustible, Monte Carlo, evolución de pista | [08](docs/08_stint_analysis.es.md) |
| `thermodynamics.py` | Ventana térmica de neumáticos (comparación) | [09](docs/09_thermodynamics.es.md) |
| `brake_fade.py` | Eficiencia de frenado y fade | [10](docs/10_brake_fade.es.md) |
| `driver_inputs.py` | FFT del volante, nerviosismo, solape de pedales | [11](docs/11_driver_inputs.es.md) |
| `suspension.py` | Pitch, roll, bottoming | [12](docs/12_suspension.es.md) |
| `slip_angle.py` | Deslizamiento lateral y balance | [13](docs/13_slip_angle.es.md) |
| `thermal_management.py` | Temperaturas y presiones de neumáticos, frenos y fluidos en la sesión | [14](docs/14_thermal_management.es.md) |
| `tyre_degradation.py` | Predicción de degradación de neumáticos | [15](docs/15_tyre_degradation.es.md) |
| `racing_line_rl.py` | Optimización de trazada | [16](docs/16_racing_line_rl.es.md) |
| `setup_advisor.py` | Recomendaciones de setup (comparación de vueltas y sesión) | [17](docs/17_setup_advisor.es.md) |
| `session_corner_analysis.py` | Estadísticas por curva a lo largo de todas las vueltas de la sesión | [08](docs/08_stint_analysis.es.md) |
| `session_telemetry_analysis.py` | Agregados de sesión de neumáticos, frenos, suspensión, inputs y balance | [08](docs/08_stint_analysis.es.md) |

## API

URL base: `http://localhost:8000`. Documentación interactiva: `/docs` (Swagger). Todos los POST usan `multipart/form-data` salvo indicación contraria. Añade `?lang=es` o `?lang=en` (si no, se usa `Accept-Language`) para elegir el idioma de mensajes y reportes. Errores: `400` para CSV ilegible o inválido, `422` para selecciones inválidas (vuelta fuera de rango, misma vuelta dos veces, menos de 3 vueltas en stint), `500` para errores internos; el cuerpo es `{"detail": "..."}`.

| Endpoint | Método | Campos del formulario | Devuelve |
|---|---|---|---|
| `/api/health` | GET | ninguno | `{status, service, version}` |
| `/api/analyze-session` | POST | `session_file` (CSV) | JSON con `laps` (tiempo, marcas de pit/atípica), `fastest_lap`, `track_map`, `total_laps`. Si no se pueden segmentar vueltas, `laps` vacío y un `message`. |
| `/api/stint/analyze` | POST | `laps`: un CSV de sesión, o 3 o más CSV de una vuelta | JSON: `laps`, `degradacion`, `combustible`, `montecarlo`, `curvas_sesion`, `telemetria_sesion`, `setup_sesion`, `thermal_analysis`, `degradacion_neumatico`, `racing_line_rl`, `track_evolution`, `health_summary` |
| `/api/compare-laps` | POST | `lap_a`, `lap_b` (CSV) | Comparación básica: `summary`, comparaciones de velocidad/freno/acelerador, `time_delta_series`, `corners`, `track_map`, `metadata`, `text_report`, `setup_advisor` y los resultados de los módulos avanzados cuando están disponibles |
| `/api/telemetry/analyze` | POST | `lap_fast`, `lap_slow` (CSV); query `resolution_m` (por defecto 5) | Pipeline avanzado: `telemetria`, `curvatura`, `apexes`, `sectores`, `corners`, `gg_diagram`, `g_limit`, `dynamic_events`, `anomaly`, `corner_clusters`, `tiempo_potencial`, `xgboost_pred`, resultados de neumáticos/frenos/inputs/suspensión/slip |
| `/api/telemetry/compare` | POST | `lap_fast`, `lap_slow` (CSV); query `resolution_m` | Subconjunto de geometría y time delta: `metadata`, `telemetria`, `curvatura`, `apexes`, `sectores`, `corners` |
| `/api/compare-session-laps` | POST | `session_file` (CSV), `lap_a`, `lap_b` (enteros desde 1; `0` = automático: la vuelta flying más rápida y la más lenta) | Comparación completa de dos vueltas de una sesión: todo lo de `compare-laps` más `telemetria`, `curvatura`, `apexes`, `sectores`, `gg_diagram`, `anomaly`, neumáticos/frenos/inputs/suspensión/slip/`thermal_analysis`, `setup_advisor`, `text_report`, `health_summary`; `metadata` incluye `distance_synthetic` |
| `/api/report/pdf` | POST | `session_file` (CSV), `lap_a`, `lap_b` (mismas reglas) | Adjunto `application/pdf` `report_V{a}_vs_V{b}.pdf` |
| `/api/report/pdf-from-json` | POST | Cuerpo JSON: un resultado de comparación ya calculado (como lo devuelven los endpoints de comparación) | Adjunto `application/pdf`, sin recalcular |

Notas:

- La UI llama a `/api/analyze-session` y luego a `/api/stint/analyze` para una sesión, a `/api/compare-laps` más `/api/telemetry/analyze` para dos archivos, a `/api/compare-session-laps` para pares de vueltas y a `/api/report/pdf-from-json` para el botón de PDF.
- `/api/telemetry/analyze` añade una observación a `data/laptime_history.db`, que alimenta con el tiempo las capas de P10 histórico y XGBoost.
- Un módulo que no puede ejecutarse devuelve `{"available": false, ...}` (a menudo con `reason`) en lugar de hacer fallar toda la petición.

## Configuración

Copia `.env.example` a `.env` (se carga con `python-dotenv`).

| Variable | Por defecto | Efecto |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000` | Orígenes permitidos, separados por coma |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TEMP_DIR` | `<proyecto>/tmp` | Directorio de archivos temporales de subida (se crea si no existe; los archivos se borran al terminar cada petición) |
| `API_HOST` / `API_PORT` / `API_RELOAD` | `0.0.0.0` / `8000` / `false` | Solo al ejecutar `python main.py` |
| `VITE_API_URL` | `http://localhost:8000/api` | URL de la API usada por el frontend (la lee Vite en dev/build) |
| `MAX_UPLOAD_MB` | n/d | Aparece en `.env.example` y `docker-compose.yml` pero **el código no la lee**: el backend no impone un límite de tamaño de subida |

## Desarrollo y tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q          # 48 tests

cd frontend
npm run lint                       # ESLint
npm run build                      # build de producción en frontend/dist
```

Archivos de test: `tests/test_alignment.py`, `test_loaders.py`, `test_metrics.py`, `test_session_pipeline.py` (fixtures en `tests/conftest.py`). Se pueden generar vueltas sintéticas con `python scripts/generate_sample_data.py` (escribe `data/raw/lap_clean.csv` y `data/raw/lap_errors.csv`, ignorados por git).

## Documentación

| Audiencia | Documento |
|---|---|
| Usuarios | [Guía de Usuario](docs/GUIA_USUARIO.es.md), [Referencia Rápida](docs/REFERENCIA_RAPIDA.es.md) |
| Desarrolladores | [Índice de docs](docs/README.es.md) con los 17 documentos científicos de módulo (matemática, algoritmos, figuras), [frontend/README.md](frontend/README.md) |
| Inglés | [README.md](README.md), [User Guide](docs/USER_GUIDE.md), [Quick Reference](docs/QUICK_REFERENCE.md), [docs/README.md](docs/README.md) |

## Limitaciones conocidas

- La detección de curvas por velocidad encuentra menos curvas que la detección por geometría (7 frente a 11 en Imola, porque las chicanes se fusionan).
- El bottoming de suspensión es heurístico: recorrido igual o superior al 90 % del recorrido máximo observado.
- Algunos canales pueden faltar según el simulador y la exportación; los paneles correspondientes lo indican en lugar de adivinar.
- Solo CSV; los archivos `.ibt` y `.ld` deben convertirse antes.
- No se impone límite de tamaño de subida (ver `MAX_UPLOAD_MB`); los archivos muy grandes requieren memoria y tiempo.

## Contribuir

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) (en inglés). En resumen: haz un fork, crea una rama, ejecuta `python -m pytest tests -q` y abre un Pull Request contra `main`. No subas CSV de telemetría ni secretos.

## Licencia

[MIT](LICENSE) - Copyright (c) 2026 Andres Gutierrez.
